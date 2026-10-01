"""Shared numerical core for reduced six-channel N*(1535) amplitudes."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

if TYPE_CHECKING:
    from graal_theory.amplitudes.nstar1535_reduced import ReducedTParameters


def validated_energy(w_gev: float, parameters: ReducedTParameters) -> float:
    if isinstance(w_gev, bool) or not isinstance(w_gev, (int, float, np.integer, np.floating)):
        raise ValueError("W must be a finite real scalar")
    w = float(w_gev)
    threshold = min(np.add(parameters.meson_masses_gev, parameters.baryon_masses_gev))
    if not np.isfinite(w) or not threshold <= w <= 1.70:
        raise ValueError("W outside reduced real-axis domain")
    return w


def wt_kernel(
    w_gev: float, parameters: ReducedTParameters, coefficients: NDArray[np.float64],
) -> NDArray[np.float64]:
    """P65 Eq. (5) Weinberg-Tomozawa s-wave kernel, in GeV^-1."""
    w = validated_energy(w_gev, parameters)
    meson = np.asarray(parameters.meson_masses_gev)
    baryon = np.asarray(parameters.baryon_masses_gev)
    f = np.asarray(parameters.decay_constants_gev)
    energy = (w*w + baryon*baryon - meson*meson) / (2*w)
    norm = np.sqrt((baryon + energy) / (2*baryon))
    return (-coefficients * (2*w - baryon[:, None] - baryon[None, :])
            * norm[:, None] * norm[None, :]
            / (4*f[:, None]*f[None, :]))


def loop_functions(w_gev: float, parameters: ReducedTParameters) -> NDArray[np.complex128]:
    """P65 Eq. (6) physical-sheet meson-baryon loops, in GeV."""
    w = validated_energy(w_gev, parameters)
    s = w*w
    meson = np.asarray(parameters.meson_masses_gev)
    baryon = np.asarray(parameters.baryon_masses_gev)
    subtraction = np.asarray(parameters.subtraction_constants)
    delta = baryon*baryon - meson*meson
    q = np.sqrt(((s-(baryon+meson)**2)*(s-(baryon-meson)**2)).astype(complex))/(2*w)
    logs = (np.log(s-delta+2*w*q) + np.log(s+delta+2*w*q)
            - np.log(-s+delta+2*w*q) - np.log(-s-delta+2*w*q))
    return (2*baryon/(4*np.pi)**2 *
            (subtraction + np.log(meson*meson/parameters.mu_gev**2)
             + (delta+s)/(2*s)*np.log(baryon*baryon/(meson*meson))
             + q/w*logs)).astype(np.complex128)


def reduced_tmatrix(
    w_gev: float, parameters: ReducedTParameters, coefficients: NDArray[np.float64],
) -> NDArray[np.complex128]:
    """Solve (I - VG)T = V for the reduced on-shell strong amplitude."""
    v = wt_kernel(w_gev, parameters, coefficients)
    g = loop_functions(w_gev, parameters)
    size = len(parameters.meson_masses_gev)
    system = np.eye(size, dtype=complex)-v*g[None, :]
    try:
        condition = np.linalg.cond(system)
        # Above 1e12, double-precision roundoff can be amplified to ~1e-4.
        if not np.isfinite(condition) or condition > 1e12:
            raise ValueError("reduced T linear system is ill-conditioned")
        t = np.linalg.solve(system, v)
    except np.linalg.LinAlgError as exc:
        raise ValueError("reduced T linear solve is singular") from exc
    if not np.all(np.isfinite(t)):
        raise ValueError("reduced T is nonfinite")
    return np.asarray(t, dtype=np.complex128)
