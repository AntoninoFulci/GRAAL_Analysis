"""Opt-in raw-mass polygon study: plot first, then compare uncorrected asymmetries.

No contour is supplied by default. This diagnostic never modifies reconstructed
events, the pairing, or nominal extraction. Run this module with --help.
"""

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

import numpy as np
import ROOT

from calibration.run_manifest import validate_manifest
from graal_common.io.filesystem import atomic_output_directory
from graal_common.parallel import validate_workers
from graal_common.physics.beam_profiles import get_beam_profile
from observable_extraction.samples import SAMPLES
from calibration.run_quality import DEFAULT_RUN_QUALITY_PATH, load_run_quality
from observable_extraction.calibration.flux_v2 import load_exposures
from observable_extraction.compare_gate import (
    _read, _extract, _phi_retention, _write_figures, bootstrap_comparison,
    selected_cutflow, write_comparison_root,
)
from observable_extraction.core.binning import PHI_EDGES_RAD
from observable_extraction.core.gate_comparison import align_points
from observable_extraction.core.mass_selection import MassPolygon
from observable_extraction.core.periods import partition_runs, exposure_summary, selection_audit
from observable_extraction.io.reconstructed_events import read_run_universe, select_sigma_events
from reconstruction.runtime.provenance import file_identities


NAMES = ("before", "after")


def mass_mask(events, polygon):
    """Disabled selection is an exact identity, including event ordering."""
    return (np.ones(len(events), dtype=bool) if polygon is None
            else polygon.mask(events.eta_mass_gev, events.pi0_mass_gev))


def selection_record(polygon):
    return dict(enabled=polygon is not None,
                polygon=polygon.to_dict() if polygon is not None else None,
                mass_source="raw eta_mass/pi0_mass branches; certified no-fit reconstruction")


def compare_mass_samples(before, exposures, periods, edges, polygon, *, replicas, seed, workers=1):
    """Apply one mask, retain every exposure, and reuse common run draws."""
    validate_workers(workers)
    if replicas < 2:
        raise ValueError("at least two paired diagnostic replicas required")
    edges = np.asarray(edges, dtype=float)
    mask = mass_mask(before, polygon)
    samples = dict(before=before, after=before.take(mask))
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
        schema=1, sample_names=NAMES, selection=selection_record(polygon),
        energy_edges_gev=edges.tolist(), phi_edges_rad=PHI_EDGES_RAD.tolist(),
        event_counts={name: len(events) for name, events in samples.items()},
        nonfinite_raw_masses=int(np.count_nonzero(~(np.isfinite(before.eta_mass_gev)
                                                    & np.isfinite(before.pi0_mass_gev)))),
        exposure=exposure_summary(exposures), exposure_universe=sorted(strata),
        cutflow=selected_cutflow(before, samples["after"], exposures, periods, edges, sample_names=NAMES),
        phi_counts=_phi_retention(samples, edges), rows=rows,
        coverage=dict(Counter(row["status"] for row in rows)), bootstrap=diagnostic,
        migration="none: surviving events keep original pairing, vectors, energy and mass bins",
        background="identically uncorrected; no nominal fraction reused",
        final_inference="suspended: independent background controls and bias/coverage validation required",
        delta_error_kind="paired run-block diagnostic, not final event/Poisson uncertainty",
        contour_uncertainty="not estimated; separate systematic if independently justified",
    )
    arrays = dict(selected_mask=mask, values=values, keys=np.asarray(replica_keys, dtype=str),
                  run_draws=np.asarray(draws, dtype=np.int64))
    return report, arrays


def write_mass_plot(output, events, mask, polygon):
    """Reuse the existing mass histogram; draw exact selection vertices."""
    from plots.mass_histograms import mass2d_hist, draw_truth_cross

    ROOT.gROOT.SetBatch(True)
    ROOT.gStyle.SetOptStat(0)
    ROOT.gStyle.SetPalette(ROOT.kBird)
    source = ROOT.TFile(str(output / "mass_selection.root"), "RECREATE")
    if source.IsZombie():
        raise OSError(f"cannot write mass selection ROOT file in {output}")
    canvas = None
    try:
        finite = np.isfinite(events.eta_mass_gev) & np.isfinite(events.pi0_mass_gev)
        hists = [mass2d_hist(f"masse_2d_{name}", name,
                             events.eta_mass_gev[cut & finite], events.pi0_mass_gev[cut & finite])
                 for name, cut in zip(NAMES, (np.ones(len(events), dtype=bool), mask))]
        graph = None
        if polygon is not None:
            vertices = np.asarray((*polygon.vertices, polygon.vertices[0]), dtype=float)
            graph = ROOT.TGraph(len(vertices), np.ascontiguousarray(vertices[:, 0]),
                                np.ascontiguousarray(vertices[:, 1]))
            graph.SetName("mass_polygon")
            graph.SetLineColor(ROOT.kMagenta + 2)
            graph.SetLineWidth(2)
            graph.Write()
        canvas = ROOT.TCanvas("c_mass_selection", "Raw mass polygon study", 1500, 650)
        canvas.Divide(2, 1)
        keep = []
        maximum = max(1., hists[0].GetMaximum())
        for i, hist in enumerate(hists, 1):
            canvas.cd(i)
            ROOT.gPad.SetRightMargin(.14)
            hist.SetMaximum(maximum)
            hist.GetZaxis().SetTitle("events / bin")
            hist.Draw("colz")
            keep.extend(draw_truth_cross())
            if graph:
                graph.Draw("L SAME")
            hist.Write()
        canvas.SaveAs(str(output / "mass_selection.png"))
        canvas.Write()
        ROOT.TNamed("mass_selection", json.dumps(dict(
            **selection_record(polygon), nonfinite_not_plotted=int((~finite).sum())), allow_nan=False)).Write()
    finally:
        if canvas is not None:
            canvas.Close()
        source.Close()


def _mc_retention(path, tree, polygon, energy_range):
    if path is None:
        return dict(status="unavailable", reason="independent reconstructed MC not supplied")
    events, metadata = _read(path, tree)
    low, high = energy_range
    eligible = (events.beam_energy_gev >= low) & (events.beam_energy_gev <= high)
    retained = eligible & mass_mask(events, polygon)
    return dict(status="unweighted_reconstructed_mc_diagnostic", before=int(eligible.sum()),
                after=int(retained.sum()), retention=float(retained.sum()/eligible.sum()) if eligible.any() else None,
                normalization="conditional on reconstruction and energy window; not detector efficiency or weighted yield",
                provenance=metadata)


def run(args):
    workers = validate_workers(getattr(args, "workers", 1))
    if args.output_dir.exists():
        raise FileExistsError(f"preserve existing study; choose a new output directory: {args.output_dir}")
    paths = [args.input] + ([args.mass_polygon] if args.mass_polygon else [])
    if args.command == "compare":
        paths += [args.flux_file, args.run_manifest, DEFAULT_RUN_QUALITY_PATH]
        paths += [p for p in (args.signal_mc, args.background_mc) if p is not None]
    identities = file_identities(paths)
    polygon = MassPolygon.read(args.mass_polygon) if args.mass_polygon is not None else None
    repo = Path(__file__).resolve().parents[1]
    code_paths = [p for directory in ("00_common", "05_reconstruction", "06_calibration", "08_observable_extraction", "plots")
                  for p in (repo / directory).rglob("*.py") if "tests" not in p.parts]
    code_before = file_identities(code_paths)
    events, provenance = _read(args.input, SAMPLES[args.sample].tree)
    profile = get_beam_profile(args.profile)
    bounds = provenance.get("selection", {}).get("energy_range_gev")
    if bounds is None or bounds[0] > profile.energy_range_gev[0] or bounds[1] < profile.energy_range_gev[1]:
        raise ValueError("reconstruction energy domain does not cover requested profile")
    raw_mask = mass_mask(events, polygon)
    report = dict(schema=1, selection=selection_record(polygon),
                  event_counts=dict(before=len(events), after=int(raw_mask.sum())))
    arrays = dict(raw_entry_mask=raw_mask)
    plot_events, plot_mask = events, raw_mask
    if args.command == "compare":
        runs, cutflow = read_run_universe(args.input)
        if not set(map(int, events.run_number)).issubset(runs):
            raise ValueError("inclusive reconstruction universe omits selected runs")
        groups = partition_runs(validate_manifest(args.run_manifest), runs,
                                target=profile.target, beam_type=profile.beam_type)
        periods = {run: period for period, members in groups.items() for run in members}
        flux_audit = {"_run_quality": load_run_quality()}
        exposures = load_exposures(args.flux_file, manifest_path=args.run_manifest, run_numbers=runs,
                                  polarization_model=profile.polarization, target=profile.target,
                                  beam_type=profile.beam_type, energy_range=profile.energy_range_gev,
                                  audit=flux_audit, allow_empty=True)
        before = select_sigma_events(events, exposures, energy_range=profile.energy_range_gev, drop_missing=True)
        report, comparison_arrays = compare_mass_samples(
            before, exposures, periods, profile.energy_edges_gev, polygon,
            replicas=args.replicas, seed=args.seed, workers=workers)
        arrays.update(comparison_arrays)
        report.update(run_quality=flux_audit["_run_quality"], flux_audit=flux_audit, reconstruction_cutflow=cutflow,
                      preselection_audit=selection_audit(events, exposures, profile.energy_range_gev),
                      excluded_runs_without_exposure=sorted(runs - set(report["exposure_universe"])),
                      mc_retention={name: _mc_retention(path, SAMPLES[args.sample].tree, polygon, profile.energy_range_gev)
                                    for name, path in (("signal", args.signal_mc), ("background", args.background_mc))})
        plot_events, plot_mask = before, arrays["selected_mask"]
    report.update(profile=args.profile, sample=args.sample, command=args.command,
                  inputs=identities, source_files=code_before, reconstruction_provenance=provenance,
                  versions=dict(python=sys.version, numpy=np.__version__, root=ROOT.gROOT.GetVersion()),
                  mask_identity="raw_entry_mask indexes input TTree entries; selected_mask indexes ordered sigma preselection")
    with atomic_output_directory(args.output_dir, overwrite=False) as output:
        (output / "study.json").write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
        np.savez_compressed(output / "selection_and_replicas.npz", **arrays)
        write_mass_plot(output, plot_events, plot_mask, polygon)
        if args.command == "compare":
            write_comparison_root(output / "comparison.root", report)
            _write_figures(output / "comparison.pdf", report)
        if identities != file_identities(paths) or code_before != file_identities(code_paths):
            raise RuntimeError("inputs or source changed during study; rerun after concurrent edits settle")
    return report


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("plot", "compare"):
        command = commands.add_parser(name)
        command.add_argument("--input", type=Path, required=True)
        command.add_argument("--sample", choices=("raw", "raw_bdt"), default="raw_bdt")
        command.add_argument("--profile", choices=("uv", "vis"), required=True)
        command.add_argument("--output-dir", type=Path, required=True)
        command.add_argument("--workers", type=lambda value: validate_workers(int(value)), default=1,
                             help="processes for independent fits or bootstrap replicas; default: 1")
        command.add_argument("--mass-polygon", type=Path,
                             help="explicit frozen JSON polygon; omitted = extra cut disabled")
        if name == "compare":
            command.add_argument("--flux-file", type=Path, required=True)
            command.add_argument("--run-manifest", type=Path, required=True)
            command.add_argument("--replicas", type=int, default=64)
            command.add_argument("--seed", type=int, default=1208)
            command.add_argument("--signal-mc", type=Path)
            command.add_argument("--background-mc", type=Path)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    run(args)
    print(f"Saved optional mass study: {args.output_dir}")


if __name__ == "__main__":
    main()
