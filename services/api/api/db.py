"""Owns SQLite: connections, pragmas, schema.

`ctx.db` is the surface commands run their data ops on. queue.db is
multi-writer with the worker by design (measured fine — see
docs/reports/2026-07-18-sqlite-wal-throughput.md at the repo root).

The queue table is the api↔worker contract (issue #11): typed columns —
the schema IS the contract, the Go worker scans rows straight into a
struct. `claim_id` is consumer-owned effectively-once state (negotiated
on #11): NULL = unclaimed; the api NEVER reads or writes it. Worker
protocol, for reference:

    BEGIN IMMEDIATE;                              -- claim
    UPDATE queue SET claim_id = :batch
      WHERE id IN (SELECT id FROM queue WHERE claim_id IS NULL
                   ORDER BY id LIMIT :n)
      RETURNING *;
    COMMIT;
    -- fold into agg.db + batch marker (one agg transaction), then ack:
    DELETE FROM queue WHERE claim_id = :batch;

A worker crash at any point recovers exactly once via the agg-side
marker (no reclaim timers, no dedup index — recovery is two lookups at
worker startup). The mark must live here, not consumer-side: plain
INTEGER PRIMARY KEY reuses rowids after the table drains empty, so a
re-runnable "DELETE id <= max" recovery could delete fresh rows.
Revisit trigger: a second consumer (claim_id would need a namespace).
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
    received_at_ms INTEGER NOT NULL, -- api clock at enqueue, epoch ms
    claim_id INTEGER                 -- consumer-owned; NULL = unclaimed (#11)
)
"""

QUEUE_UNCLAIMED_INDEX = """\
CREATE INDEX IF NOT EXISTS queue_unclaimed ON queue (id) WHERE claim_id IS NULL
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
    queue.execute(QUEUE_UNCLAIMED_INDEX)
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
