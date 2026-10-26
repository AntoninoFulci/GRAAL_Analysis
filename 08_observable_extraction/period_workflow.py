"""Partition inclusive run universes, publish periods and verify pooled closure."""
from __future__ import annotations

import argparse
from dataclasses import fields
import json
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np

from calibration.run_manifest import validate_manifest
from calibration.run_quality import load_run_quality
from reconstruction.runtime.provenance import file_identities
from graal_common.physics.beam_profiles import get_beam_profile
from graal_common.io.filesystem import atomic_output_directory
from graal_common.parallel import validate_workers
from graal_common.physics.energy_binning import energy_binning_from_args
from observable_extraction.extraction import extract_sample
from observable_extraction.samples import SAMPLES
from observable_extraction.calibration.flux_v2 import load_exposures
from observable_extraction.core.binning import phi_edges_rad
from observable_extraction.core.periods import partition_runs, selection_audit, exposure_summary
from observable_extraction.extraction_background import SIDEBAND_TREE
from observable_extraction.extraction_systematics import _point_key
from observable_extraction.workflow import (
    _sample_path,
    _run_single,
    _validate_energy_inputs,
    validate_candle_options,
)
from observable_extraction.io.reconstructed_events import (
    read_reconstructed, read_run_universe, EventArrays, select_sigma_events,
)
from observable_extraction.io.root_output import ordered_point_keys
from observable_extraction.plotting.figure4 import profile_energy_rows
from observable_extraction.plotting.diagnostics import write_period_stability_pdf


def _period_metadata(period, runs, samples, exposures, flux_audit, cutflows, profile, grid):
    return dict(
        period=period, status="estimable", run_universe=sorted(runs),
        run_quality=flux_audit["_run_quality"],
        exposed_runs=sorted({key[0] for key in exposures}),
        missing_exposure_runs=sorted(set(runs) - {key[0] for key in exposures}),
        samples={name: selection_audit(events, exposures, grid.energy_range_gev,
                                      run_quality=flux_audit["_run_quality"])
                 for name, events in samples.items()},
        exposure=exposure_summary(exposures),
        # Retain zero-yield strata and enough information to reconstruct normalization.
        exposure_strata=[vars(value) for _, value in sorted(exposures.items())],
        flux_audit={str(run): flux_audit.get(str(run), {}) for run in sorted(runs)},
        reconstruction_cutflow={name: [row for row in rows if row["run"] in runs]
                               for name, rows in cutflows.items()},
    )


def _partition_closure(args, groups, inputs, sample_keys, exposures, reference, profile, *, run_quality=None):
    """Re-extract the disjoint union; compare estimates, not means of estimates."""
    quality = load_run_quality(getattr(args, "run_quality", None)) if run_quality is None else run_quality
    grid = energy_binning_from_args(args, profile.name)
    rebuilt_exposures = {}
    for runs in groups.values():
        subset = {key: value for key, value in exposures.items() if key[0] in runs}
        if rebuilt_exposures.keys() & subset.keys():
            raise ValueError("period exposure partitions overlap")
        rebuilt_exposures.update(subset)
    if rebuilt_exposures != exposures:
        raise ValueError("period exposure union differs from pooled exposures")
    source_samples = set(sample_keys)
    ref = {
        _point_key(item): item.sigma_uncorrected
        for item in reference.points
        if item.sample in source_samples
    }
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
                                       energy_range=grid.energy_range_gev, drop_missing=True, run_quality=quality)
        expected = select_sigma_events(original, exposures,
                                       energy_range=grid.energy_range_gev, drop_missing=True, run_quality=quality)
        if len(selected) != len(expected):
            raise ValueError("period selection differs from pooled selection")
        counts[name] = len(selected)
        result = extract_sample(sample_name=name, events=selected, exposures=rebuilt_exposures,
                                 estimator=args.estimator, retain_ratio_objects=False,
                                 energy_edges=np.asarray(grid.edges_gev),
                                 phi_edges=phi_edges_rad(args.phi_bins),
                                 workers=getattr(args, "workers", 1),
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


def _source_identities(source_root: Path) -> list[dict]:
    """Hash runtime sources, including modules alongside the entry point."""
    return file_identities(
        path for folder in ("", "core", "calibration", "io", "plotting")
        for path in (source_root / folder).glob("*.py")
    )


def run_periods(args) -> int:
    validate_workers(getattr(args, "workers", 1))
    validate_candle_options(args)
    _validate_energy_inputs(args)
    quality = load_run_quality(getattr(args, "run_quality", None))
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
        key = (path, contract.tree)
        sample_keys[name] = key
        inputs[key] = read_reconstructed(path, contract.tree)
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
        broad_key, mc_key = (args.sideband, SIDEBAND_TREE), (args.signal_mc, SIDEBAND_TREE)
        inputs[broad_key] = read_reconstructed(args.sideband, SIDEBAND_TREE)
        inputs[mc_key] = read_reconstructed(args.signal_mc, SIDEBAND_TREE)
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
    flux_audit = {"_run_quality": quality}
    exposures = load_exposures(args.flux_file, manifest_path=args.run_manifest, run_numbers=runs,
                              polarization_model=profile.polarization, target=profile.target,
                              beam_type=profile.beam_type, energy_range=grid.energy_range_gev,
                              audit=flux_audit, allow_empty=True, run_quality=quality)
    if {key[0] for key in exposures} - runs:
        raise ValueError("exposures outside inclusive run universe")
    paths.append(Path(quality["path"]))
    identities = file_identities(set(paths))
    campaign = str(args.output_dir.resolve())
    all_periods = sorted({record.source_period for record in records
                          if record.target == profile.target and record.beam_type == profile.beam_type})
    index = dict(schema_version=1, profile=profile.name, final_inference="suspended",
                 run_quality=flux_audit["_run_quality"],
                 universe_source="explicit_manifest" if explicit is not None else "reconstruction_cutflow",
                 inputs=identities, versions=dict(python=sys.version, numpy=np.__version__),
                 command_options={name: str(value) if isinstance(value, Path) else value for name, value in vars(args).items()},
                 periods=[], shared_nuisances={})
    source_root = Path(__file__).parent
    index["source_files"] = _source_identities(source_root)
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
                index["closure"] = _partition_closure(args, groups, inputs, sample_keys, exposures, payload, profile,
                                                       run_quality=quality)
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


    return 0
