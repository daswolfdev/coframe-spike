from api.ctx import Ctx


def check_health(ctx: Ctx) -> None:
    """Raise if either database is unreachable."""
    ctx.db.queue.execute("SELECT 1")
    ctx.db.config.execute("SELECT 1")
