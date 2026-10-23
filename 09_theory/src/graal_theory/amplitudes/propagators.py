"""Resonance propagators and Eq. 37 energy-dependent widths."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.integrate import quad

from ..kinematics import two_body_momentum


def breit_wigner(energy_gev: ArrayLike, pole_mass: float, width: ArrayLike) -> NDArray[np.complex128]:
    energy = np.asarray(energy_gev, dtype=np.float64)
    gamma = np.asarray(width, dtype=np.float64)
    if not np.isfinite(pole_mass) or pole_mass <= 0 or np.any(~np.isfinite(energy)) or np.any(~np.isfinite(gamma)):
        raise ValueError("Breit-Wigner inputs must be finite with positive pole mass")
    if np.any(gamma < 0):
        raise ValueError("width must be nonnegative")
    denominator = energy - pole_mass + 0.5j * gamma
    if np.any(denominator == 0):
        raise ValueError("Breit-Wigner denominator vanishes")
    return np.asarray(1.0 / denominator, dtype=np.complex128)


def p_wave_width(
    energy_gev: ArrayLike,
    pole_mass: float,
    pole_width: float,
    daughter_masses: tuple[float, float],
) -> NDArray[np.float64]:
    energy = np.asarray(energy_gev, dtype=np.float64)
    if np.any(~np.isfinite(energy)) or not np.isfinite(pole_width) or pole_width < 0:
        raise ValueError("energy and pole width must be finite; width must be nonnegative")
    threshold = sum(daughter_masses)
    q0 = two_body_momentum(pole_mass, *daughter_masses)
    if q0 <= 0:
        raise ValueError("p-wave pole mass must exceed daughter threshold")
    q = np.array([
        two_body_momentum(float(value), *daughter_masses) if value > threshold else 0.0
        for value in energy.reshape(-1)
    ], dtype=np.float64).reshape(energy.shape)
    ratio = np.divide(pole_mass, energy, out=np.zeros_like(energy), where=energy > threshold)
    return np.asarray(pole_width * (q / q0) ** 3 * ratio, dtype=np.float64)


@dataclass(frozen=True)
class Delta1700WidthParameters:
    pole_mass_gev: float
    nominal_pole_width_gev: float
    proton_mass_gev: float
    pion_mass_gev: float
    delta_mass_gev: float
    delta_pole_width_gev: float
    rho_mass_gev: float
    n_pi_branching_fraction: float
    g_rho: float
    f_rho: float
    f_tilde_delta_pi: float
    g_tilde_delta_pi: float

    def __post_init__(self) -> None:
        masses = (
            self.pole_mass_gev, self.proton_mass_gev, self.pion_mass_gev,
            self.delta_mass_gev, self.rho_mass_gev,
        )
        if not all(np.isfinite(value) and value > 0 for value in masses):
            raise ValueError("resonance and daughter masses must be finite and positive")
        if not np.isfinite(self.nominal_pole_width_gev) or self.nominal_pole_width_gev < 0:
            raise ValueError("nominal pole width must be finite and nonnegative")
        if not np.isfinite(self.delta_pole_width_gev) or self.delta_pole_width_gev < 0:
            raise ValueError("Delta pole width must be finite and nonnegative")
        if not 0 <= self.n_pi_branching_fraction <= 1:
            raise ValueError("N pi branching fraction must lie in [0, 1]")
        if not all(np.isfinite(value) for value in (
            self.g_rho, self.f_rho, self.f_tilde_delta_pi, self.g_tilde_delta_pi
        )):
            raise ValueError("width couplings must be finite")

    def components_at_pole(self) -> dict[str, float]:
        return delta1700_width_components(self.pole_mass_gev, self)


def _momentum_if_open(parent: float, m1: float, m2: float) -> float:
    return two_body_momentum(parent, m1, m2) if parent > m1 + m2 else 0.0


def _delta_pi_width(energy: float, p: Delta1700WidthParameters) -> float:
    lower = p.proton_mass_gev + p.pion_mass_gev
    upper = energy - p.pion_mass_gev
    if upper <= lower:
        return 0.0

    def integrand(mass_delta: float) -> float:
        k = _momentum_if_open(energy, mass_delta, p.pion_mass_gev)
        gamma_delta = float(p_wave_width(
            mass_delta, p.delta_mass_gev, p.delta_pole_width_gev,
            (p.proton_mass_gev, p.pion_mass_gev),
        ))
        q2_over_mu2 = (k / p.pion_mass_gev) ** 2
        a_s = -np.sqrt(4.0 * np.pi) * (
            p.f_tilde_delta_pi + p.g_tilde_delta_pi * q2_over_mu2 / 3.0
        )
        a_d = np.sqrt(4.0 * np.pi) * p.g_tilde_delta_pi * q2_over_mu2 / 3.0
        denominator = (mass_delta - p.delta_mass_gev) ** 2 + (gamma_delta / 2.0) ** 2
        if denominator == 0:
            return 0.0
        return (
            mass_delta * k / (4.0 * np.pi * energy)
            * gamma_delta * (abs(a_s) ** 2 + abs(a_d) ** 2) / denominator
        )

    integral = quad(integrand, lower, upper, points=[p.delta_mass_gev] if lower < p.delta_mass_gev < upper else None,
                    epsabs=1e-8, epsrel=1e-6)[0]
    return 15.0 * integral / (16.0 * np.pi**2)


def _rho_width_at_mass(mass: float, p: Delta1700WidthParameters) -> float:
    if mass <= 2.0 * p.pion_mass_gev:
        return 0.0
    momentum = _momentum_if_open(mass, p.pion_mass_gev, p.pion_mass_gev)
    return 2.0 * p.f_rho**2 * momentum**3 / (3.0 * 4.0 * np.pi * mass**2)


def _n_rho_width(energy: float, p: Delta1700WidthParameters) -> float:
    lower = p.pion_mass_gev
    upper = energy - p.proton_mass_gev - p.pion_mass_gev
    if upper <= lower:
        return 0.0

    def integrate_second(omega1: float) -> float:
        q1 = np.sqrt(max(omega1**2 - p.pion_mass_gev**2, 0.0))
        remainder_s = energy**2 + p.pion_mass_gev**2 - 2.0 * energy * omega1
        remainder_m = np.sqrt(max(remainder_s, 0.0))
        if remainder_m <= p.proton_mass_gev + p.pion_mass_gev:
            return 0.0
        e2_star = (
            remainder_s + p.pion_mass_gev**2 - p.proton_mass_gev**2
        ) / (2.0 * remainder_m)
        q2_star = _momentum_if_open(remainder_m, p.pion_mass_gev, p.proton_mass_gev)
        low = ((energy - omega1) * e2_star - q1 * q2_star) / remainder_m
        high = ((energy - omega1) * e2_star + q1 * q2_star) / remainder_m

        def integrand(omega2: float) -> float:
            q2 = np.sqrt(max(omega2**2 - p.pion_mass_gev**2, 0.0))
            if q1 * q2 == 0:
                return 0.0
            angle = (
                (energy - omega1 - omega2) ** 2
                - p.proton_mass_gev**2 - q1**2 - q2**2
            ) / (2.0 * q1 * q2)
            angle = float(np.clip(angle, -1.0, 1.0))
            difference_squared = q1**2 + q2**2 - 2.0 * q1 * q2 * angle
            rho_s = max((omega1 + omega2) ** 2 - (q1**2 + q2**2 + 2.0 * q1 * q2 * angle),
                        (2.0 * p.pion_mass_gev) ** 2)
            gamma_rho = _rho_width_at_mass(np.sqrt(rho_s), p)
            inverse_propagator_squared = (
                (rho_s - p.rho_mass_gev**2) ** 2
                + (p.rho_mass_gev * gamma_rho) ** 2
            )
            return difference_squared / inverse_propagator_squared

        return quad(integrand, low, high, epsabs=1e-8, epsrel=1e-5)[0]

    integral = quad(integrate_second, lower, upper, epsabs=1e-8, epsrel=1e-5)[0]
    prefactor = (
        p.proton_mass_gev * p.pole_mass_gev * p.g_rho**2 * p.f_rho**2
        / (6.0 * (2.0 * np.pi) ** 3 * energy)
    )
    return prefactor * integral


@lru_cache(maxsize=256)
def _components_at_energy(energy: float, p: Delta1700WidthParameters) -> tuple[float, float, float]:
    threshold = p.proton_mass_gev + p.pion_mass_gev
    if energy <= threshold:
        n_pi = 0.0
    else:
        q = _momentum_if_open(energy, p.proton_mass_gev, p.pion_mass_gev)
        q_pole = _momentum_if_open(p.pole_mass_gev, p.proton_mass_gev, p.pion_mass_gev)
        n_pi = p.nominal_pole_width_gev * p.n_pi_branching_fraction * (q / q_pole) ** 5
    return n_pi, _n_rho_width(energy, p), _delta_pi_width(energy, p)


def delta1700_width_components(energy_gev: float, p: Delta1700WidthParameters) -> dict[str, float]:
    if not np.isfinite(energy_gev) or energy_gev <= 0:
        raise ValueError("energy must be finite and positive")
    n_pi, n_rho, delta_pi = _components_at_energy(float(energy_gev), p)
    return {"n_pi": n_pi, "n_rho": n_rho, "delta_pi": delta_pi}


def delta1700_width(energy_gev: float, p: Delta1700WidthParameters) -> float:
    return float(sum(delta1700_width_components(energy_gev, p).values()))
