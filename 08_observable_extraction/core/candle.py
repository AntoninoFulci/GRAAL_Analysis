"""Data-driven axis-aligned candle selection in the raw eta/pi0 mass plane."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import curve_fit

from graal_common.physics.channels import ETA_PI0_HYP, M_ETA, M_PI0
from observable_extraction.io.reconstructed_events import EventArrays


MIN_FIT_ENTRIES = 40
FIT_MODEL = "gaussian_plus_linear_background"


@dataclass(frozen=True)
class MassResolutionFit:
    center_gev: float
    fitted_mean_gev: float
    sigma_gev: float
    fit_half_range_gev: float
    model: str = FIT_MODEL


@dataclass(frozen=True)
class CandleSplit:
    core: EventArrays
    tails: EventArrays
    eta_fit: MassResolutionFit
    pi0_fit: MassResolutionFit
    scale_factor: float
    distance_threshold: float
    finite_event_count: int
    excluded_nonfinite_count: int
    requested_core_fraction: float


def _gaussian_plus_linear(
    mass: np.ndarray,
    amplitude: float,
    mean: float,
    sigma: float,
    background: float,
    slope: float,
    *,
    center: float,
) -> np.ndarray:
    return (
        amplitude * np.exp(-0.5 * np.square((mass - mean) / sigma))
        + background
        + slope * (mass - center)
    )


def fit_mass_resolution(
    masses: np.ndarray,
    *,
    center_gev: float,
    half_range_gev: float,
    bins: int = 80,
) -> MassResolutionFit:
    """Fit a Gaussian peak plus linear background in a fixed mass range."""
    center = float(center_gev)
    half_range = float(half_range_gev)
    if not np.isfinite(center):
        raise ValueError("center_gev must be finite")
    if not np.isfinite(half_range) or half_range <= 0.0:
        raise ValueError("half_range_gev must be finite and positive")
    if isinstance(bins, (bool, np.bool_)) or not isinstance(
        bins, (int, np.integer)
    ) or bins < 10:
        raise ValueError("bins must be an integer of at least 10")

    values = np.asarray(masses, dtype=np.float64)
    if values.ndim != 1:
        raise ValueError("masses must be one-dimensional")
    selected = values[
        np.isfinite(values)
        & (values >= center - half_range)
        & (values <= center + half_range)
    ]
    if selected.size < MIN_FIT_ENTRIES:
        raise ValueError(
            f"insufficient mass entries for peak fit: {selected.size} "
            f"< {MIN_FIT_ENTRIES}"
        )

    counts, edges = np.histogram(
        selected,
        bins=int(bins),
        range=(center - half_range, center + half_range),
    )
    bin_centers = 0.5 * (edges[:-1] + edges[1:])
    bin_width = float(edges[1] - edges[0])
    background_guess = float(np.percentile(counts, 20.0))
    amplitude_guess = max(float(np.max(counts)) - background_guess, 1.0)
    # The global maximum may belong to a sloped background near a fit-range
    # edge.  The physical mass is always feasible for the bounded peak mean.
    mean_guess = center
    sigma_guess = half_range / 6.0
    slope_limit = max(float(np.max(counts)), 1.0) * 10.0 / half_range

    def model(mass, amplitude, mean, sigma, background, slope):
        return _gaussian_plus_linear(
            mass,
            amplitude,
            mean,
            sigma,
            background,
            slope,
            center=center,
        )

    try:
        parameters, covariance = curve_fit(
            model,
            bin_centers,
            counts.astype(np.float64),
            p0=(
                amplitude_guess,
                mean_guess,
                sigma_guess,
                background_guess,
                0.0,
            ),
            sigma=np.sqrt(np.maximum(counts, 1.0)),
            absolute_sigma=True,
            bounds=(
                (0.0, center - half_range / 4.0, bin_width / 2.0, 0.0, -slope_limit),
                (np.inf, center + half_range / 4.0, half_range / 2.0, np.inf, slope_limit),
            ),
            maxfev=20_000,
        )
    except (RuntimeError, ValueError, FloatingPointError) as error:
        raise ValueError(f"mass peak fit failed: {error}") from error

    amplitude, mean, sigma_value = map(float, parameters[:3])
    amplitude_error = float(np.sqrt(covariance[0, 0]))
    if not np.all(np.isfinite(parameters)) or not np.all(np.isfinite(covariance)):
        raise ValueError("mass peak fit returned non-finite parameters")
    if sigma_value <= 0.0:
        raise ValueError("mass peak fit returned non-positive sigma")
    if not np.isfinite(amplitude_error) or amplitude_error <= 0.0:
        raise ValueError("mass peak fit has invalid peak uncertainty")
    if amplitude / amplitude_error < 5.0:
        raise ValueError("mass peak fit has no significant Gaussian peak")

    return MassResolutionFit(
        center_gev=center,
        fitted_mean_gev=mean,
        sigma_gev=sigma_value,
        fit_half_range_gev=half_range,
    )


def _validated_fit(name: str, fit: MassResolutionFit) -> None:
    values = (
        fit.center_gev,
        fit.fitted_mean_gev,
        fit.sigma_gev,
        fit.fit_half_range_gev,
    )
    if not all(np.isfinite(value) for value in values):
        raise ValueError(f"{name} fit values must be finite")
    if fit.sigma_gev <= 0.0 or fit.fit_half_range_gev <= 0.0:
        raise ValueError(f"{name} fit scales must be positive")
    if fit.model != FIT_MODEL:
        raise ValueError(f"{name} fit model is unsupported: {fit.model}")


def split_by_fitted_ellipse(
    events: EventArrays,
    *,
    eta_fit: MassResolutionFit,
    pi0_fit: MassResolutionFit,
    core_fraction: float = 0.5,
) -> CandleSplit:
    """Split finite events at an empirical axis-aligned ellipse quantile."""
    fraction = float(core_fraction)
    if not np.isfinite(fraction) or not 0.0 < fraction < 1.0:
        raise ValueError("core_fraction must be finite and strictly between 0 and 1")
    _validated_fit("eta", eta_fit)
    _validated_fit("pi0", pi0_fit)

    finite = np.isfinite(events.eta_mass_gev) & np.isfinite(
        events.pi0_mass_gev
    )
    finite_count = int(np.count_nonzero(finite))
    excluded_count = int(len(events) - finite_count)
    target_core_count = int(np.floor(fraction * finite_count))
    if target_core_count <= 0 or target_core_count >= finite_count:
        raise ValueError(
            "insufficient finite events for requested candle split: "
            f"finite={finite_count} core_fraction={fraction}"
        )

    distances = np.full(len(events), np.nan, dtype=np.float64)
    distances[finite] = (
        np.square(
            (events.eta_mass_gev[finite] - eta_fit.center_gev)
            / eta_fit.sigma_gev
        )
        + np.square(
            (events.pi0_mass_gev[finite] - pi0_fit.center_gev)
            / pi0_fit.sigma_gev
        )
    )
    ordered = np.sort(distances[finite])
    lower = float(ordered[target_core_count - 1])
    upper = float(ordered[target_core_count])
    if not lower < upper:
        raise ValueError(
            "candle quantile boundary has a distance tie and cannot define "
            "a geometric split"
        )
    threshold = lower + 0.5 * (upper - lower)
    if not np.isfinite(threshold) or threshold <= 0.0:
        raise ValueError("candle distance threshold must be finite and positive")

    core_mask = finite & (distances <= threshold)
    tail_mask = finite & (distances > threshold)
    if int(np.count_nonzero(core_mask)) != target_core_count:
        raise RuntimeError("candle ellipse did not produce the requested core count")
    return CandleSplit(
        core=events.take(core_mask),
        tails=events.take(tail_mask),
        eta_fit=eta_fit,
        pi0_fit=pi0_fit,
        scale_factor=float(np.sqrt(threshold)),
        distance_threshold=threshold,
        finite_event_count=finite_count,
        excluded_nonfinite_count=excluded_count,
        requested_core_fraction=fraction,
    )


def split_candle_core_tails(
    events: EventArrays,
    *,
    core_fraction: float = 0.5,
) -> CandleSplit:
    """Fit both mass peaks and split events with their empirical 50% ellipse."""
    finite = np.isfinite(events.eta_mass_gev) & np.isfinite(
        events.pi0_mass_gev
    )
    eta_fit = fit_mass_resolution(
        events.eta_mass_gev[finite],
        center_gev=M_ETA,
        half_range_gev=ETA_PI0_HYP.heavy_window,
    )
    pi0_fit = fit_mass_resolution(
        events.pi0_mass_gev[finite],
        center_gev=M_PI0,
        half_range_gev=ETA_PI0_HYP.light_window,
    )
    return split_by_fitted_ellipse(
        events,
        eta_fit=eta_fit,
        pi0_fit=pi0_fit,
        core_fraction=core_fraction,
    )
