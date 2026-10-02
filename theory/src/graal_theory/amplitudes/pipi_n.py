"""P65 pi pi N vertices (GeV^-3) and absorptive three-body loop (GeV^5).

Inoue, Oset, Vicente Vacas, Phys. Rev. C 65, 035204 (2002),
Eqs. (26), (29), and (30). The final fit sets the loop's real part to zero.
This is not the meson-baryon two-body loop of P65 Eq. (6).
"""

from __future__ import annotations

import numpy as np


def _finite_positive(value: float, name: str) -> float:
    if (isinstance(value, (bool, np.bool_))
            or not isinstance(value, (int, float, np.integer, np.floating))):
        raise ValueError(f"{name} must be a finite positive real scalar")
    result = float(value)
    if not np.isfinite(result) or result <= 0:
        raise ValueError(f"{name} must be a finite positive real scalar")
    return result


def pipi_n_potentials(w_gev: float, pion_mass_gev: float) -> tuple[float, float]:
    """Return the real v11 and v31 polynomials of P65 Eqs. (29)-(30)."""
    w = _finite_positive(w_gev, "W")
    m = _finite_positive(pion_mass_gev, "m_pi")
    x = (w - 1.470) / m
    v11 = (4.0 + (w - 1.213) / m) / m**3
    v31 = (-5.60*x - 1.05*x**2 + 1.77*x**3 + 0.66*x**4
           - 0.17*x**5 - 0.07*x**6) / m**3
    return v11, v31


def _roundoff_nonnegative(values, scales):
    """Clip negative roundoff only, rejecting an unphysical mapped domain."""
    tolerance = 32 * np.finfo(float).eps * scales
    if np.any(values < -tolerance):
        raise ValueError("unphysical pi pi N integration domain")
    return np.maximum(values, 0.0)


def _loop_at_order(w: float, m: float, nucleon: float, order: int) -> float:
    """Integrate Eq. (26) on physical pion energies; inputs share one unit.

    For each first-pion energy, boost the on-shell pi N pair's pion energy
    interval into the total rest frame. Both Gauss-Legendre mappings carry
    their interval Jacobians. This private primitive assumes W > M + 2m.
    """
    nodes, weights = np.polynomial.legendre.leggauss(order)
    e1_max = (w*w + m*m - (nucleon+m)**2) / (2*w)
    scale = (e1_max-m)/2
    e1 = m + scale*(nodes+1)
    q1_sq = _roundoff_nonnegative(e1*e1-m*m, e1*e1+m*m)
    q1 = np.sqrt(q1_sq)
    s23 = w*w + m*m - 2*w*e1
    root = np.sqrt(s23)
    lam = (s23-(nucleon+m)**2)*(s23-(nucleon-m)**2)
    lam_scale = (np.abs(s23)+(nucleon+m)**2) * (
        np.abs(s23)+(nucleon-m)**2
    )
    q2_star = np.sqrt(_roundoff_nonnegative(lam, lam_scale))/(2*root)
    e2_star = (s23+m*m-nucleon*nucleon)/(2*root)
    center = (w-e1)*e2_star/root
    half_width = q1*q2_star/root
    e2 = center[:, None] + half_width[:, None]*nodes[None, :]
    q2_sq = _roundoff_nonnegative(e2*e2-m*m, e2*e2+m*m)
    e_nucleon = w-e1[:, None]-e2
    positive_terms = nucleon*nucleon + 2*q1_sq[:, None] + 2*q2_sq
    b = _roundoff_nonnegative(positive_terms-e_nucleon**2,
                             positive_terms+e_nucleon**2)
    integral = scale*np.sum(weights[:, None]*weights[None, :]
                            *half_width[:, None]*b)
    return float(-nucleon*integral/(4*(2*np.pi)**3))


def pipi_n_loop(w_gev: float, pion_mass_gev: float,
                nucleon_mass_gev: float) -> complex:
    """Return the pure imaginary P65 Eq. (26) loop in GeV^5, W <= 1.70 GeV.

    All inputs are positive real scalars in GeV. At and below the physical
    M_N + 2m_pi threshold the loop vanishes exactly. Above it, the 96-point
    rule must agree with the 48-point rule to max(1e-12, 1e-3 |G96|) GeV^5.
    """
    w = _finite_positive(w_gev, "W")
    m = _finite_positive(pion_mass_gev, "m_pi")
    nucleon = _finite_positive(nucleon_mass_gev, "M_N")
    if w > 1.70:
        raise ValueError("W outside pi pi N real-axis domain")
    if w <= nucleon + 2*m:
        return 0j
    low = _loop_at_order(w, m, nucleon, 48)
    high = _loop_at_order(w, m, nucleon, 96)
    if abs(high - low) > max(1e-12, 1e-3*abs(high)):
        raise ValueError("pi pi N loop quadrature did not converge")
    return complex(0.0, high)
