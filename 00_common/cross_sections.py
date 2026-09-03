"""Compute threshold-aware channel cross-sections from phase space.

Cross-sections are normalized to a reference energy and capped at the
reference value. Phase-space volumes are relative and have no absolute units.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np

from graal_common.channels import M_PROTON, MCChannel

# Resolution for cached curves and recursive integrals.
N_GRID = 400

# Extend beyond the generator range to avoid interpolation edge clamping.
E_GRID_MAX = 2.4


def W_of_E(E: np.ndarray | float) -> np.ndarray:
    """Convert beam energy E [GeV] to gamma-proton CM energy."""
    return np.sqrt(M_PROTON**2 + 2.0 * M_PROTON * np.asarray(E, dtype=np.float64))


def _kallen(x: np.ndarray, y: float, z: float) -> np.ndarray:
    """Compute the Kallen triangle function."""
    return x * x + y * y + z * z - 2.0 * (x * y + y * z + z * x)


def _phi2(W: np.ndarray | float, ma: float, mb: float) -> np.ndarray:
    """Compute two-body phase space up to a constant."""
    W = np.asarray(W, dtype=np.float64)
    with np.errstate(invalid="ignore", divide="ignore"):
        lam = _kallen(W**2, ma**2, mb**2)
        q = np.sqrt(np.maximum(lam, 0.0)) / (2.0 * W)
        out = q / W
    return np.where(W > ma + mb, out, 0.0)


def _phi_curve(masses: tuple[float, ...], W_grid: np.ndarray) -> np.ndarray:
    """Tabulate the n-body phase-space curve on ``W_grid``."""
    if len(masses) == 2:
        return _phi2(W_grid, masses[0], masses[1])

    inner_masses, m_last = masses[:-1], masses[-1]
    inner_min = float(sum(inner_masses))

    # Interpolate the lower-body curve inside each recursive integral.
    inner_grid = np.linspace(inner_min, float(W_grid[-1]), N_GRID)
    inner_curve = _phi_curve(inner_masses, inner_grid)

    out = np.zeros_like(W_grid, dtype=np.float64)
    for i, W in enumerate(W_grid):
        hi = float(W) - m_last
        if hi <= inner_min:
            continue
        mu = np.linspace(inner_min, hi, N_GRID)
        phi_inner = np.interp(mu, inner_grid, inner_curve)
        integrand = phi_inner * 2.0 * mu * _phi2(float(W), mu, m_last)
        out[i] = np.trapezoid(integrand, mu)
    return out


@lru_cache(maxsize=None)
def _cached_curve(masses: tuple[float, ...]) -> tuple[np.ndarray, np.ndarray]:
    """Build and cache a phase-space curve for one final state."""
    W_thr = float(sum(masses))
    W_grid = np.linspace(W_thr, float(W_of_E(E_GRID_MAX)), N_GRID)
    return W_grid, _phi_curve(masses, W_grid)


def phase_space_volume(
    W: np.ndarray | float, masses: tuple[float, ...]
) -> np.ndarray:
    """Evaluate n-body phase space up to an n-dependent constant."""
    masses = tuple(float(m) for m in masses)
    if len(masses) < 2:
        raise ValueError(
            f"phase space needs at least two bodies, got {len(masses)}: {masses}"
        )
    if len(masses) == 2:
        return _phi2(W, masses[0], masses[1])

    W_grid, curve = _cached_curve(masses)
    W_arr = np.asarray(W, dtype=np.float64)
    return np.interp(W_arr, W_grid, curve, left=0.0, right=float(curve[-1]))


def sigma_at(channel: MCChannel, E: np.ndarray) -> np.ndarray:
    """Evaluate a channel cross-section at beam energies E [GeV]."""
    if channel.sigma_ref_ub is None or channel.e_ref_gev is None:
        raise ValueError(
            f"channel {channel.name!r} has no reference cross-section, so it has "
            f"no sigma(E). Channels weighted by signal_br_ratio (or the signal "
            f"itself) are weighted without one — see compute_shares."
        )

    masses = channel.production_masses
    phi = phase_space_volume(W_of_E(E), masses)

    phi_ref = float(phase_space_volume(W_of_E(channel.e_ref_gev), masses))
    if phi_ref <= 0.0:
        raise ValueError(
            f"channel {channel.name!r}: e_ref_gev {channel.e_ref_gev} is at or "
            f"below the production threshold "
            f"{channel.production_threshold_gev:.3f}, so the cross-section has "
            f"nothing to normalise against"
        )

    return channel.sigma_ref_ub * np.minimum(1.0, phi / phi_ref)
