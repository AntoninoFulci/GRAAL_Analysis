"""Validated interpolation of the sourced real-axis N*(1535) strong matrix.

The direct reconstructed matrix remains authoritative. A segment that cannot
meet the matrix bound uses direct evaluation instead of changing the model.
"""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json

import numpy as np
from numpy.typing import NDArray

from . import _reduced_t_core
from .nstar1535_full import reconstructed_full_tmatrix
from .nstar1535_reduced import ReducedTParameters
from .nstar1535_vmd import VectorMasses, switching_energies


_VERSION = "strong-t-grid-v1"
_MAX_SEGMENTS = 8192
_MAX_DEPTH = 20
_DIRECT_RULE = (48, 96, 1e-12, 1e-3)


def _matrix(raw: bytes) -> NDArray[np.complex128]:
    return np.frombuffer(raw, dtype=np.complex128).reshape(6, 6)


@dataclass(frozen=True)
class _Segment:
    lower: float
    upper: float
    lower_value: bytes
    upper_value: bytes
    direct_only: bool = False


@dataclass(frozen=True)
class StrongTGrid:
    """Immutable, parameter-bound real-axis representation of the direct T."""

    parameters: ReducedTParameters
    vector_masses: VectorMasses
    lower_gev: float
    upper_gev: float
    landmarks_gev: tuple[float, ...]
    segments: tuple[_Segment, ...]
    fingerprint: str
    atol: float
    rtol: float

    def matches(self, parameters: ReducedTParameters, masses: VectorMasses) -> bool:
        return self.parameters == parameters and self.vector_masses == masses

    def evaluate(self, w_gev: float) -> NDArray[np.complex128]:
        w = _reduced_t_core.validated_energy(w_gev, self.parameters)
        if w > self.upper_gev:
            raise ValueError("W outside strong-grid real-axis domain")
        # Do not let one floating-point step select the wrong side of a cusp.
        nearest = min(self.landmarks_gev, key=lambda landmark: abs(w - landmark))
        if abs(w - nearest) <= 16*np.finfo(float).eps*max(1., abs(nearest)):
            return reconstructed_full_tmatrix(w, self.parameters, self.vector_masses)
        index = bisect_left(tuple(part.upper for part in self.segments), w)
        if index == len(self.segments):
            raise ValueError("W outside strong-grid real-axis domain")
        part = self.segments[index]
        if part.direct_only:
            return reconstructed_full_tmatrix(w, self.parameters, self.vector_masses)
        fraction = (w - part.lower)/(part.upper - part.lower)
        value = _matrix(part.lower_value) + fraction*(_matrix(part.upper_value) - _matrix(part.lower_value))
        return np.asarray(value, dtype=np.complex128).copy()


def _fingerprint(parameters: ReducedTParameters, masses: VectorMasses,
                 landmarks: tuple[float, ...], atol: float, rtol: float) -> str:
    payload = {
        "version": _VERSION,
        "parameters": {
            "meson_masses_gev": parameters.meson_masses_gev,
            "baryon_masses_gev": parameters.baryon_masses_gev,
            "decay_constants_gev": parameters.decay_constants_gev,
            "subtraction_constants": parameters.subtraction_constants,
            "mu_gev": parameters.mu_gev,
        },
        "vector_masses": (masses.rho_gev, masses.kstar_gev),
        "domain": (landmarks[0], landmarks[-1]),
        "landmarks": landmarks,
        "direct_rule": _DIRECT_RULE,
        "tolerances": (atol, rtol),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@lru_cache(maxsize=2)
def _build(parameters: ReducedTParameters, masses: VectorMasses,
           atol: float, rtol: float, version: str) -> StrongTGrid:
    lower = float(min(np.add(parameters.meson_masses_gev, parameters.baryon_masses_gev)))
    switches = switching_energies(parameters, masses)
    landmarks = tuple(sorted({lower, 1.80, *(
        float(value) for value in np.add(parameters.meson_masses_gev,
                                         parameters.baryon_masses_gev)
        if lower <= value <= 1.80), *(
        float(value) for value in switches.flat
        if np.isfinite(value) and lower <= value <= 1.80)}))
    cache: dict[float, bytes] = {}

    def direct(w: float) -> NDArray[np.complex128]:
        if w not in cache:
            value = reconstructed_full_tmatrix(w, parameters, masses)
            if value.shape != (6, 6) or value.dtype != np.complex128 or not np.isfinite(value).all():
                raise ValueError("direct strong T must be finite complex128 (6,6)")
            cache[w] = value.tobytes()
        return _matrix(cache[w])

    segments: list[_Segment] = []

    def refine(a: float, b: float, depth: int) -> None:
        left, right = direct(a), direct(b)
        probes = (a + (b-a)*0.25, a + (b-a)*0.5, a + (b-a)*0.75)
        accurate = True
        for fraction, w in zip((0.25, 0.5, 0.75), probes):
            actual = direct(w)
            estimate = left + fraction*(right-left)
            if np.any(np.abs(estimate-actual) > np.maximum(atol, rtol*np.abs(actual))):
                accurate = False
        if accurate:
            segments.append(_Segment(a, b, cache[a], cache[b]))
        elif depth >= _MAX_DEPTH or len(cache) >= _MAX_SEGMENTS:
            segments.append(_Segment(a, b, cache[a], cache[b], direct_only=True))
        else:
            middle = probes[1]
            refine(a, middle, depth+1)
            refine(middle, b, depth+1)

    for a, b in zip(landmarks, landmarks[1:]):
        refine(a, b, 0)
    return StrongTGrid(parameters, masses, lower, 1.80, landmarks, tuple(segments),
                       _fingerprint(parameters, masses, landmarks, atol, rtol), atol, rtol)


def build_strong_t_grid(parameters: ReducedTParameters, masses: VectorMasses, *,
                        atol: float = 1e-8, rtol: float = 1e-4) -> StrongTGrid:
    """Build or reuse a bounded grid for the exact sourced physical inputs."""
    if not isinstance(parameters, ReducedTParameters) or not isinstance(masses, VectorMasses):
        raise ValueError("strong grid requires ReducedTParameters and VectorMasses")
    for label, value in (("atol", atol), ("rtol", rtol)):
        if isinstance(value, bool) or not isinstance(value, (int, float, np.integer, np.floating)) \
                or not np.isfinite(value) or value <= 0:
            raise ValueError(f"{label} must be finite and positive")
    return _build(parameters, masses, float(atol), float(rtol), _VERSION)
