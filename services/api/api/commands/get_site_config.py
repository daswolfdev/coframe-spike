from api.cfg import SiteConfig
from api.ctx import Ctx


def get_site_config(ctx: Ctx, site_id: str) -> SiteConfig | None:
    """Site config is code — see cfg.py for why git is the system of record."""
    return ctx.cfg.sites.get(site_id)
