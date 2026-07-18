"""perfmon api — event ingest and SDK config.

POST /events enqueues onto the platform queue (SQLite table in /data/queue.db —
schema and connection pragmas are the queue contract, see docs/design.md).
GET /config/{site_id} serves SDK config from a committed seed file: config has
no runtime write path, so its system of record is the file in git and this
process holds only a derived in-memory copy.
"""
import json
import os
import sqlite3
import threading
import time

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

QUEUE_DB = os.environ.get("QUEUE_DB", "/data/queue.db")
SEED_PATH = os.path.join(os.path.dirname(__file__), "config.seed.json")

DDL = """
CREATE TABLE IF NOT EXISTS events (
  id          INTEGER PRIMARY KEY,
  site_id     TEXT    NOT NULL,
  page_url    TEXT    NOT NULL,
  lcp_ms      REAL    NOT NULL,
  timestamp   INTEGER NOT NULL,
  session_id  TEXT    NOT NULL,
  received_at INTEGER NOT NULL
)
"""

_local = threading.local()


def db() -> sqlite3.Connection:
    """One connection per handler thread, queue-contract pragmas applied.

    journal_mode=WAL persists in the file (set once at init); synchronous and
    busy_timeout are per-connection and must be applied by every opener.
    """
    if not hasattr(_local, "conn"):
        conn = sqlite3.connect(QUEUE_DB, timeout=5.0, isolation_level=None)
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        _local.conn = conn
    return _local.conn


def init_queue() -> None:
    """The api owns the queue DDL; consumers only read/delete."""
    conn = sqlite3.connect(QUEUE_DB, timeout=5.0, isolation_level=None)
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(DDL)
    conn.close()


class Event(BaseModel):
    site_id: str
    page_url: str
    lcp_ms: float
    timestamp: int  # event time, unix ms (SDK clock)
    session_id: str


CONFIG: dict = json.load(open(SEED_PATH))
STARTED = time.time()

# Per-process counter (uvicorn --workers forks; /stats reports this process).
_received = 0
_received_lock = threading.Lock()

app = FastAPI()
init_queue()


@app.post("/events", status_code=202)
def post_event(e: Event) -> dict:
    global _received
    try:
        db().execute(
            "INSERT INTO events (site_id, page_url, lcp_ms, timestamp, session_id, received_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (e.site_id, e.page_url, e.lcp_ms, e.timestamp, e.session_id, int(time.time() * 1000)),
        )
    except sqlite3.OperationalError as exc:
        # busy_timeout exhausted — backpressure to the SDK, not silent loss
        raise HTTPException(status_code=503, detail="queue busy") from exc
    with _received_lock:
        _received += 1
    return {"queued": True}


@app.get("/config/{site_id}")
def get_config(site_id: str) -> dict:
    site = CONFIG.get(site_id)
    if site is None:
        raise HTTPException(status_code=404, detail="unknown site")
    return site


@app.get("/healthz")
def healthz() -> dict:
    try:
        db().execute("PRAGMA user_version")
    except sqlite3.OperationalError as exc:
        raise HTTPException(status_code=503, detail="queue.db unavailable") from exc
    return {"ok": True}


@app.get("/stats")
def stats() -> dict:
    depth = db().execute("SELECT COUNT(*) FROM events").fetchone()[0]
    return {
        "service": "api",
        "events_received_total": _received,
        "queue_depth": depth,
        "uptime_s": int(time.time() - STARTED),
    }
