import sqlite3
from pathlib import Path

import pytest
from conftest import TestCtx

from api.db import db_create


class BoomError(Exception):
    pass


def test_db_create_migrates_pre_claim_id_volume(tmp_path: Path) -> None:
    # Failure mode this guards: CREATE TABLE IF NOT EXISTS skips existing
    # tables, so a volume created before #46 lacks claim_id and the worker
    # crashes at startup ("no such column: claim_id").
    old = sqlite3.connect(tmp_path / "queue.db")
    old.execute(
        "CREATE TABLE queue (id INTEGER PRIMARY KEY, site_id TEXT NOT NULL,"
        " page_url TEXT NOT NULL, lcp_ms REAL NOT NULL, ts_ms INTEGER NOT NULL,"
        " session_id TEXT NOT NULL, received_at_ms INTEGER NOT NULL)"
    )
    old.close()

    db = db_create(tmp_path)
    cols = {str(row[1]) for row in db.queue.execute("PRAGMA table_info(queue)")}
    assert "claim_id" in cols
    # Idempotent: a second boot on the migrated volume must not error.
    db_create(tmp_path)


def _count(ctx: TestCtx) -> int:
    return int(ctx.db.queue.execute("SELECT count(*) FROM t").fetchone()[0])


def _insert_then_boom(tctx: TestCtx) -> None:
    with tctx.db.transaction(tctx.db.queue) as conn:
        conn.execute("INSERT INTO t VALUES (1)")
        raise BoomError


def test_transaction_commits(tctx: TestCtx) -> None:
    tctx.db.queue.execute("CREATE TABLE t (x)")
    with tctx.db.transaction(tctx.db.queue) as conn:
        conn.execute("INSERT INTO t VALUES (1)")
        conn.execute("INSERT INTO t VALUES (2)")
    assert _count(tctx) == 2


def test_transaction_rolls_back_on_error(tctx: TestCtx) -> None:
    # Failure mode: a raise mid-transaction must leave no partial write —
    # and no open transaction poisoning later statements.
    tctx.db.queue.execute("CREATE TABLE t (x)")
    with pytest.raises(BoomError):
        _insert_then_boom(tctx)
    assert _count(tctx) == 0
    assert not tctx.db.queue.in_transaction
