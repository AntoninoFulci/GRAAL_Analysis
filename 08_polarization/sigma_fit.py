"""Acceptance-aware binned Poisson fit for beam asymmetry Sigma."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize

from contracts import PolarizationContractError


@dataclass(frozen=True)
class SigmaFitResult:
    """Fit estimate, covariance, and bin-level diagnostics."""

    sigma: float
    stat_uncertainty: float
    state_scales: tuple[float, float]
    covariance: np.ndarray
    converged: bool
    pearson_chi2: float
    ndof: int
    residuals: np.ndarray
    expected: np.ndarray


def _array(raw, label: str) -> np.ndarray:
    try:
        value = np.asarray(raw, dtype=float)
    except (TypeError, ValueError) as exc:
        raise PolarizationContractError(f"{label} must be numeric") from exc
    if value.ndim != 1:
        raise PolarizationContractError(f"{label} must be one-dimensional")
    if not np.all(np.isfinite(value)):
        raise PolarizationContractError(f"{label} must be finite")
    return value


def _validated_inputs(
    phi,
    orientation_sign,
    polarization,
    acceptance,
    exposure,
    observed,
) -> tuple[np.ndarray, ...]:
    arrays = tuple(
        _array(raw, label)
        for raw, label in (
            (phi, "phi"),
            (orientation_sign, "orientation_sign"),
            (polarization, "polarization"),
            (acceptance, "acceptance"),
            (exposure, "exposure"),
            (observed, "observed"),
        )
    )
    if len({value.shape for value in arrays}) != 1:
        raise PolarizationContractError("fit inputs must all have same shape")
    phi_array, sign, pol, acc, exp, counts = arrays
    if phi_array.size < 8:
        raise PolarizationContractError("fit needs at least eight populated angular bins")
    if np.any((phi_array < 0.0) | (phi_array >= np.pi)):
        raise PolarizationContractError("phi must lie in [0, pi)")
    if not np.all(np.isin(sign, (-1.0, 1.0))) or set(sign) != {-1.0, 1.0}:
        raise PolarizationContractError("orientation_sign must contain both -1 and +1")
    if np.any((pol <= 0.0) | (pol > 1.0)):
        raise PolarizationContractError("polarization must lie in (0, 1]")
    if np.any((acc <= 0.0) | (acc > 1.0)):
        raise PolarizationContractError("acceptance must lie in (0, 1]")
    if np.any(exp <= 0.0):
        raise PolarizationContractError("exposure must be positive")
    if np.any(counts < 0.0):
        raise PolarizationContractError("observed counts must be nonnegative")
    modulation = np.cos(2.0 * phi_array)
    if np.unique(np.round(phi_array, 12)).size < 4 or np.ptp(modulation) < 1.0:
        raise PolarizationContractError("insufficient angular coverage for cos(2phi) fit")
    return arrays


def fit_sigma_binned(
    *,
    phi,
    orientation_sign,
    polarization,
    acceptance,
    exposure,
    observed,
) -> SigmaFitResult:
    """Fit Sigma and one positive normalization nuisance per orientation."""
    phi_array, sign, pol, acc, exp, counts = _validated_inputs(
        phi, orientation_sign, polarization, acceptance, exposure, observed
    )
    base = exp * acc
    modulation = sign * pol * np.cos(2.0 * phi_array)
    state_masks = (sign < 0.0, sign > 0.0)
    initial_scales = []
    for mask in state_masks:
        denominator = float(np.sum(base[mask]))
        numerator = float(np.sum(counts[mask]))
        initial_scales.append(max(numerator / denominator, 1e-9))
    initial = np.array([0.0, np.log(initial_scales[0]), np.log(initial_scales[1])])

    def model(parameters: np.ndarray) -> np.ndarray:
        sigma = parameters[0]
        scales = np.where(sign < 0.0, np.exp(parameters[1]), np.exp(parameters[2]))
        return base * scales * (1.0 + sigma * modulation)

    def objective_and_gradient(parameters: np.ndarray) -> tuple[float, np.ndarray]:
        expected = model(parameters)
        if np.any(expected <= 0.0) or not np.all(np.isfinite(expected)):
            return float("inf"), np.zeros(3)
        nll = float(np.sum(expected - counts * np.log(expected)))
        factor = 1.0 - counts / expected
        scales = np.where(sign < 0.0, np.exp(parameters[1]), np.exp(parameters[2]))
        derivative_sigma = base * scales * modulation
        gradient = np.array(
            [
                np.sum(factor * derivative_sigma),
                np.sum(factor[state_masks[0]] * expected[state_masks[0]]),
                np.sum(factor[state_masks[1]] * expected[state_masks[1]]),
            ],
            dtype=float,
        )
        return nll, gradient

    optimization = minimize(
        objective_and_gradient,
        initial,
        method="L-BFGS-B",
        jac=True,
        bounds=((-0.999999, 0.999999), (-30.0, 30.0), (-30.0, 30.0)),
        options={"ftol": 1e-14, "gtol": 1e-10, "maxiter": 2000},
    )
    if not optimization.success or not np.all(np.isfinite(optimization.x)):
        raise PolarizationContractError(
            f"Sigma fit did not converge: {optimization.message}"
        )
    expected = model(optimization.x)
    sigma = float(optimization.x[0])
    scales = np.where(sign < 0.0, np.exp(optimization.x[1]), np.exp(optimization.x[2]))
    derivatives = np.column_stack(
        (
            base * scales * modulation,
            np.where(sign < 0.0, expected, 0.0),
            np.where(sign > 0.0, expected, 0.0),
        )
    )
    fisher = derivatives.T @ (derivatives / expected[:, None])
    try:
        covariance = np.linalg.inv(fisher)
    except np.linalg.LinAlgError as exc:
        raise PolarizationContractError("Sigma fit covariance is singular") from exc
    if not np.all(np.isfinite(covariance)) or covariance[0, 0] <= 0.0:
        raise PolarizationContractError("Sigma fit covariance is nonphysical")
    residuals = (counts - expected) / np.sqrt(expected)
    pearson_chi2 = float(np.sum(residuals**2))
    return SigmaFitResult(
        sigma=sigma,
        stat_uncertainty=float(np.sqrt(covariance[0, 0])),
        state_scales=(float(np.exp(optimization.x[1])), float(np.exp(optimization.x[2]))),
        covariance=covariance,
        converged=True,
        pearson_chi2=pearson_chi2,
        ndof=int(phi_array.size - 3),
        residuals=residuals,
        expected=expected,
    )
