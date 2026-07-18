from collections.abc import Awaitable, Callable
from typing import Literal

from pydantic import BaseModel

from api.commands.check_health import check_health
from api.ctx import Ctx


class HealthOut(BaseModel):
    status: Literal["ok"]


def healthz(ctx: Ctx) -> Callable[[], Awaitable[HealthOut]]:
    async def handler() -> HealthOut:
        check_health(ctx)
        return HealthOut(status="ok")

    return handler
