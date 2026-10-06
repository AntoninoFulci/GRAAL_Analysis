"""Coherent Fig. 6--8 spin amplitudes, PRC 73, 045209, Eqs. (21),(24),(25).

All public functions return T in the same complex spin-matrix convention as
eta_photoproduction_amplitude. In Eq. (24), cancelling the printed -i on
both T amplitudes leaves the explicit i in the nucleon propagator intact.
Momenta are overall-CM four-vectors, ordered (eta, pi0, proton); k points +z.
"""

from __future__ import annotations

from functools import lru_cache
from types import MappingProxyType
from typing import Callable

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import brentq

from ..kinematics import cm_photon_momentum, invariant_mass, validate_final_state
from ..phase_space import ThreeBodySample
from ..spin import PAULI
from .nstar1535_reduced import CHANNELS, ReducedTParameters, loop_functions
from .production_loops import (
    ProductionParameters, _eq8_cut_density, _finite_real, _integrate_complex_1d,
    _integrate_complex_2d,
    _integrate_complex_2d_array,
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
                cutoff_squared = production.pion_form_factor_cutoff_gev**2
                form_numerator = cutoff_squared-pion_mass**2
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
                        form_divisor = cutoff_squared-meson*meson+2*omega*k
                        if form_divisor == 0:
                            raise ValueError("pion monopole: cutoff pole")
                        form = form_numerator/form_divisor
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

                def batched_density(q_nodes, x_nodes):
                    def smooth_scalar(r, angle):
                        o, el, er = energies(r, angle)
                        first = w-o-el
                        second = w-o-pion[0]-er
                        difference = second-first
                        if difference == 0:
                            raise ValueError("coincident baryon propagator poles")
                        form_divisor_r = cutoff_squared-meson*meson+2*o*k
                        if form_divisor_r == 0:
                            raise ValueError("pion monopole: cutoff pole")
                        return (left*right*form_numerator*partner/
                            (8*np.pi**2*o*el*er*difference*form_divisor_r))

                    def first_smooth_scalar(r, angle):
                        o, el, _ = energies(r, angle)
                        return smooth_scalar(r, angle)*(q0_on+o)*(w-o+el)/(2*w)

                    q = np.asarray(q_nodes, dtype=np.float64)
                    omega = np.sqrt(meson*meson+q*q)
                    energy_left = np.sqrt(left*left+q*q)
                    first_divisor = w-omega-energy_left
                    form_divisor = cutoff_squared-meson*meson+2*omega*k
                    if np.any(form_divisor == 0):
                        raise ValueError("pion monopole: cutoff pole")
                    form = form_numerator/form_divisor
                    result_nodes = np.empty((len(q), len(x_nodes)), dtype=np.complex128)
                    for j, x in enumerate(x_nodes):
                        energy_right = np.sqrt(right*right+q*q+p*p+2*q*p*x)
                        second_divisor = w-omega-pion[0]-energy_right
                        difference = second_divisor-first_divisor
                        if np.any(difference == 0):
                            raise ValueError("coincident baryon propagator poles")
                        smooth_nodes = (left*right*form*partner/
                            (8*np.pi**2*omega*energy_left*energy_right*difference))
                        near = np.zeros(len(q), dtype=bool)
                        if q0_on > 0:
                            rational = (q0_on+omega)*(w-omega+energy_left)/(2*w)
                            first_smooth_nodes = smooth_nodes*rational
                            if qon_squared > 0:
                                pole = np.sqrt(qon_squared)
                                near |= abs(q-pole) < 1e-8
                                on_shell = qon_squared*first_smooth_scalar(pole, float(x))
                                safe = np.where(near, 1., qon_squared-q*q)
                                first_density = (q*q*first_smooth_nodes-on_shell)/safe
                                analytic = np.log(abs((limit+pole)/(limit-pole)))/(2*pole)
                                if pole < limit:
                                    analytic -= 1j*np.pi/(2*pole)
                                first_density = first_density+on_shell*analytic/limit
                            elif qon_squared == 0:
                                first_density = -first_smooth_nodes
                            else:
                                kappa = np.sqrt(-qon_squared)
                                at_zero = first_smooth_scalar(0., float(x))
                                first_density = (-first_smooth_nodes
                                    +qon_squared*(first_smooth_nodes-at_zero)/(qon_squared-q*q)
                                    +kappa*at_zero*np.arctan(limit/kappa)/limit)
                        else:
                            if np.any(first_divisor == 0):
                                raise ValueError("unaccounted first baryon propagator pole")
                            first_density = q*q*smooth_nodes/first_divisor

                        def second_at(r):
                            return w-energies(r, float(x))[0]-pion[0]-energies(r, float(x))[2]
                        roots = _recoil_roots(w-pion[0], meson, right, p,
                                              float(x), second_at)
                        _endpoint_pole(roots, limit, label)
                        correction = 0j
                        poles = []
                        for root in roots:
                            if not 0 < root < limit:
                                continue
                            omega_r, _, right_r = energies(root, float(x))
                            slope = -root/omega_r-(root+p*x)/right_r
                            if slope == 0 or not np.isfinite(slope):
                                raise ValueError("nonsimple physical pole")
                            on_shell = root*root*smooth_scalar(root, float(x))
                            residue = on_shell/slope
                            poles.append((root, residue))
                            correction += residue*np.log((limit-root)/root)
                            correction -= 1j*np.pi*on_shell/abs(slope)
                            near |= abs(q-root) < 1e-8
                        if np.any((second_divisor == 0) & ~near):
                            raise ValueError("unaccounted second baryon propagator pole")
                        second_density = (q*q*smooth_nodes/
                            np.where(near, 1., second_divisor))
                        for root, residue in poles:
                            second_density -= residue/np.where(near, 1., q-root)
                        second_density = second_density+correction/limit
                        result_nodes[:, j] = first_density-second_density
                        for index in np.flatnonzero(near):
                            result_nodes[index, j] = density(float(q[index]), float(x))
                    return result_nodes

                available = w-pion[0]
                root_b = (available**2+meson**2-right**2-p*p)/2
                tangent_squared = available**2*meson**2-root_b**2
                tangent = (np.sqrt(tangent_squared)/(p*meson)
                           if p*meson > 0 and tangent_squared > 0 else np.inf)

                def analytic_recoil_angle():
                    def b_end(q, sign):
                        omega_q = np.sqrt(meson*meson+q*q)
                        recoil = np.sqrt(right*right+(q+sign*p)**2)
                        return w-omega_q-pion[0]-recoil

                    boundaries = [0., limit]
                    endpoint_references = {}
                    for sign in (-1, 1):
                        def endpoint_slope(q):
                            omega_q = np.sqrt(meson*meson+q*q)
                            recoil = np.sqrt(right*right+(q+sign*p)**2)
                            return -q/omega_q-(q+sign*p)/recoil

                        # Each endpoint is concave in q; its sole stationary
                        # point brackets both cuts even when they are narrow.
                        segments = [0.]
                        if endpoint_slope(0.)*endpoint_slope(limit) < 0:
                            stationary = brentq(endpoint_slope, 0., limit, xtol=1e-14)
                            segments.append(stationary)
                            boundaries.append(stationary)
                        segments.append(limit)
                        roots = []
                        for lower, upper in zip(segments[:-1], segments[1:]):
                            if b_end(lower, sign)*b_end(upper, sign) < 0:
                                root = brentq(lambda q: b_end(q, sign), lower, upper,
                                              xtol=1e-14)
                                roots.append(root)
                                boundaries.append(root)
                        endpoint_references[sign] = (roots, segments[1:-1])
                    boundaries = sorted(set(boundaries))

                    def stable_b_end(q, sign):
                        # Direct c-E_right loses the small gap at a tangent.
                        # Reconstruct it from an exact cut root, or from the
                        # stationary point when the cut lies outside support.
                        roots, stationary = endpoint_references[sign]
                        references = roots or stationary
                        if not references:
                            return b_end(q, sign)
                        reference = min(references, key=lambda value: abs(q-value))
                        delta = q-reference
                        omega_ref = np.sqrt(meson*meson+reference*reference)
                        recoil_ref = np.sqrt(right*right+(reference+sign*p)**2)
                        slope = (-reference/omega_ref
                                 -(reference+sign*p)/recoil_ref)

                        def convex_remainder(mass, origin):
                            base = np.sqrt(mass*mass+origin*origin)
                            shifted = np.sqrt(mass*mass+(origin+delta)**2)
                            return (delta*delta*(base*(shifted+base)
                                -origin*(2*origin+delta))
                                /(base*(shifted+base)**2))

                        residual = 0. if roots else b_end(reference, sign)
                        return (residual+slope*delta
                                -convex_remainder(meson, reference)
                                -convex_remainder(right, reference+sign*p))

                    @lru_cache(maxsize=8192)
                    def angular_numerator(q):
                        omega_q = np.sqrt(meson*meson+q*q)
                        left_q = np.sqrt(left*left+q*q)
                        cutoff_divisor = cutoff_squared-meson*meson+2*omega_q*k
                        if cutoff_divisor == 0:
                            raise ValueError("pion monopole: cutoff pole")
                        prefactor = (q*q*left*right*form_numerator*partner/
                            (8*np.pi**2*omega_q*left_q*cutoff_divisor))
                        c = w-omega_q-pion[0]
                        y_low = np.sqrt(right*right+(q-p)**2)
                        if q*p == 0:
                            angle = 2/(y_low*np.complex128(c-y_low))
                        else:
                            angle = (np.log(np.complex128(stable_b_end(q, -1)))
                                     -np.log(np.complex128(stable_b_end(q, 1))))/(q*p)
                        return prefactor*angle

                    def first_denominator(q):
                        return w-np.sqrt(meson*meson+q*q)-np.sqrt(left*left+q*q)

                    def first_derivative(q):
                        return (-q/np.sqrt(meson*meson+q*q)
                                -q/np.sqrt(left*left+q*q))

                    a_roots = (first_roots if q0_on > 0 else ())
                    def radial_density(q):
                        return _radial_cut_density(q, angular_numerator,
                            first_denominator, a_roots, first_derivative, limit, label)

                    pieces = []
                    for lower, upper in zip(boundaries[:-1], boundaries[1:]):
                        if lower != 0 and upper != limit:
                            middle = (lower+upper)/2
                            pieces.extend(((lower, middle, "lower"),
                                           (middle, upper, "upper")))
                        else:
                            pieces.append((lower, upper,
                                "lower" if lower != 0 else
                                "upper" if upper != limit else "linear"))

                    def mapped_radial(u):
                        total = 0j
                        for lower, upper, anchor in pieces:
                            length = upper-lower
                            if anchor == "lower":
                                q, jacobian = lower+length*u*u, 2*length*u
                            elif anchor == "upper":
                                q, jacobian = upper-length*u*u, 2*length*u
                            else:
                                q, jacobian = lower+length*u, length
                            total += jacobian*radial_density(q)
                        return total

                    return _integrate_complex_1d(mapped_radial, 0., 1.,
                        settings=production.quadrature, context=label)
                if tangent < 1:
                    integral = analytic_recoil_angle()
                else:
                    try:
                        integral = _integrate_complex_2d_array(
                            batched_density, 0., limit, -1., 1.,
                            settings=production.quadrature, context=label)
                    except ValueError as exc:
                        if p == 0 or "quadrature convergence failure" not in str(exc):
                            raise
                        # A near miss can defeat tensor angular quadrature;
                        # the exact angle integral uses the same source kernel.
                        integral = analytic_recoil_angle()
                prefactor = -production.electric_charge*left_coupling*right_coupling/(2*f_pi*decay)
                result[event] += prefactor*t[channel, 2]*integral*spin
                _quadrature_value(result[event], label)
            except _NUMERICAL_ERRORS as exc:
                raise ValueError(f"{label}: {exc}") from exc
    return result
