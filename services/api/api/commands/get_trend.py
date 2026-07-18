from dataclasses import dataclass

from api.ctx import Ctx

TREND_BUCKETS = 1440  # 24h of minutes bounds the payload; pruning is deferred


@dataclass(frozen=True)
class TrendPoint:
    bucket_start_ms: int
    p75_ms: int


def get_trend(ctx: Ctx, site_id: str) -> list[TrendPoint]:
    """Site-wide p75 per minute bucket, oldest first (#15).

    Reads the worker's site_minute rows — the histogram's owner denormalizes
    p75 per site so no reader ever parses hist blobs (per-page p75s don't
    compose into a site p75; merged histograms do, and the merge lives with
    the worker). Newest TREND_BUCKETS minutes, ascending for the sparkline.
    """
    rows = ctx.db.agg_rows(
        "SELECT minute, p75_ms FROM"
        " (SELECT minute, p75_ms FROM site_minute WHERE site_id = ?"
        "  ORDER BY minute DESC LIMIT ?)"
        " ORDER BY minute",
        (site_id, TREND_BUCKETS),
    )
    return [
        TrendPoint(bucket_start_ms=int(r[0]) * 60_000, p75_ms=int(r[1]))
        for r in rows or []
    ]
