"""Döring et al. PRC 73 Eq. 39 and Eq. 43 tree amplitude."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

import numpy as np
from numpy.typing import NDArray

from ..kinematics import cm_photon_momentum, invariant_mass
from ..phase_space import ThreeBodySample
from ..sources import PhysicalParameter
from ..spin import LEVI_CIVITA, PAULI, TRANSITION
from .propagators import (
    Delta1700WidthParameters,
    breit_wigner,
    delta1700_width,
    p_wave_width,
)


@dataclass(frozen=True)
class Delta1700Parameters:
    proton_mass_gev: float
    pi0_mass_gev: float
    eta_mass_gev: float
    pion_reference_mass_gev: float
    delta_mass_gev: float
    delta_width_gev: float
    delta1700_mass_gev: float
    f_delta_n_pi: float
    g_eta_delta: complex
    g1_prime: float
    g2_prime: float
    width_parameters: Delta1700WidthParameters
    provenance: Mapping[str, PhysicalParameter] = field(repr=False, compare=False)

    @classmethod
    def from_parameters(cls, values: Mapping[str, PhysicalParameter]) -> "Delta1700Parameters":
        def real(name: str) -> float:
            value = values[name].value
            if isinstance(value, complex):
                raise ValueError(f"{name} must be real")
            return float(value)

        proton_mass = real("proton_mass")
        width = Delta1700WidthParameters(
            pole_mass_gev=real("delta1700_mass"),
            nominal_pole_width_gev=real("delta1700_nominal_width"),
            proton_mass_gev=proton_mass,
            pion_mass_gev=real("charged_pion_mass"),
            delta_mass_gev=real("delta_mass"),
            delta_pole_width_gev=real("delta_pole_width"),
            rho_mass_gev=real("rho_mass"),
            n_pi_branching_fraction=real("n_pi_branching_fraction"),
            g_rho=real("g_rho"),
            f_rho=real("f_rho"),
            f_tilde_delta_pi=real("f_tilde_delta_pi"),
            g_tilde_delta_pi=real("g_tilde_delta_pi"),
        )
        return cls(
            proton_mass_gev=proton_mass,
            pi0_mass_gev=real("pi0_mass"),
            eta_mass_gev=real("eta_mass"),
            pion_reference_mass_gev=real("charged_pion_mass"),
            delta_mass_gev=real("delta_mass"),
            delta_width_gev=real("delta_pole_width"),
            delta1700_mass_gev=real("delta1700_mass"),
            f_delta_n_pi=real("f_delta_n_pi"),
            g_eta_delta=complex(values["g_eta_delta"].value),
            g1_prime=real("g1_prime") / proton_mass,
            g2_prime=real("g2_prime") / proton_mass**2,
            width_parameters=width,
            provenance=values,
        )


def delta1700_eta_delta_vertex(
    sqrt_s: float,
    photon_three_momentum: NDArray[np.float64],
    pion_three_momentum: NDArray[np.float64],
    polarization: NDArray[np.float64],
    parameters: Delta1700Parameters,
) -> NDArray[np.complex128]:
    """Eq. 39, returning final/initial nucleon spin matrix per event."""
    k = np.asarray(photon_three_momentum, dtype=np.float64)
    p_pi = np.asarray(pion_three_momentum, dtype=np.float64)
    epsilon = np.asarray(polarization, dtype=np.float64)
    if k.shape != (3,) or epsilon.shape != (3,) or p_pi.ndim != 2 or p_pi.shape[1] != 3:
        raise ValueError("Eq. 39 expects k and epsilon (3,), pion momentum (events, 3)")
    if not np.all(np.isfinite(k)) or not np.all(np.isfinite(epsilon)) or not np.all(np.isfinite(p_pi)):
        raise ValueError("Eq. 39 momenta and polarization must be finite")
    if not np.isclose(np.dot(k, epsilon), 0.0, atol=1e-12):
        raise ValueError("photon polarization must be transverse")
    photon_energy = float(np.linalg.norm(k))
    s_dot_p = np.einsum("aij,na->nij", TRANSITION, p_pi)
    sdag_dot_k = np.einsum("aij,a->ji", TRANSITION.conj(), k)
    sdag_dot_epsilon = np.einsum("aij,a->ji", TRANSITION.conj(), epsilon)
    sigma_cross_k_dot_epsilon = sum(
        epsilon[i] * LEVI_CIVITA[i, j, ell] * PAULI[j] * k[ell]
        for i in range(3) for j in range(3) for ell in range(3)
    )
    magnetic = (
        -1j * parameters.g1_prime / (2.0 * parameters.proton_mass_gev)
        * (sdag_dot_k @ sigma_cross_k_dot_epsilon)
    )
    electric_scalar = (
        parameters.g1_prime
        * (photon_energy + np.dot(k, k) / (2.0 * parameters.proton_mass_gev))
        + parameters.g2_prime * sqrt_s * photon_energy
    )
    electromagnetic = magnetic - sdag_dot_epsilon * electric_scalar
    gamma = delta1700_width(sqrt_s, parameters.width_parameters)
    propagator = breit_wigner(sqrt_s, parameters.delta1700_mass_gev, gamma)
    scalar = (
        -np.sqrt(2.0 / 3.0) * parameters.g_eta_delta
        * parameters.f_delta_n_pi / parameters.pion_reference_mass_gev
        * propagator
    )
    return np.asarray(scalar * np.einsum("nij,jk->nik", s_dot_p, electromagnetic), dtype=np.complex128)


def tree_amplitude(
    sample: ThreeBodySample,
    polarization: NDArray[np.float64],
    parameters: Delta1700Parameters,
) -> NDArray[np.complex128]:
    """Eq. 43: Eq. 39 production followed by a Delta(1232) propagator."""
    _, pion, proton = np.moveaxis(sample.momenta, 1, 0)
    z_prime = invariant_mass(pion + proton)
    gamma_delta = p_wave_width(
        z_prime,
        pole_mass=parameters.delta_mass_gev,
        pole_width=parameters.delta_width_gev,
        daughter_masses=(parameters.proton_mass_gev, parameters.pi0_mass_gev),
    )
    g_delta = breit_wigner(z_prime, parameters.delta_mass_gev, gamma_delta)
    sqrt_s = float(sample.initial[0, 0])
    production = delta1700_eta_delta_vertex(
        sqrt_s=sqrt_s,
        photon_three_momentum=cm_photon_momentum(sqrt_s, parameters.proton_mass_gev),
        pion_three_momentum=pion[:, 1:],
        polarization=polarization,
        parameters=parameters,
    )
    return production * g_delta[:, None, None]
