from api.ctx import Ctx


def list_sites(ctx: Ctx) -> list[str]:
    """Sites the dashboard can pick from (#15): config union aggregated.

    Config is where sites are provisioned; agg.db can carry a site since
    dropped from config — the union keeps its data reachable. Sorted: the
    dashboard defaults to the first entry, so order must be stable.
    """
    sites = set(ctx.cfg.sites)
    for row in ctx.db.agg_rows("SELECT DISTINCT site_id FROM page_current") or []:
        sites.add(str(row[0]))
    return sorted(sites)
