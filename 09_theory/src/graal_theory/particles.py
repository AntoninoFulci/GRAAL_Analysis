"""Immutable records for particles used by reaction models."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from .sources import SourceRef


@dataclass(frozen=True)
class Particle:
    name: str
    mass_gev: float
    width_gev: float
    source: SourceRef

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("particle name must be nonempty")
        if not isfinite(self.mass_gev) or self.mass_gev <= 0:
            raise ValueError("mass_gev must be finite and positive")
        if not isfinite(self.width_gev) or self.width_gev < 0:
            raise ValueError("width_gev must be finite and nonnegative")
        if not self.source.locator.strip():
            raise ValueError("particle requires source locator")
