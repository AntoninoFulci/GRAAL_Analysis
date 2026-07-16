"""Channel definitions for the two-meson reconstruction.

The chi2 itself lives in graal_common.pairing, which is also where the stage-1
features get it: one implementation, so the number the reconstruction minimises
and the number the BDT is handed cannot drift apart. This module only says which
final states the reconstruction knows how to name.

A channel is now little more than a hypothesis plus the branch labels it writes.
It used to also carry the path to a combination table; those tables were a
written-out enumeration of what `pairings()` derives, so they are gone, and with
them the requirement that a channel have a file on disk before it can be
reconstructed.
"""
from __future__ import annotations

from dataclasses import dataclass

from graal_common.channels import (
    CHI2_RESOLUTION,
    ETA_PI0_HYP,
    M_ETA,
    M_PI0,
    M_PROTON,
    TWO_PI0_HYP,
    Hypothesis,
)
from graal_common.pairing import Pairing, best_pairing, chi2, pair_masses

__all__ = [
    "CHI2_RESOLUTION",
    "ETA_PI0",
    "M_ETA",
    "M_PI0",
    "M_PROTON",
    "TWO_PI0",
    "Channel",
    "Pairing",
    "best_pairing",
    "chi2",
    "invariant_mass",
    "pair_masses",
]


@dataclass(frozen=True)
class Channel:
    """A two-meson final state the reconstruction can write out."""

    name: str
    hypothesis: Hypothesis

    @property
    def heavy_label(self) -> str:
        return self.hypothesis.heavy_label

    @property
    def light_label(self) -> str:
        return self.hypothesis.light_label


ETA_PI0 = Channel(name="eta_pi0", hypothesis=ETA_PI0_HYP)
TWO_PI0 = Channel(name="2pi0", hypothesis=TWO_PI0_HYP)


def invariant_mass(v) -> float:
    """Invariant mass of a single [px, py, pz, E] four-vector."""
    import numpy as np

    m2 = v[3] ** 2 - (v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
    return float(np.sqrt(max(m2, 0.0)))
