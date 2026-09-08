"""Classify manifest runs using published strip-energy and flux artifacts."""

from __future__ import annotations

from collections import Counter, defaultdict
import csv
from dataclasses import dataclass
import hashlib
import json
from math import fsum, isclose, isfinite
from numbers import Integral, Real
from pathlib import Path
from statistics import median
from typing import Mapping, Sequence
import re

from .run_manifest import RunRecord
from .strip_energy_flux import (
    LOOKUP_FIELDS,
    RUN_FLUX_FIELDS,
    FluxBinRecord,
    StripEnergyRecord,
)


class ObservableRunError(ValueError):
    """Report an artifact finding that cannot be classified safely."""


QUALITY_FIELDS = (
    "run_number",
    "source_period",
    "target",
    "beam_type",
    "group",
    "classification_source",
    "source_file",
    "quality_status",
    "reason_codes",
    "nonzero_unmapped_strip_count",
    "negative_net_bin_count",
    "brem_reference_sum",
    "brem_period_median",
    "brem_ratio",
)


@dataclass(frozen=True)
class BremMetric:
    """Reference-binning BREM total and its source-period comparison."""

    reference_sum: float | None
    period_median: float | None
    ratio: float | None


@dataclass(frozen=True)
class RunQuality:
    """The observable-quality classification for one canonical manifest run."""

    run: RunRecord
    quality_status: str
    reason_codes: tuple[str, ...]
    nonzero_unmapped_strip_count: int
    negative_net_bin_count: int
    brem: BremMetric


_RUN_HISTOGRAM = re.compile(r"^run(?P<run_number>\d+)_")
_BAD_REASONS = {
    "missing_h80",
    "nonzero_flux_without_lookup",
    "monotonic_inversion",
    "run_flux_conservation_failure",
    "brem_period_outlier",
}
_SOURCE_QA_FIELDS = frozenset(
    {
        "schema_version",
        "inputs",
        "thresholds",
        "binnings",
        "manifest_run_count",
        "h80_run_count",
        "flux_run_count",
        "lookup_strip_count",
        "h80",
        "flux",
        "missing_h80_runs",
        "extra_h80_runs",
        "extra_h80_run_count",
        "extra_h80_runs_truncated",
        "extra_flux_runs",
        "malformed_flux_triplets",
        "empty_strips",
        "nonzero_unmapped_strips",
        "monotonic_inversions",
        "mad_warnings",
        "low_stat_warnings",
        "underflow_overflow",
        "out_of_range",
        "negative_net_errors",
        "conservation",
        "run_flux_bin_count",
        "errors",
        "valid",
    }
)
_RUN_FLUX_STATUSES = frozenset({"valid", "invalid"})
_QUALITY_STATUSES = frozenset({"good", "review", "bad"})


def _manifest_by_run(manifest: Sequence[RunRecord]) -> dict[int, RunRecord]:
    records: dict[int, RunRecord] = {}
    for record in manifest:
        if record.run_number in records:
            raise ObservableRunError(f"duplicate manifest run {record.run_number}")
        records[record.run_number] = record
    return records


def _validate_brem_options(
    reference_binning: str, outlier_ratio: float, minimum_period_runs: int
) -> None:
    if not isinstance(reference_binning, str) or not reference_binning:
        raise ObservableRunError("reference_binning must be a nonempty string")
    if (
        isinstance(outlier_ratio, bool)
        or not isinstance(outlier_ratio, Real)
        or not isfinite(outlier_ratio)
        or outlier_ratio < 0
    ):
        raise ObservableRunError("outlier_ratio must be finite and nonnegative")
    if (
        isinstance(minimum_period_runs, bool)
        or not isinstance(minimum_period_runs, Integral)
        or minimum_period_runs < 1
    ):
        raise ObservableRunError("minimum_period_runs must be a positive integer")


def _validate_flux_record(record: FluxBinRecord, manifest_by_run: Mapping[int, RunRecord]) -> None:
    manifest = manifest_by_run.get(record.run_number)
    if manifest is None:
        raise ObservableRunError(f"unknown manifest run {record.run_number} in run flux")
    if (
        record.source_period != manifest.source_period
        or record.target != manifest.target
        or record.beam_type != manifest.beam_type
        or record.group != manifest.group
    ):
        raise ObservableRunError(f"run {record.run_number}: flux metadata conflicts with manifest")
    if not isfinite(record.brem) or record.brem < 0:
        raise ObservableRunError(f"run {record.run_number}: brem must be finite and nonnegative")


def calculate_brem_metrics(
    manifest: Sequence[RunRecord],
    run_flux: Sequence[FluxBinRecord],
    *,
    reference_binning: str,
    outlier_ratio: float,
    minimum_period_runs: int,
) -> tuple[dict[int, BremMetric], set[int], set[int]]:
    """Calculate BREM totals and period-relative outlier findings per run."""
    _validate_brem_options(reference_binning, outlier_ratio, minimum_period_runs)
    manifest_by_run = _manifest_by_run(manifest)
    reference_parts: dict[int, list[float]] = defaultdict(list)
    for row in run_flux:
        _validate_flux_record(row, manifest_by_run)
        if row.binning == reference_binning:
            reference_parts[row.run_number].append(row.brem)

    totals = {run_number: fsum(parts) for run_number, parts in reference_parts.items()}
    period_totals: dict[str, list[float]] = defaultdict(list)
    for run_number, total in totals.items():
        period_totals[manifest_by_run[run_number].source_period].append(total)

    period_medians: dict[str, float] = {}
    valid_periods: set[str] = set()
    for period, values in period_totals.items():
        center = float(median(values))
        period_medians[period] = center
        if len(values) >= minimum_period_runs and center > 0:
            valid_periods.add(period)

    metrics: dict[int, BremMetric] = {}
    outliers: set[int] = set()
    unavailable: set[int] = set()
    for run_number, record in manifest_by_run.items():
        total = totals.get(run_number)
        center = period_medians.get(record.source_period)
        if total is None or record.source_period not in valid_periods:
            metrics[run_number] = BremMetric(total, center, None)
            unavailable.add(run_number)
            continue
        ratio = total / center
        metrics[run_number] = BremMetric(total, center, ratio)
        if ratio >= outlier_ratio:
            outliers.add(run_number)
    return metrics, outliers, unavailable


def _run_number(entry: object, section: str, manifest_by_run: Mapping[int, RunRecord]) -> int:
    if not isinstance(entry, Mapping):
        raise ObservableRunError(f"{section} entry must be an object")
    run_number = entry.get("run_number")
    if isinstance(run_number, bool) or not isinstance(run_number, Integral):
        raise ObservableRunError(f"{section} entry has no run_number")
    if run_number not in manifest_by_run:
        raise ObservableRunError(f"unknown manifest run {run_number} in {section}")
    return int(run_number)


def _entries(source_qa: Mapping[str, object], section: str) -> Sequence[object]:
    value = source_qa.get(section, ())
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ObservableRunError(f"{section} must be an array")
    return value


def _add_qa_reasons(
    source_qa: Mapping[str, object],
    manifest_by_run: Mapping[int, RunRecord],
    reasons: dict[int, set[str]],
    unmapped: Counter[int],
    negative: Counter[int],
) -> None:
    for run_number in _entries(source_qa, "missing_h80_runs"):
        if isinstance(run_number, bool) or not isinstance(run_number, Integral):
            raise ObservableRunError("missing_h80_runs entries must be run numbers")
        if run_number not in manifest_by_run:
            raise ObservableRunError(f"unknown manifest run {run_number} in missing_h80_runs")
        reasons[int(run_number)].add("missing_h80")

    for section, reason in (
        ("nonzero_unmapped_strips", "nonzero_flux_without_lookup"),
        ("monotonic_inversions", "monotonic_inversion"),
        ("mad_warnings", "high_energy_mad"),
        ("low_stat_warnings", "low_strip_statistics"),
        ("negative_net_errors", "negative_net_flux"),
    ):
        for entry in _entries(source_qa, section):
            run_number = _run_number(entry, section, manifest_by_run)
            reasons[run_number].add(reason)
            if section == "nonzero_unmapped_strips":
                unmapped[run_number] += 1
            elif section == "negative_net_errors":
                negative[run_number] += 1

    for entry in _entries(source_qa, "underflow_overflow"):
        if not isinstance(entry, Mapping):
            raise ObservableRunError("underflow_overflow entry must be an object")
        run_number = entry.get("run_number")
        if run_number is None:
            histogram = entry.get("histogram")
            match = (
                _RUN_HISTOGRAM.match(histogram)
                if isinstance(histogram, str)
                else None
            )
            if match is None:
                raise ObservableRunError(
                    "underflow_overflow histogram lacks a canonical run<N>_ prefix"
                )
            run_number = int(match.group("run_number"))
        if isinstance(run_number, bool) or not isinstance(run_number, Integral):
            raise ObservableRunError("underflow_overflow entry has invalid run_number")
        if run_number not in manifest_by_run:
            raise ObservableRunError(f"unknown manifest run {run_number} in underflow_overflow")
        reasons[int(run_number)].add("flux_underflow_overflow")

    conservation = source_qa.get("conservation", {"failures": ()})
    if not isinstance(conservation, Mapping):
        raise ObservableRunError("conservation must be an object")
    failures = conservation.get("failures", ())
    if not isinstance(failures, Sequence) or isinstance(failures, (str, bytes)):
        raise ObservableRunError("conservation failures must be an array")
    for failure in failures:
        if not isinstance(failure, Mapping):
            raise ObservableRunError("conservation failure must be an object")
        if failure.get("scope") != "run":
            raise ObservableRunError("group-scope conservation failure cannot be assigned safely")
        run_number = _run_number(failure, "conservation", manifest_by_run)
        reasons[run_number].add("run_flux_conservation_failure")


def classify_run_quality(
    manifest: Sequence[RunRecord],
    source_qa: Mapping[str, object],
    run_flux: Sequence[FluxBinRecord],
    *,
    reference_binning: str = "ajaka_cross_section",
    brem_outlier_ratio: float = 100.0,
    minimum_period_runs: int = 5,
) -> tuple[RunQuality, ...]:
    """Return every manifest run once, ordered numerically, with a fail-closed status."""
    if not isinstance(source_qa, Mapping):
        raise ObservableRunError("source_qa must be an object")
    manifest_by_run = _manifest_by_run(manifest)
    metrics, outliers, unavailable = calculate_brem_metrics(
        manifest,
        run_flux,
        reference_binning=reference_binning,
        outlier_ratio=brem_outlier_ratio,
        minimum_period_runs=minimum_period_runs,
    )
    reasons = {run_number: set() for run_number in manifest_by_run}
    unmapped: Counter[int] = Counter()
    negative: Counter[int] = Counter()
    _add_qa_reasons(source_qa, manifest_by_run, reasons, unmapped, negative)

    negative_from_flux: Counter[int] = Counter()
    for row in run_flux:
        if row.pol1_net < 0 or row.pol2_net < 0:
            negative_from_flux[row.run_number] += 1
    for run_number, count in negative_from_flux.items():
        reasons[run_number].add("negative_net_flux")
        negative[run_number] = max(negative[run_number], count)
    for run_number in outliers:
        reasons[run_number].add("brem_period_outlier")
    for run_number in unavailable:
        # A bad finding already excludes the run; unavailable BREM is a
        # conservative review reason only for runs not otherwise unusable.
        if not _BAD_REASONS.intersection(reasons[run_number]):
            reasons[run_number].add("brem_baseline_unavailable")

    quality = []
    for run_number, record in sorted(manifest_by_run.items()):
        run_reasons = tuple(sorted(reasons[run_number]))
        status = "bad" if _BAD_REASONS.intersection(run_reasons) else "review" if run_reasons else "good"
        quality.append(
            RunQuality(
                record,
                status,
                run_reasons,
                unmapped[run_number],
                negative[run_number],
                metrics[run_number],
            )
        )
    return tuple(quality)


def _artifact_error(path: Path, row_number: int, message: str) -> ObservableRunError:
    return ObservableRunError(f"{path} row {row_number}: {message}")


def _parse_positive_integer(value: object, path: Path, row_number: int, field: str) -> int:
    if not isinstance(value, str):
        raise _artifact_error(path, row_number, f"{field} must be a positive integer")
    try:
        parsed = int(value)
    except ValueError:
        raise _artifact_error(path, row_number, f"{field} must be a positive integer") from None
    if parsed <= 0 or value.strip() != value or not value or value.startswith("+"):
        raise _artifact_error(path, row_number, f"{field} must be a positive integer")
    return parsed


def _parse_finite_float(value: object, path: Path, row_number: int, field: str) -> float:
    if not isinstance(value, str):
        raise _artifact_error(path, row_number, f"{field} must be finite")
    try:
        parsed = float(value)
    except ValueError:
        raise _artifact_error(path, row_number, f"{field} must be finite") from None
    if not isfinite(parsed):
        raise _artifact_error(path, row_number, f"{field} must be finite")
    return parsed


def _validate_manifest_metadata(
    row: Mapping[str, str], path: Path, row_number: int, manifest_by_run: Mapping[int, RunRecord]
) -> tuple[int, RunRecord]:
    run_number = _parse_positive_integer(row.get("run_number"), path, row_number, "run_number")
    manifest = manifest_by_run.get(run_number)
    if manifest is None:
        raise _artifact_error(path, row_number, f"unknown manifest run {run_number}")
    if any(
        row[field] != expected
        for field, expected in (
            ("source_period", manifest.source_period),
            ("target", manifest.target),
            ("beam_type", manifest.beam_type),
            ("group", manifest.group),
        )
    ):
        raise _artifact_error(path, row_number, "metadata conflicts with manifest")
    return run_number, manifest


def _read_csv_rows(path: Path, fields: tuple[str, ...]):
    path = Path(path)
    try:
        stream = path.open(newline="")
    except OSError as exc:
        raise ObservableRunError(f"{path}: cannot read artifact: {exc}") from None
    with stream:
        try:
            reader = csv.DictReader(stream, strict=True)
            if tuple(reader.fieldnames or ()) != fields:
                raise _artifact_error(path, 1, "header does not match required schema")
            for row_number, row in enumerate(reader, start=2):
                if None in row or any(value is None for value in row.values()):
                    raise _artifact_error(path, row_number, "row does not match required schema")
                yield path, row_number, row
        except csv.Error as exc:
            raise _artifact_error(path, max(reader.line_num, 2), f"malformed CSV: {exc}") from None


def read_lookup_artifact(
    path: Path, manifest_by_run: Mapping[int, RunRecord]
) -> tuple[StripEnergyRecord, ...]:
    """Read a strict source lookup CSV and reconstruct immutable records."""
    records = []
    keys: set[tuple[int, int]] = set()
    for source_path, row_number, row in _read_csv_rows(path, LOOKUP_FIELDS):
        run_number, _ = _validate_manifest_metadata(row, source_path, row_number, manifest_by_run)
        xstrip = _parse_positive_integer(row.get("xstrip"), source_path, row_number, "xstrip")
        if xstrip > 128:
            raise _artifact_error(source_path, row_number, "xstrip must be in 1..128")
        event_count = _parse_positive_integer(row.get("event_count"), source_path, row_number, "event_count")
        numeric = {
            field: _parse_finite_float(row.get(field), source_path, row_number, field)
            for field in (
                "energy_median_gev",
                "energy_mad_gev",
                "energy_min_gev",
                "energy_max_gev",
            )
        }
        if numeric["energy_mad_gev"] < 0:
            raise _artifact_error(source_path, row_number, "energy_mad_gev must be nonnegative")
        if not (
            numeric["energy_min_gev"]
            <= numeric["energy_median_gev"]
            <= numeric["energy_max_gev"]
        ):
            raise _artifact_error(source_path, row_number, "energy statistics are inconsistent")
        provenance = row["provenance"]
        if not provenance:
            raise _artifact_error(source_path, row_number, "provenance must be nonempty")
        key = (run_number, xstrip)
        if key in keys:
            raise _artifact_error(source_path, row_number, f"duplicate lookup key {run_number}/{xstrip}")
        keys.add(key)
        records.append(
            StripEnergyRecord(
                run_number,
                xstrip,
                event_count,
                numeric["energy_median_gev"],
                numeric["energy_mad_gev"],
                numeric["energy_min_gev"],
                numeric["energy_max_gev"],
                provenance,
            )
        )
    return tuple(records)


def read_run_flux_artifact(
    path: Path, manifest_by_run: Mapping[int, RunRecord]
) -> tuple[FluxBinRecord, ...]:
    """Read a strict per-run flux CSV and verify its numeric invariants."""
    records = []
    keys: set[tuple[str, int, float, float]] = set()
    for source_path, row_number, row in _read_csv_rows(path, RUN_FLUX_FIELDS):
        run_number, manifest = _validate_manifest_metadata(row, source_path, row_number, manifest_by_run)
        binning = row["binning"]
        if not binning:
            raise _artifact_error(source_path, row_number, "binning must be nonempty")
        numeric = {
            field: _parse_finite_float(row.get(field), source_path, row_number, field)
            for field in (
                "energy_low_gev",
                "energy_high_gev",
                "pol1",
                "brem",
                "pol2",
                "pol1_net",
                "pol2_net",
                "total_net",
            )
        }
        if numeric["energy_high_gev"] <= numeric["energy_low_gev"]:
            raise _artifact_error(source_path, row_number, "energy bin edges must increase")
        expected = {
            "pol1_net": numeric["pol1"] - numeric["brem"],
            "pol2_net": numeric["pol2"] - numeric["brem"],
        }
        expected["total_net"] = expected["pol1_net"] + expected["pol2_net"]
        for field, value in expected.items():
            if not isclose(numeric[field], value, rel_tol=1e-12, abs_tol=1e-9):
                raise _artifact_error(source_path, row_number, f"{field} does not match raw flux formula")
        status = row["status"]
        if status not in _RUN_FLUX_STATUSES:
            raise _artifact_error(source_path, row_number, "status is not in the source vocabulary")
        expected_status = "invalid" if numeric["pol1_net"] < 0 or numeric["pol2_net"] < 0 else "valid"
        if status != expected_status:
            raise _artifact_error(source_path, row_number, "status conflicts with net flux")
        key = (binning, run_number, numeric["energy_low_gev"], numeric["energy_high_gev"])
        if key in keys:
            raise _artifact_error(source_path, row_number, f"duplicate flux key {binning}/{run_number}")
        keys.add(key)
        records.append(
            FluxBinRecord(
                binning,
                run_number,
                manifest.source_period,
                manifest.target,
                manifest.beam_type,
                manifest.group,
                numeric["energy_low_gev"],
                numeric["energy_high_gev"],
                numeric["pol1"],
                numeric["brem"],
                numeric["pol2"],
                numeric["pol1_net"],
                numeric["pol2_net"],
                numeric["total_net"],
                status,
            )
        )
    return tuple(records)


def _reject_json_constant(value: str) -> object:
    raise ValueError(f"non-finite JSON value {value}")


def read_source_qa(path: Path) -> dict[str, object]:
    """Read and validate the exact schema-v1 source QA JSON document."""
    path = Path(path)
    try:
        payload = json.loads(path.read_text(), parse_constant=_reject_json_constant)
    except (OSError, UnicodeDecodeError) as exc:
        raise ObservableRunError(f"{path}: cannot read source QA: {exc}") from None
    except (json.JSONDecodeError, ValueError) as exc:
        raise ObservableRunError(f"{path}: malformed JSON: {exc}") from None
    if not isinstance(payload, dict):
        raise ObservableRunError(f"{path}: source QA must be an object")
    if set(payload) != _SOURCE_QA_FIELDS:
        raise ObservableRunError(f"{path}: source QA schema does not match version 1")
    if isinstance(payload["schema_version"], bool) or payload["schema_version"] != 1:
        raise ObservableRunError(f"{path}: schema_version must be 1")
    for field in ("inputs", "thresholds", "binnings", "h80", "flux", "out_of_range", "conservation"):
        if not isinstance(payload[field], dict):
            raise ObservableRunError(f"{path}: source QA field {field} must be an object")
    for field in (
        "missing_h80_runs", "extra_h80_runs", "extra_flux_runs", "malformed_flux_triplets",
        "empty_strips", "nonzero_unmapped_strips", "monotonic_inversions", "mad_warnings",
        "low_stat_warnings", "underflow_overflow", "negative_net_errors", "errors",
    ):
        if not isinstance(payload[field], list):
            raise ObservableRunError(f"{path}: source QA field {field} must be an array")
    if not all(isinstance(error, str) for error in payload["errors"]):
        raise ObservableRunError(f"{path}: source QA errors must be strings")
    if not isinstance(payload["valid"], bool):
        raise ObservableRunError(f"{path}: source QA valid must be boolean")
    return payload


def _qa_positive_integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral) or value <= 0:
        raise ObservableRunError(f"source QA {field} must be a positive integer")
    return int(value)


def _qa_expected_errors(qa: Mapping[str, object]) -> set[str]:
    missing = qa.get("missing_h80_runs")
    if not isinstance(missing, list):
        raise ObservableRunError("source QA missing_h80_runs must be an array")
    missing_runs = [_qa_positive_integer(run, "missing_h80_runs entry") for run in missing]
    expected = {f"manifest runs absent from h80: {missing_runs}"} if missing_runs else set()

    unmapped = qa.get("nonzero_unmapped_strips")
    if not isinstance(unmapped, list):
        raise ObservableRunError("source QA nonzero_unmapped_strips must be an array")
    for entry in unmapped:
        if not isinstance(entry, Mapping):
            raise ObservableRunError("source QA nonzero_unmapped_strips entry must be an object")
        run_number = _qa_positive_integer(entry.get("run_number"), "nonzero_unmapped_strips run_number")
        xstrip = _qa_positive_integer(entry.get("xstrip"), "nonzero_unmapped_strips xstrip")
        expected.add(f"run {run_number} strip {xstrip}: nonzero flux without lookup")

    negative = qa.get("negative_net_errors")
    if not isinstance(negative, list):
        raise ObservableRunError("source QA negative_net_errors must be an array")
    for entry in negative:
        if not isinstance(entry, Mapping):
            raise ObservableRunError("source QA negative_net_errors entry must be an object")
        run_number = _qa_positive_integer(entry.get("run_number"), "negative_net_errors run_number")
        binning = entry.get("binning")
        bin_index = entry.get("bin_index")
        if not isinstance(binning, str) or not binning:
            raise ObservableRunError("source QA negative_net_errors binning must be nonempty")
        if isinstance(bin_index, bool) or not isinstance(bin_index, Integral) or bin_index < 0:
            raise ObservableRunError("source QA negative_net_errors bin_index must be nonnegative")
        expected.add(f"run {run_number} binning {binning} bin {bin_index}: negative net flux")

    conservation = qa.get("conservation")
    if not isinstance(conservation, Mapping):
        raise ObservableRunError("source QA conservation must be an object")
    failures = conservation.get("failures")
    if not isinstance(failures, list):
        raise ObservableRunError("source QA conservation failures must be an array")
    for failure in failures:
        if not isinstance(failure, Mapping):
            raise ObservableRunError("source QA conservation failure must be an object")
        scope = failure.get("scope")
        binning = failure.get("binning")
        state = failure.get("state")
        if not isinstance(binning, str) or not binning or not isinstance(state, str) or not state:
            raise ObservableRunError("source QA conservation failure has invalid identity")
        if scope == "run":
            run_number = _qa_positive_integer(failure.get("run_number"), "conservation run_number")
            expected.add(
                "structural run raw-flux conservation failure: "
                f"binning {binning} run {run_number} state {state}"
            )
        elif scope == "group":
            group = failure.get("group")
            low = failure.get("energy_low_gev")
            high = failure.get("energy_high_gev")
            if not isinstance(group, str) or not group or not isinstance(low, Real) or not isinstance(high, Real):
                raise ObservableRunError("source QA group conservation failure has invalid identity")
            expected.add(
                "structural group raw-flux conservation failure: "
                f"binning {binning} group {group} bin [{low}, {high}] state {state}"
            )
        else:
            raise ObservableRunError("source QA conservation failure has invalid scope")
    return expected


def validate_source_qa_errors(qa: Mapping[str, object]) -> None:
    """Require every source error to have one exact structured QA identity."""
    if not isinstance(qa, Mapping):
        raise ObservableRunError("source QA must be an object")
    errors = qa.get("errors")
    if not isinstance(errors, list) or not all(isinstance(error, str) for error in errors):
        raise ObservableRunError("source QA errors must be an array of strings")
    if set(errors) != _qa_expected_errors(qa):
        raise ObservableRunError("unclassified source QA error")


def _quality_value(value: float | None, field: str) -> float | str:
    if value is None:
        return ""
    if isinstance(value, bool) or not isinstance(value, Real) or not isfinite(value):
        raise ObservableRunError(f"{field} must be finite or absent")
    return float(value)


def write_run_quality_csv(path: Path, rows: Sequence[RunQuality]) -> None:
    """Write canonical run quality rows with a stable schema and ordering."""
    path = Path(path)
    seen_runs: set[int] = set()
    serialized = []
    for quality in sorted(rows, key=lambda row: row.run.run_number):
        if quality.run.run_number in seen_runs:
            raise ObservableRunError(f"duplicate quality run {quality.run.run_number}")
        seen_runs.add(quality.run.run_number)
        if quality.quality_status not in _QUALITY_STATUSES:
            raise ObservableRunError("quality_status is not in the output vocabulary")
        if tuple(sorted(set(quality.reason_codes))) != quality.reason_codes or not all(
            isinstance(reason, str) and reason for reason in quality.reason_codes
        ):
            raise ObservableRunError("reason_codes must be sorted unique nonempty strings")
        for field, value in (
            ("nonzero_unmapped_strip_count", quality.nonzero_unmapped_strip_count),
            ("negative_net_bin_count", quality.negative_net_bin_count),
        ):
            if isinstance(value, bool) or not isinstance(value, Integral) or value < 0:
                raise ObservableRunError(f"{field} must be a nonnegative integer")
        serialized.append(
            {
                "run_number": quality.run.run_number,
                "source_period": quality.run.source_period,
                "target": quality.run.target,
                "beam_type": quality.run.beam_type,
                "group": quality.run.group,
                "classification_source": quality.run.classification_source,
                "source_file": quality.run.source_file,
                "quality_status": quality.quality_status,
                "reason_codes": ";".join(quality.reason_codes),
                "nonzero_unmapped_strip_count": quality.nonzero_unmapped_strip_count,
                "negative_net_bin_count": quality.negative_net_bin_count,
                "brem_reference_sum": _quality_value(quality.brem.reference_sum, "brem_reference_sum"),
                "brem_period_median": _quality_value(quality.brem.period_median, "brem_period_median"),
                "brem_ratio": _quality_value(quality.brem.ratio, "brem_ratio"),
            }
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=QUALITY_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(serialized)


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of a file without depending on its text encoding."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
