"""Pauli and spin-1/2 to spin-3/2 transition algebra."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray


PAULI = np.array(
    [
        [[0, 1], [1, 0]],
        [[0, -1j], [1j, 0]],
        [[1, 0], [0, -1]],
    ],
    dtype=np.complex128,
)

LEVI_CIVITA = np.zeros((3, 3, 3), dtype=np.int8)
for _index in ((0, 1, 2), (1, 2, 0), (2, 0, 1)):
    LEVI_CIVITA[_index] = 1
for _index in ((0, 2, 1), (2, 1, 0), (1, 0, 2)):
    LEVI_CIVITA[_index] = -1

TRANSITION = np.array(
    [
        [[-np.sqrt(3), 0, 1, 0], [0, -1, 0, np.sqrt(3)]],
        [[-1j * np.sqrt(3), 0, -1j, 0], [0, -1j, 0, -1j * np.sqrt(3)]],
        [[0, 2, 0, 0], [0, 0, 2, 0]],
    ],
    dtype=np.complex128,
) / np.sqrt(6)


def transverse_polarizations(k_hat: ArrayLike) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    direction = np.asarray(k_hat, dtype=np.float64)
    if direction.shape != (3,) or not np.all(np.isfinite(direction)):
        raise ValueError("photon direction must be a finite three-vector")
    norm = np.linalg.norm(direction)
    if norm == 0:
        raise ValueError("photon direction must be nonzero")
    direction = direction / norm
    reference = np.array([1.0, 0.0, 0.0]) if abs(direction[2]) > 0.9 else np.array([0.0, 0.0, 1.0])
    first = np.cross(reference, direction)
    first /= np.linalg.norm(first)
    second = np.cross(direction, first)
    return first, second
