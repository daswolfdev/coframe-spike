from fastapi import FastAPI

from api.ctx import Ctx, ctx_create
from api.endpoints.healthz import healthz


def create_app(ctx: Ctx) -> FastAPI:
    """Register every route — the whole HTTP surface on one screen."""
    app = FastAPI(title="perfmon api")
    app.get("/healthz")(healthz(ctx))
    return app


def build() -> FastAPI:
    """Uvicorn entry: `uvicorn api.app:build --factory`."""
    return create_app(ctx_create())
