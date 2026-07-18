from collections.abc import Awaitable, Callable

from pydantic import BaseModel

from api.commands.get_stats import get_stats
from api.ctx import Ctx


class StatsOut(BaseModel):
    queue_depth: int
    last_aggregate_ms: int | None


def stats(ctx: Ctx) -> Callable[[], Awaitable[StatsOut]]:
    async def handler() -> StatsOut:
        s = get_stats(ctx)
        return StatsOut(
            queue_depth=s.queue_depth, last_aggregate_ms=s.last_aggregate_ms
        )

    return handler
