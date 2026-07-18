from collections.abc import Awaitable, Callable

from pydantic import BaseModel

from api.commands.get_top_pages import get_top_pages
from api.commands.get_trend import get_trend
from api.commands.list_sites import list_sites
from api.ctx import Ctx


class PageOut(BaseModel):
    page_url: str
    count: int
    p75_ms: int
    last_seen_ms: int


class TrendPointOut(BaseModel):
    bucket_start_ms: int
    p75_ms: int


def sites(ctx: Ctx) -> Callable[[], Awaitable[list[str]]]:
    async def handler() -> list[str]:
        return list_sites(ctx)

    return handler


def site_pages(ctx: Ctx) -> Callable[[str], Awaitable[list[PageOut]]]:
    async def handler(site_id: str) -> list[PageOut]:
        return [
            PageOut(
                page_url=p.page_url,
                count=p.count,
                p75_ms=p.p75_ms,
                last_seen_ms=p.last_seen_ms,
            )
            for p in get_top_pages(ctx, site_id)
        ]

    return handler


def site_trend(ctx: Ctx) -> Callable[[str], Awaitable[list[TrendPointOut]]]:
    async def handler(site_id: str) -> list[TrendPointOut]:
        return [
            TrendPointOut(bucket_start_ms=t.bucket_start_ms, p75_ms=t.p75_ms)
            for t in get_trend(ctx, site_id)
        ]

    return handler
