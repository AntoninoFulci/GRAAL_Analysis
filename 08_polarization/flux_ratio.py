"""Flux-normalized vertical/horizontal extraction of beam asymmetry Sigma."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.special import xlogy

from contracts import PolarizationContractError


@dataclass(frozen=True)
class FluxRatioFitResult:
    sigma: float
    stat_uncertainty: float
    converged: bool
    binomial_deviance: float
    ndof: int
    fitted_vertical_fraction: np.ndarray


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
    vertical,
    horizontal,
    flux_vertical,
    flux_horizontal,
    polarization_vertical,
    polarization_horizontal,
) -> tuple[np.ndarray, ...]:
    arrays = tuple(
        _array(raw, label)
        for raw, label in (
            (phi, "phi"),
            (vertical, "vertical counts"),
            (horizontal, "horizontal counts"),
            (flux_vertical, "vertical flux"),
            (flux_horizontal, "horizontal flux"),
            (polarization_vertical, "vertical polarization"),
            (polarization_horizontal, "horizontal polarization"),
        )
    )
    if len({value.shape for value in arrays}) != 1:
        raise PolarizationContractError("flux-ratio inputs must all have same shape")
    phi_array, n_vertical, n_horizontal, f_vertical, f_horizontal, p_vertical, p_horizontal = arrays
    if np.any((phi_array < 0.0) | (phi_array >= np.pi)):
        raise PolarizationContractError("phi must lie in [0, pi)")
    if np.any(n_vertical < 0.0) or np.any(n_horizontal < 0.0):
        raise PolarizationContractError("vertical and horizontal counts must be nonnegative")
    if np.any(f_vertical <= 0.0) or np.any(f_horizontal <= 0.0):
        raise PolarizationContractError("vertical and horizontal flux must be positive")
    if np.any((p_vertical <= 0.0) | (p_vertical > 1.0)) or np.any(
        (p_horizontal <= 0.0) | (p_horizontal > 1.0)
    ):
        raise PolarizationContractError("vertical and horizontal polarization must lie in (0, 1]")
    populated = n_vertical + n_horizontal > 0.0
    cosine = np.cos(2.0 * phi_array[populated])
    if np.count_nonzero(populated) < 4 or np.ptp(cosine) < 1.0:
        raise PolarizationContractError("insufficient angular coverage for flux-ratio fit")
    return arrays


def _vertical_probability(
    sigma: float,
    cosine: np.ndarray,
    flux_vertical: np.ndarray,
    flux_horizontal: np.ndarray,
    polarization_vertical: np.ndarray,
    polarization_horizontal: np.ndarray,
) -> np.ndarray:
    vertical_rate = flux_vertical * (1.0 + polarization_vertical * sigma * cosine)
    horizontal_rate = flux_horizontal * (1.0 - polarization_horizontal * sigma * cosine)
    return vertical_rate / (vertical_rate + horizontal_rate)


def fit_flux_ratio(
    *,
    phi,
    vertical,
    horizontal,
    flux_vertical,
    flux_horizontal,
    polarization_vertical,
    polarization_horizontal,
    modulation_scale=1.0,
) -> FluxRatioFitResult:
    """Fit Sigma after conditioning away one common acceptance per phi bin."""
    arrays = _validated_inputs(
        phi,
        vertical,
        horizontal,
        flux_vertical,
        flux_horizontal,
        polarization_vertical,
        polarization_horizontal,
    )
    phi_array, n_vertical, n_horizontal, f_vertical, f_horizontal, p_vertical, p_horizontal = arrays
    try:
        scale = np.broadcast_to(np.asarray(modulation_scale, dtype=float), phi_array.shape)
    except (TypeError, ValueError) as exc:
        raise PolarizationContractError(
            "modulation_scale must broadcast to phi shape"
        ) from exc
    if not np.all(np.isfinite(scale)) or np.any((scale <= 0.0) | (scale > 1.0)):
        raise PolarizationContractError("modulation_scale must lie in (0, 1]")
    populated = n_vertical + n_horizontal > 0.0
    cosine = np.cos(2.0 * phi_array[populated]) * scale[populated]
    nv = n_vertical[populated]
    nh = n_horizontal[populated]
    fv = f_vertical[populated]
    fh = f_horizontal[populated]
    pv = p_vertical[populated]
    ph = p_horizontal[populated]

    def objective(sigma: float) -> float:
        probability = _vertical_probability(sigma, cosine, fv, fh, pv, ph)
        if np.any((probability <= 0.0) | (probability >= 1.0)):
            return float("inf")
        return float(-np.sum(xlogy(nv, probability) + xlogy(nh, 1.0 - probability)))

    optimization = minimize_scalar(
        objective,
        method="bounded",
        bounds=(-0.999999, 0.999999),
        options={"xatol": 1e-13, "maxiter": 1000},
    )
    if not optimization.success or not np.isfinite(optimization.x):
        raise PolarizationContractError(
            f"flux-ratio Sigma fit did not converge: {optimization.message}"
        )
    sigma = float(optimization.x)
    if abs(sigma) >= 0.995:
        raise PolarizationContractError(
            "flux-ratio Sigma fit is pegged at physical boundary"
        )
    probability = _vertical_probability(sigma, cosine, fv, fh, pv, ph)
    vertical_rate = fv * (1.0 + pv * sigma * cosine)
    horizontal_rate = fh * (1.0 - ph * sigma * cosine)
    derivative_vertical = fv * pv * cosine
    derivative_horizontal = -fh * ph * cosine
    derivative_probability = (
        derivative_vertical * horizontal_rate
        - vertical_rate * derivative_horizontal
    ) / (vertical_rate + horizontal_rate) ** 2
    totals = nv + nh
    fisher = float(
        np.sum(
            totals
            * derivative_probability**2
            / (probability * (1.0 - probability))
        )
    )
    if not np.isfinite(fisher) or fisher <= 0.0:
        raise PolarizationContractError("flux-ratio fit information is nonpositive")
    observed_fraction = nv / totals
    deviance = float(
        2.0
        * np.sum(
            xlogy(nv, observed_fraction / probability)
            + xlogy(nh, (1.0 - observed_fraction) / (1.0 - probability))
        )
    )
    fitted = np.full(phi_array.shape, np.nan)
    fitted[populated] = probability
    return FluxRatioFitResult(
        sigma=sigma,
        stat_uncertainty=float(1.0 / np.sqrt(fisher)),
        converged=True,
        binomial_deviance=max(0.0, deviance),
        ndof=int(np.count_nonzero(populated) - 1),
        fitted_vertical_fraction=fitted,
    )


def flux_normalized_ratio(
    vertical,
    horizontal,
    flux_vertical,
    flux_horizontal,
) -> tuple[np.ndarray, np.ndarray]:
    """Return plotted normalized fraction and Poisson uncertainty."""
    nv = _array(vertical, "vertical counts")
    nh = _array(horizontal, "horizontal counts")
    fv = _array(flux_vertical, "vertical flux")
    fh = _array(flux_horizontal, "horizontal flux")
    if len({value.shape for value in (nv, nh, fv, fh)}) != 1:
        raise PolarizationContractError("flux-normalized ratio inputs must have same shape")
    if np.any(nv < 0.0) or np.any(nh < 0.0):
        raise PolarizationContractError("vertical and horizontal counts must be nonnegative")
    if np.any(fv <= 0.0) or np.any(fh <= 0.0):
        raise PolarizationContractError("vertical and horizontal flux must be positive")
    vertical_rate = nv / fv
    horizontal_rate = nh / fh
    denominator = vertical_rate + horizontal_rate
    if np.any(denominator <= 0.0):
        raise PolarizationContractError("flux-normalized ratio has empty phi bin")
    ratio = vertical_rate / denominator
    derivative_nv = horizontal_rate / (fv * denominator**2)
    derivative_nh = -vertical_rate / (fh * denominator**2)
    variance = derivative_nv**2 * nv + derivative_nh**2 * nh
    return ratio, np.sqrt(np.maximum(variance, 0.0))
