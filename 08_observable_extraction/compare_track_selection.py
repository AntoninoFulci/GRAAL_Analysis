"""Opt-in exclusive 4 central photons + 1 forward proton asymmetry diagnostic.

The reconstructed baseline already requires exactly one PID-selected proton.
Four central neutral tracks and one good forward charged track therefore close
the raw inventory without reimplementing PID. This is not a truth-level purity
claim or a reconstruction of the legacy ICENTR_CLASS variable.
"""

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

import numpy as np
import ROOT

from calibration.run_manifest import validate_manifest
from calibration.run_quality import DEFAULT_RUN_QUALITY_PATH, load_run_quality
from graal_common.io.filesystem import atomic_output_directory
from graal_common.io.raw_tracks import has_raw_tracks, snapshot_raw_tracks
from graal_common.parallel import validate_workers
from graal_common.physics.beam_profiles import get_beam_profile
from observable_extraction.beam_asymmetry import SAMPLES
from observable_extraction.calibration.flux_v2 import load_exposures
from observable_extraction.compare_gate import (
    _read, _extract, _phi_retention, _write_figures, bootstrap_comparison,
    selected_cutflow, write_comparison_root,
)
from observable_extraction.core.binning import PHI_EDGES_RAD
from observable_extraction.core.gate_comparison import align_points
from observable_extraction.core.periods import partition_runs, exposure_summary, selection_audit
from observable_extraction.io.reconstructed_events import read_run_universe, select_sigma_events
from reconstruction.runtime.provenance import file_identities, validate_no_fit, validate_energy_domain


NAMES = ("before", "after")
REASONS = ("central_not_four", "central_not_all_neutral", "forward_not_one",
           "forward_zero_index", "forward_not_good_charged", "forward_noise")
DEFINITION = dict(
    name="strict_4central_gamma_1forward_proton_v1",
    central="Nass_3 == 4; all Itipo_track == 11; n_photons_input == 4",
    forward="Nparf == 1; 1 <= Index_trf <= N_traf; Iass_trf[Index_trf-1] in {6,7}",
    noise="Nparf_strange == 0",
    proton="exactly one PID-selected proton certified by reconstruction provenance",
    index_zero="veto; do not apply the legacy zero-to-first-element fallback",
    association_candidates="unused Iass_trf entries are not additional physical tracks",
    interpretation="exclusive candidate topology inside the existing reconstructed baseline; not truth PID",
)


def rejection_reasons(raw, n_photons_input):
    """Return all failed physics conditions; inconsistent inventories raise."""
    for count, branch, limit in (("Nass_3", "Itipo_track", 291),
                                 ("Nparf", "Index_trf", 90),
                                 ("N_traf", "Iass_trf", 90)):
        if not 0 <= raw[count] <= limit or len(raw[branch]) != raw[count]:
            raise ValueError(f"inconsistent raw inventory: {count}/{branch}")
    if n_photons_input != sum(code == 11 for code in raw["Itipo_track"]):
        raise ValueError("raw neutral count disagrees with reconstructed photon count")
    indices = raw["Index_trf"]
    if any(index < 0 or index > raw["N_traf"] for index in indices):
        raise ValueError("forward index outside association array")
    if not 0 <= raw["Nparf_strange"] <= 255:
        raise ValueError("invalid forward noise count")
    failed = (
        raw["Nass_3"] != 4 or n_photons_input != 4,
        any(code != 11 for code in raw["Itipo_track"]),
        raw["Nparf"] != 1,
        any(index == 0 for index in indices),
        any(raw["Iass_trf"][index - 1] not in (6, 7) for index in indices if index > 0),
        raw["Nparf_strange"] != 0,
    )
    return tuple(name for name, fail in zip(REASONS, failed) if fail)


def read_track_mask(path, tree_name):
    """Read original TTree entry order and reject absent/uncertified diagnostics."""
    source = ROOT.TFile.Open(str(path), "READ")
    if not source or source.IsZombie():
        raise ValueError(f"cannot open reconstruction: {path}")
    try:
        tree = source.Get(tree_name)
        if not tree or not tree.InheritsFrom("TTree"):
            raise ValueError(f"missing TTree {tree_name}: {path}")
        meta = validate_no_fit(source, tree)
        selection = meta.get("selection", {})
        if (meta.get("channel") != "eta_pi0" or selection.get("protons") != "exactly_one"
                or selection.get("photons") != "first_four_of_at_least_four"
                or meta.get("raw_track_metadata", {}).get("available") is not True):
            raise ValueError("strict inventory requires certified central photons, exactly one proton and raw diagnostics")
        if not has_raw_tracks(tree, str(path)):
            raise ValueError("strict inventory cannot use legacy reconstruction without raw diagnostics")
        for name in ("n_photons_input", "RunNumber"):
            leaf = tree.GetLeaf(name)
            if not leaf or leaf.GetTypeName() != "Int_t" or leaf.GetLeafCount() or leaf.GetLenStatic() != 1:
                raise ValueError(f"invalid scalar {name}")
        reasons = {name: np.zeros(tree.GetEntries(), dtype=bool) for name in REASONS}
        identities = set()
        for index, event in enumerate(tree):
            raw = snapshot_raw_tracks(event)
            identity = (raw["RawSourceFile"], raw["RawSourceEntry"], int(event.RunNumber))
            if identity in identities:
                raise ValueError(f"duplicate raw event identity: {identity}")
            identities.add(identity)
            for reason in rejection_reasons(raw, int(event.n_photons_input)):
                reasons[reason][index] = True
    finally:
        source.Close()
    mask = np.ones(len(identities), dtype=bool)
    steps = []
    for reason, rejected in reasons.items():
        removed = int(np.count_nonzero(mask & rejected))
        mask &= ~rejected
        steps.append(dict(reason=reason, removed=removed, remaining=int(mask.sum())))
    audit = dict(input=len(mask), kept=int(mask.sum()),
                 rejected_nonexclusive={name: int(values.sum()) for name, values in reasons.items()},
                 sequential_cutflow=steps)
    return mask, reasons, audit


def compare_samples(before, after, exposures, periods, edges, *, replicas, seed, workers=1):
    """Reuse nominal estimators with a common exposure universe and run draws."""
    validate_workers(workers)
    if replicas < 2:
        raise ValueError("at least two paired diagnostic replicas required")
    edges = np.asarray(edges, dtype=float)
    samples = dict(before=before, after=after)
    fitted = _extract(samples, exposures, edges, workers=workers)
    rows = align_points(fitted["before"], fitted["after"], edges, sample_names=NAMES)
    keys = [row["key"] for row in rows if row["status"] == "both_estimable"]
    strata = {exp.run_number: periods[exp.run_number] for exp in exposures.values()}
    diagnostic, values, replica_keys, draws = bootstrap_comparison(
        samples, exposures, strata, keys, edges, replicas, seed, sample_names=NAMES, workers=workers)
    errors = {}
    if diagnostic["difference_covariance"] is not None:
        errors = dict(zip(diagnostic["available_keys"],
                          np.sqrt(np.maximum(0, np.diag(diagnostic["difference_covariance"])))))
    for row in rows:
        error = errors.get(row["key"])
        row["delta_run_error"] = float(error) if error is not None else None
        row["delta_over_run_error"] = (float(row["delta"] / error)
                                       if error is not None and error > 0 else None)
    report = dict(
        schema=1, sample_names=NAMES, selection=DEFINITION,
        energy_edges_gev=edges.tolist(), phi_edges_rad=PHI_EDGES_RAD.tolist(),
        event_counts={name: len(events) for name, events in samples.items()},
        exposure=exposure_summary(exposures), exposure_universe=sorted(strata),
        cutflow=selected_cutflow(before, after, exposures, periods, edges, sample_names=NAMES),
        phi_counts=_phi_retention(samples, edges), rows=rows,
        coverage=dict(Counter(row["status"] for row in rows)), bootstrap=diagnostic,
        migration="none: retained events keep original pairing, vectors and bins",
        background="identically uncorrected; no nominal background fraction reused",
        delta_error_kind="paired run-block diagnostic, not final event/Poisson uncertainty",
        final_inference="selection diagnostic; independent background and detector-bias controls unavailable",
    )
    arrays = dict(values=values, keys=np.asarray(replica_keys, dtype=str),
                  run_draws=np.asarray(draws, dtype=np.int64))
    return report, arrays


def run(args):
    workers = validate_workers(args.workers)
    if args.output_dir.exists():
        raise FileExistsError(f"preserve existing study; choose new output directory: {args.output_dir}")
    if args.replicas < 2:
        raise ValueError("at least two paired diagnostic replicas required")
    paths = [args.input, args.flux_file, args.run_manifest, DEFAULT_RUN_QUALITY_PATH]
    inputs = file_identities(paths)
    repo = Path(__file__).resolve().parents[1]
    # Capture actual imported analysis dependencies, not unrelated concurrent work.
    code_paths = sorted({Path(module.__file__).resolve() for module in tuple(sys.modules.values())
                         if getattr(module, "__file__", None)
                         and str(Path(module.__file__).resolve()).startswith(str(repo) + "/")
                         and str(module.__file__).endswith(".py")})
    sources = file_identities(code_paths)
    profile = get_beam_profile(args.profile)
    tree_name = SAMPLES[args.sample].tree
    events, provenance = _read(args.input, tree_name)
    validate_energy_domain(provenance, args.profile, profile.energy_range_gev,
                           requires_bdt=args.sample == "raw_bdt")
    mask, reasons, inventory = read_track_mask(args.input, tree_name)
    if len(mask) != len(events):
        raise ValueError("track mask and reconstructed event lengths differ")
    runs, cutflow = read_run_universe(args.input)
    if not set(map(int, events.run_number)).issubset(runs):
        raise ValueError("inclusive run universe omits reconstructed events")
    groups = partition_runs(validate_manifest(args.run_manifest), runs,
                            target=profile.target, beam_type=profile.beam_type)
    periods = {run: period for period, members in groups.items() for run in members}
    flux_audit = {"_run_quality": load_run_quality()}
    exposures = load_exposures(args.flux_file, manifest_path=args.run_manifest, run_numbers=runs,
                              polarization_model=profile.polarization, target=profile.target,
                              beam_type=profile.beam_type, energy_range=profile.energy_range_gev,
                              audit=flux_audit, allow_empty=True)
    before, after = [select_sigma_events(sample, exposures, energy_range=profile.energy_range_gev,
                                        drop_missing=True) for sample in (events, events.take(mask))]
    print(f"{args.profile}/{args.sample}: raw {len(events)} -> {int(mask.sum())}; "
          f"sigma eligible {len(before)} -> {len(after)}", flush=True)
    report, arrays = compare_samples(before, after, exposures, periods, profile.energy_edges_gev,
                                     replicas=args.replicas, seed=args.seed, workers=workers)
    per_period = {}
    for period, members in groups.items():
        period_exposures = {key: value for key, value in exposures.items() if value.run_number in members}
        samples = {name: sample.take(np.isin(sample.run_number, members))
                   for name, sample in zip(NAMES, (before, after))}
        fitted = _extract(samples, period_exposures, profile.energy_edges_gev, workers=workers)
        per_period[period] = dict(
            event_counts={name: len(sample) for name, sample in samples.items()},
            rows=align_points(fitted["before"], fitted["after"], profile.energy_edges_gev, sample_names=NAMES),
            delta_uncertainty="not estimated per period")
    report.update(profile=args.profile, sample=args.sample, inputs=inputs, source_files=sources,
                  command=sys.argv, reconstruction_provenance=provenance, raw_inventory=inventory,
                  reconstruction_cutflow=cutflow, periods=per_period,
                  preselection_audit={name: selection_audit(sample, exposures, profile.energy_range_gev)
                                      for name, sample in zip(NAMES, (events, events.take(mask)))},
                  flux_audit=flux_audit, run_quality=flux_audit["_run_quality"],
                  excluded_runs_without_exposure=sorted(runs - set(report["exposure_universe"])),
                  versions=dict(python=sys.version, numpy=np.__version__, root=ROOT.gROOT.GetVersion()),
                  mask_identity="raw_entry_mask and rejection masks index original input TTree entry order")
    arrays.update(raw_entry_mask=mask, **{f"reject_{name}": value for name, value in reasons.items()})
    with atomic_output_directory(args.output_dir, overwrite=False) as output:
        (output / "study.json").write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
        np.savez_compressed(output / "selection_and_replicas.npz", **arrays)
        write_comparison_root(output / "comparison.root", report)
        _write_figures(output / "comparison.pdf", report)
        if inputs != file_identities(paths) or sources != file_identities(code_paths):
            raise RuntimeError("inputs or analysis source changed during study; rerun against stable inputs")
    print(f"Saved {args.output_dir}; coverage {report['coverage']}", flush=True)
    return report


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--sample", choices=("raw", "raw_bdt"), default="raw_bdt")
    parser.add_argument("--profile", choices=("uv", "vis"), required=True)
    parser.add_argument("--flux-file", type=Path, required=True)
    parser.add_argument("--run-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--replicas", type=int, default=64)
    parser.add_argument("--seed", type=int, default=20261021)
    parser.add_argument("--workers", type=int, default=1)
    return parser


def main(argv=None):
    run(build_parser().parse_args(argv))


if __name__ == "__main__":
    main()
