"""Systematic studies, covariance composition and run bootstrap orchestration."""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import sys
from typing import Sequence

import numpy as np

from calibration.run_manifest import validate_manifest
from reconstruction.runtime.provenance import file_identities
from observable_extraction.extraction import extract_sample
from observable_extraction.calibration.flux_v2 import load_exposures
from observable_extraction.core.binning import PHI_EDGES_RAD
from observable_extraction.core.background import BackgroundEstimate
from observable_extraction.core.photon_multiplicity import compare_multiplicity_selections
from observable_extraction.core.systematics import (
    REQUIRED_SYSTEMATICS, PairedBootstrapResult, paired_bootstrap_by_run,
    bootstrap_by_run, component_from_shift,
)
from observable_extraction.extraction_background import (
    _apply_background_correction, _estimate_background_fractions, _background_asymmetries,
)
from observable_extraction.io.reconstructed_events import select_sigma_events
from observable_extraction.io.root_output import OutputPoint, ordered_point_keys, point_key_label


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
    workers: int = 1,
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
        bundle = extract_sample(
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
        workers=workers,
    )
    embedded = np.zeros((len(points), len(points)), dtype=np.float64)
    embedded[np.ix_(selected_indices, selected_indices)] = result.covariance
    return embedded


def _paired_bootstrap_diagnostics(
    *, points, samples, exposures, run_strata, point_keys, nominal_sample,
    estimator, replicas, seed, energy_edges, phi_edges,
    broad_events=None, signal_mc=None, best_binning=False,
    workers=1,
):
    ensemble_samples = dict(samples)
    if broad_events is not None:
        if signal_mc is None:
            raise ValueError("background diagnostics require signal MC")
        ensemble_samples["sideband"] = broad_events

    def estimate(replica_samples, replica_exposures):
        fitted = {}
        for name in samples:
            bundle = extract_sample(
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
        point_keys=point_keys, replicas=replicas, seed=seed, workers=workers)


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
    workers: int = 1,
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
        bundle = extract_sample(
            sample_name=sample_name,
            events=selected_events,
            exposures=exposures,
            estimator=estimator,
            retain_ratio_objects=False,
            energy_edges=energy_edges,
            phi_edges=phi_edges,
            workers=workers,
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


@dataclass(frozen=True)
class UncertaintyResult:
    output_points: list[OutputPoint]
    systematic_covariances: dict[str, np.ndarray]
    statistical_covariance: np.ndarray
    bootstrap_covariance: np.ndarray | None
    covariance_total: np.ndarray
    point_context: dict
    uncertainty_metadata: dict
    diagnostic: PairedBootstrapResult | None
    inventory: dict
    multiplicity_shift: np.ndarray | None
    inclusive_count: int
    exactly_four_count: int
    figure_estimator: str


def evaluate_uncertainties(
    args, *, sample_paths, output_points, events, exposures, samples, input_samples,
    background_fractions, background_by_bin, broad_events, broad_input_events,
    signal_mc, energy_edges, phi_edges, binning_options, profile, grid, metadata,
    period, campaign, quality,
) -> UncertaintyResult:
    """Evaluate existing variations once and assemble their published uncertainty payload."""
    workers = binning_options["workers"]
    best_binning = bool(binning_options.get("best_binning", False))
    quality_excluded_runs = {item["run"] for item in quality["excluded_runs"]}
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
            workers=workers,
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
                         selection="pairing_missing_mass",
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
        run_strata = {record.run_number: f"{profile.name}:{record.source_period}" for record in records
                      if record.run_number not in quality_excluded_runs}
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
            beam_type=profile.beam_type, energy_range=grid.energy_range_gev, run_quality=quality)
        exposed = {exposure.run_number for exposure in diagnostic_exposures.values()}
        if exposed != set(run_strata):
            raise ValueError(f"bootstrap universe has missing exposures: {sorted(set(run_strata) - exposed)}")
        diagnostic_samples = {name: select_sigma_events(
            sample_events, diagnostic_exposures, energy_range=grid.energy_range_gev, drop_missing=True, run_quality=quality)
            for name, sample_events in input_samples.items()}
        diagnostic_broad = None if broad_input_events is None else select_sigma_events(
            broad_input_events, diagnostic_exposures, energy_range=grid.energy_range_gev, drop_missing=True, run_quality=quality)
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
            *(sample_paths[name] for name in input_samples),
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
    return UncertaintyResult(
        output_points, systematic_covariances, statistical_covariance,
        bootstrap_covariance, covariance_total, point_context, uncertainty_metadata,
        diagnostic, inventory, multiplicity_shift, inclusive_count,
        exactly_four_count, figure_estimator,
    )
