from dataclasses import dataclass

from api.ctx import Ctx


@dataclass(frozen=True)
class Event:
    site_id: str
    page_url: str
    lcp_ms: float
    ts_ms: int
    session_id: str


def record_event(ctx: Ctx, event: Event) -> None:
    """Enqueue one event: a single autocommit INSERT — the benchmarked path."""
    received_at_ms = int(ctx.clock.now().timestamp() * 1000)
    ctx.db.queue.execute(
        "INSERT INTO queue (site_id, page_url, lcp_ms, ts_ms, session_id,"
        " received_at_ms) VALUES (?, ?, ?, ?, ?, ?)",
        (
            event.site_id,
            event.page_url,
            event.lcp_ms,
            event.ts_ms,
            event.session_id,
            received_at_ms,
        ),
    )
