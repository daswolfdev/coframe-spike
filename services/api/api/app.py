from fastapi import FastAPI

from api.ctx import Ctx, ctx_create
from api.endpoints.config import get_config
from api.endpoints.events import post_events
from api.endpoints.healthz import healthz
from api.endpoints.sites import site_pages, site_trend, sites
from api.endpoints.stats import stats


def create_app(ctx: Ctx) -> FastAPI:
    """Register every route — the whole HTTP surface on one screen."""
    app = FastAPI(title="perfmon api")
    app.post("/events", status_code=202)(post_events(ctx))
    app.get("/config/{site_id}")(get_config(ctx))
    app.get("/healthz")(healthz(ctx))
    app.get("/stats")(stats(ctx))
    app.get("/sites")(sites(ctx))
    app.get("/sites/{site_id}/pages")(site_pages(ctx))
    app.get("/sites/{site_id}/trend")(site_trend(ctx))
    return app


def build() -> FastAPI:
    """Uvicorn entry: `uvicorn api.app:build --factory`."""
    return create_app(ctx_create())
