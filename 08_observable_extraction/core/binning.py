"""Figure 4 energy, configurable azimuth, and fixed invariant-mass binning."""

from __future__ import annotations

import math

import numpy as np

from graal_common.physics.beam_profiles import UV_PROFILE

ENERGY_EDGES_GEV = np.asarray(UV_PROFILE.energy_edges_gev, dtype=np.float64)
LEGACY_PHI_EDGES_RAD = np.linspace(0.0, 2.0 * math.pi, 13, dtype=np.float64)
PHI_EDGES_RAD = np.linspace(-math.pi / 12, 2.0 * math.pi - math.pi / 12, 13, dtype=np.float64)
PHI_BIN_CHOICES = (8, 12, 16)
# Approved rounded finite-bin divisors for a center-evaluated cos(2 phi) fit.
# Sigma and its error are divided by these fixed values, not a computed sinc.
# Uniform full-circle bins and common, approximately constant within-bin
# acceptance are assumed; see Zachariou et al., PRC 91, 055202 (2015),
# Eqs. (15)-(17), and wiki/finite-bin-correction.md.
PHI_BIN_DIVISORS = {8: 0.9003, 12: 0.9549, 16: 0.9745}
PAIR_NAMES = ("p_pi0", "p_eta", "eta_pi0")

_PAIR_MASS_RANGES_GEV = {
    "p_pi0": (1.0, 1.4),
    "p_eta": (1.4, 1.8),
    "eta_pi0": (0.6, 1.0),
}


def phi_edges_rad(bins: int = 12) -> np.ndarray:
    """Build full-circle bins centered on zero and the cardinal directions."""
    if isinstance(bins, bool) or not isinstance(bins, int) or bins not in PHI_BIN_CHOICES:
        raise ValueError("phi bins must be 8, 12, or 16")
    half_width = math.pi / bins
    return np.linspace(-half_width, 2.0 * math.pi - half_width, bins + 1, dtype=np.float64)


def validate_edges(edges: np.ndarray) -> np.ndarray:
    edges = np.asarray(edges, dtype=np.float64)
    if edges.ndim != 1 or len(edges) < 2:
        raise ValueError("bin edges must be a one-dimensional array of length >= 2")
    if np.any(~np.isfinite(edges)) or np.any(np.diff(edges) <= 0.0):
        raise ValueError("bin edges must be finite and strictly increasing")
    return edges


def phi_bin_origin(edges: np.ndarray) -> str:
    """Identify supported new or historical grids without conflating origins."""
    edges = validate_edges(edges)
    bins = len(edges) - 1
    expected = phi_edges_rad(bins)
    if np.allclose(edges, expected, rtol=0.0, atol=1e-12):
        return "center_zero"
    legacy = np.linspace(0.0, 2.0 * math.pi, bins + 1, dtype=np.float64)
    if np.allclose(edges, legacy, rtol=0.0, atol=1e-12):
        return "legacy_edge_zero"
    raise ValueError("phi bins require a supported uniform full-circle grid and origin")


def phi_bin_divisor(edges: np.ndarray) -> float:
    """Return the literal divisor for either supported full-circle origin."""
    phi_bin_origin(edges)
    return PHI_BIN_DIVISORS[len(edges) - 1]


def wrap_phi_rad(phi: np.ndarray, edges: np.ndarray = PHI_EDGES_RAD) -> np.ndarray:
    """Represent physical azimuths in [low, high) without rotating their phase."""
    edges = validate_edges(edges)
    phi_bin_origin(edges)
    values = np.asarray(phi, dtype=np.float64)
    if np.any(~np.isfinite(values)):
        raise ValueError("phi values must be finite")
    low, high = edges[0], edges[-1]
    wrapped = np.remainder(values - low, 2.0 * math.pi) + low
    # Preserve in-range values exactly (including neighbors of bin boundaries).
    # Negative remainders can round to a whole turn just below the lower edge.
    wrapped = np.minimum(wrapped, np.nextafter(high, low))
    return np.where((values >= low) & (values < high), values, wrapped)


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
