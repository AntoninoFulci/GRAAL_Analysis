"""Energy dependence of the channel cross-sections.

The registry in `channels` carries one number per channel: a cross-section from
a paper, measured at one energy. Used flat across the whole beam range that
number is wrong in a specific direction — it ignores that a channel does not
exist below its threshold and only reaches its published size well above it.
omega_pi0 opens at 1.366 GeV and etaprime at 1.447, in the last few percent of
GRAAL's range, yet both were weighted at their far-above-threshold values.

This module supplies the missing shape:

    sigma(E) = sigma_ref * min(1, Phi_n(W(E)) / Phi_n(W(E_ref)))

Phi_n is the n-body phase-space volume of the PRODUCTION final state — what the
reaction makes, not what those products later decay into. The decay does not
change how the cross-section turns on.

Two deliberate choices:

  The saturation. Phase space grows without bound above E_ref, so an unbounded
  ratio would scale a channel measured near its peak UPWARDS several-fold at the
  top of the beam range — inventing structure from nothing, and doing it to
  pi0pi0, the largest background. Saturating reads as "the published sigma_ref,
  with the threshold turn-on put back in", and can only ever reduce a weight,
  never inflate one.

  The shape. Pure phase space carries no resonance structure; the S11(1535) and
  the D15/F15 bump are flattened into the plateau. That is accepted: the turn-on
  is what the weights were wrong about. Real excitation functions would mean
  digitising a curve per channel, which is a larger piece of work and can follow
  if the flattening proves to matter.

Phi_n is computed UP TO AN n-DEPENDENT CONSTANT. Only ratios at fixed n are ever
taken, so every prefactor cancels. Nothing here may be read as an absolute
phase-space volume.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np

from graal_common.channels import M_PROTON

# Points per tabulated curve. The recursion below tabulates Phi_k once as a
# function of the sub-system mass and interpolates it, rather than nesting a
# quadrature per evaluation: nested quads would mean a triple integral per event
# and would never finish on a million-event sample.
N_GRID = 400

# Upper end of the tabulated range [GeV of beam energy]. The physics needs only
# ~1.75 (the generators' ceiling; W ~ 2.04), but the monotonicity tests probe a
# 5-body final state 0.8 GeV of W above its ~1.48 threshold, i.e. out to W ~
# 2.28. The grid must cover that or np.interp's edge clamp returns equal values
# and the "rises monotonically" check sees a spurious zero step. 2.4 -> W ~ 2.32,
# comfortably past both.
E_GRID_MAX = 2.4


def W_of_E(E: np.ndarray | float) -> np.ndarray:
    """CM energy of the gamma-p system for a beam energy E [GeV].

    W = sqrt(m_p^2 + 2 m_p E), the relation the production thresholds in
    `channels` invert. Both must stay the same formula: if they drift, a
    channel's cross-section turns on at an energy its own generator does not.
    """
    return np.sqrt(M_PROTON**2 + 2.0 * M_PROTON * np.asarray(E, dtype=np.float64))


def _kallen(x: np.ndarray, y: float, z: float) -> np.ndarray:
    """Kallen triangle function lambda(x, y, z)."""
    return x * x + y * y + z * z - 2.0 * (x * y + y * z + z * x)


def _phi2(W: np.ndarray | float, ma: float, mb: float) -> np.ndarray:
    """Two-body phase space, up to a constant: q / W, with q the CM momentum.

    Zero at and below threshold rather than NaN — a channel that cannot happen
    contributes nothing, and must say so numerically.
    """
    W = np.asarray(W, dtype=np.float64)
    with np.errstate(invalid="ignore", divide="ignore"):
        lam = _kallen(W**2, ma**2, mb**2)
        q = np.sqrt(np.maximum(lam, 0.0)) / (2.0 * W)
        out = q / W
    return np.where(W > ma + mb, out, 0.0)


def _phi_curve(masses: tuple[float, ...], W_grid: np.ndarray) -> np.ndarray:
    """Phi_k tabulated on W_grid, built bottom-up from the two-body case.

    The standard recursion, with dmu^2 = 2 mu dmu:

        Phi_n(W) = int dmu^2 Phi_{n-1}(mu; m_1..m_{n-1}) Phi_2(W; mu, m_n)

    The inner curve is tabulated ONCE over the sub-system mass and interpolated,
    which is what keeps this linear rather than exponential in the body count.
    """
    if len(masses) == 2:
        return _phi2(W_grid, masses[0], masses[1])

    inner_masses, m_last = masses[:-1], masses[-1]
    inner_min = float(sum(inner_masses))

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
    """(W_grid, Phi_n) for one final state, tabulated from threshold up.

    Cached on the mass tuple: the curve costs a recursion to build and never
    changes, while sigma_at is called once per channel per run. The returned
    arrays are shared — treat them as read-only.
    """
    W_thr = float(sum(masses))
    W_grid = np.linspace(W_thr, float(W_of_E(E_GRID_MAX)), N_GRID)
    return W_grid, _phi_curve(masses, W_grid)


def phase_space_volume(
    W: np.ndarray | float, masses: tuple[float, ...]
) -> np.ndarray:
    """Phi_n(W) for a final state, up to an n-dependent constant.

    Zero at or below threshold. Only ratios at fixed n are meaningful.
    """
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
