"""Compare ungated pairing with BDT+pairing on a certified no-fit baseline.

Run with ``python3 -m observable_extraction.compare_gate --help``. Outputs are
diagnostics, with identical uncorrected background treatment in both samples.
"""

import argparse
from array import array
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
from observable_extraction.extraction import extract_sample
from calibration.run_quality import DEFAULT_RUN_QUALITY_PATH, load_run_quality
from observable_extraction.calibration.flux_v2 import load_exposures
from observable_extraction.core.binning import PAIR_NAMES, PHI_EDGES_RAD
from observable_extraction.core.gate_comparison import (
    align_points, compare_contracts, paired_difference_summary, point_map, subset_audit,
)
from observable_extraction.core.kinematics import project_all_pairs
from observable_extraction.core.periods import partition_runs, selection_audit, exposure_summary
from observable_extraction.core.systematics import paired_bootstrap_by_run
from observable_extraction.io.reconstructed_events import read_reconstructed, select_sigma_events
from reconstruction.runtime.provenance import file_identities, validate_reconstruction_selection


def _read(path, tree_name):
    source = ROOT.TFile.Open(str(path), "READ")
    if not source or source.IsZombie():
        raise ValueError(f"cannot open reconstruction: {path}")
    try:
        tree = source.Get(tree_name)
        if not tree:
            raise ValueError(f"missing tree {tree_name}: {path}")
        metadata = validate_reconstruction_selection(source, tree)
    finally:
        source.Close()
    return read_reconstructed(path, tree_name), metadata


def selected_cutflow(pairing, bdt, exposures, periods, energy_edges, *, sample_names=("pairing", "bdt")):
    """Accepted reconstruction yields by run/energy/state, including zero yields."""
    rows = []
    for run, period in sorted(periods.items()):
        for index, (low, high) in enumerate(zip(energy_edges[:-1], energy_edges[1:])):
            final = index == len(energy_edges) - 2
            for state in (1, 2):
                counts = []
                for events in (pairing, bdt):
                    mask = ((events.run_number == run) & (events.polarization == state)
                            & (events.beam_energy_gev >= low)
                            & ((events.beam_energy_gev <= high) if final else (events.beam_energy_gev < high)))
                    counts.append(int(mask.sum()))
                relevant = [exp for exp in exposures.values() if exp.run_number == run
                            and low <= exp.energy_gev and (exp.energy_gev <= high if final else exp.energy_gev < high)]
                flux = sum(exp.flux_vertical if state == 1 else exp.flux_horizontal for exp in relevant)
                rows.append(dict(run=run, period=period, energy_bin=index, state=state,
                                 **dict(zip(sample_names, counts)), removed=counts[0] - counts[1],
                                 retention=counts[1] / counts[0] if counts[0] else None,
                                 flux=flux if relevant else None))
    return rows


def _extract(samples, exposures, edges, *, workers=1):
    validate_workers(workers)
    if not exposures:
        return {name: () for name in samples}
    return {name: extract_sample(sample_name=name, events=events, exposures=exposures,
                                 estimator="both", retain_ratio_objects=False,
                                 energy_edges=edges, phi_edges=PHI_EDGES_RAD, workers=workers).points
            for name, events in samples.items()}


def bootstrap_comparison(samples, exposures, strata, keys, edges, replicas, seed,
                         *, sample_names=("pairing", "bdt"), workers=1):
    """Return diagnostics and raw draws, including an explicit empty-grid result."""
    validate_workers(workers)
    if not keys:
        return (dict(status="no_common_estimable_bins", replicas=0, seed=seed,
                     available_keys=[], unavailable_keys=[], difference_covariance=None,
                     failed_replicas_by_key={}, run_strata=strata),
                np.empty((0, 0)), (), ())
    counter = 0
    def estimate(replica_samples, replica_exposures):
        nonlocal counter
        counter += 1
        extracted = _extract(replica_samples, replica_exposures, edges)
        lookup = {name: point_map(items) for name, items in extracted.items()}
        if workers == 1 and counter % 10 == 0:
            print(f"paired replica {counter}/{replicas}", flush=True)
        return np.array([lookup[name][key].point.sigma
                         if key in lookup[name] and lookup[name][key].point.diagnostics.converged else np.nan
                         for name in sample_names for key in keys])
    ensemble = paired_bootstrap_by_run(
        estimate, samples, exposures, run_strata=strata,
        point_keys=[f"{name}:{key}" for name in sample_names for key in keys],
        replicas=replicas, seed=seed, workers=workers)
    diagnostic = paired_difference_summary(ensemble.replicas, keys)
    diagnostic.update(status="diagnostic_only", seed=seed, effective_runs=ensemble.effective_runs,
                      zero_event_runs=ensemble.zero_event_runs, run_strata=strata,
                      whole_ensemble_failures=ensemble.failures)
    return diagnostic, ensemble.replicas, ensemble.point_keys, ensemble.run_draws


def _phi_retention(samples, energy_edges):
    histograms = {}
    for name, events in samples.items():
        histograms[name] = {}
        for pair, (_, phi) in project_all_pairs(events.proton, events.eta, events.pi0).items():
            histograms[name][pair] = {str(state): np.histogram2d(
                events.beam_energy_gev[events.polarization == state], phi[events.polarization == state],
                bins=(energy_edges, PHI_EDGES_RAD))[0].astype(int).tolist() for state in (1, 2)}
    return histograms


def write_comparison_root(path, report):
    sample_names = report.get("sample_names", ("pairing", "bdt"))
    output = ROOT.TFile(str(path), "RECREATE")
    if output.IsZombie():
        raise OSError(f"cannot write {path}")
    try:
        ROOT.TNamed("comparison_metadata", json.dumps(report, allow_nan=False, sort_keys=True)).Write()
        tree = ROOT.TTree("comparison", "Full grid; missing values are NaN, status in metadata")
        names = ("row", *(f"sigma_{name}" for name in sample_names), "delta", "delta_run_error")
        buffers = {name: array("d", [0.]) for name in names}
        for name, buffer in buffers.items():
            tree.Branch(name, buffer, f"{name}/D")
        for index, row in enumerate(report["rows"]):
            values = [index, *[row[name]["point"]["sigma"] if row[name] else None for name in sample_names],
                      row["delta"], row.get("delta_run_error")]
            for name, value in zip(names, values):
                buffers[name][0] = float(value) if value is not None else float("nan")
            tree.Fill()
        tree.Write()
        diagnostic = report["bootstrap"]
        for name in ("joint_covariance", "cross_covariance", "difference_covariance", "difference_covariance_mc_se"):
            values = diagnostic.get(name)
            if values is None:
                continue
            matrix = np.asarray(values)
            hist = ROOT.TH2D(name, name, len(matrix), 0, len(matrix), len(matrix), 0, len(matrix))
            labels = diagnostic["available_keys"]
            if name == "joint_covariance":
                labels = [f"{sample}:{key}" for sample in sample_names for key in labels]
            for i, label in enumerate(labels):
                hist.GetXaxis().SetBinLabel(i + 1, label)
                hist.GetYaxis().SetBinLabel(i + 1, label)
                for j in range(len(matrix)):
                    hist.SetBinContent(i + 1, j + 1, float(matrix[i, j]))
            hist.Write()
    finally:
        output.Close()


def _write_figures(path, report):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    first, second = report.get("sample_names", ("pairing", "bdt"))
    with PdfPages(path) as pdf:
        for estimator in ("ratio", "likelihood"):
            for energy_bin in range(len(report["energy_edges_gev"]) - 1):
                fig, axes = plt.subplots(2, 3, figsize=(12, 6), sharex="col", constrained_layout=True)
                for column, pair in enumerate(PAIR_NAMES):
                    rows = [row for row in report["rows"] if row["estimator"] == estimator
                            and row["energy_bin"] == energy_bin and row["pair"] == pair]
                    for sample, offset, color in ((first, -.001, "tab:blue"), (second, .001, "tab:orange")):
                        valid = [row for row in rows if row[sample] and row[sample]["point"]["diagnostics"]["converged"]]
                        points = [row[sample]["point"] for row in valid]
                        if valid:
                            axes[0, column].errorbar([(row["mass_low"] + row["mass_high"]) / 2 + offset for row in valid],
                                                    [point["sigma"] for point in points],
                                                    yerr=[[point[name] for point in points] for name in ("stat_low", "stat_high")],
                                                    fmt="o", ms=3, label=sample, color=color)
                    for row in rows:
                        if row["delta"] is not None:
                            x = (row["mass_low"] + row["mass_high"]) / 2
                            error = row.get("delta_run_error")
                            axes[1, column].errorbar(x, row["delta"], yerr=error, fmt="o" if error is not None else "x",
                                                    color="black", ms=4)
                    axes[0, column].set(title=pair, ylim=(-1.15, 1.15), ylabel="Sigma (conditional stat.)")
                    axes[0, column].legend(fontsize=8)
                    axes[1, column].axhline(0, color="grey", linewidth=.7)
                    axes[1, column].set(xlabel="Invariant mass [GeV]", ylabel=f"{second} - {first}")
                lo, hi = report["energy_edges_gev"][energy_bin:energy_bin + 2]
                fig.suptitle(f"{report['profile'].upper()} {lo:g}–{hi:g} GeV | {estimator} | uncorrected background\n"
                             "Delta errors: paired run diagnostic; x: covariance unavailable; no final inference", fontsize=10)
                pdf.savefig(fig)
                plt.close(fig)


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
    errors = {}
    if diagnostic["difference_covariance"] is not None:
        errors = dict(zip(diagnostic["available_keys"], np.sqrt(np.maximum(0, np.diag(diagnostic["difference_covariance"])))))
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
