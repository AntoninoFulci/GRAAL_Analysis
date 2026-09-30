"""Lorentz kinematics with four-vectors ordered (E, px, py, pz)."""

from __future__ import annotations

from numpy.typing import ArrayLike, NDArray
import numpy as np


def kallen(x: ArrayLike, y: ArrayLike, z: ArrayLike, *, atol: float = 1e-14) -> NDArray[np.float64]:
    x, y, z = np.broadcast_arrays(
        np.asarray(x, dtype=np.float64),
        np.asarray(y, dtype=np.float64),
        np.asarray(z, dtype=np.float64),
    )
    if atol < 0 or not np.isfinite(atol):
        raise ValueError("atol must be finite and nonnegative")
    if np.any(~np.isfinite(x + y + z)) or np.any((x < 0) | (y < 0) | (z < 0)):
        raise ValueError("Kallen arguments must be finite and nonnegative")
    result = (x - y - z) ** 2 - 4.0 * y * z
    if np.any(result < -atol):
        raise ValueError("nonphysical negative Kallen function")
    return np.maximum(result, 0.0)


def mass_squared(p: ArrayLike) -> NDArray[np.float64]:
    p = np.asarray(p, dtype=np.float64)
    if p.shape[-1] != 4 or np.any(~np.isfinite(p)):
        raise ValueError("four-vector must be finite with last axis length 4")
    return p[..., 0] ** 2 - np.sum(p[..., 1:] ** 2, axis=-1)


def invariant_mass(p: ArrayLike, *, atol: float = 1e-12) -> NDArray[np.float64]:
    m2 = mass_squared(p)
    if np.any(m2 < -atol):
        raise ValueError("four-vector has nonphysical negative mass squared")
    return np.sqrt(np.maximum(m2, 0.0))


def boost(p: ArrayLike, beta: ArrayLike) -> NDArray[np.float64]:
    """Transform to a frame moving with velocity ``beta`` from the input frame."""
    p = np.asarray(p, dtype=np.float64)
    beta = np.asarray(beta, dtype=np.float64)
    if p.shape[-1] != 4 or beta.shape[-1] != 3:
        raise ValueError("boost expects four-vectors and three-velocities")
    if np.any(~np.isfinite(p)) or np.any(~np.isfinite(beta)):
        raise ValueError("boost input must be finite")
    beta2 = np.sum(beta * beta, axis=-1)
    if np.any(beta2 >= 1.0):
        raise ValueError("beta magnitude must be less than one")
    gamma = 1.0 / np.sqrt(1.0 - beta2)
    dot = np.sum(beta * p[..., 1:], axis=-1)
    coefficient = np.where(
        beta2 > 0,
        (gamma - 1.0) * dot / np.where(beta2 > 0, beta2, 1.0) - gamma * p[..., 0],
        0.0,
    )
    energy = gamma * (p[..., 0] - dot)
    spatial = p[..., 1:] + coefficient[..., None] * beta
    return np.concatenate((energy[..., None], spatial), axis=-1)


def two_body_momentum(parent_mass: float, m1: float, m2: float) -> float:
    if not np.isfinite(parent_mass) or parent_mass <= 0:
        raise ValueError("parent_mass must be finite and positive")
    if m1 < 0 or m2 < 0 or not np.isfinite(m1 + m2):
        raise ValueError("daughter masses must be finite and nonnegative")
    if parent_mass < m1 + m2 - 1e-14:
        raise ValueError("nonphysical two-body decay below threshold")
    root = kallen(parent_mass**2, m1**2, m2**2, atol=1e-14)
    return float(np.sqrt(root) / (2.0 * parent_mass))


def s_from_lab_photon_energy(energy_gev: float, target_mass: float) -> float:
    if not np.isfinite(energy_gev) or energy_gev < 0:
        raise ValueError("photon energy must be finite and nonnegative")
    if not np.isfinite(target_mass) or target_mass <= 0:
        raise ValueError("target mass must be finite and positive")
    return target_mass**2 + 2.0 * target_mass * energy_gev


def cm_photon_momentum(sqrt_s: float, target_mass: float) -> NDArray[np.float64]:
    if not np.isfinite(sqrt_s) or not np.isfinite(target_mass) or sqrt_s <= target_mass or target_mass <= 0:
        raise ValueError("sqrt_s must exceed target mass")
    magnitude = (sqrt_s**2 - target_mass**2) / (2.0 * sqrt_s)
    return np.array([0.0, 0.0, magnitude], dtype=np.float64)


def validate_final_state(
    initial: ArrayLike,
    final: ArrayLike,
    masses: tuple[float, float, float],
    *,
    atol: float = 1e-12,
) -> None:
    initial = np.asarray(initial, dtype=np.float64)
    final = np.asarray(final, dtype=np.float64)
    if final.ndim != 3 or final.shape[1:] != (3, 4):
        raise ValueError("final state must have shape (events, 3, 4)")
    if initial.shape not in ((4,), (len(final), 4)):
        raise ValueError("initial state must have shape (4,) or (events, 4)")
    if np.any(~np.isfinite(initial)) or np.any(~np.isfinite(final)):
        raise ValueError("initial and final states must be finite")
    expected = np.broadcast_to(initial, (len(final), 4))
    residual = np.max(np.abs(final.sum(axis=1) - expected), axis=1)
    shell = np.max(np.abs(mass_squared(final) - np.square(masses)), axis=1)
    bad = np.flatnonzero((residual > atol) | (shell > atol))
    if len(bad):
        index = int(bad[0])
        raise ValueError(
            f"event {index} violates conservation/on-shell tolerance: "
            f"four-momentum={residual[index]:.3g} GeV, mass-squared={shell[index]:.3g} GeV2"
        )
