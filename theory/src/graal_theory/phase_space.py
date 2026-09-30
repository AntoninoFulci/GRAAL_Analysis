"""Deterministic three-body Lorentz-invariant phase-space sampling."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.integrate import quad
from scipy.stats import qmc

from .kinematics import boost, kallen, validate_final_state


class BelowThresholdError(ValueError):
    """Requested invariant energy cannot produce the final state."""


@dataclass(frozen=True)
class SobolConfig:
    power: int
    scramble: bool = False
    seed: int | None = None

    def __post_init__(self) -> None:
        if isinstance(self.power, bool) or not isinstance(self.power, int) or not 4 <= self.power <= 24:
            raise ValueError("Sobol power must be an integer from 4 through 24")
        if self.scramble and self.seed is None:
            raise ValueError("scrambled Sobol sequence requires an explicit seed")
        if self.seed is not None and (
            isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0
        ):
            raise ValueError("Sobol seed must be a nonnegative integer")


@dataclass(frozen=True)
class ThreeBodySample:
    initial: NDArray[np.float64]
    momenta: NDArray[np.float64]
    weights_gev2: NDArray[np.float64]
    masses: tuple[float, float, float]
    s12_gev2: NDArray[np.float64]
    config: SobolConfig


def _validate_inputs(sqrt_s: float, masses: tuple[float, float, float]) -> None:
    if not np.isfinite(sqrt_s) or sqrt_s <= 0:
        raise ValueError("sqrt_s must be finite and positive")
    if len(masses) != 3 or any(not np.isfinite(m) or m < 0 for m in masses):
        raise ValueError("exactly three finite nonnegative masses are required")
    if sqrt_s <= sum(masses):
        raise BelowThresholdError("sqrt_s at or below three-body threshold")


def _unit_directions(cos_theta: NDArray[np.float64], phi: NDArray[np.float64]) -> NDArray[np.float64]:
    sin_theta = np.sqrt(np.maximum(1.0 - cos_theta**2, 0.0))
    return np.stack(
        (sin_theta * np.cos(phi), sin_theta * np.sin(phi), cos_theta),
        axis=-1,
    )


def sample_three_body(
    sqrt_s: float,
    masses: tuple[float, float, float],
    config: SobolConfig,
) -> ThreeBodySample:
    _validate_inputs(sqrt_s, masses)
    m1, m2, m3 = masses
    points = qmc.Sobol(d=5, scramble=config.scramble, seed=config.seed).random_base2(config.power)
    s12_min = (m1 + m2) ** 2
    s12_max = (sqrt_s - m3) ** 2
    s12_range = s12_max - s12_min
    s12 = s12_min + s12_range * points[:, 0]
    mass12 = np.sqrt(s12)

    p3 = np.sqrt(kallen(sqrt_s**2, s12, m3**2, atol=1e-12)) / (2.0 * sqrt_s)
    p1_star = np.sqrt(kallen(s12, m1**2, m2**2, atol=1e-12)) / (2.0 * mass12)
    dir3 = _unit_directions(2.0 * points[:, 1] - 1.0, 2.0 * np.pi * points[:, 2])
    dir1 = _unit_directions(2.0 * points[:, 3] - 1.0, 2.0 * np.pi * points[:, 4])
    p3vec = p3[:, None] * dir3
    p1vec = p1_star[:, None] * dir1

    e3 = np.sqrt(m3**2 + p3**2)
    e12 = (sqrt_s**2 + s12 - m3**2) / (2.0 * sqrt_s)
    e1_star = (s12 + m1**2 - m2**2) / (2.0 * mass12)
    e2_star = (s12 + m2**2 - m1**2) / (2.0 * mass12)
    pair_velocity = -p3vec / e12[:, None]
    p1 = boost(np.column_stack((e1_star, p1vec)), -pair_velocity)
    p2 = boost(np.column_stack((e2_star, -p1vec)), -pair_velocity)
    p3_four = np.column_stack((e3, p3vec))
    final = np.stack((p1, p2, p3_four), axis=1)
    initial = np.broadcast_to(
        np.array([sqrt_s, 0.0, 0.0, 0.0], dtype=np.float64),
        (len(points), 4),
    ).copy()
    weights = s12_range * p3 * p1_star / (32.0 * np.pi**3 * sqrt_s * mass12)
    validate_final_state(initial, final, masses, atol=1e-12)
    return ThreeBodySample(initial, final, weights, masses, s12, config)


def phase_space_volume_quad(sqrt_s: float, masses: tuple[float, float, float]) -> float:
    """Independent one-dimensional integral for constant matrix element."""
    _validate_inputs(sqrt_s, masses)
    m1, m2, m3 = masses
    s = sqrt_s**2
    lower = (m1 + m2) ** 2
    upper = (sqrt_s - m3) ** 2

    def density(s12: float) -> float:
        first = float(np.sqrt(kallen(s, s12, m3**2, atol=1e-12)))
        second = float(np.sqrt(kallen(s12, m1**2, m2**2, atol=1e-12)))
        return first * second / (128.0 * np.pi**3 * s * s12)

    return float(quad(density, lower, upper, epsabs=1e-12, epsrel=1e-10)[0])
