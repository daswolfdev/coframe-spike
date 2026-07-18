from collections.abc import Awaitable, Callable

from fastapi import HTTPException
from pydantic import BaseModel

from api.commands.get_site_config import get_site_config
from api.ctx import Ctx


class ExperimentOut(BaseModel):
    id: str
    variants: list[str]
    traffic: float


class ConfigOut(BaseModel):
    sampling_rate: float
    experiments: list[ExperimentOut]


def get_config(ctx: Ctx) -> Callable[[str], Awaitable[ConfigOut]]:
    async def handler(site_id: str) -> ConfigOut:
        site = get_site_config(ctx, site_id)
        if site is None:
            raise HTTPException(status_code=404, detail="unknown site")
        return ConfigOut(
            sampling_rate=site.sampling_rate,
            experiments=[
                ExperimentOut(id=e.id, variants=list(e.variants), traffic=e.traffic)
                for e in site.experiments
            ],
        )

    return handler
