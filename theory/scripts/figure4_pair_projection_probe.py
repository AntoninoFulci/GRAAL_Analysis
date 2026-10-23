"""Diagnostic eta-pion projection using exact angular-family reconstruction.

The internal azimuth is integrated analytically, including the selected
pair's double-angle weight. The pion polar rule is split at its two cusps.
Mass rules use exact Dalitz-boundary knots and strong-channel thresholds.
This probe does not assign production convergence certificates.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np

from graal_theory.constants import GEV2_TO_MICROBARN
from graal_theory.kinematics import kallen

_spec = importlib.util.spec_from_file_location(
    "angular_reduction", Path(__file__).with_name("figure4_angular_reduction_probe.py"))
angular = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(angular)


def azimuth_cosine(a, b, c):
    """Mean cos(2 phi_proton) on the boosted proton cone, pion phi=0.

    At an identically zero transverse vector use zero (axis convention).
    The zero three-vector has no cone and is rejected. Quadrature nodes
    are interior, so neither axis convention contributes finite measure.
    """
    a, b, c = np.broadcast_arrays(np.asarray(a, float), np.asarray(b, float),
                                 np.asarray(c, float))
    radius = np.hypot(a, b)
    if (not np.isfinite([a, b, c]).all() or np.any(b < 0)
            or np.any(abs(c) > 1) or np.any(radius == 0)):
        raise ValueError("invalid proton cone or pion polar cosine")
    ratio = abs(a)/radius
    one_minus_ratio = (b/radius)*(b/(radius+abs(a)))
    outer = abs(c) >= ratio
    result = -(1-abs(c))/(1+abs(c))
    inner = np.zeros_like(result)
    np.divide(2*one_minus_ratio, 1-c*c, out=inner, where=~outer)
    return np.where(outer, result, 1-inner)


def proton_cone(w, masses, z, t):
    """Longitudinal/transverse CM proton momentum relative to pion axis."""
    meta, mpi, mp = masses
    q = np.sqrt(max(0., kallen(z*z, mp*mp, meta*meta)))/(2*z)
    ep = (z*z+mp*mp-meta*meta)/(2*z)
    pion_p = np.sqrt(max(0., kallen(w*w, z*z, mpi*mpi)))/(2*w)
    pair_e = (w*w+z*z-mpi*mpi)/(2*w)
    a = (pair_e*q*np.asarray(t)-pion_p*ep)/z
    b = q*np.sqrt(np.maximum(0., 1-np.asarray(t)**2))
    return a, b


def helicity_window(w, masses, z, target):
    """Clip proton helicity cosine using M(eta pi)^2 = offset + slope*t."""
    meta, mpi, mp = masses
    s = z*z
    ep = (s+mp*mp-meta*meta)/(2*z)
    epi = (w*w-s-mpi*mpi)/(2*z)
    intercept = mp*mp+mpi*mpi+2*ep*epi
    slope = np.sqrt(max(0., kallen(s, mp*mp, meta*meta))
                    *max(0., kallen(w*w, s, mpi*mpi)))/(2*s)
    offset = w*w+sum(m*m for m in masses)-s-intercept
    if slope == 0:
        return (-1., 1.) if target[0]**2 <= offset <= target[1]**2 else (1., -1.)
    return max(-1., (target[0]**2-offset)/slope), min(1., (target[1]**2-offset)/slope)


def mass_segments(w, masses, target_mass_range, thresholds=()):
    """Open p_eta intervals where eta-pion helicity bounds have fixed branches."""
    meta, mpi, mp = masses
    low, high = meta+mp, w-mpi
    if high <= low or min(target_mass_range[1], w-mp) <= max(target_mass_range[0], meta+mpi):
        return []
    knots = [low, high, *(v for v in thresholds if low < v < high)]
    for edge in target_mass_range:
        if not meta+mpi < edge < w-mp:
            continue
        y = edge*edge
        center = meta*meta+mp*mp+(y+meta*meta-mpi*mpi)*(w*w-y-mp*mp)/(2*y)
        half = np.sqrt(max(0., kallen(y, meta*meta, mpi*mpi))
                       *max(0., kallen(w*w, y, mp*mp)))/(2*y)
        knots.extend(np.sqrt(np.clip([center-half, center+half], low*low, high*high)))
    unique = []
    for value in sorted(knots):
        if not unique or value-unique[-1] > 32*np.finfo(float).eps*max(1., abs(value)):
            unique.append(float(value))
    segments = []
    for a, b in zip(unique[:-1], unique[1:]):
        tlo, thi = helicity_window(w, masses, (a+b)/2, target_mass_range)
        if thi > tlo:
            segments.append((a, b))
    return segments


def _angular_rule(w, masses, z, target, order):
    """Normalized dt/2 dc/2 rule, with polar splits at the azimuth cusps."""
    nodes, weights = np.polynomial.legendre.leggauss(order)
    low, high = helicity_window(w, masses, z, target)
    if high <= low:
        raise ValueError("empty helicity interval at active mass node")
    polar, helicity, measure, cosine = [], [], [], []
    for t, tw in zip((low+high)/2+(high-low)*nodes/2, weights*(high-low)/4):
        a, b = proton_cone(w, masses, z, t)
        r = abs(a)/np.hypot(a, b)
        for left, right in zip((-1., -r, r), (-r, r, 1.)):
            if right <= left:
                continue
            c = (left+right)/2+(right-left)*nodes/2
            polar.extend(c)
            helicity.extend(np.full(order, t))
            measure.extend(tw*weights*(right-left)/4)
            cosine.extend(azimuth_cosine(a, b, c))
    c = np.asarray(polar)
    directions = np.column_stack((np.sqrt(1-c*c), np.zeros_like(c), c))
    return directions, np.asarray(helicity), np.asarray(measure), np.asarray(cosine)


def integrate_eta_pi0(model, energy, mass, *, energy_order, mass_order, angular_orders):
    """Integrate raw N,D with coherent families and uniform incident energy.

    Each mass segment uses s=lo+(hi-lo)sin²(pi(x+1)/4), including its exact
    Jacobian. This smooths kinematic square roots at segment endpoints.
    Both azimuths and their normalized measures are already integrated.
    """
    if (len(energy) != 2 or len(mass) != 2 or not np.isfinite((*energy, *mass)).all()
            or not 0 < energy[0] < energy[1] or not 0 < mass[0] < mass[1]):
        raise ValueError("finite increasing energy and mass ranges required")
    if not angular_orders or any(type(n) is not int or n < 2
                                for n in (energy_order, mass_order, *angular_orders)):
        raise ValueError("quadrature orders must be integers >= 2")
    meta, mpi, mp = model.masses
    if mp != model.parameters.proton_mass_gev:
        raise ValueError("inconsistent proton masses")
    onset = lambda edge: ((edge+mp)**2-mp*mp)/(2*mp)
    energy_low = max(energy[0], onset(max(mass[0], meta+mpi)))
    if energy_low >= energy[1]:
        raise ValueError("no accessible energy-mass intersection")
    # Check full upper-energy support, not merely interior quadrature nodes.
    support = mass_segments(np.sqrt(mp*mp+2*mp*energy[1]), model.masses, mass)
    if any(hi > 1.80 for _, hi in support):
        raise ValueError("diagnostic requires M(eta p) <= 1.80 GeV throughout support")
    strong = model.parameters.strong
    thresholds = np.asarray(strong.meson_masses_gev)+np.asarray(strong.baryon_masses_gev)
    energy_knots = [energy_low, energy[1]]
    if energy_low < onset(mass[1]) < energy[1]:
        energy_knots.insert(1, onset(mass[1]))
    en, ew = np.polynomial.legendre.leggauss(energy_order)
    mn, mw = np.polynomial.legendre.leggauss(mass_order)
    theta = np.pi*(mn+1)/4
    totals = {order:np.zeros(2) for order in angular_orders}
    count = 0
    for elo, ehi in zip(energy_knots[:-1], energy_knots[1:]):
        for e, eweight in zip((elo+ehi)/2+(ehi-elo)*en/2,
                             ew*(ehi-elo)/(2*(energy[1]-energy[0]))):
            s = mp*mp+2*mp*e
            w = np.sqrt(s)
            full_span = (w-mpi)**2-(meta+mp)**2
            flux = GEV2_TO_MICROBARN*4*mp*mp/(2*(s-mp*mp))
            for zlo, zhi in mass_segments(w, model.masses, mass, thresholds):
                if zhi > 1.80:
                    raise ValueError("diagnostic requires M(eta p) <= 1.80 GeV throughout support")
                lo, hi = zlo*zlo, zhi*zhi
                for z, mweight in zip(np.sqrt(lo+(hi-lo)*np.sin(theta)**2),
                                      mw*(hi-lo)*np.pi/4*np.sin(2*theta)):
                    anchors = angular.fixed_mass_sample(w, model.masses, z, np.eye(3), .2, .4)
                    basis = [model.family_amplitudes(anchors, np.array(epsilon))
                             for epsilon in ([0., 1., 0.], [1., 0., 0.])]
                    count += 1
                    for order in totals:
                        directions, t, aweight, cosine = _angular_rule(w, model.masses, z, mass, order)
                        sample = angular.fixed_mass_sample(w, model.masses, z, directions, t, 0.)
                        intensities = []
                        for family, epsilon in zip(basis, ([0., 1., 0.], [1., 0., 0.])):
                            rebuilt = angular.reconstruct_families(anchors, family, sample, mp)
                            tree = model.selected_amplitude(sample, np.array(epsilon), ("eq43_tree",))
                            amplitude = np.add.reduce((*rebuilt.values(), tree))
                            intensities.append(np.sum(abs(amplitude)**2, axis=(1, 2))/2)
                        v, h = intensities
                        measure = eweight*flux*mweight*aweight*sample.weights_gev2/full_span
                        totals[order] += [np.sum((v-h)*cosine*measure), np.sum((v+h)*measure)]
    rows = []
    for order, (numerator, denominator) in totals.items():
        if not np.isfinite([numerator, denominator]).all() or denominator <= 0:
            raise ValueError("nonfinite or nonpositive reduced bin moment")
        rows.append(dict(energy_order=energy_order, mass_order=mass_order, angular_order=order,
                         anchor_nodes=count, numerator=float(numerator), denominator=float(denominator),
                         sigma=float(numerator/denominator)))
    return rows
