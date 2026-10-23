"""P65 Eq. (12)–(13) vector-propagator angular correction."""

import numpy as np


def angular_factor(
    w_gev: float,
    meson_i_gev: float,
    baryon_i_gev: float,
    meson_j_gev: float,
    baryon_j_gev: float,
    vector_mass_gev: float,
) -> float:
    """Return m_v²/2 ∫[-1,1] dz/(A-Bz), with all inputs in GeV.

    The even dependence on B allows real continuation when one channel
    is closed, without selecting or clipping complex momenta. Singular
    propagators and nonfinite kinematics raise ValueError.
    """
    values = (w_gev, meson_i_gev, baryon_i_gev, meson_j_gev,
              baryon_j_gev, vector_mass_gev)
    if any(isinstance(value, (bool, np.bool_))
           or not isinstance(value, (int, float, np.integer, np.floating))
           for value in values):
        raise ValueError("VMD inputs must be finite positive real scalars")
    try:
        scalars = np.asarray(tuple(map(float, values)))
    except (ValueError, OverflowError):
        raise ValueError("VMD inputs must be finite positive real scalars") from None
    if not np.all(np.isfinite(scalars)) or np.any(scalars <= 0):
        raise ValueError("VMD inputs must be finite positive real scalars")

    w, mi, Mi, mj, Mj, mv = scalars
    # Extreme finite inputs may overflow or underflow; reject the resulting
    # intermediates explicitly rather than emitting warnings or returning NaN.
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        ei = (w*w + mi*mi - Mi*Mi)/(2*w)
        ej = (w*w + mj*mj - Mj*Mj)/(2*w)
        qi2, qj2 = ei*ei-mi*mi, ej*ej-mj*mj
        a = mv*mv-mi*mi-mj*mj+2*ei*ej
        b2 = 4*qi2*qj2
        if a <= 0 or not np.all(np.isfinite((ei, ej, qi2, qj2, a, b2))):
            raise ValueError("vector propagator singular or nonfinite")
        x2 = b2/(a*a)
        if x2 >= 1 or not np.isfinite(x2) or not np.isfinite(a*a):
            raise ValueError("vector propagator singular or nonfinite")
        if abs(x2) < 1e-8:
            ratio = 1 + x2/3 + x2*x2/5
        elif x2 > 0:
            x = np.sqrt(x2)
            ratio = np.arctanh(x)/x
        else:
            x = np.sqrt(-x2)
            ratio = np.arctan(x)/x
        factor = mv*mv/a * ratio
    if not np.isfinite(factor):
        raise ValueError("vector propagator returned nonfinite factor")
    return float(factor)
