import sqlite3

from api.ctx import Ctx


def get_sites(ctx: Ctx) -> list[str]:
    """Sites with data or config (#15) — union, sorted for a stable dropdown.

    Config-only sites appear before their first event; sites with residual
    aggregates appear after decommission. A missing or schema-less agg.db
    just means no data-side entries yet.
    """
    sites = set(ctx.cfg.sites)
    agg = ctx.db.agg_ro()
    if agg is not None:
        try:
            rows = agg.execute("SELECT DISTINCT site_id FROM page_current").fetchall()
            sites.update(str(row[0]) for row in rows)
        except sqlite3.OperationalError:
            pass
        finally:
            agg.close()
    return sorted(sites)
