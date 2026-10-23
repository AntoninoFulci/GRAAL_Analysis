"""Partial unpolarized cross sections and invariant-mass spectra."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
from numpy.typing import NDArray

from .constants import GEV2_TO_MICROBARN
from .kinematics import invariant_mass, s_from_lab_photon_energy
from .models.eta_pi0_p import EtaPi0PModel
from .phase_space import SobolConfig, sample_three_body


@dataclass(frozen=True)
class HistogramSpec:
    bins: int = 16

    def __post_init__(self) -> None:
        if isinstance(self.bins, bool) or not isinstance(self.bins, int) or self.bins <= 0:
            raise ValueError("histogram bins must be a positive integer")


@dataclass(frozen=True)
class Histogram:
    edges: NDArray[np.float64]
    values: NDArray[np.float64]  # microbarn / GeV


@dataclass(frozen=True)
class Prediction:
    photon_energy_gev: float
    partial_cross_section_microbarn: float
    histograms: dict[str, Histogram]
    sobol_config: SobolConfig
    sample_size: int
    phase_space_volume_gev2: float


_PAIRS = {
    "eta_p": (0, 2, 1),
    "pi0_p": (1, 2, 0),
    "eta_pi0": (0, 1, 2),
}


def _histogram_edges(
    sqrt_s: float,
    masses: tuple[float, float, float],
    spec: HistogramSpec,
    *,
    below_threshold: bool,
) -> dict[str, NDArray[np.float64]]:
    result = {}
    for name, (first, second, spectator) in _PAIRS.items():
        minimum = masses[first] + masses[second]
        maximum = sqrt_s - masses[spectator]
        if below_threshold:
            result[name] = np.full(spec.bins + 1, minimum, dtype=np.float64)
        else:
            edges = np.linspace(minimum, maximum, spec.bins + 1)
            edges[0] = np.nextafter(edges[0], -np.inf)
            edges[-1] = np.nextafter(edges[-1], np.inf)
            result[name] = edges
    return result


def predict_energy(
    photon_energy_gev: float,
    model: EtaPi0PModel,
    config: SobolConfig,
    histogram_spec: HistogramSpec = HistogramSpec(),
) -> Prediction:
    proton_mass = model.parameters.proton_mass_gev
    s = s_from_lab_photon_energy(photon_energy_gev, proton_mass)
    sqrt_s = float(np.sqrt(s))
    masses = model.masses
    below_threshold = sqrt_s <= sum(masses)
    edges = _histogram_edges(sqrt_s, masses, histogram_spec, below_threshold=below_threshold)
    if below_threshold:
        empty = {name: Histogram(edge, np.zeros(histogram_spec.bins)) for name, edge in edges.items()}
        return Prediction(photon_energy_gev, 0.0, empty, config, 0, 0.0)

    sample = sample_three_body(sqrt_s, masses, config)
    amplitude2 = np.asarray(model.matrix_element_squared(sample), dtype=np.float64)
    if amplitude2.shape != (len(sample.momenta),):
        raise ValueError("matrix element must return one squared value per event")
    bad = np.flatnonzero(~np.isfinite(amplitude2))
    if len(bad):
        raise ValueError(
            f"nonfinite matrix element at E_gamma={photon_energy_gev} GeV, event={int(bad[0])}"
        )
    if np.any(amplitude2 < 0):
        raise ValueError("squared matrix element must be nonnegative")
    normalization = GEV2_TO_MICROBARN * 4.0 * proton_mass**2 / (2.0 * (s - proton_mass**2))
    per_event_microbarn = normalization * sample.weights_gev2 * amplitude2 / len(amplitude2)
    cross_section = float(np.sum(per_event_microbarn))
    histograms = {}
    for name, (first, second, _) in _PAIRS.items():
        masses_pair = invariant_mass(sample.momenta[:, first] + sample.momenta[:, second])
        binned, _ = np.histogram(masses_pair, bins=edges[name], weights=per_event_microbarn)
        values = binned / np.diff(edges[name])
        histograms[name] = Histogram(edges[name], values)
    return Prediction(
        photon_energy_gev, cross_section, histograms, config, len(amplitude2),
        float(np.mean(sample.weights_gev2)),
    )


def predict_grid(
    photon_energies_gev: Iterable[float],
    model: EtaPi0PModel,
    config: SobolConfig,
    histogram_spec: HistogramSpec = HistogramSpec(),
) -> list[Prediction]:
    return [predict_energy(float(energy), model, config, histogram_spec) for energy in photon_energies_gev]
