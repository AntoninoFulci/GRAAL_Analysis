"""Diagnostic angular factorization of the complete p_eta-bin amplitude.

At fixed W and M(eta p), six non-tree families depend only on the pion.
Contact is constant; four families are linear in its spatial direction;
external emission is linear after removing its explicit nucleon recoil
factor. Three Cartesian anchors therefore determine these families without
fitting or mass interpolation. The tree is always evaluated directly.
This identity applies to the implemented kernels, not an arbitrary model.
"""
from __future__ import annotations

import numpy as np

from graal_theory import phase_space
from graal_theory.constants import GEV2_TO_MICROBARN
from graal_theory.figure4_integration import project_azimuth_averaged_moments
from graal_theory.kinematics import invariant_mass
from graal_theory.models.eta_pi0_p_full import FAMILY_NAMES
from graal_theory.phase_space import SobolConfig, ThreeBodySample


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


def integrate_bin(model, energy, mass, *, energy_order, mass_order, angular_orders):
    """Diagnostic p_eta tensor quadrature; expensive anchors reused across angles.

    The integration uses ds_pair and normalized dc/2, dt/2 measures. Both
    azimuths have already been integrated, so no additional 2*pi factors
    belong here. This result has no convergence certification status.
    """
    if (len(energy) != 2 or len(mass) != 2 or not np.isfinite((*energy,*mass)).all()
            or not 0 < energy[0] < energy[1] or not 0 < mass[0] < mass[1]):
        raise ValueError("finite increasing energy and mass ranges required")
    if mass[1] > 1.80:
        raise ValueError("diagnostic requires M(eta p) <= 1.80 GeV")
    orders = (energy_order,mass_order,*angular_orders)
    if not angular_orders or any(type(n) is not int or n < 2 for n in orders):
        raise ValueError("quadrature orders must be integers >= 2")
    mp = model.parameters.proton_mass_gev
    mpi, threshold = model.masses[1],model.masses[0]+model.masses[2]
    mass_low = max(mass[0],threshold)
    energy_low = max(energy[0],((mass_low+mpi)**2-mp*mp)/(2*mp))
    if energy_low >= energy[1]:
        raise ValueError("no accessible energy-mass intersection")
    en, ew = np.polynomial.legendre.leggauss(energy_order)
    en = (energy_low+energy[1])/2+(energy[1]-energy_low)*en/2
    ew = ew*(energy[1]-energy_low)/(2*(energy[1]-energy[0]))
    mn, mw = np.polynomial.legendre.leggauss(mass_order)
    angular = {}
    for order in angular_orders:
        nodes, weights = np.polynomial.legendre.leggauss(order)
        polar, helicity = np.meshgrid(nodes,nodes,indexing="ij")
        polar = polar.ravel()
        directions = np.column_stack((np.sqrt(1-polar*polar),np.zeros_like(polar),polar))
        angular[order] = (directions,helicity.ravel(),np.outer(weights,weights).ravel()/4)
    totals = {order:np.zeros(2) for order in angular_orders}
    for e, eweight in zip(en,ew):
        s = mp*mp+2*mp*e
        w = np.sqrt(s)
        low, high = mass_low**2,min(mass[1],w-mpi)**2
        if high <= low:
            raise ValueError("empty mass interval at active energy node")
        full_span = (w-mpi)**2-threshold**2
        flux = GEV2_TO_MICROBARN*4*mp*mp/(2*(s-mp*mp))
        for x, mweight in zip(mn,mw):
            z = np.sqrt((low+high+(high-low)*x)/2)
            anchors = fixed_mass_sample(w,model.masses,z,np.eye(3),.2,.4)
            basis = [model.family_amplitudes(anchors,np.array(epsilon))
                     for epsilon in ([0.,1.,0.],[1.,0.,0.])]
            for order,(directions,chi,aweight) in angular.items():
                sample = fixed_mass_sample(w,model.masses,z,directions,chi,0.)
                amplitudes = []
                for family,epsilon in zip(basis,([0.,1.,0.],[1.,0.,0.])):
                    rebuilt = reconstruct_families(anchors,family,sample,mp)
                    tree = model.selected_amplitude(sample,np.array(epsilon),("eq43_tree",))
                    amplitudes.append(np.add.reduce((*rebuilt.values(),tree)))
                pair = sample.momenta[:,0]+sample.momenta[:,2]
                phi = np.arctan2(pair[:,2],pair[:,1])
                measure = eweight*flux*mweight*(high-low)/2*aweight*sample.weights_gev2/full_span
                totals[order] += project_azimuth_averaged_moments(phi,*amplitudes,measure)
    rows = []
    for order,(numerator,denominator) in totals.items():
        if not np.isfinite([numerator,denominator]).all() or denominator <= 0:
            raise ValueError("nonfinite or nonpositive reduced bin moment")
        rows.append(dict(energy_order=energy_order,mass_order=mass_order,angular_order=order,
                         numerator=float(numerator),denominator=float(denominator),
                         sigma=float(numerator/denominator)))
    return rows
