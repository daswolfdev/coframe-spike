"""Owns SQLite: connections, pragmas, schema.

`ctx.db` is the surface commands run their data ops on. queue.db is
multi-writer with the worker by design (measured fine — see
docs/reports/2026-07-18-sqlite-wal-throughput.md at the repo root).

The queue table is the api↔worker contract (issue #11): typed columns —
the schema IS the contract, the Go worker scans rows straight into a
struct — and delete-on-claim, at-most-once semantics:

    BEGIN IMMEDIATE;
    SELECT * FROM queue ORDER BY id LIMIT :batch;
    DELETE FROM queue WHERE id <= :max_claimed_id;
    COMMIT;                          -- then aggregate

A worker crash between COMMIT and aggregation drops at most one batch of
monitoring samples — acceptable for a p75 dashboard. Revisit trigger:
events that carry per-row value (e.g. billing).
"""

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

QUEUE_SCHEMA = """\
CREATE TABLE IF NOT EXISTS queue (
    id INTEGER PRIMARY KEY,          -- insertion order = claim order
    site_id TEXT NOT NULL,
    page_url TEXT NOT NULL,
    lcp_ms REAL NOT NULL,
    ts_ms INTEGER NOT NULL,          -- client event time, epoch ms
    session_id TEXT NOT NULL,
    received_at_ms INTEGER NOT NULL  -- api clock at enqueue, epoch ms
)
"""


@dataclass(frozen=True)
class Db:
    queue: sqlite3.Connection
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
    queue = _open(data_dir / "queue.db")
    queue.execute(QUEUE_SCHEMA)
    return Db(queue=queue)


def _open(path: Path) -> sqlite3.Connection:
    # check_same_thread=False: handlers here are async (event-loop thread),
    # but any future sync handler runs on FastAPI's threadpool, and tests
    # assert on this connection from a different thread than TestClient's
    # worker. SQLite is compiled serialized, so single autocommit statements
    # are safe on a shared connection. Multi-statement writes must go through
    # Db.transaction() — see its docstring for why.
    conn = sqlite3.connect(path, check_same_thread=False, autocommit=True)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
