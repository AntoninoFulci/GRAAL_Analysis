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
    M_DEUTERON,
    M_ETA,
    M_NEUTRON,
    M_PI0,
    M_PROTON,
    TWO_PI0_HYP,
    Hypothesis,
)
from graal_common.pairing import Pairing, best_pairing, chi2, pair_masses

__all__ = [
    "CHI2_RESOLUTION",
    "ETA_PI0",
    "M_DEUTERON",
    "M_ETA",
    "M_NEUTRON",
    "M_PI0",
    "M_PROTON",
    "PARTNER_MASSES",
    "TWO_PI0",
    "partner_mass",
    "passes_missing_mass",
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


# Recoil partner of the eta-pi0 system: gamma N -> N eta pi0. The missing mass
# of the eta-pi0 pair peaks at the partner's mass, and requiring it there is what
# centres the reconstructed eta -- see the design note. Proton and neutron are
# ~1.3 MeV apart, far below the missing-mass resolution, so they give the same
# cut; only the deuteron (twice the mass) is a distinct hypothesis.
PARTNER_MASSES: dict[str, float] = {
    "proton": M_PROTON,
    "neutron": M_NEUTRON,
    "deuteron": M_DEUTERON,
}


def partner_mass(name: str) -> float:
    """Mass of a named recoil partner, listing the alternatives when unknown."""
    try:
        return PARTNER_MASSES[name]
    except KeyError:
        raise KeyError(
            f"unknown recoil partner {name!r}; known: {sorted(PARTNER_MASSES)}"
        ) from None


def passes_missing_mass(
    missing_mass: float, partner_mass: float, window: float | None
) -> bool:
    """Whether an event's eta-pi0 missing mass is close enough to the partner.

    True keeps the event. A window of None or <= 0 disables the cut entirely, so
    a run can be reproduced without it by passing --missing-mass-window 0.

    The window is centred on the partner's NOMINAL mass, not on where the data's
    missing-mass peak happens to sit: the miscentred events are the contamination
    (they run high in eta mass and low in missing mass together), so cutting
    around the nominal mass keeps the kinematically correct events and drops the
    junk, while cutting around the observed peak would do the opposite.
    """
    if window is None or window <= 0.0:
        return True
    return abs(missing_mass - partner_mass) < window
