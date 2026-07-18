"""Owns SQLite: connections, pragmas, and (as tables land) schema.

`ctx.db` is the surface commands run their data ops on. One writer per file
by design: this service owns config.db; queue.db is multi-writer with the
worker (measured fine — see docs/reports/2026-07-18-sqlite-wal-throughput.md
at the repo root).
"""

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Db:
    queue: sqlite3.Connection
    config: sqlite3.Connection
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @contextmanager
    def transaction(self, conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
        """Run a multi-statement write atomically — the only legal way to BEGIN.

        Connections are shared across FastAPI's threadpool; a bare BEGIN from
        two threads would interleave into one transaction. The lock is what
        makes BEGIN IMMEDIATE safe here — never issue BEGIN outside this
        method. Serializing writers costs nothing at our load (~10µs/insert,
        ~126x headroom — see the WAL report).
        """
        with self._lock:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            else:
                conn.execute("COMMIT")


def db_create(data_dir: Path) -> Db:
    data_dir.mkdir(parents=True, exist_ok=True)
    return Db(
        queue=_open(data_dir / "queue.db"),
        config=_open(data_dir / "config.db"),
    )


def _open(path: Path) -> sqlite3.Connection:
    # check_same_thread=False: FastAPI runs sync handlers on a threadpool;
    # SQLite is compiled serialized, so single autocommit statements are safe
    # on a shared connection. Multi-statement writes must go through
    # Db.transaction() — see its docstring for why.
    conn = sqlite3.connect(path, check_same_thread=False, autocommit=True)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
