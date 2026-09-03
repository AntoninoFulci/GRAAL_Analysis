#!/usr/bin/env python3
"""Read inclusive h80 energies and tagger-flux ROOT histograms."""
from __future__ import annotations

import argparse
from array import array
from collections import defaultdict
from math import fsum, isfinite
import os
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import tempfile
from typing import Iterator, Sequence

from graal_common.run_manifest import ManifestError, validate_manifest
from graal_common.strip_energy_flux import (
    AJAKA_CROSS_SECTION,
    AJAKA_SIGMA,
    EnergyBinning,
    EnergySample,
    StripEnergyFluxError,
    StripFlux,
    aggregate_group_flux,
    atomic_output_directory,
    build_strip_energy_lookup_on_disk,
    check_flux_conservation,
    find_monotonic_inversions,
    integrate_run_flux,
    validate_energy_sample,
    write_group_flux_csv,
    write_lookup_csv,
    write_qa_json,
    write_run_flux_csv,
)


_FLUX_NAME = re.compile(r"^run([0-9]+)_(POL1|POL2|BREM)$")
_FLUX_SUFFIXES = ("POL1", "POL2", "BREM")


def _import_root():
    try:
        import ROOT
    except ImportError as exc:
        raise StripEnergyFluxError("ROOT is required to read ROOT inputs") from exc
    return ROOT


def _open_root_file(path: Path):
    root = _import_root()
    try:
        source = root.TFile.Open(str(path), "READ")
    except OSError as exc:
        raise StripEnergyFluxError(f"zombie ROOT file: {path}") from exc
    if not source:
        raise StripEnergyFluxError(f"zombie ROOT file: {path}")
    if source.IsZombie():
        try:
            source.Close()
        except Exception:
            pass
        raise StripEnergyFluxError(f"zombie ROOT file: {path}")
    return source


def _h80_paths(preanalysis_dir: Path) -> Iterator[Path]:
    preanalysis_dir = Path(preanalysis_dir)
    if not preanalysis_dir.is_dir():
        raise StripEnergyFluxError(f"preanalysis directory not found: {preanalysis_dir}")
    found = False
    for directory, child_directories, filenames in os.walk(preanalysis_dir):
        child_directories.sort()
        for filename in sorted(filenames):
            if not filename.endswith(".root"):
                continue
            path = Path(directory) / filename
            if path.is_file():
                found = True
                yield path
    if not found:
        raise StripEnergyFluxError(f"no ROOT files below: {preanalysis_dir}")


def iter_h80_samples(
    preanalysis_dir: Path,
) -> tuple[Iterator[EnergySample], dict[str, object]]:
    """Stream validated h80 samples and update QA as entries are consumed."""
    paths = _h80_paths(preanalysis_dir)
    qa: dict[str, object] = {"entries": 0, "file_count": 0}

    def samples():
        for path in paths:
            qa["file_count"] = int(qa["file_count"]) + 1
            source = _open_root_file(path)
            try:
                tree = source.Get("h80")
                if not tree:
                    raise StripEnergyFluxError(f"{path}: missing h80 tree")
                if not tree.InheritsFrom("TTree"):
                    raise StripEnergyFluxError(f"{path}: h80 is not a TTree")
                for branch in ("RunNumber", "Xstrip", "beam"):
                    if not tree.GetBranch(branch):
                        raise StripEnergyFluxError(f"{path}: missing branch {branch}")

                tree.SetBranchStatus("*", 0)
                for branch in ("RunNumber", "Xstrip", "beam"):
                    pending = [tree.GetBranch(branch)]
                    while pending:
                        active = pending.pop()
                        active.SetStatus(1)
                        pending.extend(active.GetListOfBranches())

                entry_count = int(tree.GetEntries())
                beam_branch = tree.GetBranch("beam")
                beam_class = beam_branch.GetClassName()
                if entry_count and not beam_class:
                    raise StripEnergyFluxError(
                        f"{path}: h80 entry 0: "
                        "cannot convert RunNumber/Xstrip/beam.E()"
                    )
                run_number = array("i", [0])
                xstrip = array("f", [0.0])
                beam = (
                    getattr(_import_root(), beam_class)()
                    if beam_class
                    else None
                )
                bindings = (
                    ("RunNumber", run_number),
                    ("Xstrip", xstrip),
                    ("beam", beam),
                )
                for branch, buffer in bindings:
                    if buffer is None:
                        continue
                    status = tree.SetBranchAddress(branch, buffer)
                    if status < 0:
                        raise StripEnergyFluxError(
                            f"{path}: cannot bind branch {branch} "
                            f"(ROOT status {status})"
                        )

                for entry_index in range(entry_count):
                    tree.GetEntry(entry_index)
                    try:
                        sample = EnergySample(
                            run_number[0],
                            float(xstrip[0]),
                            float(beam.E()),
                        )
                    except Exception as exc:
                        raise StripEnergyFluxError(
                            f"{path}: h80 entry {entry_index}: "
                            "cannot convert RunNumber/Xstrip/beam.E()"
                        ) from exc
                    try:
                        sample = validate_energy_sample(sample)
                    except StripEnergyFluxError as exc:
                        raise StripEnergyFluxError(
                            f"{path}: h80 entry {entry_index}: {exc}"
                        ) from exc
                    qa["entries"] = int(qa["entries"]) + 1
                    yield sample
            finally:
                source.Close()

    return samples(), qa


def read_h80_samples(preanalysis_dir: Path) -> tuple[list[EnergySample], dict[str, object]]:
    """Materialize the h80 stream for adapter callers and small tests."""
    samples, qa = iter_h80_samples(preanalysis_dir)
    return list(samples), qa


def _triplet_qa(
    objects: dict[int, dict[str, list[object]]], requested_runs: set[int]
) -> dict[str, object]:
    complete_runs = {
        run
        for run, suffixes in objects.items()
        if all(
            len(suffixes.get(suffix, [])) == 1
            and suffixes[suffix][0].GetName() == f"run{run}_{suffix}"
            for suffix in _FLUX_SUFFIXES
        )
    }
    malformed = []
    matching_keys = []
    for run, suffixes in sorted(objects.items()):
        for suffix, keys in suffixes.items():
            matching_keys.extend(
                {
                    "name": key.GetName(),
                    "cycle": int(key.GetCycle()),
                    "run_number": run,
                    "suffix": suffix,
                }
                for key in keys
            )
        missing = [suffix for suffix in _FLUX_SUFFIXES if suffix not in suffixes]
        aliases = sorted(
            key.GetName()
            for suffix, keys in suffixes.items()
            for key in keys
            if key.GetName() != f"run{run}_{suffix}"
        )
        duplicates = {
            suffix: len(keys) for suffix, keys in suffixes.items() if len(keys) != 1
        }
        if missing or aliases or duplicates:
            problem = {
                "run_number": run,
                "missing": missing,
                "present": [
                    suffix for suffix in _FLUX_SUFFIXES if suffix in suffixes
                ],
            }
            if aliases:
                problem["noncanonical"] = aliases
            if duplicates:
                problem["key_counts"] = duplicates
            malformed.append(problem)
    return {
        "run_count": len(requested_runs),
        "extra_runs": sorted(complete_runs - requested_runs),
        "malformed_triplets": malformed,
        "matching_keys": sorted(
            matching_keys,
            key=lambda item: (
                item["run_number"],
                item["suffix"],
                item["name"],
                item["cycle"],
            ),
        ),
        "underflow_overflow": [],
    }


def _required_histogram(key, run: int, suffix: str):
    name = f"run{run}_{suffix}"
    histogram = key.ReadObj()
    if not histogram:
        raise StripEnergyFluxError(f"missing required flux histogram: {name}")
    if not histogram.InheritsFrom("TH1"):
        raise StripEnergyFluxError(f"{name} is not a TH1 histogram")
    if histogram.GetDimension() != 1:
        raise StripEnergyFluxError(f"{name} is not one-dimensional")
    if histogram.GetNbinsX() != 128:
        raise StripEnergyFluxError(f"{name} must have 128 bins")

    axis = histogram.GetXaxis()
    for edge_index in range(129):
        edge = (
            axis.GetBinLowEdge(edge_index + 1)
            if edge_index < 128
            else axis.GetBinUpEdge(128)
        )
        if not isfinite(float(edge)):
            raise StripEnergyFluxError(
                f"{name} x-axis edge {edge_index} is not finite"
            )
        if abs(edge - edge_index) > 1e-6:
            raise StripEnergyFluxError(
                f"{name} x-axis edge {edge_index} must be {edge_index}"
            )
    for bin_number in range(130):
        if not isfinite(float(histogram.GetBinContent(bin_number))):
            raise StripEnergyFluxError(f"{name} bin {bin_number} is not finite")
    return histogram


def read_flux_histograms(
    path: Path, run_numbers: Sequence[int]
) -> tuple[list[StripFlux], dict[str, object]]:
    """Read one validated POL1/POL2/BREM triplet per requested run."""
    path = Path(path)
    requested_runs = set(run_numbers)
    source = _open_root_file(path)
    try:
        objects: dict[int, dict[str, list[object]]] = {}
        for key in source.GetListOfKeys():
            match = _FLUX_NAME.fullmatch(key.GetName())
            if match:
                run, suffix = match.groups()
                objects.setdefault(int(run), {}).setdefault(suffix, []).append(key)
        qa = _triplet_qa(objects, requested_runs)

        strips: list[StripFlux] = []
        for run in sorted(requested_runs):
            suffixes = objects.get(run, {})
            if not suffixes:
                raise StripEnergyFluxError(f"requested flux run {run} is absent")
            histograms = {}
            for suffix in _FLUX_SUFFIXES:
                name = f"run{run}_{suffix}"
                keys = suffixes.get(suffix, [])
                aliases = [key.GetName() for key in keys if key.GetName() != name]
                if aliases:
                    raise StripEnergyFluxError(
                        f"noncanonical flux histogram name: {aliases[0]} "
                        f"(expected {name})"
                    )
                if len(keys) != 1:
                    raise StripEnergyFluxError(
                        f"{name} must have exactly one ROOT key "
                        f"(found {len(keys)})"
                    )
                histograms[suffix] = _required_histogram(keys[0], run, suffix)
            for suffix, histogram in histograms.items():
                underflow = float(histogram.GetBinContent(0))
                overflow = float(histogram.GetBinContent(129))
                if underflow != 0.0 or overflow != 0.0:
                    qa["underflow_overflow"].append(
                        {
                            "histogram": f"run{run}_{suffix}",
                            "underflow": underflow,
                            "overflow": overflow,
                        }
                    )
            for strip in range(1, 129):
                strips.append(
                    StripFlux(
                        run,
                        strip,
                        float(histograms["POL1"].GetBinContent(strip)),
                        float(histograms["BREM"].GetBinContent(strip)),
                        float(histograms["POL2"].GetBinContent(strip)),
                    )
                )
    finally:
        source.Close()

    return strips, qa


def parse_custom_binnings(values: Sequence[str]) -> tuple[EnergyBinning, ...]:
    result = []
    seen = {AJAKA_CROSS_SECTION.name, AJAKA_SIGMA.name}
    for value in values:
        name, separator, raw_edges = value.partition(":")
        if not separator or not name or not raw_edges:
            raise StripEnergyFluxError(
                "custom binning must use NAME:EDGE,EDGE,..."
            )
        if name in seen:
            raise StripEnergyFluxError(f"duplicate binning name: {name}")
        try:
            edges = tuple(float(edge) for edge in raw_edges.split(","))
        except ValueError:
            raise StripEnergyFluxError(
                f"custom binning {name}: edges must be numeric"
            ) from None
        result.append(EnergyBinning(name, edges))
        seen.add(name)
    return tuple(result)


def _input_paths(args: argparse.Namespace) -> dict[str, str]:
    return {
        "preanalysis_dir": str(args.preanalysis_dir),
        "manifest": str(args.manifest),
        "flux": str(args.flux),
        "output_dir": str(args.output_dir),
    }


def _validate_output_location(args: argparse.Namespace) -> None:
    lexical_output = Path(os.path.abspath(args.output_dir))
    resolved_output = args.output_dir.resolve(strict=False)
    for input_path in (
        args.preanalysis_dir,
        args.manifest,
        args.flux,
    ):
        lexical_input = Path(os.path.abspath(input_path))
        resolved_input = input_path.resolve(strict=False)
        lexical_collision = (
            lexical_input == lexical_output
            or lexical_output in lexical_input.parents
        )
        resolved_collision = (
            resolved_input == resolved_output
            or resolved_output in resolved_input.parents
        )
        if lexical_collision or resolved_collision:
            raise StripEnergyFluxError(
                f"output directory contains input path: {input_path}"
            )


def build_qa_payload(
    args: argparse.Namespace,
    manifest,
    lookup,
    run_flux,
    h80_qa,
    flux_qa,
    errors,
) -> dict[str, object]:
    manifest_runs = {record.run_number for record in manifest}
    h80_runs = {record.run_number for record in lookup}
    unique_errors = sorted(set(errors))
    return {
        "schema_version": 1,
        "inputs": _input_paths(args),
        "thresholds": {
            "min_events_per_strip": args.min_events_per_strip,
            "max_mad_gev": args.max_mad_gev,
            "monotonic_tolerance_gev": args.monotonic_tolerance_gev,
        },
        "binnings": flux_qa["analysis_binnings"],
        "manifest_run_count": len(manifest_runs),
        "h80_run_count": h80_qa.get("run_count", len(h80_runs)),
        "flux_run_count": flux_qa["run_count"],
        "lookup_strip_count": len(lookup),
        "h80": h80_qa,
        "flux": {
            key: value
            for key, value in flux_qa.items()
            if key not in {
                "analysis_binnings",
                "conservation",
                "empty_strips",
                "extra_h80_runs",
                "low_stat_warnings",
                "mad_warnings",
                "missing_h80_runs",
                "monotonic_inversions",
                "negative_net_errors",
                "nonzero_unmapped_strips",
                "out_of_range",
            }
        },
        "missing_h80_runs": flux_qa["missing_h80_runs"],
        "extra_h80_runs": flux_qa["extra_h80_runs"],
        "extra_h80_run_count": flux_qa["extra_h80_run_count"],
        "extra_h80_runs_truncated": flux_qa["extra_h80_runs_truncated"],
        "extra_flux_runs": flux_qa["extra_runs"],
        "malformed_flux_triplets": flux_qa["malformed_triplets"],
        "empty_strips": flux_qa["empty_strips"],
        "nonzero_unmapped_strips": flux_qa["nonzero_unmapped_strips"],
        "monotonic_inversions": flux_qa["monotonic_inversions"],
        "mad_warnings": flux_qa["mad_warnings"],
        "low_stat_warnings": flux_qa["low_stat_warnings"],
        "underflow_overflow": flux_qa["underflow_overflow"],
        "out_of_range": flux_qa["out_of_range"],
        "negative_net_errors": flux_qa["negative_net_errors"],
        "conservation": flux_qa["conservation"],
        "run_flux_bin_count": len(run_flux),
        "errors": unique_errors,
        "valid": not unique_errors,
    }


def run(args: argparse.Namespace) -> int:
    _validate_output_location(args)
    if args.min_events_per_strip < 1:
        raise StripEnergyFluxError("min-events-per-strip must be at least 1")
    if not isfinite(args.max_mad_gev) or args.max_mad_gev < 0:
        raise StripEnergyFluxError("max-mad-gev must be finite and nonnegative")
    if (
        not isfinite(args.monotonic_tolerance_gev)
        or args.monotonic_tolerance_gev < 0
    ):
        raise StripEnergyFluxError(
            "monotonic-tolerance-gev must be finite and nonnegative"
        )

    records = validate_manifest(args.manifest)
    manifest_by_run = {record.run_number: record for record in records}
    manifest_runs = set(manifest_by_run)
    args.output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{args.output_dir.name}.energy-spool.",
        dir=args.output_dir.parent,
    ) as spool_directory:
        samples, h80_qa = iter_h80_samples(args.preanalysis_dir)
        lookup_build = build_strip_energy_lookup_on_disk(
            samples,
            Path(spool_directory) / "h80-energy.sqlite3",
            run_numbers=manifest_runs,
        )
    lookup = lookup_build.records
    sample_runs = set(lookup_build.observed_runs)
    h80_qa.update(
        {
            "run_count": lookup_build.observed_run_count,
            "unrequested_run_count": lookup_build.unrequested_run_count,
            "unrequested_runs_truncated": (
                lookup_build.unrequested_runs_truncated
            ),
        }
    )

    lookup_by_run = defaultdict(list)
    for row in lookup:
        lookup_by_run[row.run_number].append(row)

    strips, flux_qa = read_flux_histograms(args.flux, sorted(manifest_runs))
    flux_by_run = defaultdict(list)
    for row in strips:
        flux_by_run[row.run_number].append(row)
    flux_by_run_strip = {
        run_number: {row.xstrip: row for row in rows}
        for run_number, rows in flux_by_run.items()
    }

    errors = []
    extra_h80 = list(lookup_build.unrequested_runs)
    missing_h80 = sorted(manifest_runs - sample_runs)
    if lookup_build.unrequested_run_count:
        if lookup_build.unrequested_runs_truncated:
            errors.append(
                "h80 runs absent from manifest "
                f"(showing first {len(extra_h80)} of "
                f"{lookup_build.unrequested_run_count}): {extra_h80}"
            )
        else:
            errors.append(f"h80 runs absent from manifest: {extra_h80}")
    if missing_h80:
        errors.append(f"manifest runs absent from h80: {missing_h80}")

    binnings = (
        AJAKA_CROSS_SECTION,
        AJAKA_SIGMA,
        *parse_custom_binnings(args.binning),
    )

    empty_strips = []
    nonzero_unmapped = []
    for run_number in sorted(manifest_runs):
        mapped = {row.xstrip for row in lookup_by_run[run_number]}
        for xstrip in range(1, 129):
            if xstrip in mapped:
                continue
            empty_strips.append({"run_number": run_number, "xstrip": xstrip})
            strip = flux_by_run_strip.get(run_number, {}).get(xstrip)
            if strip is not None and any(
                value != 0.0 for value in (strip.pol1, strip.brem, strip.pol2)
            ):
                nonzero_unmapped.append(
                    {
                        "run_number": run_number,
                        "xstrip": xstrip,
                        "pol1": strip.pol1,
                        "brem": strip.brem,
                        "pol2": strip.pol2,
                    }
                )
                errors.append(
                    f"run {run_number} strip {xstrip}: "
                    "nonzero flux without lookup"
                )

    inversions = []
    for inversion in find_monotonic_inversions(lookup):
        delta = inversion.get("delta_gev")
        if delta is None or abs(delta) > args.monotonic_tolerance_gev:
            inversions.append(inversion)
            if delta is None:
                errors.append(
                    f"run {inversion['run_number']}: "
                    "monotonic direction is undetermined"
                )
            else:
                errors.append(
                    f"run {inversion['run_number']} strips "
                    f"{inversion['left_strip']}-{inversion['right_strip']}: "
                    f"monotonic inversion {delta} GeV"
                )

    mad_warnings = [
        {
            "run_number": row.run_number,
            "xstrip": row.xstrip,
            "energy_mad_gev": row.energy_mad_gev,
        }
        for row in lookup
        if row.energy_mad_gev > args.max_mad_gev
    ]
    low_stat_warnings = [
        {
            "run_number": row.run_number,
            "xstrip": row.xstrip,
            "event_count": row.event_count,
        }
        for row in lookup
        if row.event_count < args.min_events_per_strip
    ]

    out_of_range = {}
    out_of_range_raw: dict[
        tuple[str, int], tuple[float, float, float]
    ] = {}
    for binning in binnings:
        below = []
        above = []
        excluded_parts: list[list[float]] = [[], [], []]
        for run_number in sorted(manifest_runs):
            run_excluded_parts: list[list[float]] = [[], [], []]
            if run_number not in sample_runs:
                out_of_range_raw[(binning.name, run_number)] = (0.0, 0.0, 0.0)
                continue
            flux_by_strip = flux_by_run_strip[run_number]
            for row in lookup_by_run[run_number]:
                if row.energy_median_gev < binning.edges_gev[0]:
                    below.append((run_number, row.xstrip))
                elif row.energy_median_gev > binning.edges_gev[-1]:
                    above.append((run_number, row.xstrip))
                else:
                    continue
                strip = flux_by_strip[row.xstrip]
                for index, value in enumerate(
                    (strip.pol1, strip.brem, strip.pol2)
                ):
                    run_excluded_parts[index].append(value)
            run_excluded = tuple(fsum(parts) for parts in run_excluded_parts)
            out_of_range_raw[(binning.name, run_number)] = run_excluded
            for index, value in enumerate(run_excluded):
                excluded_parts[index].append(value)
        excluded = tuple(fsum(parts) for parts in excluded_parts)
        out_of_range[binning.name] = {
            "below_lookup_count": len(below),
            "above_lookup_count": len(above),
            "below_lookup_strips": [
                {"run_number": run_number, "xstrip": xstrip}
                for run_number, xstrip in below
            ],
            "above_lookup_strips": [
                {"run_number": run_number, "xstrip": xstrip}
                for run_number, xstrip in above
            ],
            "raw_flux_excluded": {
                "pol1": excluded[0],
                "brem": excluded[1],
                "pol2": excluded[2],
            },
        }

    run_flux = []
    negative_net_errors = []
    for binning in binnings:
        for run_number in sorted(manifest_runs & sample_runs):
            try:
                integrated = integrate_run_flux(
                    manifest_by_run[run_number],
                    lookup_by_run[run_number],
                    flux_by_run[run_number],
                    binning,
                )
            except StripEnergyFluxError as exc:
                errors.append(str(exc))
                continue
            run_flux.extend(integrated)
            for bin_index, row in enumerate(integrated):
                if row.status == "valid":
                    continue
                negative_net_errors.append(
                    {
                        "binning": row.binning,
                        "run_number": row.run_number,
                        "bin_index": bin_index,
                        "energy_low_gev": row.energy_low_gev,
                        "energy_high_gev": row.energy_high_gev,
                        "pol1_net": row.pol1_net,
                        "pol2_net": row.pol2_net,
                    }
                )
                errors.append(
                    f"run {row.run_number} binning {row.binning} "
                    f"bin {bin_index}: negative net flux"
                )

    group_flux = aggregate_group_flux(run_flux)
    conservation = check_flux_conservation(
        run_flux,
        group_flux,
        strips,
        out_of_range_raw,
    )
    for failure in conservation["failures"]:
        if failure["scope"] == "run":
            errors.append(
                "structural run raw-flux conservation failure: "
                f"binning {failure['binning']} run {failure['run_number']} "
                f"state {failure['state']}"
            )
        else:
            errors.append(
                "structural group raw-flux conservation failure: "
                f"binning {failure['binning']} group {failure['group']} "
                f"bin [{failure['energy_low_gev']}, "
                f"{failure['energy_high_gev']}] state {failure['state']}"
            )

    flux_qa.update(
        {
            "analysis_binnings": {
                binning.name: list(binning.edges_gev) for binning in binnings
            },
            "conservation": conservation,
            "missing_h80_runs": missing_h80,
            "extra_h80_runs": extra_h80,
            "extra_h80_run_count": lookup_build.unrequested_run_count,
            "extra_h80_runs_truncated": (
                lookup_build.unrequested_runs_truncated
            ),
            "empty_strips": empty_strips,
            "nonzero_unmapped_strips": nonzero_unmapped,
            "monotonic_inversions": inversions,
            "mad_warnings": mad_warnings,
            "low_stat_warnings": low_stat_warnings,
            "negative_net_errors": negative_net_errors,
            "out_of_range": out_of_range,
        }
    )

    qa = build_qa_payload(
        args,
        records,
        lookup,
        run_flux,
        h80_qa,
        flux_qa,
        errors,
    )
    with atomic_output_directory(args.output_dir) as staging:
        write_lookup_csv(
            staging / "strip_energy_lookup.csv",
            lookup,
            manifest_by_run,
        )
        write_run_flux_csv(staging / "flux_by_run_energy.csv", run_flux)
        write_group_flux_csv(
            staging / "flux_by_group_energy.csv",
            group_flux,
        )
        write_qa_json(staging / "strip_energy_flux_qa.json", qa)
    if qa["valid"]:
        print(
            f"Wrote {len(records)}-run strip-energy flux analysis "
            f"to {args.output_dir}"
        )
        return 0
    return 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build run-specific strip-energy and integrated flux artifacts."
    )
    parser.add_argument("--preanalysis-dir", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--flux", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--min-events-per-strip", type=int, default=1)
    parser.add_argument("--max-mad-gev", type=float, default=0.005)
    parser.add_argument("--monotonic-tolerance-gev", type=float, default=0.002)
    parser.add_argument("--binning", action="append", default=[])
    return parser.parse_args()


def _write_failure_qa(args: argparse.Namespace, error: str) -> Path:
    _validate_output_location(args)
    payload = {
        "schema_version": 1,
        "inputs": _input_paths(args),
        "valid": False,
        "errors": [error],
    }
    if args.output_dir.exists():
        args.output_dir.parent.mkdir(parents=True, exist_ok=True)
        failure_directory = Path(
            tempfile.mkdtemp(
                prefix=f"{args.output_dir.name}.failure.",
                dir=args.output_dir.parent,
            )
        ).resolve()
        try:
            write_qa_json(
                failure_directory / "strip_energy_flux_qa.json",
                payload,
            )
        except BaseException:
            shutil.rmtree(failure_directory, ignore_errors=True)
            raise
        return failure_directory

    with atomic_output_directory(args.output_dir) as staging:
        write_qa_json(staging / "strip_energy_flux_qa.json", payload)
    return args.output_dir.resolve()


def main() -> int:
    args = parse_args()
    try:
        return run(args)
    except (
        ManifestError,
        StripEnergyFluxError,
        OSError,
        RuntimeError,
        sqlite3.Error,
    ) as exc:
        failure_directory = None
        try:
            failure_directory = _write_failure_qa(args, str(exc))
        except (StripEnergyFluxError, OSError):
            pass
        print(f"ERROR: {exc}", file=sys.stderr)
        if failure_directory is not None:
            print(f"Failure QA: {failure_directory}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
