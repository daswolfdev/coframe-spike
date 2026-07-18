"""Non-secret config, hardcoded in Python — changing it is a reviewed code change."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Cfg:
    data_dir: Path


def cfg_create() -> Cfg:
    return Cfg(data_dir=Path("/data"))
