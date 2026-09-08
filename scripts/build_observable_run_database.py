"""Publish a good-run-only observable database from existing analysis artifacts."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Mapping, Sequence

from graal_common.observable_runs import (
    ObservableRunError,
    RunQuality,
    classify_run_quality,
    read_lookup_artifact,
    read_run_flux_artifact,
    read_source_qa,
    sha256_file,
    write_run_quality_csv,
)
from graal_common.run_manifest import ManifestError, RunRecord, validate_manifest, write_manifest
from graal_common.strip_energy_flux import (
    StripEnergyFluxError,
    aggregate_group_flux,
    atomic_output_directory,
    write_group_flux_csv,
    write_lookup_csv,
    write_qa_json,
    write_run_flux_csv,
)


SOURCE_FILES = (
    "strip_energy_lookup.csv",
    "flux_by_run_energy.csv",
    "strip_energy_flux_qa.json",
)
_OUTPUT_CSVS = (
    "run_quality.csv",
    "run_manifest_observables.csv",
    "strip_energy_lookup.csv",
    "flux_by_run_energy.csv",
    "flux_by_group_energy.csv",
)


@dataclass(frozen=True)
class _InputSnapshot:
    manifest: Path
    source_paths: dict[str, Path]
    input_sha256: dict[str, str]


def _source_paths(strip_energy_dir: Path) -> dict[str, Path]:
    source = Path(strip_energy_dir)
    paths = {name: source / name for name in SOURCE_FILES}
    missing = next((path for path in paths.values() if not path.is_file()), None)
    if missing is not None:
        raise ObservableRunError(f"source artifact not found: {missing}")
    return paths


@contextmanager
def _snapshot_inputs(
    args: argparse.Namespace, source_paths: Mapping[str, Path]
):
    """Copy all logical inputs before reading so QA hashes name parsed bytes."""
    with tempfile.TemporaryDirectory(prefix="observable-run-inputs.") as directory:
        root = Path(directory)
        manifest = root / "manifest.csv"
        source_root = root / "source"
        source_root.mkdir()
        try:
            shutil.copyfile(args.manifest, manifest)
            snapshots = {}
            for name, path in source_paths.items():
                snapshot = source_root / name
                shutil.copyfile(path, snapshot)
                snapshots[name] = snapshot
        except OSError as exc:
            raise ObservableRunError(f"cannot snapshot input artifact: {exc}") from None
        input_sha256 = {
            "manifest": sha256_file(manifest),
            "strip_energy_lookup": sha256_file(snapshots["strip_energy_lookup.csv"]),
            "flux_by_run_energy": sha256_file(snapshots["flux_by_run_energy.csv"]),
            "strip_energy_flux_qa": sha256_file(snapshots["strip_energy_flux_qa.json"]),
        }
        yield _InputSnapshot(manifest, snapshots, input_sha256)


def _paths_overlap(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents


def _validate_output_location(args: argparse.Namespace, source_paths: Mapping[str, Path]) -> None:
    output = Path(args.output_dir)
    if output.exists() and not output.is_dir():
        raise ObservableRunError(f"destination is not a directory: {output}")
    inputs = (Path(args.manifest), Path(args.strip_energy_dir), *source_paths.values())
    lexical_output = Path(os.path.abspath(output))
    resolved_output = output.resolve(strict=False)
    for input_path in inputs:
        lexical_input = Path(os.path.abspath(input_path))
        resolved_input = input_path.resolve(strict=False)
        if _paths_overlap(lexical_output, lexical_input) or _paths_overlap(
            resolved_output, resolved_input
        ):
            raise ObservableRunError(f"output directory contains input path: {input_path}")


def _validate_source_counts(
    source_qa: Mapping[str, object],
    manifest: Sequence[RunRecord],
    lookup_runs: set[int],
    lookup_count: int,
    flux_runs: set[int],
    flux_count: int,
) -> None:
    expected = {
        "manifest_run_count": len(manifest),
        "h80_run_count": len(lookup_runs),
        "flux_run_count": len(flux_runs),
        "lookup_strip_count": lookup_count,
        "run_flux_bin_count": flux_count,
    }
    for field, value in expected.items():
        if source_qa[field] != value:
            raise ObservableRunError(
                f"source QA {field} conflicts with source artifacts: "
                f"expected {value}, got {source_qa[field]}"
            )


def _validate_good_coverage(
    good_runs: set[int],
    lookup,
    run_flux,
    source_qa: Mapping[str, object],
) -> None:
    lookup_by_run: dict[int, set[int]] = defaultdict(set)
    for record in lookup:
        lookup_by_run[record.run_number].add(record.xstrip)
    flux_by_run: dict[int, set[tuple[str, float, float]]] = defaultdict(set)
    for record in run_flux:
        flux_by_run[record.run_number].add(
            (record.binning, record.energy_low_gev, record.energy_high_gev)
        )
    expected_bins = {
        (name, left, right)
        for name, edges in source_qa["binnings"].items()
        for left, right in zip(edges, edges[1:])
    }
    for run_number in sorted(good_runs):
        if not lookup_by_run[run_number]:
            raise ObservableRunError(f"good run {run_number} has no strip-energy lookup")
        missing = expected_bins.difference(flux_by_run[run_number])
        if missing:
            binning, low, high = min(missing)
            raise ObservableRunError(
                f"good run {run_number} lacks flux row for {binning} [{low}, {high}]"
            )


def _require_valid_flux(rows, label: str) -> None:
    invalid = next((row for row in rows if row.status != "valid"), None)
    if invalid is not None:
        raise ObservableRunError(
            f"{label} has non-valid row for {invalid.binning} run "
            f"{getattr(invalid, 'run_number', invalid.group)}"
        )


def _global_source_warnings(source_qa: Mapping[str, object]) -> dict[str, object]:
    warnings: dict[str, object] = {}
    for name in ("malformed_flux_triplets", "empty_strips", "out_of_range"):
        value = source_qa[name]
        if value:
            warnings[name] = value
    return warnings


def _quality_counts(quality: Sequence[RunQuality]) -> tuple[dict[str, int], dict[str, int], dict[str, int], dict[str, dict[str, int]]]:
    by_status = Counter(row.quality_status for row in quality)
    by_reason = Counter(reason for row in quality for reason in row.reason_codes)
    by_group = Counter(row.run.group for row in quality)
    by_status_group: dict[str, Counter[str]] = defaultdict(Counter)
    for row in quality:
        by_status_group[row.quality_status][row.run.group] += 1
    return (
        dict(sorted(by_status.items())),
        dict(sorted(by_reason.items())),
        dict(sorted(by_group.items())),
        {status: dict(sorted(groups.items())) for status, groups in sorted(by_status_group.items())},
    )


def _build_qa(
    args: argparse.Namespace,
    source_paths: Mapping[str, Path],
    quality: Sequence[RunQuality],
    source_qa: Mapping[str, object],
    source_run_count: int,
    output_run_count: int,
    staging: Path,
    input_sha256: Mapping[str, str],
) -> dict[str, object]:
    by_status, by_reason, by_group, by_status_group = _quality_counts(quality)
    output_sha256 = {name: sha256_file(staging / name) for name in _OUTPUT_CSVS}
    return {
        "schema_version": 1,
        "policy_version": 1,
        "inputs": {
            "manifest": str(args.manifest),
            "strip_energy_dir": str(args.strip_energy_dir),
            "source_files": {name: str(path) for name, path in sorted(source_paths.items())},
        },
        "input_sha256": dict(sorted(input_sha256.items())),
        "source_qa_sha256": input_sha256["strip_energy_flux_qa"],
        "brem_reference_binning": args.brem_reference_binning,
        "brem_outlier_ratio": args.brem_outlier_ratio,
        "minimum_period_runs": args.minimum_period_runs,
        "counts_by_status": by_status,
        "counts_by_reason": by_reason,
        "counts_by_group": by_group,
        "counts_by_status_group": by_status_group,
        "source_run_count": source_run_count,
        "output_run_count": output_run_count,
        "global_source_qa_warnings": _global_source_warnings(source_qa),
        "output_sha256": dict(sorted(output_sha256.items())),
        "valid": True,
    }


def run(args: argparse.Namespace) -> int:
    """Validate source artifacts and atomically publish observable products."""
    if not math.isfinite(args.brem_outlier_ratio) or args.brem_outlier_ratio < 0:
        raise ObservableRunError("brem-outlier-ratio must be finite and nonnegative")
    if args.minimum_period_runs < 1:
        raise ObservableRunError("minimum-period-runs must be at least 1")
    source_paths = _source_paths(args.strip_energy_dir)
    _validate_output_location(args, source_paths)
    with _snapshot_inputs(args, source_paths) as snapshots:
        manifest = validate_manifest(snapshots.manifest)
        manifest_by_run = {record.run_number: record for record in manifest}
        lookup = read_lookup_artifact(
            snapshots.source_paths["strip_energy_lookup.csv"], manifest_by_run
        )
        run_flux = read_run_flux_artifact(
            snapshots.source_paths["flux_by_run_energy.csv"], manifest_by_run
        )
        source_qa = read_source_qa(snapshots.source_paths["strip_energy_flux_qa.json"])
        _validate_source_counts(
            source_qa,
            manifest,
            {record.run_number for record in lookup},
            len(lookup),
            {record.run_number for record in run_flux},
            len(run_flux),
        )
        quality = classify_run_quality(
            manifest,
            source_qa,
            run_flux,
            reference_binning=args.brem_reference_binning,
            brem_outlier_ratio=args.brem_outlier_ratio,
            minimum_period_runs=args.minimum_period_runs,
        )
        good_runs = {row.run.run_number for row in quality if row.quality_status == "good"}
        if not good_runs:
            raise ObservableRunError("quality policy produced no good runs")
        _validate_good_coverage(good_runs, lookup, run_flux, source_qa)
        filtered_lookup = tuple(row for row in lookup if row.run_number in good_runs)
        filtered_flux = tuple(row for row in run_flux if row.run_number in good_runs)
        _require_valid_flux(filtered_flux, "filtered run flux")
        group_flux = aggregate_group_flux(filtered_flux)
        _require_valid_flux(group_flux, "filtered group flux")
        good_manifest = [record for record in manifest if record.run_number in good_runs]
        with atomic_output_directory(args.output_dir) as staging:
            write_run_quality_csv(staging / "run_quality.csv", quality)
            write_manifest(good_manifest, staging / "run_manifest_observables.csv")
            write_lookup_csv(staging / "strip_energy_lookup.csv", filtered_lookup, manifest_by_run)
            write_run_flux_csv(staging / "flux_by_run_energy.csv", filtered_flux)
            write_group_flux_csv(staging / "flux_by_group_energy.csv", group_flux)
            write_qa_json(
                staging / "observable_run_qa.json",
                _build_qa(
                    args,
                    source_paths,
                    quality,
                    source_qa,
                    len(manifest),
                    len(good_manifest),
                    staging,
                    snapshots.input_sha256,
                ),
            )
    print(f"Wrote {len(good_manifest)} good observable runs to {args.output_dir}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build an artifact-only good-run database for observables."
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--strip-energy-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--brem-reference-binning", default="ajaka_cross_section")
    parser.add_argument("--brem-outlier-ratio", type=float, default=100.0)
    parser.add_argument("--minimum-period-runs", type=int, default=5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        return run(args)
    except (ManifestError, ObservableRunError, StripEnergyFluxError, OSError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
