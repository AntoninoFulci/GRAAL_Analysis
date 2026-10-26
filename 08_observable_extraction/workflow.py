"""Read, extract and publish one observable result."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

from calibration.run_quality import load_run_quality
from graal_common.physics.beam_profiles import get_beam_profile
from graal_common.physics.channels import M_ETA, M_PI0
from graal_common.parallel import validate_workers
from graal_common.physics.energy_binning import energy_binning_from_args
from observable_extraction.extraction import extract_sample
from observable_extraction.samples import SAMPLES
from observable_extraction.calibration.flux_v2 import load_exposures
from observable_extraction.core.binning import phi_edges_rad, phi_bin_divisor, PAIR_NAMES, pair_mass_edges
from observable_extraction.core.energy_audit import energy_bin_inventory
from observable_extraction.core.background import BackgroundEstimate
from observable_extraction.core.kinematics import project_all_pairs
from observable_extraction.extraction_background import (
    SIDEBAND_TREE, _estimate_background_fractions,
    _background_asymmetries, _apply_background_correction,
)
from observable_extraction.extraction_systematics import (
    _selected_phi_bins, _point_key, evaluate_uncertainties,
)
from observable_extraction.io.reconstructed_events import (
    read_reconstructed, select_brem_control, select_sigma_events,
    split_candle_core_tails,
)
from observable_extraction.io.root_output import (
    RootOutputPayload, write_root_output, ordered_point_keys,
)
from observable_extraction.plotting.figure4 import profile_energy_rows, write_profile_figure4_pdf
from observable_extraction.plotting.candle import (
    available_candle_estimators,
    write_candle_comparison_pdf,
    write_candle_mass_plane_pdf,
)
from observable_extraction.plotting.diagnostics import (
    write_background_control_pdf, write_false_asymmetry_controls_pdf,
    write_photon_multiplicity_pdf, write_point_comparison_pdf,
    write_profile_estimator_comparison_pdf, write_profile_fit_diagnostics_pdf,
    write_systematic_summary_pdf,
)


def _sample_path(args: argparse.Namespace, sample: str) -> Path | None:
    return {
        "raw": args.raw,
        "raw_bdt": args.raw_bdt,
    }[sample]


def _write_result_reports(plots_dir, *, profile_name, energy_edges, nominal_sample, uncertainty,
                          candle_split=None, candle_width=None, events=None):
    """Render the extracted results after the ROOT payload has been published."""
    output_points = uncertainty.output_points
    figure_estimator = uncertainty.figure_estimator
    active_rows = profile_energy_rows(profile_name, energy_edges)
    points_by_profile = {profile_name: output_points}
    if candle_split is not None:
        write_candle_mass_plane_pdf(
            plots_dir / "candle_mass_plane.pdf",
            events.eta_mass_gev,
            events.pi0_mass_gev,
            half_width_gev=candle_width,
            full_core_count=candle_split.full_core_count,
            tail_count=candle_split.tail_count,
            balanced_core_count=len(candle_split.core),
            excluded_nonfinite_count=candle_split.excluded_nonfinite_count,
        )
        for estimator in available_candle_estimators(points_by_profile):
            write_candle_comparison_pdf(
                plots_dir / f"comparison_candle_{estimator}.pdf",
                points_by_profile,
                active_rows,
                estimator=estimator,
            )
    write_profile_figure4_pdf(
        plots_dir / "figure4_experimental.pdf",
        points_by_profile,
        active_rows,
        sample=nominal_sample,
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
        sample=nominal_sample,
    )
    write_profile_fit_diagnostics_pdf(
        plots_dir / "fit_diagnostics.pdf",
        {
            profile_name: tuple(
                item
                for item in output_points
                if item.sample == nominal_sample and item.estimator == "ratio"
            )
        },
        active_rows,
        sample=nominal_sample,
    )
    write_systematic_summary_pdf(
        plots_dir / "systematic_summary.pdf",
        uncertainty.systematic_covariances,
        inventory=uncertainty.inventory,
    )


def validate_candle_options(args: argparse.Namespace) -> None:
    """Reject unsupported candle requests before inspecting input ROOT files."""
    width = getattr(args, "candle_mass_half_width", None)
    if width is None:
        return
    if not np.isfinite(width) or width <= 0.0:
        raise ValueError("candle mass half-width must be finite and positive")
    if args.nominal_sample != "raw_bdt":
        raise ValueError("candle selection requires --nominal-sample raw_bdt")
    if args.sideband is not None:
        raise ValueError("candle selection is not supported with sideband correction")
    seed = getattr(args, "candle_balance_seed", None)
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("candle balance seed must be a non-negative integer")
    if getattr(args, "bootstrap_diagnostics_replicas", 0):
        raise ValueError("candle selection does not support diagnostic bootstrap")


def _run_single(args: argparse.Namespace, *, prepared=None, period="pooled", metadata=None,
                campaign=None) -> RootOutputPayload:
    workers = validate_workers(getattr(args, "workers", 1))
    if args.bootstrap_diagnostics_replicas:
        if args.bootstrap_diagnostics_replicas < 2:
            raise ValueError("diagnostic bootstrap requires at least two replicas")
        if args.bootstrap_universe_manifest is None:
            raise ValueError("diagnostic bootstrap requires an explicit inclusive run universe manifest")
        if args.bootstrap_replicas:
            raise ValueError("choose diagnostic bootstrap or legacy bootstrap, not both")
    best_binning = getattr(args, "best_binning", False)
    if best_binning and args.estimator == "likelihood":
        raise ValueError("--best-binning requires ratio or both; likelihood is unbinned")
    binning_options = {"workers": workers}
    if best_binning:
        binning_options["best_binning"] = True
    phi_edges = phi_edges_rad(12 if best_binning else args.phi_bins)
    quality = None if metadata is None else metadata.get("run_quality")
    if quality is None:
        quality = load_run_quality(getattr(args, "run_quality", None))
    quality_provenance = f"run_quality={json.dumps(quality, sort_keys=True)}\n"
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
    def read_sample(path, tree):
        if prepared is not None:
            return prepared[0][(path, tree)]
        return read_reconstructed(path, tree)

    all_nominal_events = read_sample(
        _sample_path(args, args.nominal_sample),
        sample.tree,
    )
    exposures = prepared[1] if prepared is not None else load_exposures(
        args.flux_file,
        manifest_path=args.run_manifest,
        run_numbers=np.unique(all_nominal_events.run_number),
        polarization_model=profile.polarization,
        target=profile.target,
        beam_type=profile.beam_type,
        energy_range=grid.energy_range_gev,
        run_quality=quality,
    )
    events = select_sigma_events(
        all_nominal_events,
        exposures,
        energy_range=grid.energy_range_gev,
        drop_missing=True,
        run_quality=quality,
    )
    nominal = extract_sample(
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
    candle_split = None
    candle_width = getattr(args, "candle_mass_half_width", None)
    if candle_width is not None and period == "pooled":
        candle_split = split_candle_core_tails(
            events,
            candle_width,
            seed=args.candle_balance_seed,
        )
        for sample_name, selected_events in (
            ("raw_bdt_core", candle_split.core),
            ("raw_bdt_tails", candle_split.tails),
        ):
            extracted = extract_sample(
                sample_name=sample_name,
                events=selected_events,
                exposures=exposures,
                estimator=args.estimator,
                retain_ratio_objects=False,
                energy_edges=energy_edges,
                phi_edges=phi_edges,
                **binning_options,
            )
            if not extracted.points:
                raise RuntimeError(
                    f"candle {sample_name} produced no fitted bins: "
                    f"core={len(candle_split.core)} "
                    f"tails={len(candle_split.tails)}"
                )
            output_points.extend(extracted.points)
            binning_candidates.extend(extracted.binning_candidates)
    samples = {args.nominal_sample: events}
    input_samples = {args.nominal_sample: all_nominal_events}
    broad_input_events = None
    broad_events = signal_mc = None
    background_fractions: dict[int, BackgroundEstimate] = {}
    background_leakage: float | None = None
    background_by_bin: dict = {}
    if args.sideband is not None:
        broad_input_events = read_sample(args.sideband, SIDEBAND_TREE)
        broad_events = select_sigma_events(
            broad_input_events,
            exposures,
            energy_range=grid.energy_range_gev,
            drop_missing=True,
            run_quality=quality,
        )
        signal_mc = read_sample(
            args.signal_mc,
            SIDEBAND_TREE,
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
            workers=workers,
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
            path, contract.tree)
        comparison_events = select_sigma_events(
            input_samples[sample_name],
            exposures,
            energy_range=grid.energy_range_gev,
            drop_missing=True,
            run_quality=quality,
        )
        samples[sample_name] = comparison_events
        comparison = extract_sample(
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
                       selection="pairing_missing_mass")
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
                               selection="pairing_missing_mass"),
            extraction_metadata=metadata,
            uncertainty_metadata=dict(final_inference="suspended", status="not_estimable"),
            provenance=(f"profile={profile.name}\nperiod={period}\nstatus=not_estimable\n"
                        f"energy_edges_gev={json.dumps(grid.edges_gev)}\n"
                        f"{phi_provenance}{quality_provenance}"
                        "phi_bin_correction=ratio_only_rounded\nfinal_inference=suspended"),
        )
        write_root_output(args.output_dir / "beam_asymmetry.root", payload)
        return payload

    args.output_dir.mkdir(parents=True, exist_ok=True)
    uncertainty = evaluate_uncertainties(
        args, sample_paths={name: _sample_path(args, name) for name in input_samples},
        output_points=output_points, events=events, exposures=exposures,
        samples=samples, input_samples=input_samples, background_fractions=background_fractions,
        background_by_bin=background_by_bin, broad_events=broad_events,
        broad_input_events=broad_input_events, signal_mc=signal_mc,
        energy_edges=energy_edges, phi_edges=phi_edges, binning_options=binning_options,
        profile=profile, grid=grid, metadata=metadata, period=period, campaign=campaign, quality=quality,
    )
    output_points = uncertainty.output_points
    systematic_covariances = uncertainty.systematic_covariances
    statistical_covariance = uncertainty.statistical_covariance
    bootstrap_covariance = uncertainty.bootstrap_covariance
    covariance_total = uncertainty.covariance_total
    point_context = uncertainty.point_context
    uncertainty_metadata = uncertainty.uncertainty_metadata
    diagnostic = uncertainty.diagnostic
    multiplicity_shift = uncertainty.multiplicity_shift
    inclusive_count = uncertainty.inclusive_count
    exactly_four_count = uncertainty.exactly_four_count
    provenance_lines = [
        "final_inference=suspended",
        f"sample={args.nominal_sample}",
        f"estimator={args.estimator}",
        f"profile={profile.name}",
        f"energy_edges_gev={json.dumps(grid.edges_gev)}",
        f"period={period}",
        *phi_provenance.rstrip("\n").splitlines(),
        *quality_provenance.rstrip("\n").splitlines(),
        "phi_bin_correction=ratio_only_rounded",
        "POL1=vertical",
        "POL2=horizontal",
        "BREM=independent-control",
        f"background={'sideband-corrected' if background_fractions else 'uncorrected'}",
        f"signal_mc_hard_sideband_leakage={background_leakage}",
        "best_quartet_resolved=false",
    ]
    if candle_split is not None:
        provenance_lines.extend([
            "candle_enabled=true",
            f"candle_eta_center_gev={M_ETA}",
            f"candle_pi0_center_gev={M_PI0}",
            f"candle_mass_half_width_gev={candle_width}",
            "candle_geometry=rectangular",
            "candle_core_logic=and",
            "candle_tail_logic=or_complement",
            "candle_boundary=inclusive",
            f"candle_baseline_event_count={len(events)}",
            f"candle_full_core_event_count={candle_split.full_core_count}",
            f"candle_tail_event_count={candle_split.tail_count}",
            f"candle_balanced_core_event_count={len(candle_split.core)}",
            "candle_excluded_nonfinite_event_count="
            f"{candle_split.excluded_nonfinite_count}",
            "candle_balance_method=random_without_replacement",
            f"candle_balance_seed={args.candle_balance_seed}",
            "candle_mass_source=raw_pre_fit",
        ])
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
        provenance="\n".join(provenance_lines),
        statistical_covariance=statistical_covariance,
        bootstrap_covariance=bootstrap_covariance,
    )
    write_root_output(args.output_dir / "beam_asymmetry.root", payload)
    plots_dir = args.plots_dir if args.plots_dir is not None else args.output_dir
    _write_result_reports(
        plots_dir, profile_name=profile.name, energy_edges=grid.edges_gev,
        nominal_sample=args.nominal_sample, uncertainty=uncertainty,
        candle_split=candle_split, candle_width=candle_width, events=events,
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
        run_quality=quality,
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


def run_single(args: argparse.Namespace) -> int:
    """Validate the standalone request, then publish its extraction."""
    validate_workers(getattr(args, "workers", 1))
    validate_candle_options(args)
    _validate_energy_inputs(args)
    if args.run_universe_manifest is not None:
        raise ValueError("--run-universe-manifest requires --by-period")
    _run_single(args)
    return 0
