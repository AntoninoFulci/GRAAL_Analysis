"""Beam asymmetry of the Eq. 43 partial model in invariant-mass bins."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from .constants import GEV2_TO_MICROBARN
from .kinematics import invariant_mass, s_from_lab_photon_energy
from .models.eta_pi0_p import EtaPi0PModel
from .phase_space import SobolConfig, sample_three_body
from .photon_flux import FluxSpectrum, group_flux_by_energy

_PAIR_PARTICLES = {"eta_p": (0, 2), "pi0_p": (1, 2), "eta_pi0": (0, 1)}
_HORIZONTAL = np.array([1.0, 0.0, 0.0])
_VERTICAL = np.array([0.0, 1.0, 0.0])


def fit_binned_asymmetry(vertical_counts, horizontal_counts, flux_vertical, flux_horizontal, polarization_vertical, polarization_horizontal, phi_edges_rad):
    """Nominal Stage-07-style inverse-variance cos(2φ) fit at bin centers."""
    v = np.asarray(vertical_counts, dtype=np.float64)
    h = np.asarray(horizontal_counts, dtype=np.float64)
    edges = np.asarray(phi_edges_rad, dtype=np.float64)
    if v.ndim != 1 or h.shape != v.shape or edges.shape != (len(v) + 1,):
        raise ValueError("phi counts and edges have incompatible shapes")
    if np.any(~np.isfinite(v)) or np.any(~np.isfinite(h)) or np.any(v < 0) or np.any(h < 0):
        raise ValueError("phi counts must be finite and nonnegative")
    if not np.all(np.isfinite(edges)) or np.any(np.diff(edges) <= 0):
        raise ValueError("phi edges must increase")
    if not all(np.isfinite(value) and value > 0 for value in (flux_vertical, flux_horizontal)):
        raise ValueError("flux must be positive and finite")
    if not all(np.isfinite(value) and 0 < value <= 1 for value in (polarization_vertical, polarization_horizontal)):
        raise ValueError("polarization must lie in (0, 1]")
    yv, yh = v / flux_vertical, h / flux_horizontal
    denominator = polarization_horizontal * yv + polarization_vertical * yh
    valid = denominator > 0
    derivative_v = np.zeros_like(v)
    derivative_h = np.zeros_like(h)
    derivative_v[valid] = (
        (polarization_horizontal + polarization_vertical) * yh[valid]
        / denominator[valid] ** 2 / flux_vertical
    )
    derivative_h[valid] = -(
        (polarization_horizontal + polarization_vertical) * yv[valid]
        / denominator[valid] ** 2 / flux_horizontal
    )
    variance = derivative_v**2 * v + derivative_h**2 * h
    used = valid & (variance > 0) & np.isfinite(variance)
    if np.count_nonzero(used) < 2:
        raise ValueError("not enough populated phi bins for fit")
    ratio = (yv[used] - yh[used]) / denominator[used]
    cosine = np.cos(edges[:-1] + edges[1:])[used]
    weight = 1.0 / variance[used]
    return float(np.sum(weight * cosine * ratio) / np.sum(weight * cosine**2))


@dataclass(frozen=True)
class BeamAsymmetryPrediction:
    pair: str
    energy_range_gev: tuple[float, float]
    mass_edges_gev: NDArray[np.float64]
    sigma: NDArray[np.float64]
    energy_nodes_gev: NDArray[np.float64]
    sobol_config: SobolConfig
    energy_weighting: str = "uniform"
    sigma_phi_fit: NDArray[np.float64] | None = None


def _validate_mass_edges(edges: NDArray[np.float64]) -> NDArray[np.float64]:
    edges = np.asarray(edges, dtype=np.float64)
    if edges.ndim != 1 or len(edges) < 2 or not np.all(np.isfinite(edges)) or np.any(np.diff(edges) <= 0):
        raise ValueError("mass edges must be a finite increasing one-dimensional array")
    return edges


def _polarized_moments(
    mass_gev: NDArray[np.float64],
    phi_rad: NDArray[np.float64],
    vertical_weights: NDArray[np.float64],
    horizontal_weights: NDArray[np.float64],
    mass_edges_gev: NDArray[np.float64],
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    mass = np.asarray(mass_gev, dtype=np.float64)
    phi = np.asarray(phi_rad, dtype=np.float64)
    vertical = np.asarray(vertical_weights, dtype=np.float64)
    horizontal = np.asarray(horizontal_weights, dtype=np.float64)
    if mass.ndim != 1 or any(value.shape != mass.shape for value in (phi, vertical, horizontal)):
        raise ValueError("mass, azimuth, and polarized weights must be matching vectors")
    if any(np.any(~np.isfinite(value)) for value in (mass, phi, vertical, horizontal)):
        raise ValueError("mass, azimuth, and polarized weights must be finite")
    if np.any(vertical < 0.0) or np.any(horizontal < 0.0):
        raise ValueError("polarized weights must be nonnegative")
    edges = _validate_mass_edges(mass_edges_gev)
    numerator, _ = np.histogram(
        mass, bins=edges, weights=2.0 * np.cos(2.0 * phi) * (vertical - horizontal)
    )
    denominator, _ = np.histogram(mass, bins=edges, weights=vertical + horizontal)
    return numerator, denominator


def asymmetry_from_polarized_weights(
    mass_gev: NDArray[np.float64],
    phi_rad: NDArray[np.float64],
    vertical_weights: NDArray[np.float64],
    horizontal_weights: NDArray[np.float64],
    mass_edges_gev: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Return Sigma from the V−H cos(2φ) moment; unsupported bins are NaN."""
    numerator, denominator = _polarized_moments(
        mass_gev, phi_rad, vertical_weights, horizontal_weights, mass_edges_gev
    )
    return np.divide(
        numerator, denominator,
        out=np.full_like(denominator, np.nan),
        where=denominator > 0.0,
    )


def _polarized_event_weights(
    energy: float, pair: str, model: EtaPi0PModel, config: SobolConfig,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]] | None:
    proton_mass = model.parameters.proton_mass_gev
    s = s_from_lab_photon_energy(energy, proton_mass)
    sqrt_s = float(np.sqrt(s))
    if sqrt_s <= sum(model.masses):
        return None
    sample = sample_three_body(sqrt_s, model.masses, config)
    first, second = _PAIR_PARTICLES[pair]
    pair_momentum = sample.momenta[:, first] + sample.momenta[:, second]
    mass = invariant_mass(pair_momentum)
    phi = np.arctan2(pair_momentum[:, 2], pair_momentum[:, 1])
    normalization = (
        GEV2_TO_MICROBARN * 4.0 * proton_mass**2
        / (2.0 * (s - proton_mass**2) * len(sample.momenta))
    )
    amplitudes = []
    for name, polarization in (("vertical", _VERTICAL), ("horizontal", _HORIZONTAL)):
        values = np.asarray(model.polarized_matrix_element_squared(sample, polarization), dtype=np.float64)
        if values.shape != (len(sample.momenta),):
            raise ValueError(f"{name} matrix element must return one squared value per event")
        bad = np.flatnonzero(~np.isfinite(values) | (values < 0.0))
        if len(bad):
            raise ValueError(
                f"nonfinite or negative {name} squared matrix element at "
                f"E_gamma={energy:.8g} GeV, event={int(bad[0])}"
            )
        amplitudes.append(normalization * sample.weights_gev2 * values)
    return mass, phi, amplitudes[0], amplitudes[1]


def predict_beam_asymmetry(
    energy_low_gev: float,
    energy_high_gev: float,
    pair: str,
    mass_edges_gev: NDArray[np.float64],
    model: EtaPi0PModel,
    config: SobolConfig,
    *,
    energy_nodes: int = 3,
) -> BeamAsymmetryPrediction:
    """Uniform-energy average of polarized cross sections, then form Sigma."""
    if (
        not np.isfinite(energy_low_gev)
        or not np.isfinite(energy_high_gev)
        or energy_low_gev <= 0.0
        or energy_high_gev <= energy_low_gev
    ):
        raise ValueError("energy interval must have finite positive bounds and width")
    if pair not in _PAIR_PARTICLES:
        raise ValueError(f"unknown pair: {pair}")
    edges = _validate_mass_edges(mass_edges_gev)
    if isinstance(energy_nodes, bool) or not isinstance(energy_nodes, int) or energy_nodes <= 0:
        raise ValueError("energy_nodes must be a positive integer")

    nodes, quadrature_weights = np.polynomial.legendre.leggauss(energy_nodes)
    energies = (energy_low_gev + energy_high_gev) / 2.0 + (energy_high_gev - energy_low_gev) / 2.0 * nodes
    quadrature_weights /= 2.0  # expectation over uniform photon energy
    numerator = np.zeros(len(edges) - 1, dtype=np.float64)
    denominator = np.zeros(len(edges) - 1, dtype=np.float64)
    proton_mass = model.parameters.proton_mass_gev
    first, second = _PAIR_PARTICLES[pair]

    for energy, energy_weight in zip(energies, quadrature_weights):
        sampled = _polarized_event_weights(float(energy), pair, model, config)
        if sampled is None:
            continue
        mass, phi, vertical, horizontal = sampled
        node_numerator, node_denominator = _polarized_moments(
            mass, phi, vertical, horizontal, edges
        )
        numerator += energy_weight * node_numerator
        denominator += energy_weight * node_denominator

    sigma = np.divide(
        numerator, denominator,
        out=np.full_like(denominator, np.nan),
        where=denominator > 0.0,
    )
    spectator = 3 - first - second
    minimum_mass = model.masses[first] + model.masses[second]
    maximum_mass = np.sqrt(s_from_lab_photon_energy(energy_high_gev, proton_mass)) - model.masses[spectator]
    reachable = (edges[1:] > minimum_mass) & (edges[:-1] < maximum_mass)
    unsampled = np.flatnonzero(reachable & (denominator == 0.0))
    if len(unsampled):
        index = int(unsampled[0])
        raise ValueError(
            f"reachable mass bin {index} [{edges[index]:.3f}, {edges[index + 1]:.3f}] GeV "
            "has no sampled weight; increase energy_nodes or Sobol power"
        )
    unphysical = np.flatnonzero(np.isfinite(sigma) & (np.abs(sigma) > 1.0 + 1e-12))
    if len(unphysical):
        index = int(unphysical[0])
        raise ValueError(
            f"mass bin {index} has Sigma={sigma[index]:.3f} outside [-1, 1]; "
            "increase energy_nodes or Sobol power"
        )
    return BeamAsymmetryPrediction(
        pair, (energy_low_gev, energy_high_gev), edges.copy(), sigma,
        energies, config,
    )


def predict_flux_weighted_asymmetry(
    spectrum: FluxSpectrum,
    pair: str,
    mass_edges_gev: NDArray[np.float64],
    model: EtaPi0PModel,
    config: SobolConfig,
    *,
    energy_bins: int = 9,
) -> BeamAsymmetryPrediction:
    """Predict intrinsic flux-weighted moment and nominal 12-bin ratio fit.

    Each measured state has its own energy spectrum and polarization. Model
    cross sections are evaluated at measured-flux centroids of energy slices.
    """
    if pair not in _PAIR_PARTICLES:
        raise ValueError(f"unknown pair: {pair}")
    edges = _validate_mass_edges(mass_edges_gev)
    nodes = group_flux_by_energy(spectrum, energy_bins)
    if not nodes:
        raise ValueError("no measured flux nodes")
    phi_edges = np.linspace(0.0, 2.0 * np.pi, 13)
    shape = (len(edges) - 1, 12)
    counts_v = np.zeros(shape)
    counts_h = np.zeros(shape)
    numerator = np.zeros(len(edges) - 1)
    denominator = np.zeros(len(edges) - 1)
    total_v = sum(node.flux_vertical for node in nodes)
    total_h = sum(node.flux_horizontal for node in nodes)
    total_flux = total_v + total_h
    effective_pv = sum(node.flux_vertical * node.polarization_vertical for node in nodes) / total_v
    effective_ph = sum(node.flux_horizontal * node.polarization_horizontal for node in nodes) / total_h

    for node in nodes:
        sampled = _polarized_event_weights(node.energy_gev, pair, model, config)
        if sampled is None:
            continue
        mass, phi, vertical, horizontal = sampled
        intrinsic_weight = (node.flux_vertical + node.flux_horizontal) / total_flux
        node_numerator, node_denominator = _polarized_moments(mass, phi, vertical, horizontal, edges)
        numerator += intrinsic_weight * node_numerator
        denominator += intrinsic_weight * node_denominator
        unpolarized = 0.5 * (vertical + horizontal)
        polarized = 0.5 * (vertical - horizontal)
        wrapped_phi = np.mod(phi, 2.0 * np.pi)
        counts_v += node.flux_vertical * np.histogram2d(
            mass, wrapped_phi, bins=(edges, phi_edges),
            weights=unpolarized + node.polarization_vertical * polarized,
        )[0]
        counts_h += node.flux_horizontal * np.histogram2d(
            mass, wrapped_phi, bins=(edges, phi_edges),
            weights=unpolarized - node.polarization_horizontal * polarized,
        )[0]

    sigma = np.divide(numerator, denominator, out=np.full_like(denominator, np.nan), where=denominator > 0)
    sigma_fit = np.full_like(sigma, np.nan)
    for index in np.flatnonzero(denominator > 0):
        sigma_fit[index] = fit_binned_asymmetry(
            counts_v[index], counts_h[index], total_v, total_h,
            effective_pv, effective_ph, phi_edges,
        )
    first, second = _PAIR_PARTICLES[pair]
    spectator = 3 - first - second
    minimum_mass = model.masses[first] + model.masses[second]
    maximum_mass = np.sqrt(s_from_lab_photon_energy(spectrum.energy_range_gev[1], model.parameters.proton_mass_gev)) - model.masses[spectator]
    reachable = (edges[1:] > minimum_mass) & (edges[:-1] < maximum_mass)
    unsampled = np.flatnonzero(reachable & (denominator == 0.0))
    if len(unsampled):
        raise ValueError(f"reachable mass bin {int(unsampled[0])} has no sampled weight; increase energy bins or Sobol power")
    unphysical = np.flatnonzero(np.isfinite(sigma) & (np.abs(sigma) > 1.0 + 1e-12))
    if len(unphysical):
        raise ValueError(f"mass bin {int(unphysical[0])} has Sigma outside [-1, 1]; increase resolution")
    return BeamAsymmetryPrediction(
        pair, spectrum.energy_range_gev, edges.copy(), sigma,
        np.array([node.energy_gev for node in nodes]), config,
        "measured_P_UV_flux", sigma_fit,
    )
