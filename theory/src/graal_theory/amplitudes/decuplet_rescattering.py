"""Coherent Fig. 10 eta-Delta and K-Sigma* families, PRC73 Eqs. (39)--(42).

The printed Eqs. (41),(42), rather than the plan's transcription, set the
coefficients. The eta-Delta topology retains Delta(1232); the prose's blanket
Sigma* replacement is applied only to the kaon topologies. Both Sigma* charge
states use the common dominant Lambda-pi0 running-width prescription.
"""

from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType
from typing import Callable

import numpy as np
from numpy.typing import NDArray

from ..kinematics import cm_photon_momentum, invariant_mass, validate_final_state
from ..phase_space import ThreeBodySample
from ..spin import PAULI
from .delta1700 import Delta1700Parameters, delta1700_eta_delta_vertex
from .nstar1535_reduced import CHANNELS, ReducedTParameters
from .production_loops import (
    ProductionParameters, _complex_scalar, _finite_real, _polarization,
    _quadrature_value, _real_array, eq26_rescattering_loop,
)
from .propagators import breit_wigner, p_wave_width
from .resonance_photoproduction import _delta_propagator, _parameters


# Zero-based physical order: K+Sigma0, K+Lambda, K0Sigma+. The last
# coefficient multiplies (2D+F)/(2 f_pi), giving the printed Eq. (41).
K_SIGMA_STAR_COEFFICIENTS = MappingProxyType({3: 0., 4: np.sqrt(24/25), 5: 1/5})
_K_FIELDS = ("axial_d", "axial_f", "electric_charge", "sigma_star_su3_correction")
_ERRORS = (ValueError, TypeError, AttributeError, ZeroDivisionError,
           FloatingPointError, OverflowError)


def _sigma_parameters(production, label):
    if not isinstance(production, ProductionParameters):
        raise ValueError(f"{label}: requires ProductionParameters")
    mass = _finite_real(production.sigma_star_mass_gev, "sigma_star_mass_gev")
    width = _finite_real(production.sigma_star_width_gev, "sigma_star_width_gev")
    if mass <= 0:
        raise ValueError(f"{label}: sigma_star_mass_gev must be positive")
    if width < 0:
        raise ValueError(f"{label}: sigma_star_width_gev must be nonnegative")
    return mass, width


def _sigma_star_propagator(invariant_mass, production, daughter_masses):
    """36 MeV baseline with q^3 M/E scaling only on the real physical cut.

    Eq. (26) supplies the principal invariant. Below threshold or on its
    pure-imaginary spacelike branch the width is zero; the invariant is
    retained in the denominator, as in the approved Delta continuation.
    The off-real width rule is a reconstruction convention, not printed
    in the source. Pole mass/width remain replaceable sourced parameters.
    """
    label = "Sigma* propagator"
    try:
        mass, rest_width = _sigma_parameters(production, label)
        value = _complex_scalar(invariant_mass, label)
        if value.real < 0 or value.imag < 0 or (value.real != 0 and value.imag != 0):
            raise ValueError("unsupported invariant branch")
        if not isinstance(daughter_masses, tuple) or len(daughter_masses) != 2:
            raise ValueError("daughter masses require a two-entry tuple")
        daughters = tuple(_finite_real(m, "daughter_mass_gev") for m in daughter_masses)
        if min(daughters) <= 0 or mass <= sum(daughters):
            raise ValueError("positive daughter masses must have threshold below Sigma* pole")
        if value.imag == 0:
            gamma = float(p_wave_width(value.real, mass, rest_width, daughters))
            return complex(breit_wigner(value.real, mass, gamma))
        return complex(1/(value-mass))
    except _ERRORS as exc:
        raise ValueError(f"{label}: {exc}") from exc


def _shared_vertex(w, k, pion, epsilon, tree):
    """Use Eq39 unchanged; linear decomposition retains complex polarization."""
    result = delta1700_eta_delta_vertex(w, k, pion[None, 1:], epsilon.real, tree)[0]
    if np.any(epsilon.imag):
        result = result+1j*delta1700_eta_delta_vertex(w, k, pion[None, 1:], epsilon.imag, tree)[0]
    return np.asarray(result, dtype=np.complex128)


def _kernel_inputs(pion, photon, polarization, production, tree, strong_parameters, label):
    try:
        _parameters(production, tree, _K_FIELDS, label)
        if not isinstance(strong_parameters, ReducedTParameters):
            raise ValueError("requires strong parameter record")
        _complex_scalar(production.g_k_sigma_star, label+" g_k_sigma_star")
        pion, k = _real_array(pion, label), _real_array(photon, label)
        epsilon = _quadrature_value(polarization, label+" polarization")
        if pion.shape != (4,) or k.shape != (3,) or epsilon.shape != (3,) or pion[0] <= 0:
            raise ValueError("requires pion (4,), photon/polarization (3,) and positive pion energy")
        k0 = float(np.linalg.norm(k))
        if k0 == 0 or np.linalg.norm(epsilon) == 0 or abs(k @ epsilon) > 1e-12*k0*np.linalg.norm(epsilon):
            raise ValueError("requires nonzero photon and transverse polarization")
        w = k0+np.sqrt(tree.proton_mass_gev**2+k0*k0)
        return pion, k, epsilon, w
    except _ERRORS as exc:
        raise ValueError(f"{label}: {exc}") from exc


def _k_vertex(channel, pion, photon, polarization, production, tree, strong_parameters):
    label = f"k_sigma_star Eq{40 if channel == 4 else 41} channel={channel}"
    pion, k, epsilon, w = _kernel_inputs(pion, photon, polarization, production, tree, strong_parameters, label)
    try:
        f_pi = strong_parameters.decay_constants_gev[0]
        d, f = production.axial_d, production.axial_f
        if channel == 4:
            coefficient = production.sigma_star_su3_correction*K_SIGMA_STAR_COEFFICIENTS[4]*(d+f)/(2*f_pi)
        else:
            coefficient = K_SIGMA_STAR_COEFFICIENTS[5]*(2*d+f)/(2*f_pi)
        # Eq39 has scalar -sqrt(2/3)*g_eta*(f_Delta/m_pi). Setting its
        # f_Delta/m_pi=1 and g_eta=g_K reuses the common spin/EM structure;
        # multiplication by -sqrt(3/2)*coefficient yields Eqs40--41.
        # There is no division by either original eta-specific coupling.
        unit_tree = replace(tree, g_eta_delta=production.g_k_sigma_star,
                            f_delta_n_pi=tree.pion_reference_mass_gev)
        return _quadrature_value(-np.sqrt(3/2)*coefficient*_shared_vertex(w, k, pion, epsilon, unit_tree), label)
    except _ERRORS as exc:
        raise ValueError(f"{label}: {exc}") from exc


def eq40_k_sigma_star(pion, photon_momentum, polarization, production, tree, strong_parameters):
    """Paper channel 5 K+Sigma*0 Lambda production, before Eq26 and Eq42."""
    return _k_vertex(4, pion, photon_momentum, polarization, production, tree, strong_parameters)


def eq41_k_sigma_star(pion, photon_momentum, polarization, production, tree, strong_parameters):
    """Paper channel 6 K0Sigma*+ Sigma+; printed coefficient (2D+F)/(10 f_pi)."""
    return _k_vertex(5, pion, photon_momentum, polarization, production, tree, strong_parameters)


def eq42_sigma_star_kr(pion, polarization, production, strong_parameters):
    """Printed -1.15 e (4 sqrt(3)/25) [(D+F)/(2 f_pi)]^2 KR partner."""
    label = "k_sigma_star Eq42 channel=4"
    try:
        if not isinstance(production, ProductionParameters) or not isinstance(strong_parameters, ReducedTParameters):
            raise ValueError("requires production and strong parameter records")
        values = {name: _finite_real(getattr(production, name), name) for name in _K_FIELDS}
        pion = _real_array(pion, label)
        epsilon = _polarization(polarization, label)
        if pion.shape != (4,) or pion[0] <= 0:
            raise ValueError("requires pion (4,) with positive energy")
        p = pion[1:]
        spin = 2*(p @ epsilon)*np.eye(2)-1j*np.einsum("aij,a->ij", PAULI, np.cross(p, epsilon))
        coefficient = (-values["sigma_star_su3_correction"]*values["electric_charge"]*4*np.sqrt(3)/25
                       *((values["axial_d"]+values["axial_f"])/(2*strong_parameters.decay_constants_gev[0]))**2)
        return _quadrature_value(coefficient*spin, label)
    except _ERRORS as exc:
        raise ValueError(f"{label}: {exc}") from exc


def _inputs(sample, polarization, production, tree, strong_parameters, strong_t, family):
    label = f"{family} event=unknown channel=all z=unknown"
    try:
        fields = ("first_loop_cutoff_gev",)+(_K_FIELDS if family == "k_sigma_star" else ())
        _parameters(production, tree, fields, label)
        if not isinstance(strong_parameters, ReducedTParameters) or not isinstance(sample, ThreeBodySample):
            raise ValueError("requires strong parameter record and ThreeBodySample")
        if not callable(strong_t):
            raise ValueError("strong T must be callable")
        if family == "k_sigma_star":
            _sigma_parameters(production, label)
            _complex_scalar(production.g_k_sigma_star, label+" g_k_sigma_star")
            if production.sigma_star_mass_gev <= strong_parameters.baryon_masses_gev[4]+strong_parameters.meson_masses_gev[0]:
                raise ValueError("sigma_star_mass_gev must exceed Lambda-pi0 threshold")
        else:
            _complex_scalar(tree.g_eta_delta, label+" g_eta_delta")
            if tree.delta_mass_gev <= strong_parameters.baryon_masses_gev[0]+strong_parameters.meson_masses_gev[0]:
                raise ValueError("delta_mass_gev must exceed proton-pi0 threshold")
        initial, momenta = _real_array(sample.initial, label), _real_array(sample.momenta, label)
        if momenta.ndim != 3 or momenta.shape[1:] != (3, 4) or initial.shape != (len(momenta), 4):
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
        return initial, momenta, _polarization(polarization, label), invariant_mass(momenta[:, 0]+momenta[:, 2])
    except _ERRORS as exc:
        raise ValueError(f"{label}: {exc}") from exc


def _rescattering_amplitude(sample, polarization, production, tree, strong_parameters, strong_t, family):
    initial, momenta, epsilon, invariants = _inputs(sample, polarization, production, tree,
                                                  strong_parameters, strong_t, family)
    channels = (2,) if family == "eta_delta" else (4, 5)
    daughters = ((strong_parameters.baryon_masses_gev[0], strong_parameters.meson_masses_gev[0])
        if family == "eta_delta" else
        (strong_parameters.baryon_masses_gev[4], strong_parameters.meson_masses_gev[0]))
    pole = tree.delta_mass_gev if family == "eta_delta" else production.sigma_star_mass_gev
    result = np.zeros((len(initial), 2, 2), dtype=np.complex128)
    for event, z in enumerate(invariants):
        label = f"{family} event={event} channel=all z={z:.12g}GeV"
        try:
            t = _quadrature_value(strong_t(float(z)), label+" strong T")
            if t.shape != (6, 6):
                raise ValueError("strong T requires shape (6,6)")
            pion, w = momenta[event, 1], float(initial[event, 0])
            k = cm_photon_momentum(w, tree.proton_mass_gev)
            for channel in channels:
                label = f"{family} event={event} channel={channel}={CHANNELS[channel]} z={z:.12g}GeV"
                if t[channel, 2] == 0:
                    continue
                if channel == 2:
                    source = _shared_vertex(w, k, pion, epsilon, tree)
                    def propagator(invariant):
                        return _delta_propagator(invariant, 0, tree, strong_parameters)
                else:
                    args = (pion, k, epsilon, production, tree, strong_parameters)
                    source = (eq40_k_sigma_star(*args)+eq42_sigma_star_kr(pion, epsilon, production, strong_parameters)
                              if channel == 4 else eq41_k_sigma_star(*args))
                    def propagator(invariant):
                        return _sigma_star_propagator(invariant, production, daughters)
                result[event] += eq26_rescattering_loop(sample, event, channel,
                    source_kernel=lambda q, x: source, intermediate_propagator=propagator,
                    transition=t[channel, 2], production=production, strong_parameters=strong_parameters,
                    context=label, intermediate_invariant_landmarks_gev=(sum(daughters), pole))
            _quadrature_value(result[event], label)
        except _ERRORS as exc:
            raise ValueError(f"{label}: {exc}") from exc
    return result


def eta_delta_rescattering_amplitude(
    sample: ThreeBodySample, polarization: NDArray, production: ProductionParameters,
    tree: Delta1700Parameters, strong_parameters: ReducedTParameters,
    strong_t: Callable[[float], NDArray],
) -> NDArray[np.complex128]:
    """Eq39 in Eq26, T[2,2](M_eta_p); one intermediate Delta, no Eq43 tree."""
    return _rescattering_amplitude(sample, polarization, production, tree, strong_parameters, strong_t, "eta_delta")


def k_sigma_star_rescattering_amplitude(
    sample: ThreeBodySample, polarization: NDArray, production: ProductionParameters,
    tree: Delta1700Parameters, strong_parameters: ReducedTParameters,
    strong_t: Callable[[float], NDArray],
) -> NDArray[np.complex128]:
    """Eqs40--42 coherently in Eq26; rows 4--5 only, inseparable Sigma* KR.

    Physical row 3 is exactly zero. Each row uses its own Eq27 loop masses,
    while both intermediate Sigma* widths use dominant Lambda-pi0 daughters.
    There is no switch to omit Eq42 and no squaring of amplitudes here.
    """
    return _rescattering_amplitude(sample, polarization, production, tree, strong_parameters, strong_t, "k_sigma_star")
