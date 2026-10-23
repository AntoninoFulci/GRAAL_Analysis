"""Exact angular reduction of the physical two-coupling EM basis.

Shared bin driver owns energy support and measured exposure. This backend
owns only fixed-energy integration, retaining all coherent families and
both azimuth harmonics. No quadrature here claims a production certificate.
"""
from functools import lru_cache

import numpy as np

from .angular_geometry import fixed_mass_sample, reconstruct_families, angular_rule, mass_segments
from .beam_asymmetry import _VERTICAL, _HORIZONTAL
from .constants import GEV2_TO_MICROBARN
from .figure4_basis import _NodeMoments, _integrate_basis_bin
from .figure4_integration import PAIR_DAUGHTERS
from .kinematics import invariant_mass
from .models.delta_em_basis import _basis_models, _fingerprint
from .quadratic_moments import QuadraticMoments, cone_averaged_moments, harmonic_state_moments


class AngularBasisIntegrator:
    """Reuse expensive Cartesian family anchors across angular refinements."""

    def __init__(self, model):
        self.model = model
        self.models = _basis_models(model)
        self.anchor = (model.parameters.tree.g1_prime, model.parameters.tree.g2_prime)
        self.fingerprint = _fingerprint(model, self.anchor)
        self._anchors = lru_cache(maxsize=1024)(self._build_anchors)

    def _build_anchors(self, w, z):
        sample = fixed_mass_sample(w, self.model.masses, z, np.eye(3), .2, .4)
        families = tuple(tuple(candidate.family_amplitudes(sample, epsilon)
                               for candidate in self.models)
                         for epsilon in (_VERTICAL, _HORIZONTAL))
        return sample, families

    def event_basis(self, w, z, sample):
        """Complete complex amplitudes at arbitrary polar/helicity nodes."""
        anchors, families = self._anchors(w,z)
        result = []
        for epsilon, polarized_families in zip((_VERTICAL,_HORIZONTAL), families):
            amplitudes = []
            for model, family in zip(self.models, polarized_families):
                rebuilt = reconstruct_families(anchors,family,sample,model.parameters.proton_mass_gev)
                tree = model.selected_amplitude(sample,epsilon,('eq43_tree',))
                amplitudes.append(np.add.reduce((*rebuilt.values(),tree)))
            source, first, second = amplitudes
            basis = np.stack((source,first-source,second-source)).astype(complex)
            if not np.isfinite(basis).all():
                raise ValueError('nonfinite angular EM basis')
            result.append(basis)
        return tuple(result)

    def integrate_bin(self, pair, energy_range_gev, mass_range_gev, *, energy_rule,
                      energy_order, mass_order, angular_order, flux_spectrum=None,
                      phi_bins=12, phi_bin_divisor=1., ratio_used_fallback=False):
        if any(type(n) is not int or n < 2 for n in (mass_order,angular_order)):
            raise ValueError('mass and angular orders must be integers >= 2')
        if type(phi_bins) is not int or phi_bins not in (8,12,16):
            raise ValueError('phi_bins must be 8, 12 or 16')
        if not np.isfinite(phi_bin_divisor) or not 0 < phi_bin_divisor <= 1:
            raise ValueError('invalid phi_bin_divisor')
        if type(ratio_used_fallback) is not bool:
            raise ValueError('ratio_used_fallback must be boolean')
        def node(energy, exposure):
            return self._node(energy,pair,mass_range_gev,mass_order,angular_order,exposure,phi_bins)
        return _integrate_basis_bin(self.model,pair,energy_range_gev,mass_range_gev,
            energy_rule=energy_rule,energy_order=energy_order,flux_spectrum=flux_spectrum,
            node_integrator=node,phi_bins=phi_bins,phi_bin_divisor=phi_bin_divisor,
            ratio_used_fallback=ratio_used_fallback)

    def _node(self, energy, pair, target, mass_order, angular_order, exposure, phi_bins):
        model = self.model
        meta, mpi, mp = model.masses
        if mp != model.parameters.proton_mass_gev:
            raise ValueError('inconsistent proton masses')
        s = mp*mp+2*mp*energy
        w = np.sqrt(s)
        span = (w-mpi)**2-(meta+mp)**2
        strong = model.parameters.strong
        thresholds = [1.60, *(np.asarray(strong.meson_masses_gev)+np.asarray(strong.baryon_masses_gev))]
        segments = mass_segments(w,model.masses,pair,target,thresholds)
        if not segments:
            return None
        nodes, weights = np.polynomial.legendre.leggauss(mass_order)
        theta = np.pi*(nodes+1)/4
        n,d,v,h,m,extended,sine = (np.zeros((3,3),complex) for _ in range(7))
        flux = GEV2_TO_MICROBARN*4*mp*mp/(2*(s-mp*mp))
        for zlo,zhi in segments:
            lo,hi = zlo*zlo,zhi*zhi
            for z,mweight in zip(np.sqrt(lo+(hi-lo)*np.sin(theta)**2),
                                  weights*(hi-lo)*np.pi/4*np.sin(2*theta)):
                directions,t,aweight,cosine = angular_rule(w,model.masses,z,pair,target,angular_order)
                sample = fixed_mass_sample(w,model.masses,z,directions,t,0.)
                vertical,horizontal = self.event_basis(w,z,sample)
                measure = flux*mweight*aweight*sample.weights_gev2/span
                q, qs = cone_averaged_moments(vertical,horizontal,cosine,measure)
                n += q.numerator; d += q.denominator; v += q.vertical; h += q.horizontal
                sine += qs
                daughters = PAIR_DAUGHTERS[pair]
                mass = invariant_mass(sample.momenta[:,daughters[0]]+sample.momenta[:,daughters[1]])
                qm,_ = cone_averaged_moments(vertical,horizontal,cosine,measure*mass)
                m += qm.denominator
                if z > 1.60:
                    extended += q.denominator
        state = None if exposure is None else harmonic_state_moments(n,sine,d,
            exposure.polarization_vertical,exposure.polarization_horizontal,phi_bins=phi_bins)
        return _NodeMoments(QuadraticMoments(n,d,v,h),m,extended,state,self.anchor,self.fingerprint)


def integrate_angular_basis_bin(model, *args, **kwargs):
    """Single-bin convenience entry; retain an integrator to reuse anchors."""
    return AngularBasisIntegrator(model).integrate_bin(*args, **kwargs)
