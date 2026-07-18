import sqlite3

from conftest import TestCtx
from fastapi.testclient import TestClient

from api.app import create_app

EVENT = {
    "site_id": "demo",
    "page_url": "/",
    "lcp_ms": 100.0,
    "timestamp": 1784415300000,
    "session_id": "s-1",
}

# The worker-owned agg.db contract as pinned in the worker spec
# (docs/superpowers/specs/2026-07-18-worker-design.md): last_seen is epoch
# SECONDS; the api converts to ms. Only the columns the api reads appear here.
WORKER_PAGE_CURRENT = """\
CREATE TABLE page_current (
    site_id TEXT, page_url TEXT,
    count INTEGER, p75_ms INTEGER, last_seen INTEGER,
    PRIMARY KEY (site_id, page_url))
"""


def test_stats_empty(tctx: TestCtx) -> None:
    client = TestClient(create_app(tctx))
    assert client.get("/stats").json() == {
        "queue_depth": 0,
        "last_aggregate_ms": None,
    }


def test_stats_counts_queue_depth(tctx: TestCtx) -> None:
    client = TestClient(create_app(tctx))
    client.post("/events", json=EVENT)
    client.post("/events", json=EVENT)
    assert client.get("/stats").json()["queue_depth"] == 2


def test_stats_reads_worker_aggregates_in_ms(tctx: TestCtx) -> None:
    agg = sqlite3.connect(tctx.cfg.data_dir / "agg.db")
    agg.execute(WORKER_PAGE_CURRENT)
    agg.execute("INSERT INTO page_current VALUES ('demo', '/', 5, 1200, 1784415300)")
    agg.commit()
    agg.close()
    client = TestClient(create_app(tctx))
    assert client.get("/stats").json()["last_aggregate_ms"] == 1784415300000


def test_stats_survives_agg_db_without_schema(tctx: TestCtx) -> None:
    # Real mid-rollout state: the worker created the file but not yet the
    # tables. /stats must degrade to null, not 500.
    sqlite3.connect(tctx.cfg.data_dir / "agg.db").close()
    client = TestClient(create_app(tctx))
    assert client.get("/stats").json()["last_aggregate_ms"] is None
