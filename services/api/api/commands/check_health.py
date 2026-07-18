from api.ctx import Ctx


class QueueSchemaMissingError(Exception):
    """The queue table is gone — wiped volume or failed migration."""


def check_health(ctx: Ctx) -> None:
    """Raise unless the queue database is reachable and carries its schema.

    Probing sqlite_master (not SELECT 1, which never touches storage on an
    open WAL connection) catches a wiped or recreated-empty database.
    """
    row = ctx.db.queue.execute(
        "SELECT count(*) FROM sqlite_master WHERE type = 'table' AND name = 'queue'"
    ).fetchone()
    if row[0] != 1:
        raise QueueSchemaMissingError
