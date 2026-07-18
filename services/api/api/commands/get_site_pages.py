import sqlite3
from dataclasses import dataclass

from api.ctx import Ctx

TOP_PAGES = 20  # contract-fixed on #15


@dataclass(frozen=True)
class PageStats:
    page_url: str
    count: int
    p75_ms: int
    last_seen_ms: int


def get_site_pages(ctx: Ctx, site_id: str) -> list[PageStats]:
    """Top pages by traffic from the worker's running rows (#15).

    agg.db's last_seen is epoch seconds; the wire carries ms (the
    add-don't-repurpose rule, same as /stats). Missing agg.db, missing
    schema, and unknown site all render identically on the dashboard, so
    they all answer [].
    """
    agg = ctx.db.agg_ro()
    if agg is None:
        return []
    try:
        rows = agg.execute(
            "SELECT page_url, count, p75_ms, last_seen FROM page_current"
            " WHERE site_id = ? ORDER BY count DESC LIMIT ?",
            (site_id, TOP_PAGES),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        agg.close()
    return [
        PageStats(
            page_url=str(row[0]),
            count=int(row[1]),
            p75_ms=int(row[2]),
            last_seen_ms=int(row[3]) * 1000,
        )
        for row in rows
    ]
