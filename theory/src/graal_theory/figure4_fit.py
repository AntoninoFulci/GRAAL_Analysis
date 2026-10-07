"""Covariance-aware GLS for the two sourced Delta(1700) EM couplings."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import least_squares

from .figure4_basis import BasisBinCertificate
from .native_sigma import BinKey, NativeSigmaData


@dataclass(frozen=True)
class GLSObjective:
    data: NativeSigmaData
    predictions: Mapping[BinKey, BasisBinCertificate]
    cholesky: NDArray[np.float64]
    anchor_g1: float
    anchor_g2: float
    proton_mass_gev: float
    model_fingerprint: str

    def residuals(self, theta: NDArray[np.float64]) -> NDArray[np.float64]:
        values = np.asarray(theta)
        if values.shape != (2,) or values.dtype.kind not in "iuf" or not np.isfinite(values).all():
            raise ValueError("fit coordinates must be two finite real couplings")
        c = np.array([1., float(values[0])-self.anchor_g1,
                      float(values[1])-self.anchor_g2], dtype=np.float64)
        predicted = []
        for key in self.data.keys:
            item = self.predictions[key].predict(c)
            if (not np.isfinite(item.denominator) or item.denominator <= 0
                    or item.ratio_sigma is None or not np.isfinite(item.ratio_sigma)):
                raise ValueError(f"invalid denominator or native ratio prediction for {key}")
            predicted.append(item.ratio_sigma)
        return np.linalg.solve(self.cholesky, self.data.sigma-np.asarray(predicted))


@dataclass(frozen=True)
class FitResult:
    status: str
    theta_internal: NDArray[np.float64]
    theta_source_units: NDArray[np.float64]
    source_internal: NDArray[np.float64]
    source_source_units: NDArray[np.float64]
    residuals: NDArray[np.float64] | None
    chi_square: float | None
    degrees_of_freedom: int
    jacobian_singular_values: NDArray[np.float64] | None
    parameter_covariance: NDArray[np.float64] | None
    data_fingerprint: str
    model_fingerprint: str
    message: str
    nfev: int


def build_gls(data: NativeSigmaData,
              predictions: Mapping[BinKey, BasisBinCertificate]) -> GLSObjective:
    """Align only native certified bins by their explicit Stage 07 keys."""
    if not isinstance(data, NativeSigmaData) or not isinstance(predictions, Mapping):
        raise ValueError("GLS requires native data and keyed basis certificates")
    if len(data.keys) != len(set(data.keys)) or set(data.keys) != set(predictions):
        raise ValueError("theory keys must match unique native data keys exactly")
    size = len(data.keys)
    measured = np.asarray(data.sigma)
    if measured.shape != (size,) or measured.dtype.kind not in "iuf" or not np.isfinite(measured).all():
        raise ValueError("measured Sigma must be a finite vector aligned to keys")
    covariance = np.asarray(data.covariance, dtype=np.float64)
    if (size <= 2 or covariance.shape != (size, size)
            or not np.isfinite(covariance).all()
            or not np.allclose(covariance, covariance.T, rtol=1e-10, atol=1e-12)):
        raise ValueError("invalid native covariance dimension or symmetry")
    try:
        factor = np.linalg.cholesky(covariance)
    except np.linalg.LinAlgError as exc:
        raise ValueError("native covariance must be positive definite") from exc
    stat = np.asarray(data.stat_error, dtype=np.float64)
    if stat.shape != (size,) or not np.isfinite(stat).all() or np.any(stat <= 0):
        raise ValueError("native statistical errors must be finite and positive")
    anchor = None
    fingerprint = None
    for index, key in enumerate(data.keys):
        certificate = predictions[key]
        if certificate.status != "calculated":
            raise ValueError(f"uncertified theory bin {key}")
        if certificate.moment.energy_rule != "native_flux":
            raise ValueError(f"theory bin {key} must use native flux")
        if (not np.isfinite(certificate.numerical_error_bound)
                or certificate.numerical_error_bound > min(.01, .2*stat[index])):
            raise ValueError(f"theory numerical error exceeds native precision for {key}")
        current = (certificate.moment.anchor_g1, certificate.moment.anchor_g2,
                   certificate.moment.proton_mass_gev)
        if any(value is None or not np.isfinite(value) for value in current) or current[2] <= 0:
            raise ValueError("theory source anchor and proton mass must be finite")
        if anchor is None:
            anchor = current
            fingerprint = certificate.moment.model_fingerprint
        elif current != anchor or certificate.moment.model_fingerprint != fingerprint:
            raise ValueError("theory source anchor or model fingerprint mismatch")
    if fingerprint is None:
        raise ValueError("theory model fingerprint missing")
    factor.setflags(write=False)
    return GLSObjective(data, dict(predictions), factor, *anchor, fingerprint)


def _jacobian(objective: GLSObjective, theta: NDArray[np.float64]) -> NDArray[np.float64]:
    columns = []
    for index in range(2):
        step = 1e-5*max(1., abs(theta[index]))
        plus, minus = theta.copy(), theta.copy()
        plus[index] += step
        minus[index] -= step
        columns.append((objective.residuals(plus)-objective.residuals(minus))/(2*step))
    return np.column_stack(columns)


def fit_delta_em(objective: GLSObjective, initial_theta: NDArray[np.float64]) -> FitResult:
    """Fit only if whitened two-coupling sensitivity has full rank."""
    theta = np.asarray(initial_theta, dtype=np.float64)
    if theta.shape != (2,) or not np.isfinite(theta).all():
        raise ValueError("initial_theta requires two finite couplings")
    source = np.array([objective.anchor_g1, objective.anchor_g2])
    mass = objective.proton_mass_gev
    def source_units(values):
        return np.array([values[0]*mass, values[1]*mass**2])
    def report(status, values, residual, singular, covariance, message, nfev):
        return FitResult(status, values.copy(), source_units(values), source,
                         source_units(source), None if residual is None else residual.copy(),
                         None if residual is None else float(residual@residual),
                         len(objective.data.keys)-2, singular, covariance,
                         objective.data.source_sha256, objective.model_fingerprint,
                         message, nfev)
    try:
        initial_residual = objective.residuals(theta)
        initial_jacobian = _jacobian(objective, theta)
    except (ValueError, FloatingPointError) as exc:
        return report("invalid_evaluation", theta, None, None, None, str(exc), 0)
    singular = np.linalg.svd(initial_jacobian, compute_uv=False)
    if singular[-1] <= singular[0]*1e-8:
        return report("not_identifiable", theta, initial_residual, singular, None,
                      "whitened Jacobian rank below two at initial point", 0)
    try:
        optimized = least_squares(objective.residuals, theta)
        result_theta = optimized.x
        residual = objective.residuals(result_theta)
        jacobian = _jacobian(objective, result_theta)
    except (ValueError, FloatingPointError) as exc:
        return report("invalid_evaluation", theta, initial_residual, singular, None, str(exc), 0)
    singular = np.linalg.svd(jacobian, compute_uv=False)
    if singular[-1] <= singular[0]*1e-8:
        return report("not_identifiable", result_theta, residual, singular, None,
                      "whitened Jacobian rank below two at optimum", optimized.nfev)
    covariance = np.linalg.inv(jacobian.T@jacobian)
    status = ("fit_computed" if objective.data.status == "final_input" else "exploratory_pilot")
    if not optimized.success:
        status = "optimizer_failed"
    return report(status, result_theta, residual, singular, covariance,
                  optimized.message, optimized.nfev)
