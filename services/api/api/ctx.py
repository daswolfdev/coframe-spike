"""The Ctx dataclass and ctx_create(), the one composition root.

Production and tests share this wiring; tests point it at an isolated data
dir (see tests/conftest.py).
"""

import logging
from dataclasses import dataclass

from api.cfg import Cfg, cfg_create
from api.clock import Clock, SystemClock
from api.db import Db, db_create
from api.env import secrets_from_env
from api.logger import logger_create
from api.secrets import Secrets


@dataclass(frozen=True)
class Repos:
    """Earned, not default — empty until a true external or shared SQL op exists."""


@dataclass(frozen=True)
class Ctx:
    db: Db
    repos: Repos
    cfg: Cfg
    secrets: Secrets
    logger: logging.Logger
    clock: Clock


def ctx_create(cfg: Cfg | None = None) -> Ctx:
    cfg = cfg if cfg is not None else cfg_create()
    return Ctx(
        db=db_create(cfg.data_dir),
        repos=Repos(),
        cfg=cfg,
        secrets=secrets_from_env(),
        logger=logger_create(),
        clock=SystemClock(),
    )
