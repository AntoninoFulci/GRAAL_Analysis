"""Fixed-energy full-model mass density for the PRC73 Figure 18 guard."""

from __future__ import annotations

import numpy as np

from .constants import GEV2_TO_MICROBARN
from .figure18_reference import Figure18Point
from .kinematics import s_from_lab_photon_energy
from .phase_space import SobolConfig, sample_three_body_mass_window


def predict_figure18_density(model, mass_range_gev: tuple[float, float],
                             sobol: SobolConfig) -> float:
    """Average unpolarized dσ/dM in a bounded ηp window at Eγ=1.7 GeV."""
    if not isinstance(sobol, SobolConfig):
        raise ValueError("sobol requires SobolConfig")
    try:
        low, high = map(float, mass_range_gev)
    except (TypeError, ValueError) as exc:
        raise ValueError("mass window requires two finite bounds") from exc
    masses = model.masses
    if (not np.isfinite(low) or not np.isfinite(high)
            or low < masses[0]+masses[2] or low >= high or high > 1.80):
        raise ValueError("mass window must lie from eta-p threshold through 1.80 GeV")
    proton = model.parameters.proton_mass_gev
    s = s_from_lab_photon_energy(1.7, proton)
    sample = sample_three_body_mass_window(np.sqrt(s), masses, (0, 2),
                                           (low, high), sobol,
                                           reduce_global_azimuth=callable(
                                               getattr(model, "amplitude", None)))
    if sample is None:
        raise ValueError("mass window is kinematically inaccessible")
    squared = np.asarray(model.matrix_element_squared(sample), dtype=np.float64)
    if (squared.shape != (len(sample.momenta),)
            or not np.all(np.isfinite(squared)) or np.any(squared < 0)):
        raise ValueError("unpolarized matrix element requires finite nonnegative event weights")
    flux = GEV2_TO_MICROBARN*4*proton**2/(2*(s-proton**2))
    return float(flux*np.mean(sample.weights_gev2*squared)/(high-low))


def compare_figure18_point(point: Figure18Point, predicted_density: float | None,
                           numerical_bound: float | None) -> str:
    """Compare a pre-certified density with the independent source reading."""
    if not isinstance(point, Figure18Point):
        raise ValueError("Figure 18 comparison requires a source point")
    if predicted_density is None and numerical_bound is None:
        return "masked"
    if (predicted_density is None or numerical_bound is None
            or not np.isfinite(predicted_density) or predicted_density < 0
            or not np.isfinite(numerical_bound) or numerical_bound < 0):
        raise ValueError("Figure 18 comparison requires finite nonnegative prediction and bound")
    return ("compatible" if abs(predicted_density-point.dsigma_dmass_microbarn_per_gev)
            <= point.reading_error+numerical_bound else "discrepant")
