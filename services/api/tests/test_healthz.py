from conftest import TestCtx
from fastapi.testclient import TestClient

from api.app import create_app


def test_healthz_ok(tctx: TestCtx) -> None:
    client = TestClient(create_app(tctx))
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_healthz_fails_when_schema_gone(tctx: TestCtx) -> None:
    # Regression for #31: SELECT 1 stayed green with the storage wiped.
    # Probing sqlite_master must catch a recreated-empty database.
    tctx.db.queue.execute("DROP TABLE queue")
    client = TestClient(create_app(tctx), raise_server_exceptions=False)
    assert client.get("/healthz").status_code == 500


def test_ctx_gets_isolated_real_sqlite(tctx: TestCtx) -> None:
    # Regression guard for the contract-testing rule: the ctx's database is a
    # real file in this test's own tmp dir, not shared or in-memory.
    assert (tctx.cfg.data_dir / "queue.db").is_file()
    assert tctx.db.queue.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
