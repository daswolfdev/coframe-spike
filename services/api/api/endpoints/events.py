from collections.abc import Awaitable, Callable
from typing import Literal

from pydantic import BaseModel, Field

from api.commands.record_event import Event, record_event
from api.ctx import Ctx


class EventIn(BaseModel):
    """The SDK wire format, per OBJECTIVE.md. `timestamp` is epoch ms."""

    site_id: str = Field(min_length=1, max_length=64)
    page_url: str = Field(min_length=1, max_length=2048)
    lcp_ms: float = Field(ge=0)
    timestamp: int = Field(ge=0)
    session_id: str = Field(min_length=1, max_length=128)


class Accepted(BaseModel):
    status: Literal["accepted"]


def post_events(ctx: Ctx) -> Callable[[EventIn], Awaitable[Accepted]]:
    async def handler(event: EventIn) -> Accepted:
        record_event(
            ctx,
            Event(
                site_id=event.site_id,
                page_url=event.page_url,
                lcp_ms=event.lcp_ms,
                ts_ms=event.timestamp,
                session_id=event.session_id,
            ),
        )
        return Accepted(status="accepted")

    return handler
