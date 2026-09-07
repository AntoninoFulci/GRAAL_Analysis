#!/usr/bin/env python3
"""Build strip-energy and flux artifacts from pre-analysis and ROOT inputs.

The pipeline validates h80 energy samples, reads the three flux histograms for
each run, integrates flux over configured energy binnings, and writes CSV/JSON
outputs through an atomic directory replacement.
"""
from __future__ import annotations

import argparse
from array import array
from collections import defaultdict
import csv
import hashlib
import json
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
    StripEnergyLookupBuild,
    StripEnergyRecord,
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
_H80_PROGRESS_ENTRY_INTERVAL = 1_000_000
_MAX_H80_SKIP_DETAILS = 100
_CHECKPOINT_SCHEMA_VERSION = 1
_CHECKPOINT_LOOKUP_FIELDS = (
    "run_number",
    "xstrip",
    "event_count",
    "energy_median_gev",
    "energy_mad_gev",
    "energy_min_gev",
    "energy_max_gev",
    "provenance",
)
_ROOT_SCALAR_ARRAY_CODES = {
    "Char_t": "b",
    "UChar_t": "B",
    "Short_t": "h",
    "UShort_t": "H",
    "Int_t": "i",
    "UInt_t": "I",
    "Long_t": "l",
    "ULong_t": "L",
    "Long64_t": "q",
    "ULong64_t": "Q",
    "Float_t": "f",
    "Double_t": "d",
}


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
        # Close zombie handles explicitly before reporting the invalid input.
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
    # Sort both levels so QA output and processing order are reproducible.
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


def _scalar_branch_buffer(path: Path, tree, branch_name: str):
    branch = tree.GetBranch(branch_name)
    leaves = branch.GetListOfLeaves()
    if not leaves or leaves.GetEntries() != 1:
        raise StripEnergyFluxError(
            f"{path}: branch {branch_name} must contain one scalar leaf"
        )
    leaf = leaves.At(0)
    if leaf.GetLeafCount() or leaf.GetLenStatic() != 1:
        raise StripEnergyFluxError(
            f"{path}: branch {branch_name} must contain one scalar value"
        )
    type_name = str(leaf.GetTypeName())
    try:
        # ROOT leaves use C++ type names; array() requires its one-letter codes.
        type_code = _ROOT_SCALAR_ARRAY_CODES[type_name]
    except KeyError as exc:
        raise StripEnergyFluxError(
            f"{path}: unsupported {branch_name} type {type_name}"
        ) from exc
    return array(type_code, [0])


def _record_h80_skip(
    qa: dict[str, object],
    category: str,
    detail: dict[str, object],
    warning: str,
) -> None:
    if category == "entry":
        count_key, details_key = "skipped_entry_count", "skipped_entries"
    else:
        count_key, details_key = "skipped_file_count", "skipped_files"
    truncated_key = f"{details_key}_truncated"
    count = int(qa[count_key]) + 1
    qa[count_key] = count
    details = qa[details_key]
    if not isinstance(details, list):
        raise AssertionError(f"{details_key} must be a list")
    # Keep QA bounded when a damaged input contains many invalid records.
    if len(details) < _MAX_H80_SKIP_DETAILS:
        details.append(detail)
        print(f"WARNING: {warning}", file=sys.stderr)
    else:
        qa[truncated_key] = True
        if count == _MAX_H80_SKIP_DETAILS + 1:
            print(
                f"WARNING: additional skipped h80 {category} warnings suppressed",
                file=sys.stderr,
            )


def _print_h80_progress(
    qa: dict[str, object], path: Path, state: str
) -> None:
    print(
        "PROGRESS: h80 "
        f"files={qa['file_count']} "
        f"processed_entries={qa['processed_entry_count']} "
        f"valid_entries={qa['entries']} "
        f"skipped_entries={qa['skipped_entry_count']} "
        f"skipped_files={qa['skipped_file_count']} "
        f"{state}={path}",
        file=sys.stderr,
        flush=True,
    )


def _maybe_print_h80_entry_progress(
    qa: dict[str, object], path: Path
) -> None:
    if int(qa["processed_entry_count"]) % _H80_PROGRESS_ENTRY_INTERVAL == 0:
        _print_h80_progress(qa, path, "current")


def iter_h80_samples(
    preanalysis_dir: Path,
) -> tuple[Iterator[EnergySample], dict[str, object]]:
    """Stream validated h80 samples and collect QA data.

    The returned iterator opens and processes files only when consumed. The QA
    dictionary is shared with the iterator, so its counters and skip details
    are complete after iteration finishes.

    Args:
        preanalysis_dir: Directory tree containing input ROOT files.

    Returns:
        A lazy sample iterator and its mutable QA dictionary.
    """
    paths = _h80_paths(preanalysis_dir)
    qa: dict[str, object] = {
        "entries": 0,
        "processed_entry_count": 0,
        "file_count": 0,
        "skipped_entry_count": 0,
        "skipped_entries": [],
        "skipped_entries_truncated": False,
        "skipped_file_count": 0,
        "skipped_files": [],
        "skipped_files_truncated": False,
    }

    def samples():
        for path in paths:
            qa["file_count"] = int(qa["file_count"]) + 1
            try:
                source = _open_root_file(path)
            except StripEnergyFluxError as exc:
                _record_h80_skip(
                    qa,
                    "file",
                    {"path": str(path), "error": str(exc)},
                    str(exc),
                )
                _print_h80_progress(qa, path, "skipped")
                continue
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
                run_number = _scalar_branch_buffer(path, tree, "RunNumber")
                xstrip = _scalar_branch_buffer(path, tree, "Xstrip")
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
                # Bind only the required branches to avoid loading unrelated data.
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
                    qa["processed_entry_count"] = (
                        int(qa["processed_entry_count"]) + 1
                    )
                    if tree.GetEntry(entry_index) <= 0:
                        error = "cannot read entry"
                        _record_h80_skip(
                            qa,
                            "entry",
                            {
                                "path": str(path),
                                "entry": entry_index,
                                "error": error,
                            },
                            f"{path}: h80 entry {entry_index}: {error}",
                        )
                        _maybe_print_h80_entry_progress(qa, path)
                        continue
                    try:
                        sample = EnergySample(
                            run_number[0],
                            float(xstrip[0]),
                            float(beam.E()),
                        )
                        sample = validate_energy_sample(sample)
                    except StripEnergyFluxError as exc:
                        error = str(exc)
                    except Exception:
                        error = "cannot convert RunNumber/Xstrip/beam.E()"
                    else:
                        qa["entries"] = int(qa["entries"]) + 1
                        _maybe_print_h80_entry_progress(qa, path)
                        yield sample
                        continue
                    _record_h80_skip(
                        qa,
                        "entry",
                        {
                            "path": str(path),
                            "entry": entry_index,
                            "error": error,
                        },
                        f"{path}: h80 entry {entry_index}: {error}",
                    )
                    _maybe_print_h80_entry_progress(qa, path)
            finally:
                source.Close()
            _print_h80_progress(qa, path, "completed")

    return samples(), qa


def read_h80_samples(preanalysis_dir: Path) -> tuple[list[EnergySample], dict[str, object]]:
    """Materialize validated h80 samples for callers that need a list."""
    samples, qa = iter_h80_samples(preanalysis_dir)
    return list(samples), qa


def _triplet_qa(
    objects: dict[int, dict[str, list[object]]], requested_runs: set[int]
) -> dict[str, object]:
    # Inspect keys without reading histograms; malformed inputs are reported
    # before the requested histograms are converted into strip records.
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
    # Check all visible bin edges and both flow bins before accepting values.
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
    """Read one validated POL1/POL2/BREM triplet per requested run.

    Args:
        path: ROOT file containing the flux histograms.
        run_numbers: Runs that must have a complete histogram triplet.

    Returns:
        One `StripFlux` record per run and strip, plus histogram QA data.
    """
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
            # Require exactly one canonical histogram for each polarization.
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
    """Parse custom binnings supplied as `NAME:EDGE,EDGE,...` values."""
    result = []
    seen = {AJAKA_CROSS_SECTION.name, AJAKA_SIGMA.name}
    for value in values:
        # Reject duplicates here so output keys remain unambiguous.
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


def _checkpoint_path(output_dir: Path) -> Path:
    output_dir = Path(output_dir)
    return output_dir.with_name(f"{output_dir.name}.checkpoint")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _checkpoint_fingerprint(args: argparse.Namespace) -> dict[str, object]:
    root = Path(args.preanalysis_dir)
    inventory = []
    for path in _h80_paths(root):
        stat = path.stat()
        inventory.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
            }
        )
    return {
        "manifest_sha256": _sha256(args.manifest),
        "preanalysis_inventory": inventory,
    }


def _write_checkpoint(
    path: Path,
    fingerprint: dict[str, object],
    lookup_build: StripEnergyLookupBuild,
    h80_qa: dict[str, object],
) -> None:
    metadata = {
        "schema_version": _CHECKPOINT_SCHEMA_VERSION,
        "fingerprint": fingerprint,
        "lookup_build": {
            "observed_runs": list(lookup_build.observed_runs),
            "event_count": lookup_build.event_count,
            "observed_run_count": lookup_build.observed_run_count,
            "unrequested_runs": list(lookup_build.unrequested_runs),
            "unrequested_run_count": lookup_build.unrequested_run_count,
            "unrequested_runs_truncated": (
                lookup_build.unrequested_runs_truncated
            ),
        },
        "h80_qa": h80_qa,
    }
    with atomic_output_directory(path) as staging:
        lookup_path = staging / "strip_energy_lookup.csv"
        with lookup_path.open(
            "w", encoding="utf-8", newline=""
        ) as stream:
            writer = csv.DictWriter(stream, fieldnames=_CHECKPOINT_LOOKUP_FIELDS)
            writer.writeheader()
            for record in lookup_build.records:
                writer.writerow(
                    {
                        field: getattr(record, field)
                        for field in _CHECKPOINT_LOOKUP_FIELDS
                    }
                )
        metadata["lookup_sha256"] = _sha256(lookup_path)
        with (staging / "metadata.json").open("w", encoding="utf-8") as stream:
            json.dump(metadata, stream, indent=2, sort_keys=True)
            stream.write("\n")


def _checkpoint_integer(value: object, name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def _read_checkpoint_records(path: Path) -> tuple[StripEnergyRecord, ...]:
    records = []
    previous_key = None
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != _CHECKPOINT_LOOKUP_FIELDS:
            raise ValueError("invalid strip-energy lookup header")
        for line_number, row in enumerate(reader, start=2):
            try:
                record = StripEnergyRecord(
                    run_number=int(row["run_number"]),
                    xstrip=int(row["xstrip"]),
                    event_count=int(row["event_count"]),
                    energy_median_gev=float(row["energy_median_gev"]),
                    energy_mad_gev=float(row["energy_mad_gev"]),
                    energy_min_gev=float(row["energy_min_gev"]),
                    energy_max_gev=float(row["energy_max_gev"]),
                    provenance=row["provenance"],
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid lookup row {line_number}: {exc}") from exc
            values = (
                record.energy_median_gev,
                record.energy_mad_gev,
                record.energy_min_gev,
                record.energy_max_gev,
            )
            if (
                record.run_number <= 0
                or not 1 <= record.xstrip <= 128
                or record.event_count <= 0
                or not all(isfinite(value) for value in values)
                or record.energy_median_gev <= 0
                or record.energy_mad_gev < 0
                or record.energy_min_gev <= 0
                or record.energy_max_gev < record.energy_min_gev
                or not record.energy_min_gev
                <= record.energy_median_gev
                <= record.energy_max_gev
                or record.provenance != "observed"
            ):
                raise ValueError(f"invalid lookup row {line_number}")
            key = (record.run_number, record.xstrip)
            if previous_key is not None and key <= previous_key:
                raise ValueError("lookup rows must be unique and sorted")
            previous_key = key
            records.append(record)
    return tuple(records)


def _read_checkpoint(
    path: Path,
    expected_fingerprint: dict[str, object],
) -> tuple[StripEnergyLookupBuild, dict[str, object]]:
    if not path.is_dir():
        raise StripEnergyFluxError(f"resume checkpoint not found: {path}")
    try:
        payload = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
        if payload["schema_version"] != _CHECKPOINT_SCHEMA_VERSION:
            raise ValueError("unsupported schema version")
        if payload["fingerprint"] != expected_fingerprint:
            raise StripEnergyFluxError(
                f"checkpoint input fingerprint mismatch: {path}"
            )
        stored = payload["lookup_build"]
        lookup_path = path / "strip_energy_lookup.csv"
        records = _read_checkpoint_records(lookup_path)
        observed_runs = tuple(stored["observed_runs"])
        unrequested_runs = tuple(stored["unrequested_runs"])
        if any(type(run) is not int or run <= 0 for run in observed_runs):
            raise ValueError("observed runs must be positive integers")
        if tuple(sorted(set(observed_runs))) != observed_runs:
            raise ValueError("observed runs must be unique and sorted")
        if any(type(run) is not int or run <= 0 for run in unrequested_runs):
            raise ValueError("unrequested runs must be positive integers")
        if tuple(sorted(set(unrequested_runs))) != unrequested_runs:
            raise ValueError("unrequested runs must be unique and sorted")
        if set(observed_runs) & set(unrequested_runs):
            raise ValueError("observed and unrequested runs overlap")
        event_count = _checkpoint_integer(stored["event_count"], "event_count")
        observed_run_count = _checkpoint_integer(
            stored["observed_run_count"], "observed_run_count"
        )
        unrequested_run_count = _checkpoint_integer(
            stored["unrequested_run_count"], "unrequested_run_count"
        )
        truncated = stored["unrequested_runs_truncated"]
        if type(truncated) is not bool:
            raise ValueError("unrequested_runs_truncated must be boolean")
        if {record.run_number for record in records} != set(observed_runs):
            raise ValueError("lookup runs do not match observed runs")
        if sum(record.event_count for record in records) > event_count:
            raise ValueError("lookup event counts exceed total event count")
        if (
            unrequested_run_count == 0
            and sum(record.event_count for record in records) != event_count
        ):
            raise ValueError("lookup event counts do not match total event count")
        if observed_run_count != len(observed_runs) + unrequested_run_count:
            raise ValueError("observed run count is inconsistent")
        if unrequested_run_count < len(unrequested_runs):
            raise ValueError("unrequested run count is inconsistent")
        if truncated != (unrequested_run_count > len(unrequested_runs)):
            raise ValueError("unrequested truncation flag is inconsistent")
        lookup_build = StripEnergyLookupBuild(
            records=records,
            observed_runs=observed_runs,
            event_count=event_count,
            observed_run_count=observed_run_count,
            unrequested_runs=unrequested_runs,
            unrequested_run_count=unrequested_run_count,
            unrequested_runs_truncated=truncated,
        )
        h80_qa = payload["h80_qa"]
        if not isinstance(h80_qa, dict):
            raise TypeError("h80_qa must be an object")
        if h80_qa.get("entries") != event_count:
            raise ValueError("h80 entry count is inconsistent")
        if h80_qa.get("run_count") != observed_run_count:
            raise ValueError("h80 run count is inconsistent")
        if h80_qa.get("unrequested_run_count") != unrequested_run_count:
            raise ValueError("h80 unrequested run count is inconsistent")
        if h80_qa.get("unrequested_runs_truncated") is not truncated:
            raise ValueError("h80 unrequested truncation flag is inconsistent")
        lookup_sha256 = payload["lookup_sha256"]
        if not isinstance(lookup_sha256, str) or _sha256(lookup_path) != lookup_sha256:
            raise ValueError("checkpoint lookup checksum mismatch")
    except StripEnergyFluxError:
        raise
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise StripEnergyFluxError(
            f"invalid resume checkpoint {path}: {exc}"
        ) from exc
    return lookup_build, h80_qa


def _validate_output_location(args: argparse.Namespace) -> None:
    lexical_output = Path(os.path.abspath(args.output_dir))
    resolved_output = args.output_dir.resolve(strict=False)
    for input_path in (
        args.preanalysis_dir,
        args.manifest,
        args.flux,
    ):
        # Compare lexical and resolved paths to catch aliases and symlinks.
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
    """Build the consolidated QA payload written with the analysis outputs."""
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
    """Run validation, integration, QA generation, and atomic output writing.

    Returns:
        `0` when all structural and data-quality checks pass, otherwise `1`.
    """
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
    strips, flux_qa = read_flux_histograms(args.flux, sorted(manifest_runs))
    flux_by_run = defaultdict(list)
    for row in strips:
        flux_by_run[row.run_number].append(row)
    flux_by_run_strip = {
        run_number: {row.xstrip: row for row in rows}
        for run_number, rows in flux_by_run.items()
    }

    args.output_dir.parent.mkdir(parents=True, exist_ok=True)
    checkpoint = _checkpoint_path(args.output_dir)
    fingerprint = _checkpoint_fingerprint(args)
    if getattr(args, "resume", False):
        lookup_build, h80_qa = _read_checkpoint(checkpoint, fingerprint)
        h80_qa = dict(h80_qa)
        h80_qa["resumed_from_checkpoint"] = True
        print(f"Resumed strip-energy lookup from {checkpoint}", file=sys.stderr)
    else:
        # Spool samples outside the final output so a failed run cannot publish
        # partial lookup data.
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
        h80_qa.update(
            {
                "run_count": lookup_build.observed_run_count,
                "unrequested_run_count": lookup_build.unrequested_run_count,
                "unrequested_runs_truncated": (
                    lookup_build.unrequested_runs_truncated
                ),
                "resumed_from_checkpoint": False,
            }
        )
        _write_checkpoint(
            checkpoint,
            fingerprint,
            lookup_build,
            h80_qa,
        )
    lookup = lookup_build.records
    sample_runs = set(lookup_build.observed_runs)

    lookup_by_run = defaultdict(list)
    for row in lookup:
        lookup_by_run[row.run_number].append(row)

    # Structural mismatches make the final QA invalid; advisory lists remain
    # visible in the payload without necessarily failing the run.
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
        # Keep only inversions beyond tolerance as run-invalidating findings.
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
        # Track excluded flux per run so conservation can be checked later.
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
    # All files are staged together so consumers never see a partial result.
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
    if checkpoint.exists():
        shutil.rmtree(checkpoint)
    if qa["valid"]:
        print(
            f"Wrote {len(records)}-run strip-energy flux analysis "
            f"to {args.output_dir}"
        )
        return 0
    return 1


def parse_args() -> argparse.Namespace:
    """Parse command-line options for the strip-energy flux build."""
    parser = argparse.ArgumentParser(
        description="Build run-specific strip-energy and integrated flux artifacts."
    )
    parser.add_argument("--preanalysis-dir", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--flux", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="reuse a compatible strip-energy lookup checkpoint",
    )
    parser.add_argument("--min-events-per-strip", type=int, default=1)
    parser.add_argument("--max-mad-gev", type=float, default=0.005)
    parser.add_argument("--monotonic-tolerance-gev", type=float, default=0.002)
    parser.add_argument("--binning", action="append", default=[])
    return parser.parse_args()


def _write_failure_qa(args: argparse.Namespace, error: str) -> Path:
    """Write failure QA without replacing an existing successful output."""
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
    """Run the CLI and convert expected failures into QA output."""
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
