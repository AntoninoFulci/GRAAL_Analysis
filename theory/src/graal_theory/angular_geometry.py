"""Exact fixed-p_eta geometry and angular reconstruction for three projections.

Packaged owner derived from the frozen October 19 diagnostics. The old
scripts remain unchanged for archived source-fingerprint verification.
"""
from __future__ import annotations

import numpy as np

from . import phase_space
from .figure4_integration import PAIR_DAUGHTERS
from .kinematics import invariant_mass, kallen
from .models.eta_pi0_p_full import FAMILY_NAMES
from .phase_space import SobolConfig, ThreeBodySample

def fixed_mass_sample(sqrt_s, masses, mass, directions, helicity_cos=0., helicity_phi=0.):
    """Physical p_eta samples; weights include the full accessible ds span."""
    direction = np.asarray(directions, dtype=float)
    if (direction.ndim != 2 or direction.shape[1] != 3 or not len(direction)
            or not np.isfinite(direction).all()
            or not np.allclose(np.linalg.norm(direction, axis=1), 1., rtol=0, atol=1e-12)):
        raise ValueError("pion directions must be finite unit vectors")
    lower, upper = (masses[0]+masses[2])**2, (sqrt_s-masses[1])**2
    if not np.isfinite(mass) or not masses[0]+masses[2] < mass < sqrt_s-masses[1]:
        raise ValueError("fixed invariant mass must lie inside open phase space")
    chi, phi = np.broadcast_arrays(np.asarray(helicity_cos, float),
                                   np.asarray(helicity_phi, float), np.zeros(len(direction)))[:2]
    if not np.isfinite(chi).all() or not np.isfinite(phi).all() or np.any(abs(chi) > 1):
        raise ValueError("invalid helicity angles")
    azimuth = np.arctan2(direction[:, 1], direction[:, 0])
    c, s = direction[:, 2], np.linalg.norm(direction[:, :2], axis=1)
    e_theta = np.column_stack((c*np.cos(azimuth), c*np.sin(azimuth), -s))
    e_phi = np.column_stack((-np.sin(azimuth), np.cos(azimuth), np.zeros(len(c))))
    rest = chi[:, None]*direction+np.sqrt(np.maximum(1-chi*chi, 0.))[:, None]*(
        np.cos(phi)[:, None]*e_theta+np.sin(phi)[:, None]*e_phi)
    points = np.column_stack((np.full(len(c), (mass*mass-lower)/(upper-lower)),
        (c+1)/2, np.mod(azimuth, 2*np.pi)/(2*np.pi),
        (np.clip(rest[:, 2], -1., 1.)+1)/2,
        np.mod(np.arctan2(rest[:, 1], rest[:, 0]), 2*np.pi)/(2*np.pi)))
    ordered = phase_space._sample_ordered(sqrt_s, (masses[2], masses[0], masses[1]),
        SobolConfig(4), points, lower, upper)
    momenta = ordered.momenta[:, [1, 2, 0], :].copy()
    return ThreeBodySample(ordered.initial, momenta, ordered.weights_gev2, masses,
        invariant_mass(momenta[:, 0]+momenta[:, 1])**2, ordered.config)


def _external_recoil(sample, proton_mass):
    w = sample.initial[:, 0]
    k = (w*w-proton_mass**2)/(2*w)
    pion = sample.momenta[:, 1]
    shifted = pion[:, 1:].copy()
    shifted[:, 2] += k
    eout = np.sqrt(proton_mass**2+np.sum(shifted**2, axis=1))
    denominator = np.sqrt(proton_mass**2+k*k)-pion[:, 0]-eout
    if np.any(abs(denominator) <= 32*np.finfo(float).eps*np.maximum(eout, pion[:,0])):
        raise ValueError("singular external nucleon denominator")
    return 1/(eout*denominator)


def reconstruct_families(anchors, families, sample, proton_mass):
    """Reconstruct six whole families from Cartesian anchors at identical W,z."""
    ap, p = anchors.momenta[:, 1, 1:], sample.momenta[:, 1, 1:]
    if ap.shape != (3, 3) or not np.allclose(ap/np.linalg.norm(ap, axis=1)[:,None],
                                           np.eye(3), rtol=0, atol=1e-12):
        raise ValueError("anchors require ordered positive Cartesian pion directions")
    az = invariant_mass(anchors.momenta[:, 0]+anchors.momenta[:, 2])
    z = invariant_mass(sample.momenta[:, 0]+sample.momenta[:, 2])
    if (not np.allclose(anchors.initial[:,0], sample.initial[0,0], rtol=0, atol=1e-12)
            or not np.allclose(sample.initial[:,0], sample.initial[0,0], rtol=0, atol=1e-12)
            or not np.allclose(az, z[0], rtol=0, atol=1e-12)
            or not np.allclose(z, z[0], rtol=0, atol=1e-12)
            or not np.allclose(anchors.masses, sample.masses, rtol=0, atol=1e-12)):
        raise ValueError("angular reconstruction requires identical energy and invariant mass")
    if set(families) != set(FAMILY_NAMES):
        raise ValueError("anchors require all seven complete families")
    direction = p/np.linalg.norm(p, axis=1)[:, None]
    result = {}
    for name in FAMILY_NAMES[:-1]:
        matrix = np.asarray(families[name], dtype=complex)
        if matrix.shape != (3, 2, 2) or not np.isfinite(matrix).all():
            raise ValueError("invalid anchor matrices")
        if name == "chiral_contact":
            if not np.allclose(matrix, matrix[0], rtol=1e-10, atol=1e-12):
                raise ValueError("contact anchors violate angular independence")
            value = np.broadcast_to(matrix[0], (len(p), 2, 2)).copy()
        else:
            if name == "external_pi0":
                matrix = matrix/_external_recoil(anchors, proton_mass)[:,None,None]
            value = np.einsum("ni,ijk->njk", direction, matrix)
            if name == "external_pi0":
                value *= _external_recoil(sample, proton_mass)[:,None,None]
        if not np.isfinite(value).all():
            raise ValueError("nonfinite reconstructed family")
        result[name] = value
    return result


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


def spectator_cone(w, masses, z, t, pair):
    """CM cone of the selected pair's spectator around the pion axis."""
    if pair not in PAIR_DAUGHTERS:
        raise ValueError(f"unknown pair: {pair}")
    meta, mpi, mp = masses
    q = np.sqrt(max(0., kallen(z*z, mp*mp, meta*meta)))/(2*z)
    pion_p = np.sqrt(max(0., kallen(w*w, z*z, mpi*mpi)))/(2*w)
    if pair == "p_eta":
        return -pion_p, np.zeros_like(np.asarray(t, float))
    spectator = mp if pair == "eta_pi0" else meta
    other = meta if pair == "eta_pi0" else mp
    energy = (z*z+spectator*spectator-other*other)/(2*z)
    pair_e = (w*w+z*z-mpi*mpi)/(2*w)
    helicity = np.asarray(t) if pair == "eta_pi0" else -np.asarray(t)
    return ((pair_e*q*helicity-pion_p*energy)/z,
            q*np.sqrt(np.maximum(0., 1-np.asarray(t)**2)))


def helicity_window(w, masses, z, pair, target):
    """Proton helicity range inside the requested pair-mass window."""
    if pair not in PAIR_DAUGHTERS:
        raise ValueError(f"unknown pair: {pair}")
    if pair == "p_eta":
        return (-1., 1.) if target[0] <= z <= target[1] else (1., -1.)
    meta, mpi, mp = masses
    s = z*z
    ep = (s+mp*mp-meta*meta)/(2*z)
    epi = (w*w-s-mpi*mpi)/(2*z)
    intercept = mp*mp+mpi*mpi+2*ep*epi
    slope = np.sqrt(max(0., kallen(s, mp*mp, meta*meta))
                    *max(0., kallen(w*w, s, mpi*mpi)))/(2*s)
    if pair == "eta_pi0":
        offset = w*w+sum(m*m for m in masses)-s-intercept
        low, high = target[0]**2-offset, target[1]**2-offset
    else:
        offset = intercept
        low, high = offset-target[1]**2, offset-target[0]**2
    if slope == 0:
        return (-1., 1.) if target[0]**2 <= offset <= target[1]**2 else (1., -1.)
    return max(-1., low/slope), min(1., high/slope)


def mass_segments(w, masses, pair, target, thresholds=()):
    """Fixed-p_eta mass segments with exact Dalitz-edge and channel splits."""
    if pair not in PAIR_DAUGHTERS:
        raise ValueError(f"unknown pair: {pair}")
    meta, mpi, mp = masses
    low, high = meta+mp, w-mpi
    if pair == "p_eta":
        low, high = max(low, target[0]), min(high, target[1])
        if high <= low:
            return []
        knots = [low, high, *(v for v in thresholds if low < v < high)]
    else:
        shared, spectator = (meta, mp) if pair == "eta_pi0" else (mp, meta)
        if high <= low or min(target[1], w-spectator) <= max(target[0], shared+mpi):
            return []
        knots = [low, high, *(v for v in thresholds if low < v < high)]
        for edge in target:
            if not shared+mpi < edge < w-spectator:
                continue
            y = edge*edge
            center = shared*shared+spectator*spectator+(
                y+shared*shared-mpi*mpi)*(w*w-y-spectator*spectator)/(2*y)
            half = np.sqrt(max(0., kallen(y, shared*shared, mpi*mpi))
                           *max(0., kallen(w*w, y, spectator*spectator)))/(2*y)
            knots.extend(np.sqrt(np.clip([center-half, center+half], low*low, high*high)))
    unique = []
    for value in sorted(knots):
        if not unique or value-unique[-1] > 32*np.finfo(float).eps*max(1., abs(value)):
            unique.append(float(value))
    result = []
    for a,b in zip(unique[:-1], unique[1:]):
        lo,hi = helicity_window(w, masses, (a+b)/2, pair, target)
        if hi > lo:
            result.append((a,b))
    return result


def angular_rule(w, masses, z, pair, target, order):
    """Normalized dt/2 dc/2 rule and exact internal-azimuth cosine mean."""
    nodes, weights = np.polynomial.legendre.leggauss(order)
    low, high = helicity_window(w, masses, z, pair, target)
    if high <= low:
        raise ValueError("empty helicity interval at active mass node")
    polar, helicity, measure, cosine = [], [], [], []
    for t,tw in zip((low+high)/2+(high-low)*nodes/2, weights*(high-low)/4):
        a,b = spectator_cone(w, masses, z, t, pair)
        r = abs(a)/np.hypot(a,b)
        for left,right in zip((-1., -r, r), (-r, r, 1.)):
            if right <= left:
                continue
            c = (left+right)/2+(right-left)*nodes/2
            polar.extend(c)
            helicity.extend(np.full(order,t))
            measure.extend(tw*weights*(right-left)/4)
            cosine.extend(azimuth_cosine(a,b,c))
    c = np.asarray(polar)
    directions = np.column_stack((np.sqrt(1-c*c),np.zeros_like(c),c))
    return directions, np.asarray(helicity), np.asarray(measure), np.asarray(cosine)
