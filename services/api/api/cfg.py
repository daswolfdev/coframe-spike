"""Non-secret config, hardcoded in Python — changing it is a reviewed code change.

Site SDK config lives here too (OBJECTIVE.md sanctions an in-memory map):
git is the system of record and `make deploy S=api` is the edit path —
seconds, health-gated, auditable. Trigger to move it into SQLite: the first
time a non-engineer needs to change a value.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Experiment:
    id: str
    variants: tuple[str, ...]
    traffic: float


@dataclass(frozen=True)
class SiteConfig:
    sampling_rate: float
    experiments: tuple[Experiment, ...] = ()


@dataclass(frozen=True)
class Cfg:
    data_dir: Path
    sites: Mapping[str, SiteConfig]


def cfg_create() -> Cfg:
    return Cfg(
        data_dir=Path("/data"),
        sites={
            "demo": SiteConfig(
                sampling_rate=1.0,
                experiments=(
                    Experiment(
                        id="checkout-cta-color",
                        variants=("control", "green"),
                        traffic=0.5,
                    ),
                    Experiment(
                        id="hero-image-lazyload",
                        variants=("control", "eager"),
                        traffic=0.2,
                    ),
                ),
            ),
            "acme": SiteConfig(sampling_rate=0.1),
        },
    )
