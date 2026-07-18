from collections.abc import Awaitable, Callable

from pydantic import BaseModel

from api.commands.get_site_pages import get_site_pages
from api.commands.get_site_trend import get_site_trend
from api.commands.get_sites import get_sites
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
        return get_sites(ctx)

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
            for p in get_site_pages(ctx, site_id)
        ]

    return handler


def site_trend(ctx: Ctx) -> Callable[[str], Awaitable[list[TrendPointOut]]]:
    async def handler(site_id: str) -> list[TrendPointOut]:
        return [
            TrendPointOut(bucket_start_ms=p.bucket_start_ms, p75_ms=p.p75_ms)
            for p in get_site_trend(ctx, site_id)
        ]

    return handler
