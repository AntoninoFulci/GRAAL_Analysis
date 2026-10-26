"""Compare ungated pairing with BDT+pairing on a certified no-fit baseline.

Run with ``python3 -m observable_extraction.compare_gate --help``. Outputs are
diagnostics, with identical uncorrected background treatment in both samples.
"""

import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import ROOT

from calibration.run_manifest import validate_manifest
from graal_common.io.filesystem import atomic_output_directory
from graal_common.parallel import validate_workers
from graal_common.physics.beam_profiles import get_beam_profile
from observable_extraction.samples import SAMPLES
from observable_extraction.plotting.comparison import write_comparison_pdf as _write_figures
from observable_extraction.io.root_output import write_comparison_root
from observable_extraction.extraction import extract_sample  # Compatibility import.
from observable_extraction.comparison import (
    extract_comparison_samples as _extract, bootstrap_comparison,
)
from calibration.run_quality import DEFAULT_RUN_QUALITY_PATH, load_run_quality
from observable_extraction.calibration.flux_v2 import load_exposures
from observable_extraction.core.binning import PHI_EDGES_RAD
from observable_extraction.core.gate_comparison import (
    align_points, compare_contracts, subset_audit, difference_errors,
    selected_cutflow, phi_retention as _phi_retention,
)
from observable_extraction.core.periods import partition_runs, selection_audit, exposure_summary
from observable_extraction.io.reconstructed_events import read_comparison_sample as _read, select_sigma_events
from reconstruction.runtime.provenance import file_identities


def run(args):
    workers = validate_workers(getattr(args, "workers", 1))
    if args.output_dir.exists():
        raise FileExistsError(f"preserve existing study; choose a new output directory: {args.output_dir}")
    if args.replicas < 2:
        raise ValueError("at least two diagnostic replicas required")
    profile = get_beam_profile(args.profile)
    edges = np.asarray(profile.energy_edges_gev)
    repo = Path(__file__).resolve().parents[1]
    code_paths = [p for directory in ("00_common", "05_reconstruction", "06_calibration", "08_observable_extraction")
                  for p in (repo / directory).rglob("*.py") if "tests" not in p.parts]
    code_paths.append(DEFAULT_RUN_QUALITY_PATH)
    source_before = file_identities(code_paths)
    input_identities = file_identities([args.pairing, args.bdt, args.flux_file, args.run_manifest])
    a, meta_a = _read(args.pairing, SAMPLES["raw"].tree)
    b, meta_b = _read(args.bdt, SAMPLES["raw_bdt"].tree)
    contract = compare_contracts(meta_a, meta_b)
    if list(contract["energy_range_gev"]) != list(profile.energy_range_gev):
        raise ValueError("reconstruction selection does not match requested energy profile")
    subset = subset_audit(a, b)
    runs = {row["run"] for row in meta_a["counts_by_run_state"]}
    groups = partition_runs(validate_manifest(args.run_manifest), runs,
                            target=profile.target, beam_type=profile.beam_type)
    periods = {run: period for period, members in groups.items() for run in members}
    flux_audit = {"_run_quality": load_run_quality()}
    exposures = load_exposures(args.flux_file, manifest_path=args.run_manifest, run_numbers=runs,
                              polarization_model=profile.polarization, target=profile.target,
                              beam_type=profile.beam_type, energy_range=profile.energy_range_gev,
                              audit=flux_audit, allow_empty=True)
    samples = {name: select_sigma_events(events, exposures, energy_range=profile.energy_range_gev, drop_missing=True)
               for name, events in (("pairing", a), ("bdt", b))}
    selected_subset = subset_audit(samples["pairing"], samples["bdt"])
    print(f"{args.profile}: common exposures {len(exposures)}, selected "
          f"pairing={len(samples['pairing'])}, BDT={len(samples['bdt'])}", flush=True)
    points = _extract(samples, exposures, edges, workers=workers)
    rows = align_points(points["pairing"], points["bdt"], edges)
    keys = tuple(row["key"] for row in rows if row["status"] == "both_estimable")
    exposed_runs = {exp.run_number for exp in exposures.values()}
    strata = {run: f"{args.profile}:{periods[run]}" for run in exposed_runs}
    diagnostic, replica_values, replica_keys, run_draws = bootstrap_comparison(
        samples, exposures, strata, keys, edges, args.replicas, args.seed, workers=workers)
    errors = difference_errors(diagnostic)
    for row in rows:
        row["delta_run_error"] = float(errors[row["key"]]) if row["key"] in errors else None
    per_period = {}
    for period, members in groups.items():
        exp = {key: value for key, value in exposures.items() if value.run_number in members}
        if not exp:
            per_period[period] = dict(status="no_exposure", rows=[])
            continue
        selected = {name: events.take(np.isin(events.run_number, members)) for name, events in samples.items()}
        fitted = _extract(selected, exp, edges, workers=workers)
        per_period[period] = dict(status="diagnostic_only", rows=align_points(fitted["pairing"], fitted["bdt"], edges))
    report = dict(schema=1, profile=args.profile, command=sys.argv, inputs=input_identities,
                  revision=subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip(),
                  source_files=source_before, versions=dict(python=sys.version, numpy=np.__version__, root=ROOT.gROOT.GetVersion()),
                  selection=contract, energy_edges_gev=edges.tolist(), phi_edges_rad=PHI_EDGES_RAD.tolist(),
                  subset=subset, selected_subset=selected_subset,
                  reconstruction_cutflow=dict(pairing=meta_a["counts_by_run_state"], bdt=meta_b["counts_by_run_state"]),
                  reconstruction_provenance=dict(pairing=meta_a, bdt=meta_b),
                  selection_audit={name: selection_audit(events, exposures, profile.energy_range_gev)
                                   for name, events in (("pairing", a), ("bdt", b))},
                  cutflow=selected_cutflow(samples["pairing"], samples["bdt"], exposures, periods, edges),
                  run_quality=flux_audit["_run_quality"], flux_audit=flux_audit, exposure=exposure_summary(exposures),
                  excluded_runs_without_exposure=sorted(runs - exposed_runs),
                  phi_counts=_phi_retention(samples, edges), rows=rows,
                  coverage=dict(Counter(row["status"] for row in rows)), periods=per_period, bootstrap=diagnostic,
                  background="identically uncorrected; independent per-selection controls unavailable",
                  efficiency="data retention only; independent signal MC efficiency unavailable",
                  final_inference="suspended",
                  limitations=["Kinematic fingerprints do not certify source-entry identity.",
                               "Run-block bootstrap is not event/Poisson uncertainty or coverage calibration.",
                               "No detector bias, independent background or finite-MC uncertainty estimated.",
                               "Pre-reconstruction cutflow has run/state counts, not energy subdivisions.",
                               "No comparison to publication or claim of improved physics precision."])
    if source_before != file_identities(code_paths):
        raise RuntimeError("source changed during study; rerun after concurrent edits settle")
    with atomic_output_directory(args.output_dir) as output:
        (output / "comparison.json").write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
        np.savez_compressed(output / "paired_replicas.npz", values=replica_values,
                            keys=np.array(replica_keys), run_draws=np.array(run_draws))
        write_comparison_root(output / "comparison.root", report)
        _write_figures(output / "comparison.pdf", report)
    print(f"{args.profile}: {len(keys)} common points; covariance for {len(errors)}; saved {args.output_dir}", flush=True)
    return report


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairing", type=Path, required=True)
    parser.add_argument("--bdt", type=Path, required=True)
    parser.add_argument("--flux-file", type=Path, required=True)
    parser.add_argument("--run-manifest", type=Path, required=True)
    parser.add_argument("--profile", choices=("uv", "vis"), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--replicas", type=int, default=64)
    parser.add_argument("--seed", type=int, default=1208)
    parser.add_argument("--workers", type=lambda value: validate_workers(int(value)), default=1,
                        help="processes for independent fits or bootstrap replicas; default: 1")
    return parser


def main(argv=None):
    run(build_parser().parse_args(argv))


if __name__ == "__main__":
    main()
