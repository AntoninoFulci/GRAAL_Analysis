"""Coherent Fig. 9 production, PRC 73, 045209, Eqs. (26)--(35).

Kernels are complex final/initial nucleon spin matrices before Eq. (26).
The Delta KR and pion-pole contributions form one inseparable kernel.
N*(1520) widths use NPA 695, Eqs. (11),(13)--(16),(20),(21),(75).
The dimensionally inconsistent unsquared m in NPA Eq. (17) is replaced by
the M_N^2 printed for the same angle in PRC Eq. (37).
"""

from __future__ import annotations

from functools import lru_cache
from numbers import Integral
from typing import Callable

import numpy as np
from numpy.typing import NDArray
from scipy.integrate import quad

from ..kinematics import cm_photon_momentum, invariant_mass, two_body_momentum, validate_final_state
from ..phase_space import ThreeBodySample
from ..spin import PAULI, TRANSITION
from .delta1700 import Delta1700Parameters
from .nstar1535_reduced import CHANNELS, ReducedTParameters
from .production_loops import (
    ProductionParameters, QuadratureSettings, _complex_scalar, _finite_real,
    _integrate_complex_2d, _polarization, _quadrature_value, _real_array,
    _reject_zero_width_intermediate_pole,
    eq26_rescattering_loop, pion_monopole,
)
from .propagators import Delta1700WidthParameters, breit_wigner, delta1700_width, p_wave_width


_WIDTH_FIELDS = ("nstar1520_mass_gev", "nstar1520_npi_width_gev",
                 "f_tilde_nstar_delta_pi", "g_tilde_nstar_delta_pi",
                 "g_rho_nstar", "rho_form_factor_cutoff_gev")
_PRODUCTION_FIELDS = _WIDTH_FIELDS + ("electric_charge", "g1_nstar_per_gev",
    "g2_nstar_per_gev2", "pion_form_factor_cutoff_gev", "first_loop_cutoff_gev")
_ERRORS = (ValueError, TypeError, AttributeError, ZeroDivisionError,
           FloatingPointError, OverflowError)


def _parameters(production, tree, fields, label):
    if not isinstance(production, ProductionParameters) or not isinstance(tree, Delta1700Parameters):
        raise ValueError(f"{label}: requires production and tree parameter records")
    # The frozen nested record owns its field invariants; verify its type
    # here before a zero transition or neutral-channel shortcut can hide it.
    if not isinstance(tree.width_parameters, Delta1700WidthParameters):
        raise ValueError(f"{label}: width_parameters requires Delta1700WidthParameters")
    for name in fields:
        value = _finite_real(getattr(production, name), name)
        if (name.endswith("mass_gev") or "cutoff" in name) and value <= 0:
            raise ValueError(f"{label}: {name} must be positive")
        if name == "nstar1520_npi_width_gev" and value < 0:
            raise ValueError(f"{label}: {name} must be nonnegative")
    for name in ("proton_mass_gev", "pion_reference_mass_gev", "pi0_mass_gev",
                 "delta_mass_gev", "delta1700_mass_gev", "delta_width_gev",
                 "f_delta_n_pi", "g1_prime", "g2_prime"):
        value = _finite_real(getattr(tree, name), name)
        if "mass" in name and value <= 0:
            raise ValueError(f"{label}: {name} must be positive")
        if name == "delta_width_gev" and value < 0:
            raise ValueError(f"{label}: {name} must be nonnegative")
    if not isinstance(production.quadrature, QuadratureSettings):
        raise ValueError(f"{label}: requires QuadratureSettings")


@lru_cache(maxsize=256)
def _nstar_width(w, pole, npi_pole, ft, gt, g_rho, rho_cutoff, rho_mass,
                 f_rho, delta_mass, delta_pole_width, m, mu, settings):
    """Cache only the source width, with every dependent input in the key."""
    if pole <= m+mu:
        raise ValueError("Nstar pole must exceed Npi threshold")
    npi = (npi_pole*(two_body_momentum(w, m, mu)/two_body_momentum(pole, m, mu))**5
           if w > m+mu else 0.)
    if w <= m+2*mu:
        return float(npi)

    delta = 0.
    # With zero spectral width, a pole at/above the upper phase-space
    # endpoint contributes zero; an active interior pole is unsupported.
    if (ft != 0 or gt != 0) and (delta_pole_width != 0 or w-mu > delta_mass):
        low, high = m+mu, w-mu
        if delta_pole_width == 0 and low < delta_mass < high:
            raise ValueError("zero-width Delta spectral pole inside accessible phase space")
        def delta_integrand(mi):
            k = two_body_momentum(w, mi, mu)
            gamma = float(p_wave_width(mi, delta_mass, delta_pole_width, (m, mu)))
            a_s = -np.sqrt(4*np.pi)*(ft+gt*k*k/(3*mu*mu))
            a_d = np.sqrt(4*np.pi)*gt*k*k/(3*mu*mu)
            denominator = (mi-delta_mass)**2+(gamma/2)**2
            if denominator == 0:
                raise ValueError("zero-width Delta spectral pole")
            return gamma/denominator*mi*k*(a_s*a_s+a_d*a_d)/(8*np.pi**3*w)
        points = [delta_mass] if low < delta_mass < high else None
        delta, error = quad(delta_integrand, low, high, points=points,
                           epsabs=settings.absolute_tolerance,
                           epsrel=settings.relative_tolerance)
        if error > settings.absolute_tolerance+settings.relative_tolerance*abs(delta):
            raise ValueError("Delta-pi spectral quadrature convergence failure")

    rho = 0.
    if g_rho != 0:
        upper = (w*w+mu*mu-(m+mu)**2)/(2*w)
        span = upper-mu

        def rho_integrand(angle, x):
            # Map the exact theta(1-|A|) Dalitz domain onto a rectangle.
            # sin^2 removes both square-root endpoints of the omega1 integral.
            o1 = mu+span*np.sin(angle)**2
            q1 = np.sqrt(max(o1*o1-mu*mu, 0.))
            rem2 = w*w+mu*mu-2*w*o1
            rem = np.sqrt(rem2)
            e2 = (rem2+mu*mu-m*m)/(2*rem)
            q2_star = two_body_momentum(rem, m, mu)
            half_range = q1*q2_star/rem
            o2 = (w-o1)*e2/rem+half_range*x
            q2_squared = o2*o2-mu*mu
            # 2 q1 q2 A follows directly from energy conservation with M_N^2.
            twice_product = (w-o1-o2)**2-m*m-q1*q1-q2_squared
            difference = q1*q1+q2_squared-twice_product
            rho_s = (o1+o2)**2-q1*q1-q2_squared-twice_product
            if rho_s < 4*mu*mu:
                if 4*mu*mu-rho_s > 1e-12:
                    raise ValueError("unphysical rho invariant in Dalitz domain")
                rho_s = 4*mu*mu
            momentum = np.sqrt(max(rho_s/4-mu*mu, 0.))
            gamma = 2*f_rho*f_rho*momentum**3/(12*np.pi*rho_s)
            denominator = (rho_s-rho_mass*rho_mass)**2+(rho_mass*gamma)**2
            form = pion_monopole(rho_s, rho_mass, rho_cutoff)
            jacobian = span*np.sin(2*angle)*half_range
            return jacobian*form*form*difference/denominator

        integral = _integrate_complex_2d(rho_integrand, 0., np.pi/2, -1., 1.,
            settings=settings, context=f"nstar1520 N-rho width energy={w:.12g}GeV")
        rho = (3*m*pole*g_rho*g_rho*f_rho*f_rho/(6*(2*np.pi)**3*w))*float(integral.real)
    total = float(npi+delta+rho)
    if not np.isfinite(total) or total < 0:
        raise ValueError("nonfinite or negative total width")
    return total


def _width_for_masses(w, production, tree, m, mu):
    p = tree.width_parameters
    return _nstar_width(w, production.nstar1520_mass_gev,
        production.nstar1520_npi_width_gev, production.f_tilde_nstar_delta_pi,
        production.g_tilde_nstar_delta_pi, production.g_rho_nstar,
        production.rho_form_factor_cutoff_gev, p.rho_mass_gev, p.f_rho,
        tree.delta_mass_gev, tree.delta_width_gev, m, mu, production.quadrature)


def nstar1520_width(energy_gev: float, production: ProductionParameters,
                    tree: Delta1700Parameters, strong_parameters: ReducedTParameters) -> float:
    """Npi d wave + finite-width Delta-pi + N-rho[pi pi], in GeV.

    The NPA Eq. (16) isospin factor 3 and Eq. (75) |F_rho|^2 are retained;
    g_rho=5.09 is the refit including this form factor (NPA PDF p. 9).
    """
    label = "nstar1520 width"
    try:
        _parameters(production, tree, _WIDTH_FIELDS, label)
        w = _finite_real(energy_gev, "energy_gev")
        if w <= 0 or not isinstance(strong_parameters, ReducedTParameters):
            raise ValueError("requires positive energy and strong parameter record")
        return _width_for_masses(w, production, tree,
            strong_parameters.baryon_masses_gev[0], strong_parameters.meson_masses_gev[1])
    except _ERRORS as exc:
        raise ValueError(f"{label}: {exc}") from exc


def _kernel_inputs(channel, q, x, pion, photon, polarization, production, tree, family):
    label = f"{family} channel={channel!r}"
    try:
        if isinstance(channel, (bool, np.bool_)) or not isinstance(channel, Integral) or channel not in (0, 1):
            raise ValueError("channel must be 0=pi0_p or 1=pi_plus_n")
        _parameters(production, tree, _PRODUCTION_FIELDS, label)
        q, x = _finite_real(q, "q_gev"), _finite_real(x, "cos_theta")
        pion, k = _real_array(pion, label), _real_array(photon, label)
        epsilon = _quadrature_value(polarization, label)
        if q < 0 or not -1 <= x <= 1:
            raise ValueError("requires q>=0 and cos_theta in [-1,1]")
        if pion.shape != (4,) or k.shape != (3,) or epsilon.shape != (3,) or pion[0] <= 0:
            raise ValueError("requires pion (4,), photon/polarization (3,) and positive pion energy")
        k0 = float(np.linalg.norm(k))
        if k0 == 0 or np.linalg.norm(epsilon) == 0 or abs(k @ epsilon) > 1e-12*k0*np.linalg.norm(epsilon):
            raise ValueError("requires nonzero real photon and transverse polarization")
        w = k0+np.sqrt(tree.proton_mass_gev**2+k0*k0)
        return q, pion[1:], k, epsilon, k0, w, label
    except _ERRORS as exc:
        raise ValueError(f"{label}: {exc}") from exc


def _spin(vector):
    return np.einsum("aij,a->ij", PAULI, vector)


def _resonance_kernel(q, p, k, epsilon, k0, w, coefficient, ft, gt, g1, g2, propagator, tree):
    s_dot_p = np.einsum("aij,a->ij", TRANSITION, p)
    sdag_dot_k = np.einsum("aij,a->ji", TRANSITION.conj(), k)
    sdag_dot_epsilon = np.einsum("aij,a->ji", TRANSITION.conj(), epsilon)
    electromagnetic = (g1/(2*tree.proton_mass_gev)*sdag_dot_k @ _spin(np.cross(k, epsilon))
        -1j*sdag_dot_epsilon*(g1*(k0+k0*k0/(2*tree.proton_mass_gev))+g2*w*k0))
    factor = (-1j*coefficient*tree.f_delta_n_pi/tree.pion_reference_mass_gev
        *(ft+gt*q*q/(3*tree.pion_reference_mass_gev**2))*propagator)
    return np.asarray(factor*s_dot_p @ electromagnetic, dtype=np.complex128)


def delta1700_pi_delta_kernel(charge_channel, q_gev, cos_theta, event_pion,
                              photon_momentum, polarization, production, tree) -> NDArray[np.complex128]:
    """PRC Eqs. (30),(33); no intermediate Delta(1232) propagator here."""
    q, p, k, epsilon, k0, w, label = _kernel_inputs(charge_channel, q_gev, cos_theta,
        event_pion, photon_momentum, polarization, production, tree, "delta1700_pi_delta")
    try:
        width = tree.width_parameters
        prop = breit_wigner(w, tree.delta1700_mass_gev, delta1700_width(w, width))
        coefficient = 2/np.sqrt(3)*(1/(2*np.sqrt(2)) if charge_channel == 0 else 1.)
        return _quadrature_value(_resonance_kernel(q, p, k, epsilon, k0, w, coefficient,
            width.f_tilde_delta_pi, width.g_tilde_delta_pi, tree.g1_prime, tree.g2_prime, prop, tree), label)
    except _ERRORS as exc:
        raise ValueError(f"{label}: {exc}") from exc


def nstar1520_pi_delta_kernel(charge_channel, q_gev, cos_theta, event_pion,
                             photon_momentum, polarization, production, tree) -> NDArray[np.complex128]:
    """PRC Eqs. (31),(34), using the NPA three-channel N*(1520) width."""
    q, p, k, epsilon, k0, w, label = _kernel_inputs(charge_channel, q_gev, cos_theta,
        event_pion, photon_momentum, polarization, production, tree, "nstar1520_pi_delta")
    try:
        gamma = _width_for_masses(w, production, tree, tree.width_parameters.proton_mass_gev,
                                 tree.width_parameters.pion_mass_gev)
        prop = breit_wigner(w, production.nstar1520_mass_gev, gamma)
        coefficient = np.sqrt(2)/3*(np.sqrt(2) if charge_channel == 0 else 1.)
        return _quadrature_value(_resonance_kernel(q, p, k, epsilon, k0, w, coefficient,
            production.f_tilde_nstar_delta_pi, production.g_tilde_nstar_delta_pi,
            production.g1_nstar_per_gev, production.g2_nstar_per_gev2, prop, tree), label)
    except _ERRORS as exc:
        raise ValueError(f"{label}: {exc}") from exc


def delta_kr_pole_kernel(charge_channel, q_gev, cos_theta, event_pion,
                         photon_momentum, polarization, production, tree) -> NDArray[np.complex128]:
    """Inseparable PRC Eq. (32) KR+pion-pole pair; Eq. (35) is exactly zero.

    q_on belongs to gamma p -> pi Delta in Fig. 9(f), rather than pi N.
    Retain signed q_on^2 below that threshold. The angle-averaged monopole
    uses the printed on-shell q_on-k, unlike the q-k in PRC Eq. (25).
    """
    _, p, _, epsilon, k0, w, label = _kernel_inputs(charge_channel, q_gev, cos_theta,
        event_pion, photon_momentum, polarization, production, tree, "delta_kr_pole")
    if charge_channel == 0:
        return np.zeros((2, 2), dtype=np.complex128)
    try:
        mu = tree.pion_reference_mass_gev
        q0 = (w*w+mu*mu-tree.delta_mass_gev**2)/(2*w)
        qon_squared = q0*q0-mu*mu
        if q0*k0 == 0:
            raise ValueError("singular on-shell pion-pole denominator")
        partner = 1-qon_squared/(3*q0*k0)
        form = pion_monopole(mu*mu-2*q0*k0, mu, production.pion_form_factor_cutoff_gev)
        spin = 2*(p @ epsilon)*np.eye(2)-1j*_spin(np.cross(p, epsilon))
        return _quadrature_value(production.electric_charge*np.sqrt(2)/9
            *(tree.f_delta_n_pi/mu)**2*form*partner*spin, label)
    except _ERRORS as exc:
        raise ValueError(f"{label}: {exc}") from exc


def _delta_propagator(invariant, channel, tree, strong_parameters):
    """Principal invariant retained; physical p-wave width vanishes off-real."""
    label = f"Delta1232 propagator channel={channel}"
    value = _complex_scalar(invariant, label)
    if value.real < 0 or value.imag < 0 or (value.real != 0 and value.imag != 0):
        raise ValueError(f"{label}: unsupported invariant branch")
    m, mu = strong_parameters.baryon_masses_gev[channel], strong_parameters.meson_masses_gev[channel]
    if value.imag == 0:
        gamma = float(p_wave_width(value.real, tree.delta_mass_gev, tree.delta_width_gev, (m, mu)))
        return complex(breit_wigner(value.real, tree.delta_mass_gev, gamma))
    return complex(1/(value-tree.delta_mass_gev))


def explicit_resonance_amplitude(
    sample: ThreeBodySample, polarization: NDArray, production: ProductionParameters,
    tree: Delta1700Parameters, strong_parameters: ReducedTParameters,
    strong_t: Callable[[float], NDArray],
) -> NDArray[np.complex128]:
    """Sum Eqs. (30)--(35) coherently inside Eq. (26), pi channels only.

    Uses event pion momentum, z=M(eta p), and channel-specific masses.
    Task2 owns the physical +i0 cut and checked base/doubled quadrature.
    The intermediate Delta propagator appears once, solely in Eq. (26).
    """
    label = "explicit_resonances event=unknown channel=all z=unknown"
    try:
        _parameters(production, tree, _PRODUCTION_FIELDS, label)
        if not isinstance(strong_parameters, ReducedTParameters) or not isinstance(sample, ThreeBodySample):
            raise ValueError("requires strong parameter record and ThreeBodySample")
        if not callable(strong_t):
            raise ValueError("strong T must be callable")
        initial, momenta = _real_array(sample.initial, label), _real_array(sample.momenta, label)
        if (momenta.ndim != 3 or momenta.shape[1:] != (3, 4)
                or initial.shape != (len(momenta), 4)):
            raise ValueError("invalid sample shape")
        masses = (strong_parameters.meson_masses_gev[2], strong_parameters.meson_masses_gev[0],
                  strong_parameters.baryon_masses_gev[0])
        actual_masses = _real_array(sample.masses, label)
        if actual_masses.shape != (3,) or not np.allclose(actual_masses, masses, rtol=0, atol=1e-12):
            raise ValueError("sample masses must follow (eta,pi0,proton) ordering")
        if np.any(abs(initial[:, 1:]) > 1e-12):
            raise ValueError("sample must be in overall CM frame")
        if np.any(initial[:, 0] <= sum(masses)) or np.any(momenta[:, :, 0] <= 0):
            raise ValueError("requires open three-body threshold and positive final energies")
        validate_final_state(initial, momenta, masses)
        epsilon = _polarization(polarization, label)
        invariants = invariant_mass(momenta[:, 0]+momenta[:, 2])
    except _ERRORS as exc:
        raise ValueError(f"{label}: {exc}") from exc

    result = np.zeros((len(initial), 2, 2), dtype=np.complex128)
    for event, z in enumerate(invariants):
        label = f"explicit_resonances event={event} channel=all z={z:.12g}GeV"
        try:
            t = _quadrature_value(strong_t(float(z)), label+" strong T")
            if t.shape != (6, 6):
                raise ValueError("strong T requires shape (6,6)")
            pion = momenta[event, 1]
            k = cm_photon_momentum(float(initial[event, 0]), tree.proton_mass_gev)
            for channel in (0, 1):
                label = f"explicit_resonances event={event} channel={channel}={CHANNELS[channel]} z={z:.12g}GeV"
                if t[channel, 2] == 0:
                    continue
                _reject_zero_width_intermediate_pole(float(initial[event, 0]),
                    strong_parameters.meson_masses_gev[channel], tree.delta_mass_gev,
                    tree.delta_width_gev, production.first_loop_cutoff_gev, label, "Delta")
                def source(q, x):
                    args = (channel, q, x, pion, k, epsilon, production, tree)
                    return np.add.reduce((delta1700_pi_delta_kernel(*args),
                        nstar1520_pi_delta_kernel(*args), delta_kr_pole_kernel(*args)))
                def propagator(invariant):
                    return _delta_propagator(invariant, channel, tree, strong_parameters)
                result[event] += eq26_rescattering_loop(sample, event, channel,
                    source_kernel=source, intermediate_propagator=propagator,
                    transition=t[channel, 2], production=production,
                    strong_parameters=strong_parameters, context=label,
                    intermediate_invariant_landmarks_gev=(
                        strong_parameters.baryon_masses_gev[channel]
                        +strong_parameters.meson_masses_gev[channel], tree.delta_mass_gev))
            _quadrature_value(result[event], label)
        except _ERRORS as exc:
            raise ValueError(f"{label}: {exc}") from exc
    return result
