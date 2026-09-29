"""Raw-mass sidebands, template fractions, and asymmetry correction."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math

import numpy as np
from scipy.optimize import minimize_scalar


class Region(Enum):
    SIGNAL = "signal"
    HARD_SIDEBAND = "hard_sideband"
    TRANSITION = "transition"
    OUTSIDE = "outside"


@dataclass(frozen=True)
class SidebandWindows:
    eta_center: float
    eta_half_width: float
    pi0_center: float
    pi0_half_width: float
    missing_center: float
    missing_half_width: float

    def __post_init__(self) -> None:
        values = (
            self.eta_center,
            self.eta_half_width,
            self.pi0_center,
            self.pi0_half_width,
            self.missing_center,
            self.missing_half_width,
        )
        if not all(math.isfinite(value) for value in values):
            raise ValueError("sideband windows must be finite")
        if min(
            self.eta_half_width,
            self.pi0_half_width,
            self.missing_half_width,
        ) <= 0.0:
            raise ValueError("sideband half-widths must be positive")


@dataclass(frozen=True)
class BackgroundEstimate:
    fraction: float
    error: float
    nll: float
    converged: bool


def factorized_sideband_template(
    hard_sideband_hist: np.ndarray,
    *,
    pseudocount: float = 0.5,
) -> np.ndarray:
    """Extrapolate hard sidebands with product of three fitted marginals.

    Hard-sideband definition leaves signal cube empty by construction. Product
    model uses all three observed one-dimensional marginals and Jeffreys
    pseudocount, allowing explicit interpolation into signal cube.
    """
    histogram = np.asarray(hard_sideband_hist, dtype=np.float64)
    if histogram.ndim != 3:
        raise ValueError("hard-sideband histogram must be three-dimensional")
    if np.any(~np.isfinite(histogram)) or np.any(histogram < 0.0):
        raise ValueError("hard-sideband histogram must be finite and non-negative")
    if histogram.sum() <= 0.0:
        raise ValueError("hard-sideband histogram must contain events")
    if not math.isfinite(pseudocount) or pseudocount < 0.0:
        raise ValueError("pseudocount must be finite and non-negative")
    marginals = []
    for axis in range(3):
        summed = histogram.sum(axis=tuple(index for index in range(3) if index != axis))
        summed = summed + pseudocount
        if summed.sum() <= 0.0:
            raise ValueError("sideband marginal has zero integral")
        marginals.append(summed / summed.sum())
    template = np.einsum("i,j,k->ijk", *marginals)
    return template / template.sum()


def fraction_in_mask(
    broad_fraction: float,
    signal_template: np.ndarray,
    background_template: np.ndarray,
    mask: np.ndarray,
) -> float:
    """Convert fitted broad-region mixture fraction into selected-region fraction."""
    if not 0.0 <= broad_fraction <= 1.0:
        raise ValueError("broad_fraction must be in [0, 1]")
    signal = np.asarray(signal_template, dtype=np.float64)
    background = np.asarray(background_template, dtype=np.float64)
    selected = np.asarray(mask, dtype=bool)
    if signal.shape != background.shape or signal.shape != selected.shape:
        raise ValueError("templates and mask must have matching shapes")
    if np.any(~np.isfinite(signal)) or np.any(signal < 0.0):
        raise ValueError("signal template must be finite and non-negative")
    if np.any(~np.isfinite(background)) or np.any(background < 0.0):
        raise ValueError("background template must be finite and non-negative")
    if signal.sum() <= 0.0 or background.sum() <= 0.0:
        raise ValueError("templates must have positive integrals")
    signal = signal / signal.sum()
    background = background / background.sum()
    signal_yield = (1.0 - broad_fraction) * float(signal[selected].sum())
    background_yield = broad_fraction * float(background[selected].sum())
    denominator = signal_yield + background_yield
    if denominator <= 0.0:
        raise ValueError("selected region has zero expected yield")
    return background_yield / denominator


def classify_region(
    *,
    eta_mass: float,
    pi0_mass: float,
    missing_mass: float,
    windows: SidebandWindows,
) -> Region:
    values = (eta_mass, pi0_mass, missing_mass)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("sideband masses must be finite")
    pulls = np.abs(
        np.array(
            [
                (eta_mass - windows.eta_center) / windows.eta_half_width,
                (pi0_mass - windows.pi0_center) / windows.pi0_half_width,
                (missing_mass - windows.missing_center)
                / windows.missing_half_width,
            ]
        )
    )
    if np.all(pulls < 1.0):
        return Region.SIGNAL
    if np.all(pulls < 4.0) and np.count_nonzero((pulls >= 2.0) & (pulls < 4.0)) >= 2:
        return Region.HARD_SIDEBAND
    if np.all(pulls < 4.0):
        return Region.TRANSITION
    return Region.OUTSIDE


def fit_background_fraction(
    data_hist: np.ndarray,
    signal_template: np.ndarray,
    background_template: np.ndarray,
) -> BackgroundEstimate:
    data = np.asarray(data_hist, dtype=np.float64)
    signal = np.asarray(signal_template, dtype=np.float64)
    background = np.asarray(background_template, dtype=np.float64)
    if data.shape != signal.shape or data.shape != background.shape:
        raise ValueError("data and templates must have matching shapes")
    if np.any(~np.isfinite(data)) or np.any(data < 0.0):
        raise ValueError("data histogram must be finite and non-negative")
    if np.any(~np.isfinite(signal)) or np.any(signal < 0.0):
        raise ValueError("signal template must be finite and non-negative")
    if np.any(~np.isfinite(background)) or np.any(background < 0.0):
        raise ValueError("background template must be finite and non-negative")
    total = float(np.sum(data))
    if total <= 0.0 or signal.sum() <= 0.0 or background.sum() <= 0.0:
        raise ValueError("data and templates must have positive integrals")
    signal = signal / signal.sum()
    background = background / background.sum()

    def nll(fraction: float) -> float:
        expectation = total * ((1.0 - fraction) * signal + fraction * background)
        if np.any((expectation <= 0.0) & (data > 0.0)):
            return float("inf")
        positive = expectation > 0.0
        return float(
            np.sum(expectation[positive] - data[positive] * np.log(expectation[positive]))
        )

    result = minimize_scalar(
        nll,
        bounds=(0.0, 1.0),
        method="bounded",
        options={"xatol": 1e-12},
    )
    fraction = float(result.x)
    mixture = (1.0 - fraction) * signal + fraction * background
    difference = background - signal
    positive = mixture > 0.0
    curvature = float(
        np.sum(data[positive] * (difference[positive] / mixture[positive]) ** 2)
    )
    error = 1.0 / math.sqrt(curvature) if curvature > 0.0 else float("inf")
    return BackgroundEstimate(
        fraction=fraction,
        error=error,
        nll=float(result.fun),
        converged=bool(result.success),
    )


def correct_sigma(
    sigma_observed: float,
    background_fraction: float,
    sigma_background: float,
) -> float:
    if not 0.0 <= background_fraction < 1.0:
        raise ValueError("background_fraction must be in [0, 1)")
    return (sigma_observed - background_fraction * sigma_background) / (
        1.0 - background_fraction
    )


def correct_sigma_with_uncertainty(
    *,
    sigma_observed: float,
    observed_error: float,
    background_fraction: float,
    fraction_error: float,
    sigma_background: float,
    background_error: float,
) -> tuple[float, float]:
    corrected = correct_sigma(
        sigma_observed, background_fraction, sigma_background
    )
    if min(observed_error, fraction_error, background_error) < 0.0:
        raise ValueError("uncertainties must be non-negative")
    remaining = 1.0 - background_fraction
    variance = (
        (observed_error / remaining) ** 2
        + (background_fraction * background_error / remaining) ** 2
        + (
            (sigma_observed - sigma_background)
            * fraction_error
            / remaining**2
        )
        ** 2
    )
    return corrected, math.sqrt(variance)


def signal_leakage_fraction(regions: np.ndarray) -> float:
    regions = np.asarray(regions, dtype=object)
    if regions.size == 0:
        raise ValueError("signal MC region sample is empty")
    return float(np.mean(regions == Region.HARD_SIDEBAND))


def validate_signal_leakage(
    regions: np.ndarray,
    *,
    maximum: float = 0.05,
) -> float:
    if not 0.0 <= maximum < 1.0:
        raise ValueError("maximum leakage must be in [0, 1)")
    leakage = signal_leakage_fraction(regions)
    if leakage > maximum:
        raise ValueError(
            f"hard-sideband signal leakage {leakage:.3%} exceeds {maximum:.3%}"
        )
    return leakage
