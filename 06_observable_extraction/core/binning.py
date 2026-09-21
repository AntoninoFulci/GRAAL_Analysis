"""Fixed Figure 4 energy, azimuth, and invariant-mass binning."""

from __future__ import annotations

import math

import numpy as np

from graal_common.physics.channels import M_ETA, M_PI0, M_PROTON

ENERGY_EDGES_GEV = np.array([1.10, 1.20, 1.30, 1.40, 1.50], dtype=np.float64)
PHI_EDGES_RAD = np.linspace(0.0, 2.0 * math.pi, 13, dtype=np.float64)
PAIR_NAMES = ("p_pi0", "p_eta", "eta_pi0")

_PAIR_MASSES = {
    "p_pi0": (M_PROTON, M_PI0, M_ETA),
    "p_eta": (M_PROTON, M_ETA, M_PI0),
    "eta_pi0": (M_ETA, M_PI0, M_PROTON),
}


def w_max(beam_energy_gev: float) -> float:
    if not math.isfinite(beam_energy_gev) or beam_energy_gev < 0.0:
        raise ValueError("beam_energy_gev must be finite and non-negative")
    return math.sqrt(M_PROTON**2 + 2.0 * M_PROTON * beam_energy_gev)


def bin_index(value: float, edges: np.ndarray) -> int | None:
    if not math.isfinite(value):
        raise ValueError("bin value must be finite")
    edges = np.asarray(edges, dtype=np.float64)
    if value < edges[0] or value > edges[-1]:
        return None
    if value == edges[-1]:
        return len(edges) - 2
    return int(np.searchsorted(edges, value, side="right") - 1)


def energy_bin_index(energy_gev: float) -> int | None:
    return bin_index(energy_gev, ENERGY_EDGES_GEV)


def pair_mass_edges(pair: str, bins: int = 10) -> np.ndarray:
    if pair not in _PAIR_MASSES:
        raise ValueError(f"unknown pair: {pair}")
    if bins <= 0:
        raise ValueError("bins must be positive")
    first, second, spectator = _PAIR_MASSES[pair]
    return np.linspace(
        first + second,
        w_max(1.5) - spectator,
        bins + 1,
        dtype=np.float64,
    )
