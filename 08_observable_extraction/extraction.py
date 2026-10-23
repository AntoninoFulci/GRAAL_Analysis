"""Public event-array extraction engine shared by analysis and diagnostics."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from graal_common.parallel import validate_workers
from observable_extraction.core.binning import (
    PHI_EDGES_RAD, PHI_BIN_CHOICES, PAIR_NAMES, energy_bin_index,
    pair_mass_edges, phi_edges_rad,
)
from observable_extraction.core.conditional_likelihood import extract_likelihood_grid
from observable_extraction.core.kinematics import project_all_pairs
from observable_extraction.core.models import FluxExposure
from observable_extraction.core.ratio_fit import extract_ratio_grid, binning_quality_key
from observable_extraction.io.reconstructed_events import EventArrays
from observable_extraction.io.root_output import OutputPoint, RatioObject


@dataclass(frozen=True)
class ExtractionBundle:
    points: tuple[OutputPoint, ...]
    ratio_objects: tuple[RatioObject, ...]
    binning_candidates: tuple[OutputPoint, ...] = ()
    candidate_ratio_objects: tuple[RatioObject, ...] = ()


def extract_sample(
    *,
    sample_name: str,
    events: EventArrays,
    exposures: Mapping[tuple[int, int], FluxExposure],
    estimator: str,
    retain_ratio_objects: bool,
    energy_edges: np.ndarray,
    phi_edges: np.ndarray = PHI_EDGES_RAD,
    best_binning: bool = False,
    selected_phi_bins: dict[tuple[str, int, int], int] | None = None,
    workers: int = 1,
) -> ExtractionBundle:
    """Project once, then fit all requested binnings on the same selected events.

    selected_phi_bins freezes the nominal choice for sideband and systematic
    controls. Missing fixed-bin fits remain missing; never substitute another
    binning silently. Bootstrap replicas instead repeat the best-bin selection.
    """
    validate_workers(workers)
    projections = project_all_pairs(events.proton, events.eta, events.pi0)
    output_points, ratio_objects, candidates, candidate_objects = [], [], [], []
    if selected_phi_bins is not None:
        binnings = {n: phi_edges_rad(n) for n in sorted(set(selected_phi_bins.values()))}
    elif best_binning:
        binnings = {n: phi_edges_rad(n) for n in PHI_BIN_CHOICES}
    else:
        binnings = {len(phi_edges) - 1: phi_edges}

    for pair in PAIR_NAMES:
        masses, phis = projections[pair]
        results_by_key = {}
        for bins, edges in binnings.items():
            results = extract_ratio_grid(
                pair=pair, mass_gev=masses, phi_rad=phis,
                beam_energy_gev=events.beam_energy_gev,
                polarization=events.polarization, exposures=exposures,
                energy_edges=energy_edges, phi_edges=edges,
                workers=workers,
            )
            for item in results:
                key = (pair, item.point.energy_bin, item.point.mass_bin)
                results_by_key.setdefault(key, []).append((bins, item))
                if best_binning and estimator in {"ratio", "both"}:
                    candidates.append(_ratio_output_point(sample_name, item))
                    if retain_ratio_objects:
                        candidate_objects.append(_ratio_object(item, edges))
        for key, available in results_by_key.items():
            if selected_phi_bins is not None:
                available = [(n, item) for n, item in available if n == selected_phi_bins.get(key)]
            elif best_binning:
                available = [(n, item) for n, item in available
                             if item.fit.diagnostics.converged and item.fit.diagnostics.ndf > 0]
                available.sort(key=lambda entry: binning_quality_key(entry[1].fit.diagnostics, entry[0]))
            if not available:
                continue
            bins, item = available[0]
            if estimator in {"ratio", "both"}:
                output_points.append(_ratio_output_point(sample_name, item))
                if retain_ratio_objects:
                    ratio_objects.append(_ratio_object(item, binnings[bins]))
        if estimator in {"likelihood", "both"}:
            likelihood_results = extract_likelihood_grid(
                pair=pair, mass_gev=masses, phi_rad=phis,
                beam_energy_gev=events.beam_energy_gev,
                polarization=events.polarization, run_number=events.run_number,
                xstrip=events.xstrip, exposures=exposures, energy_edges=energy_edges,
                workers=workers,
            )
            output_points.extend(
                _likelihood_output_point(
                    sample_name, item, events=events, masses=masses,
                    exposures=exposures, energy_edges=energy_edges,
                )
                for item in likelihood_results
            )
    return ExtractionBundle(tuple(output_points), tuple(ratio_objects),
                            tuple(candidates), tuple(candidate_objects))


def _ratio_object(item, edges) -> RatioObject:
    used = item.fit.used_mask
    centers = 0.5 * (edges[:-1] + edges[1:])
    return RatioObject(
        pair=item.point.pair, energy_bin=item.point.energy_bin,
        mass_bin=item.point.mass_bin, phi=centers[used],
        value=item.fit.ratio[used], error=item.fit.ratio_error[used],
        sigma=item.fit.sigma, phi_bins=len(edges) - 1,
        c0=item.fit.diagnostics.c0 or 0.0, s2=item.fit.diagnostics.s2 or 0.0,
    )


def _ratio_output_point(sample: str, result) -> OutputPoint:
    point = result.point
    return OutputPoint(
        sample=sample,
        estimator="ratio",
        phi_bins=len(result.counts_vertical),
        point=point,
        sigma_uncorrected=point.sigma,
        systematic_total=0.0,
        background_fraction=0.0,
        count_vertical=int(np.sum(result.counts_vertical)),
        count_horizontal=int(np.sum(result.counts_horizontal)),
        flux_vertical=result.flux_vertical,
        flux_horizontal=result.flux_horizontal,
        polarization_vertical=result.polarization_vertical,
        polarization_horizontal=result.polarization_horizontal,
    )


def _likelihood_output_point(
    sample: str, result, *, events, masses, exposures, energy_edges,
) -> OutputPoint:
    point = result.point
    energy = events.beam_energy_gev
    energy_mask = (energy >= point.energy_low_gev) & (
        (energy < point.energy_high_gev)
        | ((point.energy_bin == len(energy_edges) - 2) & (energy <= point.energy_high_gev))
    )
    mass_mask = (masses >= point.mass_low_gev) & (
        (masses < point.mass_high_gev)
        | ((point.mass_bin == len(pair_mass_edges(point.pair)) - 2) & (masses <= point.mass_high_gev))
    )
    selected = energy_mask & mass_mask
    # Count the likelihood's own events and all exposure strata in its energy
    # bin, including when sparse phi bins cannot support a ratio fit.
    selected_exposures = [
        item for item in exposures.values()
        if energy_bin_index(item.energy_gev, energy_edges) == point.energy_bin
    ]
    flux_vertical = float(sum(item.flux_vertical for item in selected_exposures))
    flux_horizontal = float(sum(item.flux_horizontal for item in selected_exposures))
    return OutputPoint(
        sample=sample,
        estimator="likelihood",
        point=point,
        sigma_uncorrected=point.sigma,
        systematic_total=0.0,
        background_fraction=0.0,
        count_vertical=int(np.count_nonzero(selected & (events.polarization == 1))),
        count_horizontal=int(np.count_nonzero(selected & (events.polarization == 2))),
        flux_vertical=flux_vertical,
        flux_horizontal=flux_horizontal,
        polarization_vertical=float(sum(
            item.flux_vertical * item.polarization_vertical for item in selected_exposures
        ) / flux_vertical) if flux_vertical else 0.0,
        polarization_horizontal=float(sum(
            item.flux_horizontal * item.polarization_horizontal for item in selected_exposures
        ) / flux_horizontal) if flux_horizontal else 0.0,
    )
