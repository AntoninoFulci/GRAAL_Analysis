"""Framework-native observables and panel fits for a Figure-4-style comparison."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np

from contracts import PolarizationContractError
from flux_ratio import fit_flux_ratio


PAIR_NAMES = ("p_pi0", "p_eta", "eta_pi0")


@dataclass(frozen=True)
class PairObservables:
    mass: np.ndarray
    phi: np.ndarray
    valid_phi: np.ndarray


@dataclass(frozen=True)
class PanelHistogram:
    vertical: np.ndarray
    horizontal: np.ndarray


@dataclass(frozen=True)
class PanelExposure:
    vertical_flux: float
    horizontal_flux: float
    vertical_polarization: float
    horizontal_polarization: float
    vertical_polarization_variance: float = 0.0
    horizontal_polarization_variance: float = 0.0
    vertical_polarization_weighting_bound: float = 0.0
    horizontal_polarization_weighting_bound: float = 0.0

    def __post_init__(self) -> None:
        values = (
            self.vertical_flux,
            self.horizontal_flux,
            self.vertical_polarization,
            self.horizontal_polarization,
            self.vertical_polarization_variance,
            self.horizontal_polarization_variance,
            self.vertical_polarization_weighting_bound,
            self.horizontal_polarization_weighting_bound,
        )
        if any(not np.isfinite(value) for value in values):
            raise PolarizationContractError("panel exposure values must be finite")
        if self.vertical_flux <= 0.0 or self.horizontal_flux <= 0.0:
            raise PolarizationContractError("panel flux must be positive")
        if (
            not 0.0 < self.vertical_polarization <= 1.0
            or not 0.0 < self.horizontal_polarization <= 1.0
        ):
            raise PolarizationContractError("panel polarization must lie in (0, 1]")
        if (
            self.vertical_polarization_variance < 0.0
            or self.horizontal_polarization_variance < 0.0
        ):
            raise PolarizationContractError("polarization variances must be nonnegative")
        if (
            self.vertical_polarization_weighting_bound < 0.0
            or self.horizontal_polarization_weighting_bound < 0.0
        ):
            raise PolarizationContractError("polarization weighting bounds must be nonnegative")


@dataclass(frozen=True)
class SigmaPoint:
    mass_low: float
    mass_high: float
    mass_center: float
    sigma: float
    stat_uncertainty: float
    valid: bool
    reason: str | None
    event_count: float
    fit_deviance: float
    fit_ndof: int


def physical_mass_edges(
    maximum_beam_energy_gev: float,
    *,
    bins: int,
    masses_gev: dict[str, float],
) -> dict[str, np.ndarray]:
    """Derive global pair-mass ranges from threshold and three-body limits."""
    if not np.isfinite(maximum_beam_energy_gev) or maximum_beam_energy_gev <= 0.0:
        raise PolarizationContractError("maximum beam energy must be positive")
    if isinstance(bins, bool) or not isinstance(bins, int) or bins < 1:
        raise PolarizationContractError("mass-bin count must be a positive integer")
    if set(masses_gev) != {"proton", "eta", "pi0"}:
        raise PolarizationContractError("masses_gev must define proton, eta, and pi0")
    masses = {name: float(value) for name, value in masses_gev.items()}
    if any(not np.isfinite(value) or value <= 0.0 for value in masses.values()):
        raise PolarizationContractError("particle masses must be finite and positive")
    proton = masses["proton"]
    total_energy = float(
        np.sqrt(proton**2 + 2.0 * proton * maximum_beam_energy_gev)
    )
    ranges = {
        "p_pi0": (proton + masses["pi0"], total_energy - masses["eta"]),
        "p_eta": (proton + masses["eta"], total_energy - masses["pi0"]),
        "eta_pi0": (masses["eta"] + masses["pi0"], total_energy - proton),
    }
    if any(high <= low for low, high in ranges.values()):
        raise PolarizationContractError("beam energy is below three-body threshold")
    return {
        name: np.linspace(low, high, bins + 1)
        for name, (low, high) in ranges.items()
    }


def _four_vectors(raw, label: str) -> np.ndarray:
    try:
        vectors = np.asarray(raw, dtype=float)
    except (TypeError, ValueError) as exc:
        raise PolarizationContractError(f"{label} must be numeric four-vectors") from exc
    if vectors.ndim != 2 or vectors.shape[1] != 4:
        raise PolarizationContractError(f"{label} must have shape (events, 4)")
    if not np.all(np.isfinite(vectors)):
        raise PolarizationContractError(f"{label} four-vectors must be finite")
    return vectors


def invariant_mass(four_vectors) -> np.ndarray:
    """Return invariant mass for `(px, py, pz, E)` rows."""
    vectors = _four_vectors(four_vectors, "input")
    mass_squared = vectors[:, 3] ** 2 - np.sum(vectors[:, :3] ** 2, axis=1)
    scale = np.maximum(1.0, vectors[:, 3] ** 2 + np.sum(vectors[:, :3] ** 2, axis=1))
    if np.any(mass_squared < -1e-10 * scale):
        raise PolarizationContractError("input contains spacelike four-vector")
    return np.sqrt(np.maximum(mass_squared, 0.0))


def _pair_observable(left: np.ndarray, right: np.ndarray, tolerance: float) -> PairObservables:
    pair = left + right
    transverse = np.hypot(pair[:, 0], pair[:, 1])
    valid = transverse > tolerance
    phi = np.full(pair.shape[0], np.nan)
    phi[valid] = np.mod(np.arctan2(pair[valid, 1], pair[valid, 0]), np.pi)
    phi[phi >= np.pi] = 0.0
    return PairObservables(invariant_mass(pair), phi, valid)


def event_pair_observables(
    proton,
    eta,
    pi0,
    *,
    tolerance: float = 1e-12,
) -> dict[str, PairObservables]:
    """Compute three pair masses and lab azimuths from reconstructed events."""
    if not np.isfinite(tolerance) or tolerance <= 0.0:
        raise PolarizationContractError("pair-plane tolerance must be positive")
    proton_vectors = _four_vectors(proton, "proton")
    eta_vectors = _four_vectors(eta, "eta")
    pi0_vectors = _four_vectors(pi0, "pi0")
    if len({array.shape for array in (proton_vectors, eta_vectors, pi0_vectors)}) != 1:
        raise PolarizationContractError("particle four-vector arrays must have same shape")
    return {
        "p_pi0": _pair_observable(proton_vectors, pi0_vectors, tolerance),
        "p_eta": _pair_observable(proton_vectors, eta_vectors, tolerance),
        "eta_pi0": _pair_observable(eta_vectors, pi0_vectors, tolerance),
    }


def _edges(
    raw,
    label: str,
    expected_start: float | None = None,
    expected_end: float | None = None,
) -> np.ndarray:
    values = np.asarray(raw, dtype=float)
    if values.ndim != 1 or values.size < 2 or not np.all(np.isfinite(values)):
        raise PolarizationContractError(f"{label} edges must be finite one-dimensional values")
    if not np.all(np.diff(values) > 0.0):
        raise PolarizationContractError(f"{label} edges must be strictly increasing")
    if expected_start is not None and not np.isclose(values[0], expected_start):
        raise PolarizationContractError(f"{label} edges must start at {expected_start}")
    if expected_end is not None and not np.isclose(values[-1], expected_end):
        raise PolarizationContractError(f"{label} edges must end at {expected_end}")
    return values


def histogram_panel(
    energy,
    mass,
    phi,
    orientation_sign,
    *,
    energy_range: tuple[float, float],
    mass_edges,
    phi_edges,
    final_energy_bin: bool = False,
) -> PanelHistogram:
    """Count events in mass/phi bins for positive(vertical) and negative(horizontal) states."""
    arrays = tuple(
        np.asarray(raw, dtype=float) for raw in (energy, mass, phi, orientation_sign)
    )
    if any(array.ndim != 1 for array in arrays) or len({array.shape for array in arrays}) != 1:
        raise PolarizationContractError("event observables must be same-shape vectors")
    energy_values, mass_values, phi_values, signs = arrays
    if not np.all(np.isfinite(energy_values)) or not np.all(np.isfinite(mass_values)):
        raise PolarizationContractError("energy and mass values must be finite")
    finite_phi_values = phi_values[np.isfinite(phi_values)]
    if np.any((finite_phi_values < 0.0) | (finite_phi_values >= np.pi)):
        raise PolarizationContractError("finite phi must lie in [0, pi)")
    if not np.all(np.isin(signs, (-1.0, 1.0))):
        raise PolarizationContractError("orientation_sign must be -1 or +1")
    mass_bins = _edges(mass_edges, "mass")
    phi_bins = _edges(phi_edges, "phi", 0.0, np.pi)
    low, high = map(float, energy_range)
    if not np.isfinite(low) or not np.isfinite(high) or high <= low:
        raise PolarizationContractError("energy range must have positive width")
    energy_mask = (energy_values >= low) & (
        energy_values <= high if final_energy_bin else energy_values < high
    )
    finite_phi = np.isfinite(phi_values)

    def counts_for(sign: float) -> np.ndarray:
        selected = energy_mask & finite_phi & (signs == sign)
        counts, _, _ = np.histogram2d(
            mass_values[selected],
            phi_values[selected],
            bins=(mass_bins, phi_bins),
        )
        return counts.astype(int)

    return PanelHistogram(vertical=counts_for(1.0), horizontal=counts_for(-1.0))


def fit_panel_histograms(
    vertical,
    horizontal,
    phi_centers,
    mass_edges,
    exposure: PanelExposure,
    *,
    phi_bin_widths=None,
) -> list[SigmaPoint]:
    """Fit every mass row of one energy/pair panel independently."""
    vertical_counts = np.asarray(vertical, dtype=float)
    horizontal_counts = np.asarray(horizontal, dtype=float)
    phi = np.asarray(phi_centers, dtype=float)
    edges = _edges(mass_edges, "mass")
    expected_shape = (edges.size - 1, phi.size)
    if vertical_counts.shape != expected_shape or horizontal_counts.shape != expected_shape:
        raise PolarizationContractError(
            f"panel count arrays must have shape {expected_shape}"
        )
    if phi_bin_widths is None:
        modulation_scale = np.ones(phi.shape)
    else:
        widths = np.asarray(phi_bin_widths, dtype=float)
        if widths.shape != phi.shape or not np.all(np.isfinite(widths)) or np.any(widths <= 0.0):
            raise PolarizationContractError(
                "phi_bin_widths must be positive and match phi centers"
            )
        modulation_scale = np.sin(widths) / widths
    points = []
    for index, (low, high) in enumerate(zip(edges, edges[1:])):
        nv = vertical_counts[index]
        nh = horizontal_counts[index]
        total = float(np.sum(nv + nh))
        if total <= 0.0:
            points.append(
                SigmaPoint(
                    float(low), float(high), float((low + high) / 2.0),
                    float("nan"), float("nan"), False, "empty mass bin", 0.0,
                    float("nan"), 0,
                )
            )
            continue
        try:
            fit = fit_flux_ratio(
                phi=phi,
                vertical=nv,
                horizontal=nh,
                flux_vertical=np.full(phi.shape, exposure.vertical_flux),
                flux_horizontal=np.full(phi.shape, exposure.horizontal_flux),
                polarization_vertical=np.full(phi.shape, exposure.vertical_polarization),
                polarization_horizontal=np.full(phi.shape, exposure.horizontal_polarization),
                modulation_scale=modulation_scale,
            )
        except PolarizationContractError as exc:
            points.append(
                SigmaPoint(
                    float(low), float(high), float((low + high) / 2.0),
                    float("nan"), float("nan"), False, str(exc), total,
                    float("nan"), 0,
                )
            )
            continue
        points.append(
            SigmaPoint(
                float(low), float(high), float((low + high) / 2.0),
                fit.sigma, fit.stat_uncertainty, True, None, total,
                fit.binomial_deviance, fit.ndof,
            )
        )
    return points


def analyze_sigma_grid(
    energy,
    proton,
    eta,
    pi0,
    orientation_sign,
    *,
    energy_ranges,
    mass_edges,
    phi_edges,
    exposures,
) -> dict[tuple[int, str], list[SigmaPoint]]:
    """Build and fit every energy-by-pair panel from reconstructed events."""
    energy_values = np.asarray(energy, dtype=float)
    signs = np.asarray(orientation_sign, dtype=float)
    if energy_values.ndim != 1 or signs.shape != energy_values.shape:
        raise PolarizationContractError(
            "energy and orientation_sign must be same-shape vectors"
        )
    if not np.all(np.isfinite(energy_values)):
        raise PolarizationContractError("beam energy must be finite")
    observables = event_pair_observables(proton, eta, pi0)
    if any(item.mass.shape != energy_values.shape for item in observables.values()):
        raise PolarizationContractError(
            "event four-vectors must match energy-vector length"
        )
    ranges = tuple(energy_ranges)
    panel_exposures = tuple(exposures)
    if len(ranges) != len(panel_exposures):
        raise PolarizationContractError(
            "one panel exposure is required for each energy range"
        )
    mass_edge_rows = tuple(mass_edges)
    if len(mass_edge_rows) != len(ranges) or any(
        not isinstance(row_edges, Mapping) or set(row_edges) != set(PAIR_NAMES)
        for row_edges in mass_edge_rows
    ):
        raise PolarizationContractError(
            "mass_edges must define every pair for each energy range"
        )
    phi_bins = _edges(phi_edges, "phi", 0.0, np.pi)
    centers = 0.5 * (phi_bins[:-1] + phi_bins[1:])
    results = {}
    for row, (energy_range, exposure) in enumerate(zip(ranges, panel_exposures)):
        row_mass_edges = mass_edge_rows[row]
        for pair in PAIR_NAMES:
            observable = observables[pair]
            histogram = histogram_panel(
                energy_values,
                observable.mass,
                observable.phi,
                signs,
                energy_range=energy_range,
                mass_edges=row_mass_edges[pair],
                phi_edges=phi_bins,
                final_energy_bin=row == len(ranges) - 1,
            )
            results[(row, pair)] = fit_panel_histograms(
                histogram.vertical,
                histogram.horizontal,
                centers,
                row_mass_edges[pair],
                exposure,
                phi_bin_widths=np.diff(phi_bins),
            )
    return results
