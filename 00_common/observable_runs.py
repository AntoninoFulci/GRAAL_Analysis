"""Classify manifest runs using published strip-energy and flux artifacts."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from math import fsum, isfinite
from numbers import Integral, Real
from statistics import median
from typing import Mapping, Sequence
import re

from .run_manifest import RunRecord
from .strip_energy_flux import FluxBinRecord


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
            match = _RUN_HISTOGRAM.match(histogram) if isinstance(histogram, str) else None
            if match is None:
                continue
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
