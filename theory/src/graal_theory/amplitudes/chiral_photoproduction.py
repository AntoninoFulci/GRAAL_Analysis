"""Coherent Fig. 6--8 spin amplitudes, PRC 73, 045209, Eqs. (21),(24),(25).

All public functions return T in the same complex spin-matrix convention as
eta_photoproduction_amplitude. In Eq. (24), cancelling the printed -i on
both T amplitudes leaves the explicit i in the nucleon propagator intact.
Momenta are overall-CM four-vectors, ordered (eta, pi0, proton); k points +z.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Callable

import numpy as np
from numpy.typing import NDArray

from ..kinematics import cm_photon_momentum, invariant_mass, validate_final_state
from ..phase_space import ThreeBodySample
from ..spin import PAULI
from .nstar1535_reduced import CHANNELS, ReducedTParameters, loop_functions
from .production_loops import (
    ProductionParameters, _eq8_cut_density, _finite_real, _integrate_complex_2d,
    _polarization, _quadrature_value, _radial_cut_density, _real_array,
    eta_photoproduction_amplitude, pion_monopole,
)


# Table III, p. 045209-7, in the existing six-channel charge-+1 ordering.
X1 = np.array([0., np.sqrt(2), 0., .5, -1/(2*np.sqrt(3)), 0.])
Y1 = np.array([0., np.sqrt(2), 0., -.5, -np.sqrt(3)/2, 0.])
X1.setflags(write=False)
Y1.setflags(write=False)
# Post-Eq.(25), p. 045209-8: (a_i, a'_i, b_i, b'_i).
INTERNAL = MappingProxyType({
    1: (-1/np.sqrt(2), -1., 0., 0.),
    3: (1/np.sqrt(6), np.sqrt(2/3), 1/np.sqrt(6), -1/np.sqrt(6)),
    4: (1/np.sqrt(6), 0., 1/np.sqrt(6), -1/np.sqrt(2)),
})
_LEFT_BARYON = {1: 1, 3: 4, 4: 3}
_NUMERICAL_ERRORS = (ValueError, TypeError, ZeroDivisionError,
                     FloatingPointError, OverflowError)


def _spin(vector):
    return np.einsum("aij,a->ij", PAULI, vector)


def _inputs(sample, polarization, production, strong_parameters, strong_t, family, fields):
    label = f"{family} event=unknown channel=all z=unknown"
    try:
        if (not isinstance(production, ProductionParameters)
                or not isinstance(strong_parameters, ReducedTParameters)):
            raise ValueError("requires production and strong parameter records")
        if not isinstance(sample, ThreeBodySample):
            raise ValueError("requires ThreeBodySample")
        for field in fields:
            _finite_real(getattr(production, field), field)
        if not callable(strong_t):
            raise ValueError("strong T must be callable")
        initial = _real_array(sample.initial, label)
        momenta = _real_array(sample.momenta, label)
        if (momenta.ndim != 3 or momenta.shape[1:] != (3, 4)
                or initial.shape != (len(momenta), 4)):
            raise ValueError("invalid sample shape")
        expected_masses = (strong_parameters.meson_masses_gev[2],
                           strong_parameters.meson_masses_gev[0],
                           strong_parameters.baryon_masses_gev[0])
        masses = _real_array(sample.masses, label)
        if masses.shape != (3,) or not np.allclose(masses, expected_masses, rtol=0, atol=1e-12):
            raise ValueError("sample masses must follow (eta,pi0,proton) ordering")
        if np.any(np.abs(initial[:, 1:]) > 1e-12):
            raise ValueError("sample must be in the overall CM frame")
        if np.any(initial[:, 0] <= sum(expected_masses)):
            raise ValueError("invariant below three-body threshold")
        if np.any(momenta[:, :, 0] <= 0):
            raise ValueError("final particles must have positive energies")
        validate_final_state(initial, momenta, expected_masses)
        epsilon = _polarization(polarization, label)
        z = invariant_mass(momenta[:, 0]+momenta[:, 2])
    except (ValueError, TypeError, AttributeError, OverflowError) as exc:
        raise ValueError(f"{label}: {exc}") from exc
    return initial, momenta, epsilon, z


def _strong_matrix(strong_t, z, label):
    try:
        t = _quadrature_value(strong_t(float(z)), label)
        if t.shape != (6, 6):
            raise ValueError("strong T requires shape (6,6)")
        return t
    except _NUMERICAL_ERRORS as exc:
        raise ValueError(f"{label}: strong T {exc}") from exc


def chiral_contact_amplitude(
    sample: ThreeBodySample, polarization: NDArray, production: ProductionParameters,
    strong_parameters: ReducedTParameters, strong_t: Callable[[float], NDArray],
) -> NDArray[np.complex128]:
    """Eq. (21): sourced magnetic contact vertex, strong G(z), T[j,eta](z)."""
    family = "chiral_contact"
    initial, _, epsilon, invariants = _inputs(
        sample, polarization, production, strong_parameters, strong_t, family,
        ("electric_charge", "b6d", "b6f"),
    )
    result = np.zeros((len(initial), 2, 2), dtype=np.complex128)
    coefficients = production.b6d*X1+production.b6f*Y1
    mass = strong_parameters.baryon_masses_gev[0]
    decays = np.asarray(strong_parameters.decay_constants_gev)
    for event, z in enumerate(invariants):
        label = f"{family} event={event} channel=all z={z:.12g}GeV"
        try:
            t = _strong_matrix(strong_t, z, label)
            g = loop_functions(float(z), strong_parameters)
            terms = -1j*coefficients*production.electric_charge*g*t[:, 2]/(8*decays[0]*decays*mass)
            for channel, term in enumerate(terms):
                if not np.isfinite(term):
                    raise ValueError(f"channel={channel}={CHANNELS[channel]} nonfinite contact term")
            k = cm_photon_momentum(float(initial[event, 0]), mass)
            result[event] = np.sum(terms)*_spin(np.cross(k, epsilon))
            _quadrature_value(result[event], label)
        except _NUMERICAL_ERRORS as exc:
            raise ValueError(f"{label}: {exc}") from exc
    return result


def external_pi0_amplitude(
    sample: ThreeBodySample, polarization: NDArray, production: ProductionParameters,
    strong_parameters: ReducedTParameters, strong_t: Callable[[float], NDArray],
) -> NDArray[np.complex128]:
    """Eq. (24): pion emission followed by the inseparable Eq. (8)+(9) pair.

    Source: (-iT_new)=prefactor*i/denominator*(-iT_eta)*(-sigma.p_pi),
    hence T_new=prefactor*i/denominator*T_eta*(-sigma.p_pi).
    """
    family = "external_pi0"
    initial, momenta, epsilon, invariants = _inputs(
        sample, polarization, production, strong_parameters, strong_t, family,
        ("electric_charge", "axial_d", "axial_f"),
    )
    result = np.zeros((len(initial), 2, 2), dtype=np.complex128)
    mass = strong_parameters.baryon_masses_gev[0]
    decay = strong_parameters.decay_constants_gev[0]
    for event, z in enumerate(invariants):
        label = f"{family} event={event} channel=all z={z:.12g}GeV"
        try:
            pion = momenta[event, 1]
            k = cm_photon_momentum(float(initial[event, 0]), mass)
            energy_in = np.sqrt(mass*mass+np.dot(k, k))
            energy_out = np.sqrt(mass*mass+np.dot(k+pion[1:], k+pion[1:]))
            denominator = energy_in-pion[0]-energy_out
            scale = max(energy_in, pion[0], energy_out)
            if abs(denominator) <= 32*np.finfo(float).eps*scale:
                raise ValueError("singular nucleon denominator")
            eta_photo = _quadrature_value(eta_photoproduction_amplitude(
                float(z), epsilon, production, strong_parameters, strong_t), label)
            if eta_photo.shape != (2, 2):
                raise ValueError("eta photoproduction requires shape (2,2)")
            prefactor = (production.axial_d+production.axial_f)*mass/(2*decay*energy_out)
            result[event] = 1j*prefactor/denominator*(eta_photo @ _spin(-pion[1:]))
            _quadrature_value(result[event], label)
        except _NUMERICAL_ERRORS as exc:
            raise ValueError(f"{label}: {exc}") from exc
    return result


def _recoil_roots(available, meson, baryon, p, x, denominator):
    b = (available**2+meson**2-baryon**2-p*p)/2
    c = available**2-(p*x)**2
    discriminant = (b*p*x)**2-c*(available**2*meson**2-b*b)
    roots = []
    if discriminant >= 0:
        for root in ((-b*p*x-np.sqrt(discriminant))/c,
                     (-b*p*x+np.sqrt(discriminant))/c):
            if root > 0 and abs(denominator(root)) < 1e-10:
                if not roots or abs(root-roots[0]) > 1e-12:
                    roots.append(root)
    return roots


def _endpoint_pole(roots, limit, label):
    for root in roots:
        if abs(root-limit) <= 32*np.finfo(float).eps*max(1., root, limit):
            raise ValueError(f"{label}: pole at radial cutoff")


def internal_pi0_amplitude(
    sample: ThreeBodySample, polarization: NDArray, production: ProductionParameters,
    strong_parameters: ReducedTParameters, strong_t: Callable[[float], NDArray],
) -> NDArray[np.complex128]:
    """Eq. (25), with Fig. 8(c)+(d) kept together for channels 2,4,5.

    Physical +i0 cuts use Task2's analytic subtraction and negative delta cut.
    For the two propagators A,B, 1/(A+i0)/(B+i0) is evaluated as
    [1/(A+i0)-1/(B+i0)]/(B-A). Each individual cut therefore retains the
    other propagator's sign, including when both are open. No epsilon is used.

    The form factor uses omega(q) and angular-average (q-k)^2=m_i^2-2omega*k.
    Only the pole-partner factor uses on-shell q_on; its signed q_on^2 is
    analytically continued below the initial meson/left-baryon threshold.
    Left/right baryons are n/n, Lambda/Sigma0, Sigma0/Lambda as printed.
    """
    family = "internal_pi0"
    initial, momenta, epsilon, invariants = _inputs(
        sample, polarization, production, strong_parameters, strong_t, family,
        ("electric_charge", "axial_d", "axial_f", "first_loop_cutoff_gev",
         "pion_form_factor_cutoff_gev"),
    )
    if production.first_loop_cutoff_gev <= 0 or production.pion_form_factor_cutoff_gev <= 0:
        raise ValueError(f"{family} event=unknown channel=all z=unknown: cutoff must be positive")
    result = np.zeros((len(initial), 2, 2), dtype=np.complex128)
    limit = production.first_loop_cutoff_gev
    d, f = production.axial_d, production.axial_f
    pion_mass = strong_parameters.meson_masses_gev[0]
    f_pi = strong_parameters.decay_constants_gev[0]
    for event, z in enumerate(invariants):
        event_label = f"{family} event={event} channel=all z={z:.12g}GeV"
        t = _strong_matrix(strong_t, z, event_label)
        w = float(initial[event, 0])
        pion = momenta[event, 1]
        p = float(np.linalg.norm(pion[1:]))
        k = cm_photon_momentum(w, strong_parameters.baryon_masses_gev[0])[2]
        spin = _spin(pion[1:]) @ _spin(epsilon)
        for channel, (a, ap, b, bp) in INTERNAL.items():
            label = f"{family} event={event} channel={channel}={CHANNELS[channel]} z={z:.12g}GeV"
            left_coupling, right_coupling = a*(d+f)+b*(d-f), ap*(d+f)+bp*(d-f)
            if t[channel, 2] == 0 or production.electric_charge*left_coupling*right_coupling == 0:
                continue
            meson = strong_parameters.meson_masses_gev[channel]
            left = strong_parameters.baryon_masses_gev[_LEFT_BARYON[channel]]
            right = strong_parameters.baryon_masses_gev[channel]
            decay = strong_parameters.decay_constants_gev[channel]
            try:
                q0_on = (w*w+meson*meson-left*left)/(2*w)
                qon_squared = ((w*w-(meson+left)**2)*(w*w-(meson-left)**2)/(4*w*w))
                if q0_on*k == 0:
                    raise ValueError("singular on-shell pole-partner denominator")
                partner = 1-qon_squared/(3*q0_on*k)
                first_roots = [np.sqrt(qon_squared)] if qon_squared > 0 and q0_on > 0 else []
                _endpoint_pole(first_roots, limit, label)

                def energies(q, x):
                    return (np.sqrt(meson*meson+q*q), np.sqrt(left*left+q*q),
                            np.sqrt(right*right+q*q+p*p+2*q*p*x))

                def density(q, x):
                    def denominators(r):
                        omega, energy_left, energy_right = energies(r, x)
                        return w-omega-energy_left, w-omega-pion[0]-energy_right

                    def smooth(r):
                        omega, energy_left, energy_right = energies(r, x)
                        first, second = denominators(r)
                        difference = second-first
                        if difference == 0:
                            raise ValueError("coincident baryon propagator poles")
                        form = pion_monopole(meson*meson-2*omega*k, pion_mass,
                                             production.pion_form_factor_cutoff_gev)
                        return left*right*form*partner/(8*np.pi**2*omega*energy_left*energy_right*difference)

                    def first_smooth(r):
                        omega, energy_left, _ = energies(r, x)
                        rational = (q0_on+omega)*(w-omega+energy_left)/(2*w)
                        return smooth(r)*rational

                    def second_denominator(r):
                        return denominators(r)[1]

                    def second_derivative(r):
                        omega, _, energy_right = energies(r, x)
                        return -r/omega-(r+p*x)/energy_right

                    roots = _recoil_roots(w-pion[0], meson, right, p, x, second_denominator)
                    _endpoint_pole(roots, limit, label)
                    if q0_on > 0:
                        first_density = _eq8_cut_density(q, first_smooth, qon_squared, limit, label)
                    else:
                        # Below the pseudothreshold W<|M-m|, positive Kallen
                        # q_on^2 is not a physical positive-energy meson pole.
                        first_density = _radial_cut_density(
                            q, lambda r: r*r*smooth(r), lambda r: denominators(r)[0], [],
                            lambda r: -r/energies(r, x)[0]-r/energies(r, x)[1],
                            limit, label,
                        )
                    second_density = _radial_cut_density(
                        q, lambda r: r*r*smooth(r), second_denominator, roots,
                        second_derivative, limit, label,
                    )
                    return first_density-second_density

                integral = _integrate_complex_2d(density, 0., limit, -1., 1.,
                    settings=production.quadrature, context=label)
                prefactor = -production.electric_charge*left_coupling*right_coupling/(2*f_pi*decay)
                result[event] += prefactor*t[channel, 2]*integral*spin
                _quadrature_value(result[event], label)
            except _NUMERICAL_ERRORS as exc:
                raise ValueError(f"{label}: {exc}") from exc
    return result
