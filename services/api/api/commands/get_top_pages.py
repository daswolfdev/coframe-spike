from dataclasses import dataclass

from api.ctx import Ctx

TOP_PAGES = 20  # the dashboard renders a short table, not a report


@dataclass(frozen=True)
class PageStat:
    page_url: str
    count: int
    p75_ms: int
    last_seen_ms: int


def get_top_pages(ctx: Ctx, site_id: str) -> list[PageStat]:
    """Top pages by all-time volume (#15), from the worker's page_current.

    last_seen is epoch seconds in agg.db; x1000 here keeps the HTTP contract
    in ms without repurposing the worker's column (per the #15 negotiation).
    p75_ms is the worker's trailing-60-minute window, served as-is. Empty
    until the worker first folds this site.
    """
    rows = ctx.db.agg_rows(
        "SELECT page_url, count, p75_ms, last_seen FROM page_current"
        " WHERE site_id = ? ORDER BY count DESC LIMIT ?",
        (site_id, TOP_PAGES),
    )
    return [
        PageStat(
            page_url=str(r[0]),
            count=int(r[1]),
            p75_ms=int(r[2]),
            last_seen_ms=int(r[3]) * 1000,
        )
        for r in rows or []
    ]
