#!/usr/bin/env python3
"""Read inclusive h80 energies and tagger-flux ROOT histograms."""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime
from math import isfinite
import os
from pathlib import Path
import re
import sys
import time
from typing import Sequence

from graal_common.calibration.run_manifest import ManifestError, validate_manifest
from graal_common.calibration.strip_energy_flux import (
    AJAKA_CROSS_SECTION,
    AJAKA_SIGMA,
    FLUX_SCHEMA_VERSION,
    EnergyBinning,
    EnergySample,
    StripEnergyFluxError,
    StripFlux,
    aggregate_group_flux,
    atomic_output_directory,
    build_strip_energy_lookup,
    find_monotonic_inversions,
    integrate_run_flux,
    join_strip_exposures,
    write_group_flux_csv,
    write_lookup_csv,
    write_qa_json,
    write_run_flux_csv,
    write_strip_exposure_csv,
)


_FLUX_NAME = re.compile(r"^run([0-9]+)_(POL1|POL2|BREM)$")
_FLUX_SUFFIXES = ("POL1", "POL2", "BREM")


class ProgressReporter:
    """Timestamped, flushed progress messages for long ROOT scans."""

    def __init__(self) -> None:
        self._started = time.monotonic()

    def log(self, message: str) -> None:
        timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
        elapsed = time.monotonic() - self._started
        print(
            f"[{timestamp}] [+{elapsed:,.1f}s] {message}",
            file=sys.stderr,
            flush=True,
        )


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


def read_h80_samples(
    preanalysis_dir: Path,
    *,
    progress: ProgressReporter | None = None,
    progress_every_events: int = 250_000,
) -> tuple[list[EnergySample], dict[str, object]]:
    """Read the required h80 branches from every ROOT file below a directory."""
    preanalysis_dir = Path(preanalysis_dir)
    if not preanalysis_dir.is_dir():
        raise StripEnergyFluxError(f"preanalysis directory not found: {preanalysis_dir}")
    paths = sorted(path for path in preanalysis_dir.rglob("*.root") if path.is_file())
    if not paths:
        raise StripEnergyFluxError(f"no ROOT files below: {preanalysis_dir}")
    if progress_every_events < 0:
        raise StripEnergyFluxError("progress-every-events must be nonnegative")
    if progress is not None:
        progress.log(f"h80 files discovered: {len(paths)}")

    samples: list[EnergySample] = []
    processed_events = 0
    for file_index, path in enumerate(paths, start=1):
        if progress is not None:
            progress.log(f"h80 file {file_index}/{len(paths)}: {path}")
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
            for entry_index, entry in enumerate(tree):
                try:
                    sample = EnergySample(
                        int(entry.RunNumber),
                        float(entry.Xstrip),
                        float(entry.beam.E()),
                    )
                except Exception as exc:
                    raise StripEnergyFluxError(
                        f"{path}: h80 entry {entry_index}: "
                        "cannot convert RunNumber/Xstrip/beam.E()"
                    ) from exc
                samples.append(sample)
                processed_events += 1
                if (
                    progress is not None
                    and progress_every_events > 0
                    and processed_events % progress_every_events == 0
                ):
                    progress.log(f"h80 events processed: {processed_events}")
        finally:
            source.Close()
        if progress is not None:
            progress.log(
                f"h80 file {file_index}/{len(paths)} complete; "
                f"cumulative events: {processed_events}"
            )

    return samples, {"entries": len(samples), "file_count": len(paths)}


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
    path: Path,
    run_numbers: Sequence[int],
    *,
    progress: ProgressReporter | None = None,
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
        sorted_runs = sorted(requested_runs)
        for run_index, run in enumerate(sorted_runs, start=1):
            if progress is not None:
                progress.log(f"flux run {run_index}/{len(sorted_runs)}: {run}")
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
                        float(histograms["POL2"].GetBinContent(strip)),
                        float(histograms["BREM"].GetBinContent(strip)),
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
        "schema_version": FLUX_SCHEMA_VERSION,
        "inputs": _input_paths(args),
        "thresholds": {
            "min_events_per_strip": args.min_events_per_strip,
            "max_mad_gev": args.max_mad_gev,
            "monotonic_tolerance_gev": args.monotonic_tolerance_gev,
        },
        "binnings": flux_qa["analysis_binnings"],
        "manifest_run_count": len(manifest_runs),
        "h80_run_count": len(h80_runs),
        "flux_run_count": flux_qa["run_count"],
        "lookup_strip_count": len(lookup),
        "h80": h80_qa,
        "flux": {
            key: value
            for key, value in flux_qa.items()
            if key not in {
                "analysis_binnings",
                "empty_strips",
                "extra_h80_runs",
                "low_stat_warnings",
                "mad_warnings",
                "missing_h80_runs",
                "monotonic_inversions",
                "nonzero_unmapped_strips",
                "out_of_range",
            }
        },
        "missing_h80_runs": flux_qa["missing_h80_runs"],
        "extra_h80_runs": flux_qa["extra_h80_runs"],
        "extra_flux_runs": flux_qa["extra_runs"],
        "malformed_flux_triplets": flux_qa["malformed_triplets"],
        "empty_strips": flux_qa["empty_strips"],
        "nonzero_unmapped_strips": flux_qa["nonzero_unmapped_strips"],
        "monotonic_inversions": flux_qa["monotonic_inversions"],
        "mad_warnings": flux_qa["mad_warnings"],
        "low_stat_warnings": flux_qa["low_stat_warnings"],
        "underflow_overflow": flux_qa["underflow_overflow"],
        "out_of_range": flux_qa["out_of_range"],
        "run_flux_bin_count": len(run_flux),
        "errors": unique_errors,
        "valid": not unique_errors,
    }


def run(args: argparse.Namespace) -> int:
    progress = ProgressReporter()
    progress_every_events = getattr(args, "progress_every_events", 250_000)
    progress.log("starting strip-energy/flux build")
    progress.log(
        f"inputs: preanalysis={args.preanalysis_dir}; manifest={args.manifest}; "
        f"flux={args.flux}; output={args.output_dir}"
    )
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
    if progress_every_events < 0:
        raise StripEnergyFluxError("progress-every-events must be nonnegative")

    progress.log("validating run manifest")
    records = validate_manifest(args.manifest)
    progress.log(f"manifest loaded: {len(records)} runs")
    manifest_by_run = {record.run_number: record for record in records}
    progress.log("reading h80 energy samples")
    samples, h80_qa = read_h80_samples(
        args.preanalysis_dir,
        progress=progress,
        progress_every_events=progress_every_events,
    )
    progress.log(f"h80 scan complete: {h80_qa['entries']} events")
    progress.log("building strip-energy lookup")
    lookup = build_strip_energy_lookup(samples)
    del samples
    progress.log(f"strip-energy lookup built: {len(lookup)} run/strip rows")

    lookup_by_run = defaultdict(list)
    for row in lookup:
        lookup_by_run[row.run_number].append(row)
    manifest_runs = set(manifest_by_run)
    sample_runs = set(lookup_by_run)

    progress.log("reading POL1/POL2/BREM flux histograms")
    strips, flux_qa = read_flux_histograms(
        args.flux,
        sorted(manifest_runs),
        progress=progress,
    )
    progress.log(f"flux scan complete: {len(strips)} run/strip rows")
    flux_by_run = defaultdict(list)
    for row in strips:
        flux_by_run[row.run_number].append(row)
    flux_by_run_strip = {
        run_number: {row.xstrip: row for row in rows}
        for run_number, rows in flux_by_run.items()
    }

    errors = []
    extra_h80 = sorted(sample_runs - manifest_runs)
    missing_h80 = sorted(manifest_runs - sample_runs)
    if extra_h80:
        errors.append(f"h80 runs absent from manifest: {extra_h80}")
    if missing_h80:
        errors.append(f"manifest runs absent from h80: {missing_h80}")
    if flux_qa["extra_runs"]:
        for run_number in flux_qa["extra_runs"]:
            print(
                f"WARNING: unused complete flux run {run_number}",
                file=sys.stderr,
            )
    for problem in flux_qa["malformed_triplets"]:
        errors.append(
            f"malformed flux triplet for run {problem['run_number']}"
        )

    binnings = (
        AJAKA_CROSS_SECTION,
        AJAKA_SIGMA,
        *parse_custom_binnings(args.binning),
    )

    progress.log("running lookup and flux QA")
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
                value != 0.0
                for value in (
                    strip.flux_pol1,
                    strip.flux_pol2,
                    strip.flux_brem,
                )
            ):
                nonzero_unmapped.append(
                    {
                        "run_number": run_number,
                        "xstrip": xstrip,
                        "flux_pol1": strip.flux_pol1,
                        "flux_pol2": strip.flux_pol2,
                        "flux_brem": strip.flux_brem,
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
    for binning in binnings:
        below = []
        above = []
        excluded = [0.0, 0.0, 0.0]
        for run_number in sorted(manifest_runs & sample_runs):
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
                    (strip.flux_pol1, strip.flux_pol2, strip.flux_brem)
                ):
                    excluded[index] += value
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
                "flux_pol1": excluded[0],
                "flux_pol2": excluded[1],
                "flux_brem": excluded[2],
            },
        }

    run_flux = []
    for binning in binnings:
        progress.log(f"integrating flux binning: {binning.name}")
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

    progress.log("joining event strata to run/strip exposures")
    try:
        strip_exposures = join_strip_exposures(
            [row for row in lookup if row.run_number in manifest_by_run],
            strips,
            manifest_by_run,
        )
    except StripEnergyFluxError as exc:
        errors.append(str(exc))
        strip_exposures = ()
    for row in strip_exposures:
        if row.status != "valid":
            errors.append(
                f"run {row.run_number} strip {row.xstrip}: "
                "selected polarization exposure must be positive"
            )

    flux_qa.update(
        {
            "analysis_binnings": {
                binning.name: list(binning.edges_gev) for binning in binnings
            },
            "missing_h80_runs": missing_h80,
            "extra_h80_runs": extra_h80,
            "empty_strips": empty_strips,
            "nonzero_unmapped_strips": nonzero_unmapped,
            "monotonic_inversions": inversions,
            "mad_warnings": mad_warnings,
            "low_stat_warnings": low_stat_warnings,
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
    progress.log("writing output artifacts")
    with atomic_output_directory(args.output_dir) as staging:
        progress.log("writing strip_energy_lookup.csv")
        write_lookup_csv(
            staging / "strip_energy_lookup.csv",
            [row for row in lookup if row.run_number in manifest_by_run],
            manifest_by_run,
        )
        progress.log("writing flux_by_run_energy.csv")
        write_run_flux_csv(staging / "flux_by_run_energy.csv", run_flux)
        progress.log("writing flux_by_run_strip.csv")
        write_strip_exposure_csv(
            staging / "flux_by_run_strip.csv", strip_exposures
        )
        progress.log("writing flux_by_group_energy.csv")
        write_group_flux_csv(
            staging / "flux_by_group_energy.csv",
            aggregate_group_flux(run_flux),
        )
        progress.log("writing strip_energy_flux_qa.json")
        write_qa_json(staging / "strip_energy_flux_qa.json", qa)
    if qa["valid"]:
        progress.log("completed successfully")
        print(
            f"Wrote {len(records)}-run strip-energy flux analysis "
            f"to {args.output_dir}"
        )
        return 0
    progress.log(f"completed with invalid QA: {len(qa['errors'])} errors")
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
    parser.add_argument(
        "--progress-every-events",
        type=int,
        default=250_000,
        help="emit h80 event progress every N entries; 0 disables inner updates",
    )
    parser.add_argument("--binning", action="append", default=[])
    return parser.parse_args()


def _write_failure_qa(args: argparse.Namespace, error: str) -> None:
    _validate_output_location(args)
    payload = {
        "schema_version": FLUX_SCHEMA_VERSION,
        "inputs": _input_paths(args),
        "valid": False,
        "errors": [error],
    }
    with atomic_output_directory(args.output_dir) as staging:
        write_qa_json(staging / "strip_energy_flux_qa.json", payload)


def main() -> int:
    args = parse_args()
    try:
        return run(args)
    except (ManifestError, StripEnergyFluxError, OSError, RuntimeError) as exc:
        try:
            _write_failure_qa(args, str(exc))
        except (StripEnergyFluxError, OSError):
            pass
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
