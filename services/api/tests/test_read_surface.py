"""The dashboard read contract (#15).

/sites, /sites/{id}/pages, and /sites/{id}/trend, served from the
worker-owned agg.db and degrading to empty — never 500 — through every
real mid-rollout state.
"""

import sqlite3

from conftest import TestCtx
from fastapi.testclient import TestClient

from api.app import create_app

# The worker's agg.db DDL as landed (services/worker/internal/aggregate/
# store.go) — only the columns the api reads, plus site_minute's hist so
# NOT NULL shapes match.
WORKER_SCHEMA = """
CREATE TABLE page_current (
    site_id TEXT, page_url TEXT,
    count INTEGER, p75_ms INTEGER, last_seen INTEGER,
    PRIMARY KEY (site_id, page_url));
CREATE TABLE site_minute (
    site_id TEXT, minute INTEGER,
    count INTEGER, hist BLOB, p75_ms INTEGER, last_seen INTEGER,
    PRIMARY KEY (site_id, minute));
"""


def agg_with_schema(tctx: TestCtx) -> sqlite3.Connection:
    conn = sqlite3.connect(tctx.cfg.data_dir / "agg.db")
    conn.executescript(WORKER_SCHEMA)
    return conn


def test_read_surface_before_agg_db_exists(tctx: TestCtx) -> None:
    client = TestClient(create_app(tctx))
    assert client.get("/sites").json() == ["acme", "demo"]  # cfg sites, sorted
    assert client.get("/sites/demo/pages").json() == []
    assert client.get("/sites/demo/trend").json() == []


def test_read_surface_survives_schemaless_agg_db(tctx: TestCtx) -> None:
    # Real mid-rollout state: worker created the file but not yet the tables.
    sqlite3.connect(tctx.cfg.data_dir / "agg.db").close()
    client = TestClient(create_app(tctx))
    assert client.get("/sites").json() == ["acme", "demo"]
    assert client.get("/sites/demo/pages").json() == []
    assert client.get("/sites/demo/trend").json() == []


def test_trend_survives_agg_db_without_site_minute(tctx: TestCtx) -> None:
    # An agg.db written by a pre-site_minute worker: pages still serve.
    agg = agg_with_schema(tctx)
    agg.executescript("DROP TABLE site_minute")
    agg.execute("INSERT INTO page_current VALUES ('demo', '/', 5, 1200, 100)")
    agg.commit()
    agg.close()
    client = TestClient(create_app(tctx))
    assert client.get("/sites/demo/trend").json() == []
    assert len(client.get("/sites/demo/pages").json()) == 1


def test_sites_unions_config_and_aggregated(tctx: TestCtx) -> None:
    agg = agg_with_schema(tctx)
    agg.execute("INSERT INTO page_current VALUES ('zeta', '/', 1, 100, 100)")
    agg.commit()
    agg.close()
    client = TestClient(create_app(tctx))
    assert client.get("/sites").json() == ["acme", "demo", "zeta"]


def test_pages_ordered_by_count_with_ms_conversion(tctx: TestCtx) -> None:
    agg = agg_with_schema(tctx)
    agg.execute("INSERT INTO page_current VALUES ('demo', '/', 5, 1200, 1784415300)")
    agg.execute(
        "INSERT INTO page_current VALUES ('demo', '/checkout', 9, 2400, 1784415301)"
    )
    agg.execute("INSERT INTO page_current VALUES ('acme', '/x', 99, 100, 1)")
    agg.commit()
    agg.close()
    client = TestClient(create_app(tctx))
    assert client.get("/sites/demo/pages").json() == [
        {
            "page_url": "/checkout",
            "count": 9,
            "p75_ms": 2400,
            "last_seen_ms": 1784415301000,
        },
        {"page_url": "/", "count": 5, "p75_ms": 1200, "last_seen_ms": 1784415300000},
    ]


def test_pages_capped_at_top_20(tctx: TestCtx) -> None:
    agg = agg_with_schema(tctx)
    for i in range(25):
        agg.execute(
            "INSERT INTO page_current VALUES ('demo', ?, ?, 100, 100)",
            (f"/p{i}", i + 1),
        )
    agg.commit()
    agg.close()
    client = TestClient(create_app(tctx))
    pages = client.get("/sites/demo/pages").json()
    assert len(pages) == 20
    assert pages[0]["count"] == 25  # highest volume first; the tail dropped


def test_trend_minutes_to_ms_oldest_first(tctx: TestCtx) -> None:
    agg = agg_with_schema(tctx)
    agg.execute("INSERT INTO site_minute VALUES ('demo', 2, 4, x'', 1700, 120)")
    agg.execute("INSERT INTO site_minute VALUES ('demo', 1, 2, x'', 1500, 60)")
    agg.execute("INSERT INTO site_minute VALUES ('acme', 1, 1, x'', 100, 60)")
    agg.commit()
    agg.close()
    client = TestClient(create_app(tctx))
    assert client.get("/sites/demo/trend").json() == [
        {"bucket_start_ms": 60000, "p75_ms": 1500},
        {"bucket_start_ms": 120000, "p75_ms": 1700},
    ]
