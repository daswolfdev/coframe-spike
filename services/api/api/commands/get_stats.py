import sqlite3
from dataclasses import dataclass

from api.ctx import Ctx


@dataclass(frozen=True)
class Stats:
    queue_depth: int
    last_aggregate_ms: int | None


def get_stats(ctx: Ctx) -> Stats:
    """Serve the ops read surface (#19): the runbook's diagnostic numbers.

    queue_depth is the one metric that matters when the worker dies (depth
    grows instead of events dropping). last_aggregate_ms is the newest event
    time the worker has folded into page_current (agg.db is worker-owned;
    last_seen there is epoch seconds — converted to ms here, per the
    add-don't-repurpose contract rule). None until the worker first writes:
    the dashboard renders that as "no aggregates yet".
    """
    depth = int(ctx.db.queue.execute("SELECT count(*) FROM queue").fetchone()[0])
    return Stats(queue_depth=depth, last_aggregate_ms=_last_aggregate_ms(ctx))


def _last_aggregate_ms(ctx: Ctx) -> int | None:
    agg = ctx.db.agg_ro()
    if agg is None:
        return None
    try:
        row = agg.execute("SELECT max(last_seen) FROM page_current").fetchone()
    except sqlite3.OperationalError:
        # agg.db exists but the worker hasn't created its schema yet.
        return None
    finally:
        agg.close()
    return None if row[0] is None else int(row[0]) * 1000
