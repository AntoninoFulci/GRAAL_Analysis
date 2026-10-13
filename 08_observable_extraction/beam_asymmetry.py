"""Standalone extraction of gamma p -> eta pi0 p beam asymmetry."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, fields, replace
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Sequence

import numpy as np

from calibration.run_manifest import validate_manifest
from reconstruction.runtime.provenance import file_identities

from graal_common.physics.beam_profiles import BEAM_PROFILES, get_beam_profile
from graal_common.io.filesystem import atomic_output_directory
from graal_common.physics.channels import ETA_PI0_HYP, M_ETA, M_PI0, M_PROTON

from observable_extraction.calibration.flux_v2 import load_exposures
from observable_extraction.core.binning import (
    PHI_EDGES_RAD,
    PHI_BIN_CHOICES,
    phi_edges_rad,
    phi_bin_divisor,
    energy_bin_index,
    PAIR_NAMES,
    pair_mass_edges,
)
from observable_extraction.core.conditional_likelihood import (
    extract_likelihood_grid,
)
from observable_extraction.core.background import (
    BackgroundEstimate,
    Region,
    SidebandWindows,
    classify_region,
    correct_sigma_with_uncertainty,
    factorized_sideband_template,
    fit_background_fraction,
    fraction_in_mask,
    validate_signal_leakage,
)
from graal_common.physics.energy_binning import add_energy_arguments, energy_binning_from_args
from observable_extraction.core.energy_audit import energy_bin_inventory
from observable_extraction.core.kinematics import project_all_pairs
from observable_extraction.core.photon_multiplicity import (
    compare_multiplicity_selections,
)
from observable_extraction.core.ratio_fit import extract_ratio_grid, binning_quality_key
from observable_extraction.core.periods import partition_runs, selection_audit, exposure_summary
from observable_extraction.core.systematics import (
    REQUIRED_SYSTEMATICS,
    paired_bootstrap_by_run,
    bootstrap_by_run,
    component_from_shift,
)
from observable_extraction.io.reconstructed_events import (
    read_reconstructed,
    read_run_universe,
    EventArrays,
    select_brem_control,
    select_sigma_events,
)
from observable_extraction.io.root_output import (
    OutputPoint,
    RatioObject,
    RootOutputPayload,
    write_root_output,
    ordered_point_keys,
    point_key_label,
)
from observable_extraction.plotting.figure4 import (
    profile_energy_rows,
    write_profile_figure4_pdf,
)
from observable_extraction.plotting.diagnostics import (
    write_background_control_pdf,
    write_false_asymmetry_controls_pdf,
    write_photon_multiplicity_pdf,
    write_point_comparison_pdf,
    write_profile_estimator_comparison_pdf,
    write_profile_fit_diagnostics_pdf,
    write_systematic_summary_pdf,
    write_period_stability_pdf,
)


@dataclass(frozen=True)
class SampleInput:
    tree: str
    vector_mode: str
    requires_bdt: bool


@dataclass(frozen=True)
class ExtractionBundle:
    points: tuple[OutputPoint, ...]
    ratio_objects: tuple[RatioObject, ...]
    binning_candidates: tuple[OutputPoint, ...] = ()
    candidate_ratio_objects: tuple[RatioObject, ...] = ()


SAMPLES = {
    "raw": SampleInput("reco_eta_pi0_chi2", "raw", False),
    "raw_bdt": SampleInput("reco_eta_pi0_bdt", "raw", True),
    "raw_bdt_fit": SampleInput("reco_eta_pi0_bdt", "fit", True),
}

SIDEBAND_TREE = "reco_eta_pi0_bdt_sideband"
SIDEBAND_WINDOWS = SidebandWindows(
    eta_center=M_ETA,
    eta_half_width=ETA_PI0_HYP.heavy_window,
    pi0_center=M_PI0,
    pi0_half_width=ETA_PI0_HYP.light_window,
    missing_center=M_PROTON,
    missing_half_width=0.06,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw",
        type=Path,
        default=Path("results/reco/reco_eta_pi0_chi2_raw.root"),
    )
    parser.add_argument(
        "--raw-bdt",
        type=Path,
        default=Path("results/reco/reco_eta_pi0_bdt_raw.root"),
    )
    parser.add_argument(
        "--raw-bdt-fit",
        type=Path,
        default=None,
        help="explicit opt-in for archived 6C comparison; disabled by default",
    )
    parser.add_argument("--sideband", type=Path)
    parser.add_argument("--signal-mc", type=Path)
    parser.add_argument(
        "--flux-file",
        type=Path,
        default=Path("data/00_external/flux_calibrated.root"),
    )
    parser.add_argument(
        "--run-manifest",
        type=Path,
        default=Path("config/run_manifest.csv"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/beam_asymmetry"),
    )
    parser.add_argument("--plots-dir", type=Path, help="directory for diagnostic PDFs (default: output-dir)")
    parser.add_argument(
        "--nominal-sample",
        choices=tuple(SAMPLES),
        default="raw_bdt",
    )
    parser.add_argument(
        "--estimator",
        choices=("ratio", "likelihood", "both"),
        default="both",
    )
    parser.add_argument("--profile", choices=BEAM_PROFILES, default="uv")
    add_energy_arguments(parser)
    parser.add_argument("--phi-bins", type=int, choices=PHI_BIN_CHOICES, default=12)
    parser.add_argument("--best-binning", action="store_true",
                        help="fit 8/12/16 phi bins together and select each ratio point by fit quality; overrides --phi-bins")
    parser.add_argument("--mass-bins", type=int, default=10)
    parser.add_argument("--bootstrap-replicas", type=int, default=0)
    parser.add_argument("--bootstrap-seed", type=int, default=1208)
    parser.add_argument("--bootstrap-diagnostics-replicas", type=int, default=0,
                        help="paired run diagnostic only; never added to published covariance")
    parser.add_argument("--bootstrap-universe-manifest", type=Path,
                        help="explicit inclusive run universe, including zero-yield runs; standard manifest schema")
    parser.add_argument("--by-period", action="store_true",
                        help="extract exact manifest periods and pooled union with inclusive run accounting")
    parser.add_argument("--run-universe-manifest", type=Path,
                        help="inclusive input runs; otherwise use reconstruction run/state cutflow")
    return parser


def _sample_path(args: argparse.Namespace, sample: str) -> Path | None:
    return {
        "raw": args.raw,
        "raw_bdt": args.raw_bdt,
        "raw_bdt_fit": args.raw_bdt_fit,
    }[sample]


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


def _apply_background_correction(
    points: Sequence[OutputPoint],
    fractions_by_energy: dict[int, BackgroundEstimate],
    background_by_bin: dict[tuple[str, int, int], object],
) -> list[OutputPoint]:
    """Correct Sigma while retaining observed value and propagated uncertainty."""
    corrected_points: list[OutputPoint] = []
    for output in points:
        point = output.point
        fraction = fractions_by_energy.get(point.energy_bin)
        background = background_by_bin.get(
            (output.estimator, point.pair, point.energy_bin, point.mass_bin)
        )
        if background is None:
            background = background_by_bin.get(
                (point.pair, point.energy_bin, point.mass_bin)
            )
        if fraction is None or background is None:
            corrected_points.append(output)
            continue
        observed_error = 0.5 * (point.stat_low + point.stat_high)
        background_error = 0.5 * (
            background.point.stat_low + background.point.stat_high
        )
        sigma, error = correct_sigma_with_uncertainty(
            sigma_observed=point.sigma,
            observed_error=observed_error,
            background_fraction=fraction.fraction,
            fraction_error=fraction.error,
            sigma_background=background.point.sigma,
            background_error=background_error,
        )
        corrected_points.append(
            replace(
                output,
                point=replace(point, sigma=sigma, stat_low=error, stat_high=error),
                sigma_uncorrected=point.sigma,
                background_fraction=fraction.fraction,
                uncertainty_kind="background_propagated_unclassified",
            )
        )
    return corrected_points


def _sideband_regions(events) -> np.ndarray:
    return np.array(
        [
            classify_region(
                eta_mass=float(eta_mass),
                pi0_mass=float(pi0_mass),
                missing_mass=float(missing_mass),
                windows=SIDEBAND_WINDOWS,
            )
            for eta_mass, pi0_mass, missing_mass in zip(
                events.eta_mass_gev,
                events.pi0_mass_gev,
                events.missing_mass_gev,
            )
        ],
        dtype=object,
    )


def _mass_pulls(events) -> np.ndarray:
    return np.column_stack(
        (
            (events.eta_mass_gev - SIDEBAND_WINDOWS.eta_center)
            / SIDEBAND_WINDOWS.eta_half_width,
            (events.pi0_mass_gev - SIDEBAND_WINDOWS.pi0_center)
            / SIDEBAND_WINDOWS.pi0_half_width,
            (events.missing_mass_gev - SIDEBAND_WINDOWS.missing_center)
            / SIDEBAND_WINDOWS.missing_half_width,
        )
    )


def _estimate_background_fractions(
    broad_events,
    signal_mc,
    energy_edges: np.ndarray,
) -> tuple[dict[int, BackgroundEstimate], float]:
    """Fit broad 3D mass mixtures, then project fractions into signal cube."""
    broad_regions = _sideband_regions(broad_events)
    signal_regions = _sideband_regions(signal_mc)
    leakage = validate_signal_leakage(signal_regions, maximum=0.05)
    broad_pulls = _mass_pulls(broad_events)
    signal_pulls = _mass_pulls(signal_mc)
    histogram_edges = [np.linspace(-4.0, 4.0, 9)] * 3
    centers = 0.5 * (histogram_edges[0][:-1] + histogram_edges[0][1:])
    signal_cube = (
        (np.abs(centers[:, None, None]) < 1.0)
        & (np.abs(centers[None, :, None]) < 1.0)
        & (np.abs(centers[None, None, :]) < 1.0)
    )
    estimates: dict[int, BackgroundEstimate] = {}
    for energy_bin, (energy_low, energy_high) in enumerate(
        zip(energy_edges[:-1], energy_edges[1:])
    ):
        last = energy_bin == len(energy_edges) - 2
        broad_energy = (broad_events.beam_energy_gev >= energy_low) & (
            (broad_events.beam_energy_gev < energy_high)
            | (last & (broad_events.beam_energy_gev <= energy_high))
        )
        signal_energy = (signal_mc.beam_energy_gev >= energy_low) & (
            (signal_mc.beam_energy_gev < energy_high)
            | (last & (signal_mc.beam_energy_gev <= energy_high))
        )
        hard = broad_energy & (broad_regions == Region.HARD_SIDEBAND)
        if not np.any(broad_energy) or not np.any(signal_energy) or not np.any(hard):
            continue
        data_hist, _ = np.histogramdd(
            broad_pulls[broad_energy], bins=histogram_edges
        )
        signal_hist, _ = np.histogramdd(
            signal_pulls[signal_energy], bins=histogram_edges
        )
        hard_hist, _ = np.histogramdd(broad_pulls[hard], bins=histogram_edges)
        if data_hist.sum() <= 0.0 or signal_hist.sum() <= 0.0 or hard_hist.sum() <= 0.0:
            continue
        signal_template = signal_hist + 0.5
        signal_template /= signal_template.sum()
        background_template = factorized_sideband_template(hard_hist)
        broad_fit = fit_background_fraction(
            data_hist,
            signal_template,
            background_template,
        )
        fraction = fraction_in_mask(
            broad_fit.fraction,
            signal_template,
            background_template,
            signal_cube,
        )
        low = fraction_in_mask(
            max(0.0, broad_fit.fraction - broad_fit.error),
            signal_template,
            background_template,
            signal_cube,
        )
        high = fraction_in_mask(
            min(1.0, broad_fit.fraction + broad_fit.error),
            signal_template,
            background_template,
            signal_cube,
        )
        estimates[energy_bin] = BackgroundEstimate(
            fraction=min(fraction, 1.0 - 1e-12),
            error=0.5 * abs(high - low),
            nll=broad_fit.nll,
            converged=broad_fit.converged,
        )
    return estimates, leakage


def _background_asymmetries(
    broad_events,
    exposures,
    estimator: str,
    energy_edges: np.ndarray,
    phi_edges: np.ndarray = PHI_EDGES_RAD,
    selected_phi_bins: dict | None = None,
) -> dict[tuple[str, str, int, int], OutputPoint]:
    regions = _sideband_regions(broad_events)
    hard_events = broad_events.take(regions == Region.HARD_SIDEBAND)
    if len(hard_events) == 0:
        return {}
    bundle = _extract_sample(
        sample_name="hard_sideband",
        events=hard_events,
        exposures=exposures,
        estimator=estimator,
        retain_ratio_objects=False,
        energy_edges=energy_edges,
        phi_edges=phi_edges,
        **({"selected_phi_bins": selected_phi_bins} if selected_phi_bins is not None else {}),
    )
    return {
        (
            item.estimator,
            item.point.pair,
            item.point.energy_bin,
            item.point.mass_bin,
        ): item
        for item in bundle.points
    }


def _extract_sample(
    *,
    sample_name: str,
    events,
    exposures,
    estimator: str,
    retain_ratio_objects: bool,
    energy_edges: np.ndarray,
    phi_edges: np.ndarray = PHI_EDGES_RAD,
    best_binning: bool = False,
    selected_phi_bins: dict | None = None,
) -> ExtractionBundle:
    """Project once, then fit all requested binnings on the same selected events.

    selected_phi_bins freezes the nominal choice for sideband and systematic
    controls. Missing fixed-bin fits remain missing; never substitute another
    binning silently. Bootstrap replicas instead repeat the best-bin selection.
    """
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


def _selected_phi_bins(points, sample):
    return {(p.point.pair, p.point.energy_bin, p.point.mass_bin): p.phi_bins
            for p in points if p.sample == sample and p.estimator == "ratio" and p.phi_bins}


def _point_key(output: OutputPoint, *, include_estimator: bool = True) -> tuple:
    point = output.point
    key = (output.sample, point.pair, point.energy_bin, point.mass_bin)
    return (*key, output.estimator) if include_estimator else key


def _systematic_studies(points, extra_shifts=None):
    """Signed diagnostic variations and their measured-point masks."""
    lookup = {_point_key(item): item for item in points}
    size = len(points)
    studies = {}
    for name in REQUIRED_SYSTEMATICS:
        studies[name] = (np.zeros(size), np.zeros(size, dtype=bool))
    for index, item in enumerate(points):
        point = item.point
        studies["polarization_scale_3pct"][0][index] = -0.03 * point.sigma
        studies["polarization_scale_3pct"][1][index] = True
        other = "likelihood" if item.estimator == "ratio" else "ratio"
        counterpart = lookup.get((item.sample, point.pair, point.energy_bin, point.mass_bin, other))
        if counterpart is not None:
            studies["estimator_ratio_vs_likelihood"][0][index] = 0.5 * (counterpart.point.sigma - point.sigma)
            studies["estimator_ratio_vs_likelihood"][1][index] = True
        if (item.uncertainty_kind == "background_propagated_unclassified"
                or item.background_fraction != 0.0 or point.sigma != item.sigma_uncorrected):
            studies["background_template"][0][index] = point.sigma - item.sigma_uncorrected
            studies["background_template"][1][index] = True
        if point.diagnostics.s2 is not None:
            studies["angular_offset_sine_leakage"][0][index] = point.diagnostics.s2
            studies["angular_offset_sine_leakage"][1][index] = True
    for name, shift in (extra_shifts or {}).items():
        if name == "raw_vs_kinematic_fit":
            raise ValueError("raw_vs_kinematic_fit is retired from operational systematics")
        component = component_from_shift(name, shift)
        if component.shift.shape != (size,):
            raise ValueError("systematic shift dimension does not match points")
        studies[name] = (component.shift, np.ones(size, dtype=bool))
    return studies


def _systematic_covariances(points, extra_shifts=None):
    """Legacy rank-one model, with absent variations distinguished from zero."""
    return {name: component_from_shift(name, shift).covariance
            for name, (shift, measured) in _systematic_studies(points, extra_shifts).items()
            if np.any(measured)}


def _systematic_inventory(points, covariances, extra_shifts=None):
    definitions = {
        "polarization_scale_3pct": ("published Sigma; polarization scale +3%", "-0.03 * Sigma", "experimental_nuisance"),
        "estimator_ratio_vs_likelihood": ("same sample and bin; counterpart estimator", "(counterpart - nominal) / 2", "model_variation_with_statistical_noise"),
        "background_template": ("corrected and uncorrected nominal result", "corrected - uncorrected", "correction_shift_not_independent_fraction_uncertainty"),
        "angular_offset_sine_leakage": ("fallback harmonic fit", "s2", "fit_diagnostic_with_statistical_noise"),
        "photon_multiplicity": ("same sample; n_photons_input == 4", "restricted - inclusive", "selection_variation_with_statistical_noise"),
    }
    inventory = {}
    for name, (shift, measured) in _systematic_studies(points, extra_shifts).items():
        status = "executed" if name in covariances else "unavailable"
        reason = "" if status == "executed" else "required variation or matching fitted points unavailable"
        if name == "raw_vs_kinematic_fit":
            status, reason = "not_applicable", "retired; baseline without 6C; archived comparisons are diagnostic only"
        inputs, variation, category = definitions.get(name, ("not supplied", "not evaluated", "unclassified"))
        inventory[name] = dict(
            status=status, reason=reason, inputs=inputs, variation=variation,
            units="dimensionless Sigma", category=category,
            measured_points=measured.tolist(),
            signed_shift=[float(value) if valid else None for value, valid in zip(shift, measured)],
            correlation_model="legacy single common nuisance; physical scope unvalidated" if status == "executed" else "unknown",
            independent_of_other_sources="unvalidated",
        )
    return inventory


def _attach_systematic_totals(
    points: Sequence[OutputPoint],
    covariances: dict[str, np.ndarray],
) -> tuple[OutputPoint, ...]:
    if not points:
        return ()
    variance = np.zeros(len(points), dtype=np.float64)
    for covariance in covariances.values():
        variance += np.diag(covariance)
    return tuple(
        replace(item, systematic_total=float(np.sqrt(max(variance[index], 0.0))))
        for index, item in enumerate(points)
    )


def _bootstrap_covariance_for_points(
    *,
    points: Sequence[OutputPoint],
    events,
    exposures,
    sample_name: str,
    estimator: str,
    replicas: int,
    seed: int,
    energy_edges: np.ndarray,
    phi_edges: np.ndarray = PHI_EDGES_RAD,
    best_binning: bool = False,
) -> np.ndarray | None:
    if replicas == 0:
        return None
    if replicas < 0:
        raise ValueError("bootstrap replicas must be non-negative")
    if len(np.unique(events.run_number)) < 2:
        print(
            "warning: run bootstrap skipped because nominal sample has fewer than two runs",
            file=sys.stderr,
        )
        return None
    selected_indices = [
        index
        for index, item in enumerate(points)
        if item.sample == sample_name and item.estimator == estimator
    ]
    reference_keys = [
        (
            points[index].point.pair,
            points[index].point.energy_bin,
            points[index].point.mass_bin,
        )
        for index in selected_indices
    ]
    if not reference_keys:
        return None

    def estimate(replica_events, replica_exposures) -> np.ndarray:
        bundle = _extract_sample(
            sample_name=sample_name,
            events=replica_events,
            exposures=replica_exposures,
            estimator=estimator,
            retain_ratio_objects=False,
            energy_edges=energy_edges,
            phi_edges=phi_edges,
            **({"best_binning": True} if best_binning else {}),
        )
        fitted = {
            (item.point.pair, item.point.energy_bin, item.point.mass_bin): item.point.sigma
            for item in bundle.points
            if item.estimator == estimator
        }
        missing = [key for key in reference_keys if key not in fitted]
        if missing:
            raise RuntimeError(f"bootstrap replica lost fitted bins: {missing}")
        return np.array([fitted[key] for key in reference_keys], dtype=np.float64)

    result = bootstrap_by_run(
        estimate,
        events,
        exposures,
        replicas=replicas,
        seed=seed,
    )
    embedded = np.zeros((len(points), len(points)), dtype=np.float64)
    embedded[np.ix_(selected_indices, selected_indices)] = result.covariance
    return embedded



def _paired_bootstrap_diagnostics(
    *, points, samples, exposures, run_strata, point_keys, nominal_sample,
    estimator, replicas, seed, energy_edges, phi_edges,
    broad_events=None, signal_mc=None, best_binning=False,
):
    ensemble_samples = dict(samples)
    if broad_events is not None:
        if signal_mc is None:
            raise ValueError("background diagnostics require signal MC")
        ensemble_samples["sideband"] = broad_events

    def estimate(replica_samples, replica_exposures):
        fitted = {}
        for name in samples:
            bundle = _extract_sample(
                sample_name=name, events=replica_samples[name], exposures=replica_exposures,
                estimator=estimator, retain_ratio_objects=False,
                energy_edges=energy_edges, phi_edges=phi_edges,
                **({"best_binning": True} if best_binning else {}))
            fitted.update({_point_key(item): item for item in bundle.points})
        fractions, background = {}, {}
        if broad_events is not None:
            fractions, _ = _estimate_background_fractions(replica_samples["sideband"], signal_mc, energy_edges)
            background = _background_asymmetries(replica_samples["sideband"], replica_exposures,
                                                estimator, energy_edges, phi_edges,
                                                **({"selected_phi_bins": _selected_phi_bins(fitted.values(), nominal_sample)}
                                                   if best_binning else {}))
        values = np.full(len(points), np.nan)
        for index, reference in enumerate(points):
            item = fitted.get(_point_key(reference))
            if item is None or not item.point.diagnostics.converged:
                continue
            value = item.point.sigma
            if reference.uncertainty_kind == "background_propagated_unclassified":
                point = item.point
                fraction = fractions.get(point.energy_bin)
                bkg = background.get((item.estimator, point.pair, point.energy_bin, point.mass_bin))
                if (fraction is None or bkg is None or not fraction.converged
                        or not 0.0 <= fraction.fraction < 1.0):
                    continue
                value = (value - fraction.fraction * bkg.point.sigma) / (1.0 - fraction.fraction)
            values[index] = value
        return values

    return paired_bootstrap_by_run(
        estimate, ensemble_samples, exposures, run_strata=run_strata,
        point_keys=point_keys, replicas=replicas, seed=seed)


def _validate_diagnostic_universe(samples, run_strata):
    for name, events in samples.items():
        omitted = set(map(int, events.run_number)) - set(run_strata)
        if omitted:
            raise ValueError(f"bootstrap universe omits selected runs in {name}: {sorted(omitted)}")

def _photon_multiplicity_component(
    *,
    points: Sequence[OutputPoint],
    events,
    exposures,
    sample_name: str,
    estimator: str,
    fractions: dict[int, BackgroundEstimate],
    background_by_bin: dict,
    energy_edges: np.ndarray,
    phi_edges: np.ndarray = PHI_EDGES_RAD,
) -> tuple[np.ndarray | None, int, int]:
    selected_indices = [
        index for index, item in enumerate(points) if item.sample == sample_name
    ]
    reference_keys = [
        (
            points[index].estimator,
            points[index].point.pair,
            points[index].point.energy_bin,
            points[index].point.mass_bin,
        )
        for index in selected_indices
    ]

    def estimate(selected_events) -> np.ndarray:
        bundle = _extract_sample(
            sample_name=sample_name,
            events=selected_events,
            exposures=exposures,
            estimator=estimator,
            retain_ratio_objects=False,
            energy_edges=energy_edges,
            phi_edges=phi_edges,
            **({"selected_phi_bins": _selected_phi_bins(points, sample_name)}
               if _selected_phi_bins(points, sample_name) else {}),
        )
        extracted = list(bundle.points)
        if fractions:
            extracted = _apply_background_correction(
                extracted,
                fractions,
                background_by_bin,
            )
        fitted = {
            (
                item.estimator,
                item.point.pair,
                item.point.energy_bin,
                item.point.mass_bin,
            ): item.point.sigma
            for item in extracted
        }
        missing = [key for key in reference_keys if key not in fitted]
        if missing:
            raise RuntimeError(f"exactly-four selection lost fitted bins: {missing}")
        return np.array([fitted[key] for key in reference_keys], dtype=np.float64)

    exactly_four_count = int(np.count_nonzero(events.n_photons_input == 4))
    try:
        study = compare_multiplicity_selections(events, estimate)
    except (ValueError, RuntimeError) as error:
        print(f"warning: photon-multiplicity study unavailable: {error}", file=sys.stderr)
        return None, len(events), exactly_four_count
    shift = np.zeros(len(points), dtype=np.float64)
    shift[selected_indices] = study.sigma_shift
    return shift, study.inclusive_count, study.exactly_four_count


def _run_single(args: argparse.Namespace, *, prepared=None, period="pooled", metadata=None,
                campaign=None) -> RootOutputPayload:
    if args.bootstrap_diagnostics_replicas:
        if args.bootstrap_diagnostics_replicas < 2:
            raise ValueError("diagnostic bootstrap requires at least two replicas")
        if args.bootstrap_universe_manifest is None:
            raise ValueError("diagnostic bootstrap requires an explicit inclusive run universe manifest")
        if args.bootstrap_replicas:
            raise ValueError("choose diagnostic bootstrap or legacy bootstrap, not both")
    if args.nominal_sample == "raw_bdt_fit" and args.raw_bdt_fit is None:
        raise ValueError("fitted nominal sample requires explicit --raw-bdt-fit")
    no_fit = args.raw_bdt_fit is None
    best_binning = getattr(args, "best_binning", False)
    if best_binning and args.estimator == "likelihood":
        raise ValueError("--best-binning requires ratio or both; likelihood is unbinned")
    binning_options = {"best_binning": True} if best_binning else {}
    phi_edges = phi_edges_rad(12 if best_binning else args.phi_bins)
    phi_provenance = ("phi_bins=best-binning\nphi_bin_divisor=per_point\n"
                      "phi_bin_selection=acceptable_nominal_closest_reduced_chi2_to_one\n"
                      "phi_bin_candidates=8,12,16\n" if best_binning else
                      f"phi_bins={args.phi_bins}\nphi_bin_divisor={phi_bin_divisor(phi_edges)}\n")
    if args.mass_bins != 10:
        raise ValueError("nominal extraction requires 10 mass bins")
    if (args.sideband is None) != (args.signal_mc is None):
        raise ValueError("--sideband and --signal-mc must be supplied together")
    profile = get_beam_profile(args.profile)
    grid = energy_binning_from_args(args, args.profile)
    energy_edges = np.asarray(grid.edges_gev, dtype=np.float64)
    sample = SAMPLES[args.nominal_sample]
    def read_sample(path, tree, **kwargs):
        if prepared is not None:
            return prepared[0][(path, tree, kwargs["vector_mode"])]
        return read_reconstructed(path, tree, **kwargs)

    all_nominal_events = read_sample(
        _sample_path(args, args.nominal_sample),
        sample.tree,
        vector_mode=sample.vector_mode,
        require_no_fit=no_fit,
    )
    exposures = prepared[1] if prepared is not None else load_exposures(
        args.flux_file,
        manifest_path=args.run_manifest,
        run_numbers=np.unique(all_nominal_events.run_number),
        polarization_model=profile.polarization,
        target=profile.target,
        beam_type=profile.beam_type,
        energy_range=grid.energy_range_gev,
    )
    events = select_sigma_events(
        all_nominal_events,
        exposures,
        energy_range=grid.energy_range_gev,
        drop_missing=True,
    )
    nominal = _extract_sample(
        sample_name=args.nominal_sample,
        events=events,
        exposures=exposures,
        estimator=args.estimator,
        retain_ratio_objects=True,
        energy_edges=energy_edges,
        phi_edges=phi_edges,
        **binning_options,
    )
    output_points = list(nominal.points)
    binning_candidates = list(nominal.binning_candidates)
    samples = {args.nominal_sample: events}
    input_samples = {args.nominal_sample: all_nominal_events}
    broad_input_events = None
    broad_events = signal_mc = None
    background_fractions: dict[int, BackgroundEstimate] = {}
    background_leakage: float | None = None
    background_by_bin: dict = {}
    if args.sideband is not None:
        broad_input_events = read_sample(args.sideband, SIDEBAND_TREE, vector_mode="raw", require_no_fit=no_fit)
        broad_events = select_sigma_events(
            broad_input_events,
            exposures,
            energy_range=grid.energy_range_gev,
            drop_missing=True,
        )
        signal_mc = read_sample(
            args.signal_mc,
            SIDEBAND_TREE,
            vector_mode="raw",
        )
        background_fractions, background_leakage = _estimate_background_fractions(
            broad_events,
            signal_mc,
            energy_edges,
        )
        background_by_bin = _background_asymmetries(
            broad_events,
            exposures,
            args.estimator,
            energy_edges,
            phi_edges,
            **({"selected_phi_bins": _selected_phi_bins(nominal.points, args.nominal_sample)}
               if best_binning else {}),
        )
        output_points = _apply_background_correction(
            output_points,
            background_fractions,
            background_by_bin,
        )
    for sample_name, contract in SAMPLES.items():
        if sample_name == args.nominal_sample:
            continue
        path = _sample_path(args, sample_name)
        if path is None:
            continue
        if not path.is_file():
            print(
                f"warning: optional comparison sample missing: {sample_name} ({path})",
                file=sys.stderr,
            )
            continue
        input_samples[sample_name] = read_sample(
            path, contract.tree, vector_mode=contract.vector_mode, require_no_fit=no_fit)
        comparison_events = select_sigma_events(
            input_samples[sample_name],
            exposures,
            energy_range=grid.energy_range_gev,
            drop_missing=True,
        )
        samples[sample_name] = comparison_events
        comparison = _extract_sample(
            sample_name=sample_name,
            events=comparison_events,
            exposures=exposures,
            estimator=args.estimator,
            retain_ratio_objects=False,
            energy_edges=energy_edges,
            phi_edges=phi_edges,
            **binning_options,
        )
        binning_candidates.extend(comparison.binning_candidates)
        output_points.extend(comparison.points)
    if metadata is not None:
        context = dict(campaign=campaign, period=period, profile=profile.name,
                       selection="no-fit" if no_fit else "archived-fit-selected")
        failed = [item for item in output_points if not item.point.diagnostics.converged]
        metadata["failed_fit_keys"] = ordered_point_keys(failed, context)
        metadata["failed_fit_diagnostics"] = [vars(item.point.diagnostics) for item in failed]
        output_points = [item for item in output_points if item.point.diagnostics.converged]
        metadata["point_keys"] = ordered_point_keys(output_points, context)
        metadata["estimable_points"] = len(output_points)
        fitted = {_point_key(item) for item in output_points}
        estimators = ("ratio", "likelihood") if args.estimator == "both" else (args.estimator,)
        metadata["bins"] = [
            dict(sample=name, estimator=estimator, pair=pair, energy_bin=e, mass_bin=m,
                 status="estimable" if (name, pair, e, m, estimator) in fitted else "not_estimable")
            for name in input_samples for estimator in estimators for pair in PAIR_NAMES
            for e in range(len(energy_edges) - 1) for m in range(len(pair_mass_edges(pair)) - 1)]
    energy_inventory = energy_bin_inventory(input_samples, exposures, energy_edges, output_points)
    if metadata is not None:
        metadata["energy_bins"] = energy_inventory
        metadata["energy_edges_gev"] = list(grid.edges_gev)
    if not output_points:
        if metadata is None:
            raise RuntimeError("no beam-asymmetry bins could be fitted")
        metadata["status"] = "not_estimable"
        payload = RootOutputPayload(
            points=(), energy_edges=energy_edges, phi_edges=phi_edges,
            mass_edges={pair: pair_mass_edges(pair) for pair in PAIR_NAMES},
            covariance_total=np.empty((0, 0)), statistical_covariance=np.empty((0, 0)),
            systematic_covariances={}, ratio_objects=(),
            binning_candidates=tuple(binning_candidates),
            candidate_ratio_objects=nominal.candidate_ratio_objects,
            point_context=dict(campaign=campaign, period=period, profile=profile.name,
                               selection="no-fit" if no_fit else "archived-fit-selected"),
            extraction_metadata=metadata,
            uncertainty_metadata=dict(final_inference="suspended", status="not_estimable"),
            provenance=(f"profile={profile.name}\nperiod={period}\nstatus=not_estimable\n"
                        f"energy_edges_gev={json.dumps(grid.edges_gev)}\n"
                        f"{phi_provenance}"
                        "phi_bin_correction=ratio_only_rounded\nfinal_inference=suspended"),
        )
        write_root_output(args.output_dir / "beam_asymmetry.root", payload)
        return payload

    args.output_dir.mkdir(parents=True, exist_ok=True)
    multiplicity_shift, inclusive_count, exactly_four_count = (
        _photon_multiplicity_component(
            points=output_points,
            events=events,
            exposures=exposures,
            sample_name=args.nominal_sample,
            estimator=args.estimator,
            fractions=background_fractions,
            background_by_bin=background_by_bin,
            energy_edges=energy_edges,
            phi_edges=phi_edges,
        )
    )
    extra_shifts = (
        {"photon_multiplicity": multiplicity_shift}
        if multiplicity_shift is not None
        else {}
    )
    systematic_covariances = _systematic_covariances(output_points, extra_shifts)
    output_points = list(
        _attach_systematic_totals(output_points, systematic_covariances)
    )
    statistical_covariance = np.diag(
        [
            (0.5 * (item.point.stat_low + item.point.stat_high)) ** 2
            for item in output_points
        ]
    )
    figure_estimator = "ratio" if args.estimator in {"ratio", "both"} else "likelihood"
    bootstrap_covariance = _bootstrap_covariance_for_points(
        points=output_points,
        events=events,
        exposures=exposures,
        sample_name=args.nominal_sample,
        estimator=figure_estimator,
        replicas=args.bootstrap_replicas,
        seed=args.bootstrap_seed,
        energy_edges=energy_edges,
        phi_edges=phi_edges,
        **binning_options,
    )
    if bootstrap_covariance is not None:
        off_diagonal = bootstrap_covariance.copy()
        np.fill_diagonal(off_diagonal, 0.0)
        statistical_covariance += off_diagonal
        bootstrap_diagonal = np.diag(bootstrap_covariance)
        fit_diagonal = np.diag(statistical_covariance).copy()
        np.fill_diagonal(
            statistical_covariance,
            np.maximum(fit_diagonal, bootstrap_diagonal),
        )
    covariance_total = statistical_covariance.copy()
    for covariance in systematic_covariances.values():
        covariance_total += covariance
    point_context = dict(campaign=campaign or str(args.output_dir.resolve()),
                         selection="no-fit" if no_fit else "archived-fit-selected",
                         profile=profile.name, period=period)
    inventory = _systematic_inventory(output_points, systematic_covariances, extra_shifts)
    if multiplicity_shift is not None:
        # The legacy matrix embeds zeros for comparison samples not reevaluated.
        measured = [item.sample == args.nominal_sample for item in output_points]
        inventory["photon_multiplicity"]["measured_points"] = measured
        inventory["photon_multiplicity"]["signed_shift"] = [
            float(value) if valid else None for value, valid in zip(multiplicity_shift, measured)]
    diagnostic = None
    diagnostic_inputs = []
    run_strata = {}
    if args.bootstrap_diagnostics_replicas:
        records = validate_manifest(args.bootstrap_universe_manifest)
        if any(record.target != profile.target or record.beam_type != profile.beam_type for record in records):
            raise ValueError("bootstrap universe must contain only the selected target/profile")
        run_strata = {record.run_number: f"{profile.name}:{record.source_period}" for record in records}
        if metadata is not None:
            run_strata = {run: stratum for run, stratum in run_strata.items()
                          if run in metadata["run_universe"]}
        required_samples = dict(samples)
        if broad_events is not None:
            required_samples["sideband"] = broad_events
        _validate_diagnostic_universe(required_samples, run_strata)
        diagnostic_exposures = load_exposures(
            args.flux_file, manifest_path=args.run_manifest, run_numbers=run_strata,
            polarization_model=profile.polarization, target=profile.target,
            beam_type=profile.beam_type, energy_range=grid.energy_range_gev)
        exposed = {exposure.run_number for exposure in diagnostic_exposures.values()}
        if exposed != set(run_strata):
            raise ValueError(f"bootstrap universe has missing exposures: {sorted(set(run_strata) - exposed)}")
        diagnostic_samples = {name: select_sigma_events(
            sample_events, diagnostic_exposures, energy_range=grid.energy_range_gev, drop_missing=True)
            for name, sample_events in input_samples.items()}
        diagnostic_broad = None if broad_input_events is None else select_sigma_events(
            broad_input_events, diagnostic_exposures, energy_range=grid.energy_range_gev, drop_missing=True)
        diagnostic = _paired_bootstrap_diagnostics(
            points=output_points, samples=diagnostic_samples, exposures=diagnostic_exposures,
            run_strata=run_strata,
            point_keys=tuple(point_key_label(key) for key in ordered_point_keys(output_points, point_context)),
            nominal_sample=args.nominal_sample, estimator=args.estimator,
            replicas=args.bootstrap_diagnostics_replicas, seed=args.bootstrap_seed,
            energy_edges=energy_edges, phi_edges=phi_edges,
            broad_events=diagnostic_broad, signal_mc=signal_mc, **binning_options)
        diagnostic_inputs = file_identities([
            args.bootstrap_universe_manifest, args.run_manifest, args.flux_file,
            *(_sample_path(args, name) for name in input_samples),
            *([args.sideband, args.signal_mc] if args.sideband is not None else []),
        ])
    uncertainty_metadata = dict(
        schema_version=1, final_inference="suspended", sources=inventory,
        statistical_correlations="unknown outside any stored legacy nominal bootstrap block",
        statistical_model="conditional fit diagonal; optional legacy bootstrap diagonal maximum",
        binning_selection=("adaptive 8/12/16; conditional errors exclude selection uncertainty; "
                           "bootstrap repeats selection" if best_binning else "fixed"),
        systematic_model="legacy rank-one shifts; source independence unvalidated",
        background_model="legacy diagonal propagation; f classification and shared covariance unresolved",
        background_shift_warning="correction shift is not independent evidence for fraction uncertainty",
        interval_warning="background correction currently symmetrizes conditional intervals; joint Jacobian does not replace likelihood intervals",
        bootstrap_diagnostic_status="not_requested" if diagnostic is None else ("failed_replicas" if diagnostic.failures else "available_not_combined"),
        bootstrap_inputs=diagnostic_inputs, bootstrap_run_strata=run_strata,
        bootstrap_selection_counts=({name: dict(input=len(input_samples[name]), selected=len(sample_events),
                                               excluded=len(input_samples[name]) - len(sample_events))
                                     for name, sample_events in diagnostic_samples.items()} if diagnostic is not None else {}),
        bootstrap_fixed_inputs="signal MC template fixed; finite-MC uncertainty not resampled",
        command_options={name: str(value) if isinstance(value, Path) else value for name, value in vars(args).items()},
        event_poisson_ensemble="not_implemented; common event identity and model require review",
    )
    payload = RootOutputPayload(
        points=tuple(output_points),
        point_context=point_context,
        uncertainty_metadata=uncertainty_metadata,
        bootstrap_diagnostics=diagnostic,
        extraction_metadata={**(metadata or {}), "energy_bins": energy_inventory,
                             "energy_edges_gev": list(grid.edges_gev)},
        energy_edges=energy_edges,
        phi_edges=phi_edges,
        mass_edges={pair: pair_mass_edges(pair) for pair in PAIR_NAMES},
        covariance_total=covariance_total,
        systematic_covariances=systematic_covariances,
        ratio_objects=nominal.ratio_objects,
        binning_candidates=tuple(binning_candidates),
        candidate_ratio_objects=nominal.candidate_ratio_objects,
        provenance=(
            "raw_vs_kinematic_fit=disabled\n"
            "final_inference=suspended\n"
            f"sample={args.nominal_sample}\n"
            f"estimator={args.estimator}\n"
            f"profile={profile.name}\n"
            f"energy_edges_gev={json.dumps(grid.edges_gev)}\n"
            f"period={period}\n"
            f"{phi_provenance}"
            "phi_bin_correction=ratio_only_rounded\n"
            "POL1=vertical\nPOL2=horizontal\nBREM=independent-control\n"
            f"background={'sideband-corrected' if background_fractions else 'uncorrected'}\n"
            f"signal_mc_hard_sideband_leakage={background_leakage}\n"
            "best_quartet_resolved=false"
        ),
        statistical_covariance=statistical_covariance,
        bootstrap_covariance=bootstrap_covariance,
    )
    write_root_output(args.output_dir / "beam_asymmetry.root", payload)
    plots_dir = args.plots_dir if args.plots_dir is not None else args.output_dir
    active_rows = profile_energy_rows(profile.name, grid.edges_gev)
    points_by_profile = {profile.name: output_points}
    write_profile_figure4_pdf(
        plots_dir / "figure4_experimental.pdf",
        points_by_profile,
        active_rows,
        sample=args.nominal_sample,
        estimator=figure_estimator,
    )
    write_point_comparison_pdf(
        plots_dir / "comparison_reconstruction_samples.pdf",
        [item for item in output_points if item.estimator == figure_estimator],
        group_by="sample",
    )
    write_profile_estimator_comparison_pdf(
        plots_dir / "comparison_estimators.pdf",
        points_by_profile,
        active_rows,
        sample=args.nominal_sample,
    )
    write_profile_fit_diagnostics_pdf(
        plots_dir / "fit_diagnostics.pdf",
        {
            profile.name: tuple(
                item
                for item in output_points
                if item.sample == args.nominal_sample and item.estimator == "ratio"
            )
        },
        active_rows,
        sample=args.nominal_sample,
    )
    write_systematic_summary_pdf(
        plots_dir / "systematic_summary.pdf",
        systematic_covariances,
        inventory=inventory,
    )
    if background_leakage is not None:
        write_background_control_pdf(
            plots_dir / "background_control.pdf",
            background_fractions,
            signal_leakage=background_leakage,
        )
    brem_events = select_brem_control(
        all_nominal_events,
        exposures,
        energy_range=grid.energy_range_gev,
        drop_missing=True,
    )
    brem_phi = {}
    if len(brem_events):
        brem_projections = project_all_pairs(
            brem_events.proton,
            brem_events.eta,
            brem_events.pi0,
        )
        brem_phi = {pair: brem_projections[pair][1] for pair in PAIR_NAMES}
    write_false_asymmetry_controls_pdf(
        plots_dir / "false_asymmetry_controls.pdf",
        brem_phi,
        phi_edges=phi_edges,
    )
    write_photon_multiplicity_pdf(
        plots_dir / "photon_multiplicity.pdf",
        inclusive_count=inclusive_count,
        exactly_four_count=exactly_four_count,
        shifts=(
            multiplicity_shift
            if multiplicity_shift is not None
            else np.array([], dtype=np.float64)
        ),
        best_quartet_resolved=False,
    )
    return payload


def _validate_energy_inputs(args):
    grid = energy_binning_from_args(args, args.profile)
    nominal_low, nominal_high = get_beam_profile(args.profile).energy_range_gev
    low, high = grid.energy_range_gev
    allow_legacy = low >= nominal_low and high <= nominal_high
    from reconstruction.runtime.provenance import validate_energy_domain
    import ROOT
    inputs = [(_sample_path(args, name), sample.requires_bdt) for name, sample in SAMPLES.items()
              if _sample_path(args, name) is not None
              and (name == args.nominal_sample or _sample_path(args, name).is_file())]
    if args.sideband is not None:
        inputs.append((args.sideband, True))
    if args.signal_mc is not None:
        inputs.append((args.signal_mc, True))
    for path, requires_bdt in inputs:
        # Missing nominal inputs are reported by the existing event reader.
        if allow_legacy and not path.is_file():
            continue
        source = ROOT.TFile.Open(str(path), "READ")
        if not source or source.IsZombie():
            raise ValueError(f"cannot validate energy domain: {path}")
        try:
            record = source.Get("reconstruction_provenance")
            metadata = json.loads(record.GetTitle()) if record else {}
            validate_energy_domain(metadata, args.profile, grid.energy_range_gev,
                                   requires_bdt=requires_bdt, allow_legacy=allow_legacy)
        finally:
            source.Close()


def run(args: argparse.Namespace) -> int:
    _validate_energy_inputs(args)
    if args.by_period:
        _run_periods(args)
    else:
        if args.run_universe_manifest is not None:
            raise ValueError("--run-universe-manifest requires --by-period")
        _run_single(args)
    return 0


def _period_metadata(period, runs, samples, exposures, flux_audit, cutflows, profile, grid):
    return dict(
        period=period, status="estimable", run_universe=sorted(runs),
        exposed_runs=sorted({key[0] for key in exposures}),
        missing_exposure_runs=sorted(set(runs) - {key[0] for key in exposures}),
        samples={name: selection_audit(events, exposures, grid.energy_range_gev)
                 for name, events in samples.items()},
        exposure=exposure_summary(exposures),
        # Retain zero-yield strata and enough information to reconstruct normalization.
        exposure_strata=[vars(value) for _, value in sorted(exposures.items())],
        flux_audit={str(run): flux_audit.get(str(run), {}) for run in sorted(runs)},
        reconstruction_cutflow={name: [row for row in rows if row["run"] in runs]
                               for name, rows in cutflows.items()},
    )


def _partition_closure(args, groups, inputs, sample_keys, exposures, reference, profile):
    """Re-extract the disjoint union; compare estimates, not means of estimates."""
    grid = energy_binning_from_args(args, profile.name)
    rebuilt_exposures = {}
    for runs in groups.values():
        subset = {key: value for key, value in exposures.items() if key[0] in runs}
        if rebuilt_exposures.keys() & subset.keys():
            raise ValueError("period exposure partitions overlap")
        rebuilt_exposures.update(subset)
    if rebuilt_exposures != exposures:
        raise ValueError("period exposure union differs from pooled exposures")
    ref = {_point_key(item): item.sigma_uncorrected for item in reference.points}
    reconstructed = {}
    counts = {}
    for name, key in sample_keys.items():
        original = inputs[key]
        chunks = [original.take(np.isin(original.run_number, runs)) for runs in groups.values()]
        joined = EventArrays(**{field.name: np.concatenate([getattr(chunk, field.name) for chunk in chunks])
                                for field in fields(EventArrays)})
        if len(joined) != len(original):
            raise ValueError("period event union differs from pooled input")
        selected = select_sigma_events(joined, rebuilt_exposures,
                                       energy_range=grid.energy_range_gev, drop_missing=True)
        expected = select_sigma_events(original, exposures,
                                       energy_range=grid.energy_range_gev, drop_missing=True)
        if len(selected) != len(expected):
            raise ValueError("period selection differs from pooled selection")
        counts[name] = len(selected)
        result = _extract_sample(sample_name=name, events=selected, exposures=rebuilt_exposures,
                                 estimator=args.estimator, retain_ratio_objects=False,
                                 energy_edges=np.asarray(grid.edges_gev),
                                 phi_edges=phi_edges_rad(args.phi_bins),
                                 **({"best_binning": True} if getattr(args, "best_binning", False) else {}))
        reconstructed.update({_point_key(item): item.point.sigma for item in result.points
                              if item.point.diagnostics.converged})
    if reconstructed.keys() != ref.keys():
        raise ValueError("period union changes estimable bins")
    differences = [abs(reconstructed[key] - ref[key]) for key in ref]
    if not np.allclose(list(reconstructed.values()), [ref[key] for key in reconstructed],
                       rtol=1e-8, atol=1e-8):
        raise ValueError("period union does not reproduce pooled Sigma")
    return dict(same_estimable_bins=True, same_event_counts=True, same_exposure_strata=True,
                selected_counts=counts, max_abs_sigma_difference=max(differences, default=0.0),
                tolerance=1e-8, comparison="uncorrected fits before any common background correction")


def _run_periods(args):
    profile = get_beam_profile(args.profile)
    grid = energy_binning_from_args(args, args.profile)
    records = validate_manifest(args.run_manifest)
    # Validate labels before using them as directory names, including absent periods.
    partition_runs(records, set(), target=profile.target, beam_type=profile.beam_type)
    inputs, sample_keys, cutflows, universes = {}, {}, {}, {}
    paths = [args.run_manifest, args.flux_file]
    explicit = None
    if args.run_universe_manifest is not None:
        explicit_records = validate_manifest(args.run_universe_manifest)
        canonical = {record.run_number: record for record in records}
        for record in explicit_records:
            if record != canonical.get(record.run_number):
                raise ValueError(f"inclusive manifest conflicts with canonical manifest for run {record.run_number}")
        explicit = {record.run_number for record in explicit_records}
        paths.append(args.run_universe_manifest)
    for name, contract in SAMPLES.items():
        path = _sample_path(args, name)
        if path is None or (name != args.nominal_sample and not path.is_file()):
            continue
        key = (path, contract.tree, contract.vector_mode)
        sample_keys[name] = key
        inputs[key] = read_reconstructed(path, contract.tree, vector_mode=contract.vector_mode,
                                          require_no_fit=args.raw_bdt_fit is None)
        paths.append(path)
        if explicit is None:
            universes[name], cutflows[name] = read_run_universe(path)
        else:
            recorded, cutflows[name] = read_run_universe(path, allow_missing=True)
            if recorded is not None and recorded != explicit:
                raise ValueError(f"{name}: explicit run universe differs from reconstruction cutflow")
            universes[name] = explicit
    if args.nominal_sample not in sample_keys:
        raise ValueError("nominal sample is unavailable")
    runs = universes[args.nominal_sample]
    for name, universe in universes.items():
        if universe != runs:
            raise ValueError(f"{name}: inclusive run universe differs from nominal sample")
    groups = partition_runs(records, runs, target=profile.target, beam_type=profile.beam_type)
    if not groups:
        raise ValueError("inclusive run universe is empty")
    for name, key in sample_keys.items():
        unknown = set(map(int, inputs[key].run_number)) - runs
        if unknown:
            raise ValueError(f"{name}: unknown input runs outside inclusive universe: {sorted(unknown)}")
    broad_key = mc_key = None
    if (args.sideband is None) != (args.signal_mc is None):
        raise ValueError("--sideband and --signal-mc must be supplied together")
    if args.sideband is not None:
        broad_key, mc_key = (args.sideband, SIDEBAND_TREE, "raw"), (args.signal_mc, SIDEBAND_TREE, "raw")
        inputs[broad_key] = read_reconstructed(args.sideband, SIDEBAND_TREE, vector_mode="raw",
                                               require_no_fit=args.raw_bdt_fit is None)
        inputs[mc_key] = read_reconstructed(args.signal_mc, SIDEBAND_TREE, vector_mode="raw")
        if explicit is None:
            broad_universe, cutflows["sideband"] = read_run_universe(args.sideband)
        else:
            broad_universe, cutflows["sideband"] = read_run_universe(args.sideband, allow_missing=True)
            if broad_universe is None:
                broad_universe = explicit
        if broad_universe != runs:
            raise ValueError("sideband inclusive run universe differs from nominal sample")
        if set(map(int, inputs[broad_key].run_number)) - runs:
            raise ValueError("sideband input runs outside inclusive universe")
        paths.extend([args.sideband, args.signal_mc])
    flux_audit = {}
    exposures = load_exposures(args.flux_file, manifest_path=args.run_manifest, run_numbers=runs,
                              polarization_model=profile.polarization, target=profile.target,
                              beam_type=profile.beam_type, energy_range=grid.energy_range_gev,
                              audit=flux_audit, allow_empty=True)
    if {key[0] for key in exposures} - runs:
        raise ValueError("exposures outside inclusive run universe")
    identities = file_identities(set(paths))
    campaign = str(args.output_dir.resolve())
    all_periods = sorted({record.source_period for record in records
                          if record.target == profile.target and record.beam_type == profile.beam_type})
    index = dict(schema_version=1, profile=profile.name, final_inference="suspended",
                 universe_source="explicit_manifest" if explicit is not None else "reconstruction_cutflow",
                 inputs=identities, versions=dict(python=sys.version, numpy=np.__version__),
                 command_options={name: str(value) if isinstance(value, Path) else value for name, value in vars(args).items()},
                 periods=[], shared_nuisances={})
    source_root = Path(__file__).parent
    index["source_files"] = file_identities([Path(__file__),
        *(path for folder in ("core", "calibration", "io", "plotting")
          for path in (source_root / folder).glob("*.py"))])
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=source_root,
                              capture_output=True, text=True, check=False)
    index["source_revision"] = revision.stdout.strip() or "unknown"
    period_points, nuisance_responses = {}, {}
    with atomic_output_directory(args.output_dir) as output:
        for period, selected_runs in [("pooled", sorted(runs)), *[(name, groups[name]) for name in all_periods if name in groups]]:
            subset = {key: (events if key == mc_key else events.take(np.isin(events.run_number, selected_runs)))
                      for key, events in inputs.items()}
            subset_exposures = {key: value for key, value in exposures.items() if key[0] in selected_runs}
            named_samples = {name: subset[key] for name, key in sample_keys.items()}
            if broad_key is not None:
                named_samples["sideband"] = subset[broad_key]
            metadata = _period_metadata(period, selected_runs, named_samples, subset_exposures,
                                        flux_audit, cutflows, profile, grid)
            metadata.update(input_identities=identities, universe_source=index["universe_source"],
                            command_options=index["command_options"], versions=index["versions"],
                            source_files=index["source_files"], source_revision=index["source_revision"])
            destination = output if period == "pooled" else output / "periods" / period
            child_args = argparse.Namespace(**vars(args))
            child_args.output_dir, child_args.plots_dir = destination, None
            payload = _run_single(child_args, prepared=(subset, subset_exposures), period=period,
                                  metadata=metadata, campaign=campaign)
            metadata["point_keys"] = ordered_point_keys(payload.points, payload.point_context)
            metadata["estimable_points"] = len(payload.points)
            if period == "pooled":
                index["aggregate"] = metadata
                index["closure"] = _partition_closure(args, groups, inputs, sample_keys, exposures, payload, profile)
            else:
                metadata["root"] = f"{period}/beam_asymmetry.root"
                index["periods"].append(metadata)
                period_points[period] = payload.points
                source = payload.uncertainty_metadata.get("sources", {}).get("polarization_scale_3pct")
                if source:
                    nuisance_responses[period] = dict(point_keys=metadata["point_keys"],
                                                      signed_shift=source["signed_shift"])
        for period in all_periods:
            if period not in groups:
                index["periods"].append(dict(period=period, status="not_available", run_universe=[],
                                              reason="no runs in inclusive input universe"))
        index["periods"].sort(key=lambda row: row["period"])
        index["shared_nuisances"]["polarization_scale_3pct"] = dict(
            correlation="shared_across_periods", responses=nuisance_responses,
            cross_covariance="outer product of signed response vectors; diagnostic legacy model")
        index["other_cross_period_covariances"] = "unknown; no independence assumed; no significance or pulls"
        index["period_differences"] = []
        names = sorted(period_points)
        for i, left in enumerate(names):
            a = {_point_key(item): item for item in period_points[left]}
            for right in names[i + 1:]:
                b = {_point_key(item): item for item in period_points[right]}
                for key in sorted(a.keys() & b.keys()):
                    index["period_differences"].append(dict(
                        period_a=left, period_b=right, sample=key[0], pair=key[1],
                        energy_bin=key[2], mass_bin=key[3], estimator=key[4],
                        sigma_difference=a[key].point.sigma - b[key].point.sigma,
                        uncertainty_status="not_evaluated; correlated nuisances unresolved"))
        write_period_stability_pdf(output / "period_stability.pdf", period_points,
                                   profile_energy_rows(profile.name, grid.edges_gev), sample=args.nominal_sample,
                                   estimator="ratio" if args.estimator in {"both", "ratio"} else "likelihood")
        (output / "periods").mkdir(exist_ok=True)
        (output / "periods/index.json").write_text(json.dumps(index, indent=2, allow_nan=False) + "\n")
    if args.plots_dir is not None and args.plots_dir.resolve() != args.output_dir.resolve():
        args.plots_dir.mkdir(parents=True, exist_ok=True)
        for path in args.output_dir.glob("*.pdf"):
            shutil.copy2(path, args.plots_dir / path.name)


def main(argv: Sequence[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
