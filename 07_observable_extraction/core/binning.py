"""Fixed Figure 4 energy, azimuth, and invariant-mass binning."""

from __future__ import annotations

import math

import numpy as np

ENERGY_EDGES_GEV = np.array([1.10, 1.20, 1.30, 1.40, 1.50], dtype=np.float64)
PHI_EDGES_RAD = np.linspace(0.0, 2.0 * math.pi, 13, dtype=np.float64)
PAIR_NAMES = ("p_pi0", "p_eta", "eta_pi0")

_PAIR_MASS_RANGES_GEV = {
    "p_pi0": (1.0, 1.4),
    "p_eta": (1.4, 1.8),
    "eta_pi0": (0.6, 1.0),
}


def validate_edges(edges: np.ndarray) -> np.ndarray:
    edges = np.asarray(edges, dtype=np.float64)
    if edges.ndim != 1 or len(edges) < 2:
        raise ValueError("bin edges must be a one-dimensional array of length >= 2")
    if np.any(~np.isfinite(edges)) or np.any(np.diff(edges) <= 0.0):
        raise ValueError("bin edges must be finite and strictly increasing")
    return edges


def bin_index(value: float, edges: np.ndarray) -> int | None:
    if not math.isfinite(value):
        raise ValueError("bin value must be finite")
    edges = validate_edges(edges)
    if value < edges[0] or value > edges[-1]:
        return None
    if value == edges[-1]:
        return len(edges) - 2
    return int(np.searchsorted(edges, value, side="right") - 1)


def energy_bin_index(
    energy_gev: float,
    energy_edges: np.ndarray = ENERGY_EDGES_GEV,
) -> int | None:
    return bin_index(energy_gev, energy_edges)


def pair_mass_edges(pair: str, bins: int = 10) -> np.ndarray:
    if pair not in _PAIR_MASS_RANGES_GEV:
        raise ValueError(f"unknown pair: {pair}")
    if bins <= 0:
        raise ValueError("bins must be positive")
    low, high = _PAIR_MASS_RANGES_GEV[pair]
    return np.linspace(low, high, bins + 1, dtype=np.float64)
