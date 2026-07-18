from conftest import TestCtx
from fastapi.testclient import TestClient

from api.app import create_app


def test_healthz_ok(tctx: TestCtx) -> None:
    client = TestClient(create_app(tctx))
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ctx_gets_isolated_real_sqlite(tctx: TestCtx) -> None:
    # Regression guard for the contract-testing rule: the ctx's databases are
    # real files in this test's own tmp dir, not shared or in-memory.
    assert (tctx.cfg.data_dir / "queue.db").is_file()
    assert (tctx.cfg.data_dir / "config.db").is_file()
    assert tctx.db.queue.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
