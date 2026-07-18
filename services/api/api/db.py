"""Owns SQLite: connections, pragmas, and (as tables land) schema.

`ctx.db` is the surface commands run their data ops on. One writer per file
by design: this service owns config.db; queue.db is multi-writer with the
worker (measured fine — see docs/reports/2026-07-18-sqlite-wal-throughput.md
at the repo root).
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Db:
    queue: sqlite3.Connection
    config: sqlite3.Connection


def db_create(data_dir: Path) -> Db:
    data_dir.mkdir(parents=True, exist_ok=True)
    return Db(
        queue=_open(data_dir / "queue.db"),
        config=_open(data_dir / "config.db"),
    )


def _open(path: Path) -> sqlite3.Connection:
    # check_same_thread=False: FastAPI runs sync handlers on a threadpool;
    # SQLite is compiled serialized, so cross-thread use of one connection
    # is safe. autocommit=True matches the benchmarked per-request enqueue;
    # multi-statement transactions issue explicit BEGIN IMMEDIATE.
    conn = sqlite3.connect(path, check_same_thread=False, autocommit=True)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
