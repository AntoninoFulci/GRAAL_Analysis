"""Paper-style flux-normalized beam-asymmetry ratio and harmonic fits."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping

import numpy as np
from scipy.stats import chi2 as chi2_distribution

from observable_extraction.core.binning import (
    ENERGY_EDGES_GEV,
    PHI_EDGES_RAD,
    energy_bin_index,
    pair_mass_edges,
)
from observable_extraction.core.models import (
    FitDiagnostics,
    FluxExposure,
    SigmaPoint,
)


@dataclass(frozen=True)
class RatioFitResult:
    sigma: float
    sigma_error: float
    ratio: np.ndarray
    ratio_error: np.ndarray
    used_mask: np.ndarray
    diagnostics: FitDiagnostics
    flags: tuple[str, ...] = ()
    c0_error: float | None = None
    s2_error: float | None = None


@dataclass(frozen=True)
class RatioBinResult:
    point: SigmaPoint
    fit: RatioFitResult
    counts_vertical: np.ndarray
    counts_horizontal: np.ndarray
    flux_vertical: float
    flux_horizontal: float
    polarization_vertical: float
    polarization_horizontal: float


def _validate_state_inputs(
    n_v: np.ndarray,
    n_h: np.ndarray,
    flux_v: float,
    flux_h: float,
    pol_v: float,
    pol_h: float,
) -> tuple[np.ndarray, np.ndarray]:
    n_v = np.asarray(n_v, dtype=np.float64)
    n_h = np.asarray(n_h, dtype=np.float64)
    if n_v.shape != n_h.shape:
        raise ValueError("vertical and horizontal counts must have matching shape")
    if np.any(~np.isfinite(n_v)) or np.any(~np.isfinite(n_h)):
        raise ValueError("counts must be finite")
    if np.any(n_v < 0.0) or np.any(n_h < 0.0):
        raise ValueError("counts must be non-negative")
    if not math.isfinite(flux_v) or not math.isfinite(flux_h):
        raise ValueError("flux must be finite")
    if flux_v <= 0.0 or flux_h <= 0.0:
        raise ValueError("selected flux must be positive")
    for value in (pol_v, pol_h):
        if not math.isfinite(value) or not 0.0 < value <= 1.0:
            raise ValueError("polarization must be in (0, 1]")
    return n_v, n_h


def normalized_ratio(
    n_v: np.ndarray,
    n_h: np.ndarray,
    flux_v: float,
    flux_h: float,
    pol_v: float,
    pol_h: float,
) -> tuple[np.ndarray, np.ndarray]:
    n_v, n_h = _validate_state_inputs(n_v, n_h, flux_v, flux_h, pol_v, pol_h)
    y_v = n_v / flux_v
    y_h = n_h / flux_h
    denominator = pol_h * y_v + pol_v * y_h
    ratio = np.full(n_v.shape, np.nan, dtype=np.float64)
    error = np.full(n_v.shape, np.nan, dtype=np.float64)
    valid = denominator > 0.0
    ratio[valid] = (y_v[valid] - y_h[valid]) / denominator[valid]
    d_v = np.zeros_like(n_v)
    d_h = np.zeros_like(n_h)
    d_v[valid] = (
        (pol_h + pol_v) * y_h[valid] / denominator[valid] ** 2
    ) / flux_v
    d_h[valid] = -(
        (pol_h + pol_v) * y_v[valid] / denominator[valid] ** 2
    ) / flux_h
    variance = d_v**2 * n_v + d_h**2 * n_h
    positive = valid & (variance > 0.0) & np.isfinite(variance)
    error[positive] = np.sqrt(variance[positive])
    return ratio, error


def _weighted_fit(
    design: np.ndarray,
    values: np.ndarray,
    errors: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, float, int, float]:
    weights = 1.0 / errors**2
    normal = design.T @ (design * weights[:, None])
    if np.linalg.matrix_rank(normal) != normal.shape[0]:
        raise ValueError("fit design is rank deficient")
    covariance = np.linalg.inv(normal)
    parameters = covariance @ (design.T @ (values * weights))
    residual = (values - design @ parameters) / errors
    chi2 = float(np.dot(residual, residual))
    ndf = int(len(values) - design.shape[1])
    if ndf < 0:
        raise ValueError("not enough populated phi bins for fit")
    p_value = float(chi2_distribution.sf(chi2, ndf)) if ndf > 0 else 1.0
    return parameters, covariance, chi2, ndf, p_value


def fit_ratio(
    phi: np.ndarray,
    n_v: np.ndarray,
    n_h: np.ndarray,
    flux_v: float,
    flux_h: float,
    pol_v: float,
    pol_h: float,
) -> RatioFitResult:
    phi = np.asarray(phi, dtype=np.float64)
    n_v, n_h = _validate_state_inputs(n_v, n_h, flux_v, flux_h, pol_v, pol_h)
    if phi.shape != n_v.shape or np.any(~np.isfinite(phi)):
        raise ValueError("phi must be finite and match count shape")
    ratio, error = normalized_ratio(n_v, n_h, flux_v, flux_h, pol_v, pol_h)
    used = np.isfinite(ratio) & np.isfinite(error) & (error > 0.0)
    if np.count_nonzero(used) < 2:
        raise ValueError("not enough populated phi bins for nominal fit")

    phi_used = phi[used]
    ratio_used = ratio[used]
    error_used = error[used]
    cosine = np.cos(2.0 * phi_used)
    nominal = _weighted_fit(cosine[:, None], ratio_used, error_used)
    parameters, covariance, chi2, ndf, p_value = nominal
    if p_value >= 0.01:
        return RatioFitResult(
            sigma=float(parameters[0]),
            sigma_error=float(np.sqrt(covariance[0, 0])),
            ratio=ratio,
            ratio_error=error,
            used_mask=used,
            diagnostics=FitDiagnostics(True, chi2, ndf, p_value, False),
        )

    if np.count_nonzero(used) < 4:
        raise ValueError("not enough populated phi bins for diagnostic fit")
    design = np.column_stack(
        (np.ones_like(phi_used), cosine, np.sin(2.0 * phi_used))
    )
    parameters, covariance, chi2, ndf, p_value = _weighted_fit(
        design, ratio_used, error_used
    )
    errors = np.sqrt(np.diag(covariance))
    flags = []
    if abs(parameters[0]) > 3.0 * errors[0]:
        flags.append("significant_c0")
    if abs(parameters[2]) > 3.0 * errors[2]:
        flags.append("significant_s2")
    return RatioFitResult(
        sigma=float(parameters[1]),
        sigma_error=float(errors[1]),
        ratio=ratio,
        ratio_error=error,
        used_mask=used,
        diagnostics=FitDiagnostics(
            True,
            chi2,
            ndf,
            p_value,
            True,
            c0=float(parameters[0]),
            s2=float(parameters[2]),
        ),
        flags=tuple(flags),
        c0_error=float(errors[0]),
        s2_error=float(errors[2]),
    )


def extract_ratio_grid(
    *,
    pair: str,
    mass_gev: np.ndarray,
    phi_rad: np.ndarray,
    beam_energy_gev: np.ndarray,
    polarization: np.ndarray,
    exposures: Mapping[tuple[int, int], FluxExposure],
) -> tuple[RatioBinResult, ...]:
    mass_gev = np.asarray(mass_gev, dtype=np.float64)
    phi_rad = np.asarray(phi_rad, dtype=np.float64)
    beam_energy_gev = np.asarray(beam_energy_gev, dtype=np.float64)
    polarization = np.asarray(polarization, dtype=np.int64)
    shape = mass_gev.shape
    if any(array.shape != shape for array in (phi_rad, beam_energy_gev, polarization)):
        raise ValueError("event arrays must have matching shapes")
    if np.any(~np.isfinite(mass_gev)) or np.any(~np.isfinite(phi_rad)):
        raise ValueError("mass and phi arrays must be finite")

    mass_edges = pair_mass_edges(pair)
    results = []
    for energy_bin, (energy_low, energy_high) in enumerate(
        zip(ENERGY_EDGES_GEV[:-1], ENERGY_EDGES_GEV[1:])
    ):
        selected_exposures = [
            exposure
            for exposure in exposures.values()
            if energy_bin_index(exposure.energy_gev) == energy_bin
        ]
        energy_mask = (beam_energy_gev >= energy_low) & (
            (beam_energy_gev < energy_high)
            | ((energy_bin == len(ENERGY_EDGES_GEV) - 2) & (beam_energy_gev <= energy_high))
        )
        if not np.any(energy_mask):
            continue
        if not selected_exposures:
            raise ValueError(f"no flux exposure for energy bin {energy_bin}")
        flux_v = float(sum(item.flux_vertical for item in selected_exposures))
        flux_h = float(sum(item.flux_horizontal for item in selected_exposures))
        pol_v = float(
            sum(
                item.flux_vertical * item.polarization_vertical
                for item in selected_exposures
            )
            / flux_v
        )
        pol_h = float(
            sum(
                item.flux_horizontal * item.polarization_horizontal
                for item in selected_exposures
            )
            / flux_h
        )

        for mass_bin, (mass_low, mass_high) in enumerate(
            zip(mass_edges[:-1], mass_edges[1:])
        ):
            mass_mask = (mass_gev >= mass_low) & (
                (mass_gev < mass_high)
                | ((mass_bin == len(mass_edges) - 2) & (mass_gev <= mass_high))
            )
            selected = energy_mask & mass_mask
            if not np.any(selected):
                continue
            counts_v, _ = np.histogram(
                phi_rad[selected & (polarization == 1)], bins=PHI_EDGES_RAD
            )
            counts_h, _ = np.histogram(
                phi_rad[selected & (polarization == 2)], bins=PHI_EDGES_RAD
            )
            try:
                fit = fit_ratio(
                    0.5 * (PHI_EDGES_RAD[:-1] + PHI_EDGES_RAD[1:]),
                    counts_v,
                    counts_h,
                    flux_v,
                    flux_h,
                    pol_v,
                    pol_h,
                )
            except ValueError:
                continue
            point = SigmaPoint(
                pair=pair,
                energy_bin=energy_bin,
                mass_bin=mass_bin,
                energy_low_gev=float(energy_low),
                energy_high_gev=float(energy_high),
                mass_low_gev=float(mass_low),
                mass_high_gev=float(mass_high),
                mass_mean_gev=float(np.mean(mass_gev[selected])),
                sigma=fit.sigma,
                stat_low=fit.sigma_error,
                stat_high=fit.sigma_error,
                diagnostics=fit.diagnostics,
            )
            results.append(
                RatioBinResult(
                    point,
                    fit,
                    counts_v,
                    counts_h,
                    flux_v,
                    flux_h,
                    pol_v,
                    pol_h,
                )
            )
    return tuple(results)
