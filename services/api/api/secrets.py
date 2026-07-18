"""Secret values. Redacting repr; never logged, never in Cfg.

No secrets exist yet — the dataclass holds the seam so the first real secret
lands as a typed field, not an ad-hoc env read.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Secrets:
    def __repr__(self) -> str:
        return "Secrets(<redacted>)"
