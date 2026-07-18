"""TestCtx and test_ctx_create() — the test mirror of the composition root.

SQLite runs real (fresh files per test in an isolated tmp dir); every
non-SQLite dependency is narrowed to a Fake* with test helpers.
"""

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import ClassVar

import pytest

from api.cfg import Cfg, cfg_create
from api.ctx import Ctx, Repos
from api.db import db_create
from api.logger import logger_create
from api.secrets import Secrets

EPOCH = datetime(2026, 1, 1, tzinfo=UTC)


@dataclass
class FakeClock:
    """Clock stand-in: starts frozen at EPOCH, moves only when told."""

    now_value: datetime = field(default=EPOCH)

    def now(self) -> datetime:
        return self.now_value

    def set(self, value: datetime) -> None:
        self.now_value = value

    def advance(self, seconds: float) -> None:
        self.now_value += timedelta(seconds=seconds)


@dataclass(frozen=True)
class TestCtx(Ctx):
    """Ctx narrowed so no real non-SQLite dependency can leak into a test."""

    __test__: ClassVar[bool] = False  # class, not a pytest collection target

    clock: FakeClock


def test_ctx_create(tmp_path: Path, cfg: Cfg | None = None) -> TestCtx:
    """Production cfg with the data dir swapped to an isolated tmp dir."""
    if cfg is None:
        cfg = replace(cfg_create(), data_dir=tmp_path / "data")
    return TestCtx(
        db=db_create(cfg.data_dir),
        repos=Repos(),
        cfg=cfg,
        secrets=Secrets(),
        logger=logger_create(),
        clock=FakeClock(),
    )


@pytest.fixture
def tctx(tmp_path: Path) -> TestCtx:
    return test_ctx_create(tmp_path)
