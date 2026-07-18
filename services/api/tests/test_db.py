import pytest
from conftest import TestCtx


class BoomError(Exception):
    pass


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
