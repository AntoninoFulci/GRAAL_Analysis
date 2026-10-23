"""Diagnostic delta-helicity proposal; production phase space stays unchanged.

At fixed sampled pair mass, use the first daughter's angle relative to the
spectator in the pair rest frame. Rotation of this sphere preserves dOmega.
The secondary p-pi0 invariant is A +/- B*cos(chi). Draw that invariant from
a truncated Cauchy with center m_Delta^2 and scale m_Delta*Gamma_Delta, then
multiply by (ds/du)/(s_max-s_min). When p-pi0 is the sampled pair, apply the
same proposal to the primary invariant instead. This density is a sampling
proposal only; the physical amplitude retains its sourced running widths.
"""
from __future__ import annotations

import numpy as np
from scipy.stats import qmc

from graal_theory import phase_space
from graal_theory.kinematics import invariant_mass, kallen, validate_final_state
from graal_theory.phase_space import ThreeBodySample


COORDINATES = ("primary_mass_quantile", "spectator_cos_theta_quantile",
               "helicity_or_secondary_mass_quantile", "helicity_azimuth_quantile")


def _cauchy_fraction(u, lower, upper, center, scale):
    """Return normalized displacement without subtracting nearby invariants."""
    u, lower, upper, center, scale = np.broadcast_arrays(
        *[np.asarray(v, dtype=float) for v in (u, lower, upper, center, scale)])
    if (any(not np.isfinite(v).all() for v in (u, lower, upper, center, scale))
            or np.any((u < 0) | (u > 1)) or np.any(upper < lower) or np.any(scale <= 0)):
        raise ValueError("Cauchy proposal requires finite bounds, unit quantiles and positive scale")
    width = upper-lower
    angle_low = np.arctan2(lower-center, scale)
    # atan2 difference avoids cancellation for a nearly collapsed interval.
    angle_span = np.arctan2(scale*width, scale**2+(lower-center)*(upper-center))
    angle = angle_low+u*angle_span
    # Stable form of (tan(angle)-tan(low))/(tan(high)-tan(low)).
    fraction = np.divide(np.sin(u*angle_span)*np.cos(angle_low+angle_span),
                         np.sin(angle_span)*np.cos(angle),
                         out=u.copy(), where=width > 0)
    fraction = np.where(u == 0, 0., np.where(u == 1, 1., fraction))
    if not np.isfinite(fraction).all() or np.any((fraction < -1e-12) | (fraction > 1+1e-12)):
        raise ValueError("Cauchy quantile escaped its physical interval")
    jacobian = np.divide(scale*angle_span, width*np.cos(angle)**2,
                         out=np.ones_like(width), where=width > 0)
    return np.clip(fraction, 0., 1.), jacobian


def cauchy_quantile(u, lower, upper, center, scale):
    """Return truncated quantile and Jacobian relative to a uniform interval."""
    fraction, jacobian = _cauchy_fraction(u, lower, upper, center, scale)
    lower, upper = np.asarray(lower), np.asarray(upper)
    return lower+(upper-lower)*fraction, jacobian


def sample_delta_helicity(sqrt_s, masses, pair, mass_range_gev, config, *,
                          reduce_global_azimuth=False, resonance_mass, resonance_width):
    """Conditional four-coordinate sampler for canonical (eta, pi0, p)."""
    if (not np.isfinite(resonance_mass) or not np.isfinite(resonance_width)
            or resonance_mass <= 0 or resonance_width <= 0):
        raise ValueError("proposal requires positive finite resonance mass and width")
    if not reduce_global_azimuth:
        raise ValueError("delta-helicity proposal requires exact global azimuth reduction")
    baseline = phase_space.sample_three_body_mass_window(sqrt_s, masses, pair,
        mass_range_gev, config, reduce_global_azimuth=True)
    if baseline is None:
        return None
    if any(m <= 0 for m in masses):
        raise ValueError("delta-helicity diagnostic requires massive daughters")
    spectator = next(i for i in range(3) if i not in pair)
    permutation = (*pair, spectator)
    ordered_masses = tuple(masses[i] for i in permutation)
    m1, m2, m3 = ordered_masses
    low = max(mass_range_gev[0], m1+m2)**2
    high = min(mass_range_gev[1], sqrt_s-m3)**2
    raw = qmc.Sobol(4, scramble=config.scramble, seed=config.seed).random_base2(config.power)
    primary = raw[:, 0].copy()
    jacobian = np.ones(len(raw))
    center, scale = resonance_mass**2, resonance_mass*resonance_width
    if set(pair) == {1, 2}:
        primary, jacobian = _cauchy_fraction(primary, low, high, center, scale)
    s12 = low+(high-low)*primary
    cosine = 2*raw[:, 2]-1
    if set(pair) != {1, 2}:
        # The p-pi0 pair contains the spectator and one sampled daughter.
        daughter = next(i for i in pair if i in (1, 2))
        other = next(i for i in pair if i != daughter)
        mr, mo = masses[daughter], masses[other]
        er = (s12+mr**2-mo**2)/(2*np.sqrt(s12))
        e3 = (sqrt_s**2-s12-m3**2)/(2*np.sqrt(s12))
        a = mr**2+m3**2+2*er*e3
        b = np.sqrt(kallen(s12, m1**2, m2**2, atol=1e-12)
                    *kallen(sqrt_s**2, s12, m3**2, atol=1e-12))/(2*s12)
        sign = 1 if daughter == pair[1] else -1
        quantile = raw[:, 2] if sign == 1 else 1-raw[:, 2]
        fraction, angular_jacobian = _cauchy_fraction(quantile, a-b, a+b, center, scale)
        cosine = sign*(2*fraction-1)
        jacobian *= angular_jacobian
    if np.any(np.abs(cosine) > 1+1e-12):
        raise ValueError("helicity cosine escaped physical support")
    cosine = np.clip(cosine, -1., 1.)
    sine = np.sqrt(np.maximum(1-cosine**2, 0.))
    phi = 2*np.pi*raw[:, 3]
    local_x, local_y = sine*np.cos(phi), sine*np.sin(phi)
    spectator_cos = 2*raw[:, 1]-1
    spectator_sin = np.sqrt(np.maximum(1-spectator_cos**2, 0.))
    # R_y(theta_spectator) rotates local z onto the spectator direction.
    global_x = spectator_cos*local_x+spectator_sin*cosine
    global_z = -spectator_sin*local_x+spectator_cos*cosine
    points = np.column_stack((primary, raw[:, 1], np.zeros(len(raw)),
        (np.clip(global_z, -1., 1.)+1)/2,
        np.mod(np.arctan2(local_y, global_x), 2*np.pi)/(2*np.pi)))
    ordered = phase_space._sample_ordered(sqrt_s, ordered_masses, config, points, low, high)
    momenta = ordered.momenta[:, np.argsort(permutation), :].copy()
    validate_final_state(ordered.initial, momenta, masses, atol=1e-12)
    return ThreeBodySample(ordered.initial, momenta, ordered.weights_gev2*jacobian,
        masses, invariant_mass(momenta[:, 0]+momenta[:, 1])**2, config)
