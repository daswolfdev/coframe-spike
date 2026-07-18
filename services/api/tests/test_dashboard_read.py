"""The dashboard read contract (#15): /sites, /sites/{id}/pages, /sites/{id}/trend.

Seeds agg.db with the worker's DDL (verified against
services/worker/internal/aggregate/store.go): last_seen is epoch SECONDS
(api converts to ms), minute is epoch-seconds // 60, hist is the blob
encoding tested in test_hist.py. Only the columns the api reads appear.
"""

import sqlite3
import struct
from pathlib import Path

from conftest import EPOCH, TestCtx
from fastapi.testclient import TestClient

from api.app import create_app

WORKER_AGG_DDL = """\
CREATE TABLE page_current (
    site_id TEXT, page_url TEXT,
    count INTEGER, p75_ms INTEGER, last_seen INTEGER,
    PRIMARY KEY (site_id, page_url));
CREATE TABLE page_minute (
    site_id TEXT, page_url TEXT, minute INTEGER,
    count INTEGER, hist BLOB, p75_ms INTEGER, last_seen INTEGER,
    PRIMARY KEY (site_id, page_url, minute));
"""

NOW_MINUTE = int(EPOCH.timestamp()) // 60  # FakeClock starts frozen at EPOCH

CurrentRow = tuple[str, str, int, int, int]
MinuteRow = tuple[str, str, int, int, bytes, int, int]


def agg_seed(
    data_dir: Path,
    current: list[CurrentRow] | None = None,
    minute: list[MinuteRow] | None = None,
) -> None:
    agg = sqlite3.connect(data_dir / "agg.db")
    agg.executescript(WORKER_AGG_DDL)
    agg.executemany("INSERT INTO page_current VALUES (?, ?, ?, ?, ?)", current or [])
    agg.executemany(
        "INSERT INTO page_minute VALUES (?, ?, ?, ?, ?, ?, ?)", minute or []
    )
    agg.commit()
    agg.close()


def hist_blob(bins: dict[int, int]) -> bytes:
    """Encode a histogram blob — bin/edge vectors derived in test_hist.py."""
    counts = [0] * 128
    for i, c in bins.items():
        counts[i] = c
    return struct.pack("<128I", *counts)


def test_sites_without_agg_db_lists_configured_sites(tctx: TestCtx) -> None:
    client = TestClient(create_app(tctx))
    assert client.get("/sites").json() == ["acme", "demo"]


def test_sites_unions_config_with_data(tctx: TestCtx) -> None:
    agg_seed(tctx.cfg.data_dir, current=[("zebra", "/", 1, 100, 1784415300)])
    client = TestClient(create_app(tctx))
    assert client.get("/sites").json() == ["acme", "demo", "zebra"]


def test_sites_survives_agg_db_without_schema(tctx: TestCtx) -> None:
    sqlite3.connect(tctx.cfg.data_dir / "agg.db").close()
    client = TestClient(create_app(tctx))
    assert client.get("/sites").json() == ["acme", "demo"]


def test_pages_without_agg_db_is_empty(tctx: TestCtx) -> None:
    client = TestClient(create_app(tctx))
    assert client.get("/sites/demo/pages").json() == []


def test_pages_sorted_by_count_desc_in_ms(tctx: TestCtx) -> None:
    agg_seed(
        tctx.cfg.data_dir,
        current=[
            ("demo", "/", 5, 1620, 1784415290),
            ("demo", "/checkout", 18, 2410, 1784415300),
            ("acme", "/landing", 99, 1210, 1784414000),
        ],
    )
    client = TestClient(create_app(tctx))
    assert client.get("/sites/demo/pages").json() == [
        {
            "page_url": "/checkout",
            "count": 18,
            "p75_ms": 2410,
            "last_seen_ms": 1784415300000,
        },
        {"page_url": "/", "count": 5, "p75_ms": 1620, "last_seen_ms": 1784415290000},
    ]


def test_pages_caps_at_top_20(tctx: TestCtx) -> None:
    agg_seed(
        tctx.cfg.data_dir,
        current=[("demo", f"/p{n}", n, 100, 1784415300) for n in range(1, 26)],
    )
    client = TestClient(create_app(tctx))
    counts = [p["count"] for p in client.get("/sites/demo/pages").json()]
    assert counts == list(range(25, 5, -1))


def test_pages_unknown_site_is_empty(tctx: TestCtx) -> None:
    agg_seed(tctx.cfg.data_dir, current=[("demo", "/", 5, 1620, 1784415290)])
    client = TestClient(create_app(tctx))
    assert client.get("/sites/nope/pages").json() == []


def test_trend_without_agg_db_is_empty(tctx: TestCtx) -> None:
    client = TestClient(create_app(tctx))
    assert client.get("/sites/demo/trend").json() == []


def test_trend_merges_site_hists_per_minute_ascending(tctx: TestCtx) -> None:
    # Minute m1 has two pages whose merged histogram crosses p75 in bin 13
    # (upper edge 101 ms) — per-page p75s (101, 1003) must NOT be averaged.
    m1, m2 = NOW_MINUTE - 5, NOW_MINUTE - 3
    agg_seed(
        tctx.cfg.data_dir,
        minute=[
            ("demo", "/", m1, 3, hist_blob({13: 3}), 101, 1),
            ("demo", "/c", m1, 1, hist_blob({59: 1}), 1003, 1),
            ("demo", "/", m2, 4, hist_blob({59: 4}), 1003, 1),
            ("acme", "/", m2, 1, hist_blob({13: 1}), 101, 1),
        ],
    )
    client = TestClient(create_app(tctx))
    assert client.get("/sites/demo/trend").json() == [
        {"bucket_start_ms": m1 * 60_000, "p75_ms": 101},
        {"bucket_start_ms": m2 * 60_000, "p75_ms": 1003},
    ]


def test_trend_drops_minutes_outside_trailing_hour(tctx: TestCtx) -> None:
    # Same cutoff as the worker's page_current window: minute > now - 60.
    m_out, m_in = NOW_MINUTE - 60, NOW_MINUTE - 59
    agg_seed(
        tctx.cfg.data_dir,
        minute=[
            ("demo", "/", m_out, 1, hist_blob({13: 1}), 101, 1),
            ("demo", "/", m_in, 1, hist_blob({13: 1}), 101, 1),
        ],
    )
    client = TestClient(create_app(tctx))
    buckets = [p["bucket_start_ms"] for p in client.get("/sites/demo/trend").json()]
    assert buckets == [m_in * 60_000]
