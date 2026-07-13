"""Pure chi2 pairing physics for the two-meson reconstruction.

No ROOT, no IO: everything here is arithmetic on (4,) [px, py, pz, E] arrays.
That is what makes it testable, and what keeps the chi2 analysis and the
BDT-gated analysis provably identical downstream of the gate.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

M_PI0 = 0.134977
M_ETA = 0.547862
M_PROTON = 0.938272

# The chi2 assumes a mass resolution of 8% of the target mass.
CHI2_RESOLUTION = 0.08

# In the eta+pi0 channel, the pair whose target mass exceeds this is the eta.
HEAVY_MASS_THRESHOLD = 0.4

DATA_DIR = Path(__file__).parent / "data"


@dataclass(frozen=True)
class Channel:
    """A two-meson final state and how to read its combination table."""

    name: str
    combinations_file: Path
    heavy_label: str
    light_label: str
    # True  -> the pair with the larger target mass is the heavy meson (eta+pi0)
    # False -> the pairs keep the order the combination table gives them (2pi0)
    split_by_target_mass: bool


ETA_PI0 = Channel(
    name="eta_pi0",
    combinations_file=DATA_DIR / "combinations_eta_pi0.txt",
    heavy_label="eta",
    light_label="pi0",
    split_by_target_mass=True,
)

TWO_PI0 = Channel(
    name="2pi0",
    combinations_file=DATA_DIR / "combinations_2pi0.txt",
    heavy_label="pi0_1",
    light_label="pi0_2",
    split_by_target_mass=False,
)


def invariant_mass(v: np.ndarray) -> float:
    """Invariant mass of a [px, py, pz, E] four-vector."""
    m2 = v[3] ** 2 - (v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
    return float(np.sqrt(max(m2, 0.0)))


def chi2_value(m_meas_1: float, m_tgt_1: float, m_meas_2: float, m_tgt_2: float) -> float:
    """chi2 of one pairing hypothesis: two measured masses against two targets."""
    d1 = (m_meas_1 - m_tgt_1) / (m_tgt_1 * CHI2_RESOLUTION)
    d2 = (m_meas_2 - m_tgt_2) / (m_tgt_2 * CHI2_RESOLUTION)
    return float(d1**2 + d2**2)


def best_combination(photons: np.ndarray, combinations: np.ndarray) -> tuple[int, float]:
    """Return the (row index, chi2) of the best-fitting row of the table.

    Args:
        photons: (4, 4) array, one row per photon, columns [px, py, pz, E].
        combinations: (K, 6) table, columns [i1, i2, i3, i4, m_tgt_12, m_tgt_34].
    """
    best_idx = -1
    best_chi2 = float("inf")

    for idx, row in enumerate(combinations):
        i1, i2, i3, i4 = (int(row[k]) for k in range(4))
        m12 = invariant_mass(photons[i1] + photons[i2])
        m34 = invariant_mass(photons[i3] + photons[i4])
        c = chi2_value(m12, float(row[4]), m34, float(row[5]))
        if c < best_chi2:
            best_chi2 = c
            best_idx = idx

    return best_idx, best_chi2


def assign_pairs(row: np.ndarray, channel: Channel) -> tuple[tuple[int, int], tuple[int, int]]:
    """Split one table row into (heavy meson photon pair, light meson photon pair)."""
    pair_a = (int(row[0]), int(row[1]))
    pair_b = (int(row[2]), int(row[3]))

    if channel.split_by_target_mass and float(row[4]) <= HEAVY_MASS_THRESHOLD:
        return pair_b, pair_a
    return pair_a, pair_b
