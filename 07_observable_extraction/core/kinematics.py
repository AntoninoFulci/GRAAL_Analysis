"""Pair invariant masses and laboratory azimuths for Figure 4."""

from __future__ import annotations

import math

import numpy as np

from observable_extraction.core.models import PairProjection


def mass_and_phi(vectors: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    vectors = np.asarray(vectors, dtype=np.float64)
    if vectors.ndim == 1:
        vectors = vectors.reshape(1, 4)
    if vectors.ndim != 2 or vectors.shape[1] != 4:
        raise ValueError("vectors must have shape (N, 4)")
    mass_squared = vectors[:, 3] ** 2 - np.sum(vectors[:, :3] ** 2, axis=1)
    if np.any(mass_squared < -1e-12):
        raise ValueError("materially spacelike pair four-vector")
    mass = np.sqrt(np.clip(mass_squared, 0.0, None))
    phi = np.mod(np.arctan2(vectors[:, 1], vectors[:, 0]), 2.0 * math.pi)
    return mass, phi


def project_pair(
    pair: str, first: np.ndarray, second: np.ndarray
) -> PairProjection:
    mass, phi = mass_and_phi(np.asarray(first) + np.asarray(second))
    return PairProjection(pair, float(mass[0]), float(phi[0]))


def project_all_pairs(
    proton: np.ndarray,
    eta: np.ndarray,
    pi0: np.ndarray,
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    proton = np.asarray(proton, dtype=np.float64)
    eta = np.asarray(eta, dtype=np.float64)
    pi0 = np.asarray(pi0, dtype=np.float64)
    if proton.shape != eta.shape or proton.shape != pi0.shape:
        raise ValueError("proton, eta, and pi0 arrays must have matching shape")
    return {
        "p_pi0": mass_and_phi(proton + pi0),
        "p_eta": mass_and_phi(proton + eta),
        "eta_pi0": mass_and_phi(eta + pi0),
    }
