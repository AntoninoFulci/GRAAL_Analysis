"""Hermitian spin-interference moments for an exact three-term amplitude basis."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


def _inputs(vertical_basis, horizontal_basis, phi, weights):
    v, h = (np.asarray(value) for value in (vertical_basis, horizontal_basis))
    angle, measure = (np.asarray(value) for value in (phi, weights))
    if (v.ndim != 4 or v.shape[0] != 3 or v.shape[2:] != (2, 2) or v.shape[1] == 0
            or h.shape != v.shape or angle.shape != (v.shape[1],)
            or measure.shape != angle.shape or v.dtype.kind != "c" or h.dtype.kind != "c"
            or angle.dtype.kind not in "iuf" or measure.dtype.kind not in "iuf"
            or not all(np.isfinite(item).all() for item in (v, h, angle, measure))
            or np.any(measure < 0)):
        raise ValueError("basis moments require matching finite spin matrices, angles and nonnegative weights")
    return (np.asarray(v, dtype=np.complex128), np.asarray(h, dtype=np.complex128),
            np.asarray(angle, dtype=np.float64), np.asarray(measure, dtype=np.float64))


def _gram(left, right, weights):
    return np.einsum("anij,bnij,n->ab", left.conj(), right, weights, optimize=False)/2


def _hermitian(value):
    matrix = np.asarray((value + value.conj().T)/2, dtype=np.complex128)
    if matrix.shape != (3, 3) or not np.isfinite(matrix).all():
        raise ValueError("quadratic moment matrix must be finite (3,3)")
    matrix.setflags(write=False)
    return matrix


@dataclass(frozen=True)
class QuadraticMoments:
    numerator: NDArray[np.complex128]
    denominator: NDArray[np.complex128]
    vertical: NDArray[np.complex128] | None = None
    horizontal: NDArray[np.complex128] | None = None

    def evaluate(self, coefficients) -> tuple[float, float, float]:
        raw = np.asarray(coefficients)
        if (raw.shape != (3,) or raw.dtype.kind not in "iuf"
                or not np.isfinite(raw).all()):
            raise ValueError("coefficients must be three finite real values")
        c = np.asarray(raw, dtype=np.float64)
        numerator = float(np.real(c @ self.numerator @ c))
        denominator = float(np.real(c @ self.denominator @ c))
        if not np.isfinite(numerator) or not np.isfinite(denominator) or denominator <= 0:
            raise ValueError("quadratic moments require finite positive denominator")
        return numerator, denominator, numerator/denominator


def quadratic_moments(vertical_basis, horizontal_basis, phi, weights) -> QuadraticMoments:
    """Integrate the existing exact global-azimuth projection as Gram forms."""
    v, h, angle, measure = _inputs(vertical_basis, horizontal_basis, phi, weights)
    cosine = np.cos(2*angle)
    sine = np.sin(2*angle)
    vertical = _hermitian(_gram(v, v, measure))
    horizontal = _hermitian(_gram(h, h, measure))
    denominator = vertical + horizontal
    cross = _gram(h, v, measure*sine)
    numerator = _gram(v, v, measure*cosine) - _gram(h, h, measure*cosine)
    numerator -= cross + cross.conj().T
    return QuadraticMoments(_hermitian(numerator), _hermitian(denominator),
                            vertical, horizontal)


def azimuth_state_moments(vertical_basis, horizontal_basis, phi, weights,
                          polarization_vertical: float,
                          polarization_horizontal: float, *, phi_bins: int = 12) -> NDArray[np.complex128]:
    """Twelve exact azimuth-bin expected-count matrices for V/H, before flux."""
    v, h, angle, measure = _inputs(vertical_basis, horizontal_basis, phi, weights)
    for value in (polarization_vertical, polarization_horizontal):
        if isinstance(value, (bool, np.bool_)) or not np.isscalar(value) or not np.isreal(value) \
                or not np.isfinite(value) or not 0 < value <= 1:
            raise ValueError("polarization must lie in (0,1]")
    total = _gram(v, v, measure) + _gram(h, h, measure)
    if type(phi_bins) is not int or phi_bins not in (8, 12, 16):
        raise ValueError("phi_bins must be 8, 12 or 16")
    edges = np.linspace(0., 2*np.pi, phi_bins+1)
    result = np.empty((2, phi_bins, 3, 3), dtype=np.complex128)
    for index, (lower, upper) in enumerate(zip(edges[:-1], edges[1:])):
        cos_integral = (np.sin(2*(upper-angle)) - np.sin(2*(lower-angle)))/2
        sin_integral = (np.cos(2*(lower-angle)) - np.cos(2*(upper-angle)))/2
        cross = _gram(h, v, measure*sin_integral)
        polarized = (_gram(v, v, measure*cos_integral)
                     - _gram(h, h, measure*cos_integral) - cross - cross.conj().T)
        baseline = (upper-lower)/(4*np.pi)*total
        result[0, index] = _hermitian(baseline + polarization_vertical/(4*np.pi)*polarized)
        result[1, index] = _hermitian(baseline - polarization_horizontal/(4*np.pi)*polarized)
    result.setflags(write=False)
    return result


def cone_averaged_moments(vertical_basis, horizontal_basis, cosine_mean, weights):
    """Average a symmetric internal azimuth cone; retain both output harmonics."""
    v, h, cosine, measure = _inputs(vertical_basis, horizontal_basis, cosine_mean, weights)
    if np.any(abs(cosine) > 1+1e-12):
        raise ValueError("cone cosine mean must lie in [-1,1]")
    vertical, horizontal = _hermitian(_gram(v,v,measure)), _hermitian(_gram(h,h,measure))
    numerator = _hermitian(_gram(v,v,measure*cosine)-_gram(h,h,measure*cosine))
    cross = _gram(h,v,measure*cosine)
    sine = _hermitian(-cross-cross.conj().T)
    return QuadraticMoments(numerator, _hermitian(vertical+horizontal), vertical, horizontal), sine


def harmonic_state_moments(numerator, sine, denominator, polarization_vertical,
                           polarization_horizontal, *, phi_bins=12):
    """Integrate cosine/sine density exactly over native azimuth bins, before flux."""
    if type(phi_bins) is not int or phi_bins not in (8,12,16):
        raise ValueError("phi_bins must be 8, 12 or 16")
    if any(not np.isscalar(p) or isinstance(p, (bool, np.bool_)) or not np.isreal(p)
           or not np.isfinite(p) or not 0 < p <= 1
           for p in (polarization_vertical, polarization_horizontal)):
        raise ValueError("polarization must lie in (0,1]")
    n, s, d = map(_hermitian, (numerator, sine, denominator))
    edges = np.linspace(0., 2*np.pi, phi_bins+1)
    result = np.empty((2,phi_bins,3,3), complex)
    for i,(lo,hi) in enumerate(zip(edges[:-1],edges[1:])):
        harmonic = ((np.sin(2*hi)-np.sin(2*lo))*n
                    +(np.cos(2*lo)-np.cos(2*hi))*s)/(8*np.pi)
        baseline = (hi-lo)*d/(4*np.pi)
        result[0,i] = baseline + polarization_vertical*harmonic
        result[1,i] = baseline - polarization_horizontal*harmonic
    result.setflags(write=False)
    return result
