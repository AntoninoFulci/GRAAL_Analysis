"""Standalone extraction of gamma p -> eta pi0 p beam asymmetry."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from pathlib import Path
import sys
from typing import Sequence

import numpy as np

from graal_common.physics.channels import ETA_PI0_HYP, M_ETA, M_PI0, M_PROTON

from observable_extraction.calibration.flux_v2 import load_exposures
from observable_extraction.core.binning import (
    ENERGY_EDGES_GEV,
    PHI_EDGES_RAD,
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
from observable_extraction.core.kinematics import project_all_pairs
from observable_extraction.core.photon_multiplicity import (
    compare_multiplicity_selections,
)
from observable_extraction.core.ratio_fit import extract_ratio_grid
from observable_extraction.core.systematics import (
    bootstrap_by_run,
    component_from_shift,
    polarization_scale_component,
)
from observable_extraction.io.reconstructed_events import (
    read_reconstructed,
    select_brem_control,
    select_sigma_events,
)
from observable_extraction.io.root_output import (
    OutputPoint,
    RatioObject,
    RootOutputPayload,
    write_root_output,
)
from observable_extraction.plotting.figure4 import write_figure4_pdf
from observable_extraction.plotting.diagnostics import (
    write_fit_diagnostics_pdf,
    write_background_control_pdf,
    write_false_asymmetry_controls_pdf,
    write_photon_multiplicity_pdf,
    write_point_comparison_pdf,
    write_systematic_summary_pdf,
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
        default=Path("results/reco/reco_eta_pi0_bdt_fit.root"),
    )
    parser.add_argument("--sideband", type=Path)
    parser.add_argument("--signal-mc", type=Path)
    parser.add_argument(
        "--calibration-dir",
        type=Path,
        default=Path("results/strip_energy_flux"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/beam_asymmetry"),
    )
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
    parser.add_argument("--phi-bins", type=int, default=12)
    parser.add_argument("--mass-bins", type=int, default=10)
    parser.add_argument("--bootstrap-replicas", type=int, default=0)
    parser.add_argument("--bootstrap-seed", type=int, default=1208)
    return parser


def _sample_path(args: argparse.Namespace, sample: str) -> Path:
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


def _likelihood_output_point(sample: str, result, ratio_by_bin) -> OutputPoint:
    point = result.point
    ratio = ratio_by_bin.get((point.pair, point.energy_bin, point.mass_bin))
    return OutputPoint(
        sample=sample,
        estimator="likelihood",
        point=point,
        sigma_uncorrected=point.sigma,
        systematic_total=0.0,
        background_fraction=0.0,
        count_vertical=(int(np.sum(ratio.counts_vertical)) if ratio else 0),
        count_horizontal=(int(np.sum(ratio.counts_horizontal)) if ratio else 0),
        flux_vertical=(ratio.flux_vertical if ratio else 0.0),
        flux_horizontal=(ratio.flux_horizontal if ratio else 0.0),
        polarization_vertical=(ratio.polarization_vertical if ratio else 0.0),
        polarization_horizontal=(ratio.polarization_horizontal if ratio else 0.0),
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
        zip(ENERGY_EDGES_GEV[:-1], ENERGY_EDGES_GEV[1:])
    ):
        last = energy_bin == len(ENERGY_EDGES_GEV) - 2
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
) -> ExtractionBundle:
    projections = project_all_pairs(events.proton, events.eta, events.pi0)
    output_points: list[OutputPoint] = []
    ratio_objects: list[RatioObject] = []
    ratio_by_bin = {}
    for pair in PAIR_NAMES:
        masses, phis = projections[pair]
        ratio_results = extract_ratio_grid(
            pair=pair,
            mass_gev=masses,
            phi_rad=phis,
            beam_energy_gev=events.beam_energy_gev,
            polarization=events.polarization,
            exposures=exposures,
        )
        ratio_by_bin.update(
            {
                (pair, item.point.energy_bin, item.point.mass_bin): item
                for item in ratio_results
            }
        )
        if estimator in {"ratio", "both"}:
            output_points.extend(
                _ratio_output_point(sample_name, item) for item in ratio_results
            )
            if retain_ratio_objects:
                phi_centers = 0.5 * (PHI_EDGES_RAD[:-1] + PHI_EDGES_RAD[1:])
                for item in ratio_results:
                    used = item.fit.used_mask
                    ratio_objects.append(
                        RatioObject(
                            pair=pair,
                            energy_bin=item.point.energy_bin,
                            mass_bin=item.point.mass_bin,
                            phi=phi_centers[used],
                            value=item.fit.ratio[used],
                            error=item.fit.ratio_error[used],
                            sigma=item.point.sigma,
                        )
                    )
        if estimator in {"likelihood", "both"}:
            likelihood_results = extract_likelihood_grid(
                pair=pair,
                mass_gev=masses,
                phi_rad=phis,
                beam_energy_gev=events.beam_energy_gev,
                polarization=events.polarization,
                run_number=events.run_number,
                xstrip=events.xstrip,
                exposures=exposures,
            )
            output_points.extend(
                _likelihood_output_point(sample_name, item, ratio_by_bin)
                for item in likelihood_results
            )
    return ExtractionBundle(tuple(output_points), tuple(ratio_objects))


def _point_key(output: OutputPoint, *, include_estimator: bool = True) -> tuple:
    point = output.point
    key = (output.sample, point.pair, point.energy_bin, point.mass_bin)
    return (*key, output.estimator) if include_estimator else key


def _systematic_covariances(
    points: Sequence[OutputPoint],
    extra_shifts: dict[str, np.ndarray] | None = None,
) -> dict[str, np.ndarray]:
    """Build only systematic components supported by available variations."""
    if not points:
        return {}
    sigma = np.array([item.point.sigma for item in points], dtype=np.float64)
    components = [polarization_scale_component(sigma)]

    lookup = {_point_key(item): item for item in points}
    estimator_shift = np.zeros(len(points), dtype=np.float64)
    reconstruction_shift = np.zeros(len(points), dtype=np.float64)
    background_shift = np.zeros(len(points), dtype=np.float64)
    angular_shift = np.zeros(len(points), dtype=np.float64)
    for index, item in enumerate(points):
        point = item.point
        other_estimator = "likelihood" if item.estimator == "ratio" else "ratio"
        counterpart = lookup.get(
            (item.sample, point.pair, point.energy_bin, point.mass_bin, other_estimator)
        )
        if counterpart is not None:
            estimator_shift[index] = 0.5 * (
                counterpart.point.sigma - point.sigma
            )
        if item.sample in {"raw_bdt", "raw_bdt_fit"}:
            other_sample = (
                "raw_bdt_fit" if item.sample == "raw_bdt" else "raw_bdt"
            )
            counterpart = lookup.get(
                (other_sample, point.pair, point.energy_bin, point.mass_bin, item.estimator)
            )
            if counterpart is not None:
                reconstruction_shift[index] = 0.5 * (
                    counterpart.point.sigma - point.sigma
                )
        background_shift[index] = point.sigma - item.sigma_uncorrected
        if point.diagnostics.s2 is not None:
            angular_shift[index] = point.diagnostics.s2

    for name, shift in (
        ("estimator_ratio_vs_likelihood", estimator_shift),
        ("raw_vs_kinematic_fit", reconstruction_shift),
        ("background_template", background_shift),
        ("angular_offset_sine_leakage", angular_shift),
    ):
        if np.any(shift != 0.0):
            components.append(component_from_shift(name, shift))
    for name, shift in (extra_shifts or {}).items():
        components.append(component_from_shift(name, shift))
    return {item.name: item.covariance for item in components}


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


def _photon_multiplicity_component(
    *,
    points: Sequence[OutputPoint],
    events,
    exposures,
    sample_name: str,
    estimator: str,
    fractions: dict[int, BackgroundEstimate],
    background_by_bin: dict,
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


def run(args: argparse.Namespace) -> int:
    if args.phi_bins != 12 or args.mass_bins != 10:
        raise ValueError("nominal extraction requires 12 phi bins and 10 mass bins")
    if (args.sideband is None) != (args.signal_mc is None):
        raise ValueError("--sideband and --signal-mc must be supplied together")
    exposures = load_exposures(args.calibration_dir / "flux_by_run_strip.csv")
    sample = SAMPLES[args.nominal_sample]
    all_nominal_events = read_reconstructed(
        _sample_path(args, args.nominal_sample),
        sample.tree,
        vector_mode=sample.vector_mode,
    )
    events = select_sigma_events(all_nominal_events, exposures)
    nominal = _extract_sample(
        sample_name=args.nominal_sample,
        events=events,
        exposures=exposures,
        estimator=args.estimator,
        retain_ratio_objects=True,
    )
    output_points = list(nominal.points)
    background_fractions: dict[int, BackgroundEstimate] = {}
    background_leakage: float | None = None
    background_by_bin: dict = {}
    if args.sideband is not None:
        broad_events = select_sigma_events(
            read_reconstructed(args.sideband, SIDEBAND_TREE, vector_mode="raw"),
            exposures,
        )
        signal_mc = read_reconstructed(
            args.signal_mc,
            SIDEBAND_TREE,
            vector_mode="raw",
        )
        background_fractions, background_leakage = _estimate_background_fractions(
            broad_events,
            signal_mc,
        )
        background_by_bin = _background_asymmetries(
            broad_events,
            exposures,
            args.estimator,
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
        if not path.is_file():
            print(
                f"warning: optional comparison sample missing: {sample_name} ({path})",
                file=sys.stderr,
            )
            continue
        comparison_events = select_sigma_events(
            read_reconstructed(path, contract.tree, vector_mode=contract.vector_mode),
            exposures,
        )
        comparison = _extract_sample(
            sample_name=sample_name,
            events=comparison_events,
            exposures=exposures,
            estimator=args.estimator,
            retain_ratio_objects=False,
        )
        output_points.extend(comparison.points)
    if not output_points:
        raise RuntimeError("no beam-asymmetry bins could be fitted")

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
    payload = RootOutputPayload(
        points=tuple(output_points),
        energy_edges=ENERGY_EDGES_GEV,
        mass_edges={pair: pair_mass_edges(pair) for pair in PAIR_NAMES},
        covariance_total=covariance_total,
        systematic_covariances=systematic_covariances,
        ratio_objects=nominal.ratio_objects,
        provenance=(
            f"sample={args.nominal_sample}\n"
            f"estimator={args.estimator}\n"
            "POL1=vertical\nPOL2=horizontal\nBREM=independent-control\n"
            f"background={'sideband-corrected' if background_fractions else 'uncorrected'}\n"
            f"signal_mc_hard_sideband_leakage={background_leakage}\n"
            "best_quartet_resolved=false"
        ),
        statistical_covariance=statistical_covariance,
        bootstrap_covariance=bootstrap_covariance,
    )
    write_root_output(args.output_dir / "beam_asymmetry.root", payload)
    write_figure4_pdf(
        args.output_dir / "figure4_experimental.pdf",
        output_points,
        sample=args.nominal_sample,
        estimator=figure_estimator,
    )
    write_point_comparison_pdf(
        args.output_dir / "comparison_reconstruction_samples.pdf",
        [item for item in output_points if item.estimator == figure_estimator],
        group_by="sample",
    )
    write_point_comparison_pdf(
        args.output_dir / "comparison_estimators.pdf",
        [item for item in output_points if item.sample == args.nominal_sample],
        group_by="estimator",
    )
    write_fit_diagnostics_pdf(
        args.output_dir / "fit_diagnostics.pdf",
        [item for item in output_points if item.sample == args.nominal_sample],
    )
    write_systematic_summary_pdf(
        args.output_dir / "systematic_summary.pdf",
        systematic_covariances,
    )
    if background_leakage is not None:
        write_background_control_pdf(
            args.output_dir / "background_control.pdf",
            background_fractions,
            signal_leakage=background_leakage,
        )
    brem_events = select_brem_control(all_nominal_events, exposures)
    brem_phi = {}
    if len(brem_events):
        brem_projections = project_all_pairs(
            brem_events.proton,
            brem_events.eta,
            brem_events.pi0,
        )
        brem_phi = {pair: brem_projections[pair][1] for pair in PAIR_NAMES}
    write_false_asymmetry_controls_pdf(
        args.output_dir / "false_asymmetry_controls.pdf",
        brem_phi,
    )
    write_photon_multiplicity_pdf(
        args.output_dir / "photon_multiplicity.pdf",
        inclusive_count=inclusive_count,
        exactly_four_count=exactly_four_count,
        shifts=(
            multiplicity_shift
            if multiplicity_shift is not None
            else np.array([], dtype=np.float64)
        ),
        best_quartet_resolved=False,
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
