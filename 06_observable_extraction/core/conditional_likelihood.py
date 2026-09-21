"""Run/strip conditional likelihood for linearly polarized beam asymmetry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np
from scipy.optimize import brentq, minimize_scalar

from observable_extraction.core.binning import ENERGY_EDGES_GEV, pair_mass_edges
from observable_extraction.core.models import (
    FitDiagnostics,
    FluxExposure,
    SigmaPoint,
)


@dataclass(frozen=True)
class LikelihoodFitResult:
    sigma: float
    interval_low: float
    interval_high: float
    nll: float
    converged: bool
    at_lower_boundary: bool
    at_upper_boundary: bool
    unbounded_sigma: float
    unbounded_nll: float
    pressure_against_boundary: bool


@dataclass(frozen=True)
class LikelihoodBinResult:
    point: SigmaPoint
    fit: LikelihoodFitResult
    event_count: int


def vertical_probability(
    phi: np.ndarray,
    sigma: float,
    exposure: FluxExposure,
) -> np.ndarray:
    phi = np.asarray(phi, dtype=np.float64)
    cosine = np.cos(2.0 * phi)
    vertical_rate = exposure.flux_vertical * (
        1.0 + exposure.polarization_vertical * sigma * cosine
    )
    horizontal_rate = exposure.flux_horizontal * (
        1.0 - exposure.polarization_horizontal * sigma * cosine
    )
    if np.any(vertical_rate <= 0.0) or np.any(horizontal_rate <= 0.0):
        raise ValueError("sigma gives non-positive polarized rate")
    return vertical_rate / (vertical_rate + horizontal_rate)


def _event_exposure_arrays(
    run_number: np.ndarray,
    xstrip: np.ndarray,
    exposures: Mapping[tuple[int, int], FluxExposure],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    missing = sorted(
        {
            (int(run), int(strip))
            for run, strip in zip(run_number, xstrip)
            if (int(run), int(strip)) not in exposures
        }
    )
    if missing:
        raise ValueError(f"missing exposure for event strata: {missing}")
    selected = [
        exposures[(int(run), int(strip))]
        for run, strip in zip(run_number, xstrip)
    ]
    return (
        np.fromiter((item.flux_vertical for item in selected), dtype=np.float64),
        np.fromiter((item.flux_horizontal for item in selected), dtype=np.float64),
        np.fromiter(
            (item.polarization_vertical for item in selected), dtype=np.float64
        ),
        np.fromiter(
            (item.polarization_horizontal for item in selected), dtype=np.float64
        ),
    )


def _positivity_domain(
    cosine: np.ndarray,
    polarization_vertical: np.ndarray,
    polarization_horizontal: np.ndarray,
) -> tuple[float, float]:
    lower = -np.inf
    upper = np.inf
    for coefficient in np.concatenate(
        (polarization_vertical * cosine, -polarization_horizontal * cosine)
    ):
        if coefficient > 0.0:
            lower = max(lower, -1.0 / coefficient)
        elif coefficient < 0.0:
            upper = min(upper, -1.0 / coefficient)
    if not np.isfinite(lower):
        lower = -5.0
    if not np.isfinite(upper):
        upper = 5.0
    epsilon = 1e-10 * max(1.0, abs(lower), abs(upper))
    return lower + epsilon, upper - epsilon


def fit_conditional_sigma(
    phi: np.ndarray,
    polarization: np.ndarray,
    run_number: np.ndarray,
    xstrip: np.ndarray,
    exposures: Mapping[tuple[int, int], FluxExposure],
) -> LikelihoodFitResult:
    phi = np.asarray(phi, dtype=np.float64)
    polarization = np.asarray(polarization, dtype=np.int64)
    run_number = np.asarray(run_number, dtype=np.int64)
    xstrip = np.asarray(xstrip, dtype=np.int64)
    if phi.ndim != 1 or any(
        array.shape != phi.shape for array in (polarization, run_number, xstrip)
    ):
        raise ValueError("likelihood event arrays must be matching one-dimensional arrays")
    if len(phi) == 0 or np.any(~np.isfinite(phi)):
        raise ValueError("likelihood requires finite events")
    if not np.all(np.isin(polarization, (1, 2))):
        raise ValueError("polarization states must be 1 or 2")

    flux_v, flux_h, pol_v, pol_h = _event_exposure_arrays(
        run_number, xstrip, exposures
    )
    cosine = np.cos(2.0 * phi)

    def nll(sigma: float) -> float:
        vertical_rate = flux_v * (1.0 + pol_v * sigma * cosine)
        horizontal_rate = flux_h * (1.0 - pol_h * sigma * cosine)
        if np.any(vertical_rate <= 0.0) or np.any(horizontal_rate <= 0.0):
            return float("inf")
        probability = vertical_rate / (vertical_rate + horizontal_rate)
        if np.any(probability <= 0.0) or np.any(probability >= 1.0):
            return float("inf")
        log_probability = np.where(
            polarization == 1,
            np.log(probability),
            np.log1p(-probability),
        )
        return -float(np.sum(log_probability))

    physical = minimize_scalar(
        nll,
        bounds=(-1.0, 1.0),
        method="bounded",
        options={"xatol": 1e-12},
    )
    if not physical.success or not np.isfinite(physical.fun):
        raise RuntimeError(f"conditional likelihood fit failed: {physical.message}")
    sigma = float(physical.x)
    minimum = float(physical.fun)
    target = minimum + 0.5

    def profile_root(value: float) -> float:
        return nll(value) - target

    if profile_root(-1.0) <= 0.0 or sigma <= -1.0 + 1e-10:
        interval_low = -1.0
    else:
        interval_low = float(brentq(profile_root, -1.0, sigma))
    if profile_root(1.0) <= 0.0 or sigma >= 1.0 - 1e-10:
        interval_high = 1.0
    else:
        interval_high = float(brentq(profile_root, sigma, 1.0))

    domain_low, domain_high = _positivity_domain(cosine, pol_v, pol_h)
    diagnostic = minimize_scalar(
        nll,
        bounds=(domain_low, domain_high),
        method="bounded",
        options={"xatol": 1e-12},
    )
    unbounded_sigma = float(diagnostic.x)
    at_lower = sigma <= -1.0 + 1e-4
    at_upper = sigma >= 1.0 - 1e-4
    pressure = (at_lower and unbounded_sigma < -1.0) or (
        at_upper and unbounded_sigma > 1.0
    )
    return LikelihoodFitResult(
        sigma=sigma,
        interval_low=interval_low,
        interval_high=interval_high,
        nll=minimum,
        converged=True,
        at_lower_boundary=at_lower,
        at_upper_boundary=at_upper,
        unbounded_sigma=unbounded_sigma,
        unbounded_nll=float(diagnostic.fun),
        pressure_against_boundary=pressure,
    )


def extract_likelihood_grid(
    *,
    pair: str,
    mass_gev: np.ndarray,
    phi_rad: np.ndarray,
    beam_energy_gev: np.ndarray,
    polarization: np.ndarray,
    run_number: np.ndarray,
    xstrip: np.ndarray,
    exposures: Mapping[tuple[int, int], FluxExposure],
) -> tuple[LikelihoodBinResult, ...]:
    mass_gev = np.asarray(mass_gev, dtype=np.float64)
    phi_rad = np.asarray(phi_rad, dtype=np.float64)
    beam_energy_gev = np.asarray(beam_energy_gev, dtype=np.float64)
    polarization = np.asarray(polarization, dtype=np.int64)
    run_number = np.asarray(run_number, dtype=np.int64)
    xstrip = np.asarray(xstrip, dtype=np.int64)
    arrays = (phi_rad, beam_energy_gev, polarization, run_number, xstrip)
    if any(array.shape != mass_gev.shape for array in arrays):
        raise ValueError("event arrays must have matching shapes")

    mass_edges = pair_mass_edges(pair)
    results = []
    for energy_bin, (energy_low, energy_high) in enumerate(
        zip(ENERGY_EDGES_GEV[:-1], ENERGY_EDGES_GEV[1:])
    ):
        energy_mask = (beam_energy_gev >= energy_low) & (
            (beam_energy_gev < energy_high)
            | ((energy_bin == len(ENERGY_EDGES_GEV) - 2) & (beam_energy_gev <= energy_high))
        )
        for mass_bin, (mass_low, mass_high) in enumerate(
            zip(mass_edges[:-1], mass_edges[1:])
        ):
            mass_mask = (mass_gev >= mass_low) & (
                (mass_gev < mass_high)
                | ((mass_bin == len(mass_edges) - 2) & (mass_gev <= mass_high))
            )
            selected = energy_mask & mass_mask & np.isin(polarization, (1, 2))
            if np.count_nonzero(selected) < 4:
                continue
            if not np.any(polarization[selected] == 1) or not np.any(
                polarization[selected] == 2
            ):
                continue
            fit = fit_conditional_sigma(
                phi_rad[selected],
                polarization[selected],
                run_number[selected],
                xstrip[selected],
                exposures,
            )
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
                stat_low=fit.sigma - fit.interval_low,
                stat_high=fit.interval_high - fit.sigma,
                diagnostics=FitDiagnostics(
                    converged=fit.converged,
                    chi2=0.0,
                    ndf=0,
                    p_value=1.0,
                    used_fallback=False,
                ),
            )
            results.append(
                LikelihoodBinResult(point, fit, int(np.count_nonzero(selected)))
            )
    return tuple(results)
