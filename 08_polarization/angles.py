"""Periodic reaction-plane angle for linearly polarized photons."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from contracts import PolarizationContractError


@dataclass(frozen=True)
class PhiResult:
    """Reaction-plane angle or an explicit degeneracy marker."""

    value: float
    valid: bool
    reason: str | None = None


def _vector3(raw, label: str) -> np.ndarray:
    try:
        vector = np.asarray(raw, dtype=float)
    except (TypeError, ValueError) as exc:
        raise PolarizationContractError(f"{label} must be a numeric vector") from exc
    if vector.shape != (3,):
        raise PolarizationContractError(f"{label} must have shape (3,)")
    if not np.all(np.isfinite(vector)):
        raise PolarizationContractError(f"{label} components must be finite")
    return vector


def reaction_plane_phi(
    beam,
    reference,
    momentum,
    tolerance: float = 1e-12,
) -> PhiResult:
    """Return signed reference-to-reaction-plane azimuth modulo `pi`.

    `beam` fixes positive longitudinal direction. `reference` is an axis in
    polarization plane; its sign is immaterial after modulo-`pi` reduction.
    `momentum` fixes reaction plane together with beam.
    """
    if not np.isfinite(tolerance) or tolerance <= 0.0:
        raise PolarizationContractError("angle tolerance must be finite and positive")
    beam_vector = _vector3(beam, "beam")
    reference_vector = _vector3(reference, "reference")
    momentum_vector = _vector3(momentum, "momentum")
    beam_norm = float(np.linalg.norm(beam_vector))
    if beam_norm <= tolerance:
        raise PolarizationContractError("beam vector magnitude is zero")
    direction = beam_vector / beam_norm
    reference_transverse = reference_vector - direction * np.dot(
        direction, reference_vector
    )
    reference_norm = float(np.linalg.norm(reference_transverse))
    if reference_norm <= tolerance:
        return PhiResult(float("nan"), False, "degenerate polarization reference axis")
    reaction_transverse = momentum_vector - direction * np.dot(
        direction, momentum_vector
    )
    reaction_norm = float(np.linalg.norm(reaction_transverse))
    if reaction_norm <= tolerance:
        return PhiResult(float("nan"), False, "degenerate reaction plane")
    reference_unit = reference_transverse / reference_norm
    reaction_unit = reaction_transverse / reaction_norm
    sine = float(np.dot(direction, np.cross(reference_unit, reaction_unit)))
    cosine = float(np.dot(reference_unit, reaction_unit))
    phi = float(np.arctan2(sine, cosine) % np.pi)
    # NumPy can return pi after rounding a tiny negative angle modulo pi.
    if phi >= np.pi:
        phi = 0.0
    return PhiResult(phi, True)
