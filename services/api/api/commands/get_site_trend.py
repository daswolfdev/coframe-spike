import sqlite3
from dataclasses import dataclass

from api.ctx import Ctx
from api.hist import Hist, hist_decode, hist_merge, hist_p75

TRAILING_MINUTES = 60  # the worker's page_current window; the trend shows the same hour


@dataclass(frozen=True)
class TrendPoint:
    bucket_start_ms: int
    p75_ms: int


def get_site_trend(ctx: Ctx, site_id: str) -> list[TrendPoint]:
    """Per-minute site-wide p75 over the trailing hour, time-ascending (#15).

    Per-page p75s can't be combined, so each minute merges its pages'
    histogram blobs and reports the merged p75. Minutes with no rows are
    omitted — #15 locks the shape, not bucket density; the dashboard
    renders whatever points arrive.
    """
    agg = ctx.db.agg_ro()
    if agg is None:
        return []
    since = int(ctx.clock.now().timestamp()) // 60 - TRAILING_MINUTES
    try:
        rows = agg.execute(
            "SELECT minute, hist FROM page_minute"
            " WHERE site_id = ? AND minute > ? ORDER BY minute",
            (site_id, since),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        agg.close()
    minutes: dict[int, Hist] = {}
    for row in rows:
        minute, h = int(row[0]), hist_decode(bytes(row[1]))
        minutes[minute] = hist_merge(minutes[minute], h) if minute in minutes else h
    return [
        TrendPoint(bucket_start_ms=minute * 60_000, p75_ms=hist_p75(h))
        for minute, h in minutes.items()
    ]
