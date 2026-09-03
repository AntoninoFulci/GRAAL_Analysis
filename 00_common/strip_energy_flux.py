"""Build strip-energy lookups and energy-binned flux products."""

from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
import csv
from dataclasses import asdict, dataclass
import json
from math import floor, fsum, isclose, isfinite
from numbers import Integral
from pathlib import Path
import shutil
import sqlite3
from statistics import median
import tempfile
from typing import Iterable, Iterator, Sequence

from .run_manifest import RunRecord


class StripEnergyFluxError(ValueError):
    """Report invalid strip-energy or flux input."""

    pass


@dataclass(frozen=True)
class EnergyBinning:
    """Define named, strictly increasing energy-bin edges in GeV."""

    name: str
    edges_gev: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.name:
            raise StripEnergyFluxError("binning name is empty")
        if len(self.edges_gev) < 2:
            raise StripEnergyFluxError("binning needs at least two edges")
        if not all(isfinite(edge) for edge in self.edges_gev):
            raise StripEnergyFluxError("binning edges must be finite")
        if any(right <= left for left, right in zip(self.edges_gev, self.edges_gev[1:])):
            raise StripEnergyFluxError("binning edges must be strictly increasing")


AJAKA_CROSS_SECTION = EnergyBinning(
    "ajaka_cross_section",
    tuple(0.95 + index * (1.50 - 0.95) / 15 for index in range(16)),
)
AJAKA_SIGMA = EnergyBinning("ajaka_sigma", (1.10, 1.20, 1.30, 1.40, 1.50))
MAX_UNREQUESTED_RUN_DIAGNOSTICS = 100

LOOKUP_FIELDS = (
    "run_number",
    "source_period",
    "target",
    "beam_type",
    "group",
    "xstrip",
    "event_count",
    "energy_median_gev",
    "energy_mad_gev",
    "energy_min_gev",
    "energy_max_gev",
    "provenance",
)
RUN_FLUX_FIELDS = (
    "binning",
    "run_number",
    "source_period",
    "target",
    "beam_type",
    "group",
    "energy_low_gev",
    "energy_high_gev",
    "pol1",
    "brem",
    "pol2",
    "pol1_net",
    "pol2_net",
    "total_net",
    "status",
)
GROUP_FLUX_FIELDS = (
    "binning",
    "target",
    "beam_type",
    "group",
    "energy_low_gev",
    "energy_high_gev",
    "pol1",
    "brem",
    "pol2",
    "pol1_net",
    "pol2_net",
    "total_net",
    "status",
)


@dataclass(frozen=True)
class EnergySample:
    """Store one run, strip, and measured beam-energy sample."""

    run_number: int
    xstrip: float
    energy_gev: float


@dataclass(frozen=True)
class StripEnergyRecord:
    """Store robust energy statistics for one run and strip."""

    run_number: int
    xstrip: int
    event_count: int
    energy_median_gev: float
    energy_mad_gev: float
    energy_min_gev: float
    energy_max_gev: float
    provenance: str = "observed"


@dataclass(frozen=True)
class StripEnergyLookupBuild:
    """Return a lookup and run-count QA metadata from the disk builder."""

    records: tuple[StripEnergyRecord, ...]
    observed_runs: tuple[int, ...]
    event_count: int
    observed_run_count: int
    unrequested_runs: tuple[int, ...]
    unrequested_run_count: int
    unrequested_runs_truncated: bool


@dataclass(frozen=True)
class StripFlux:
    """Store three raw flux components for one run and strip."""

    run_number: int
    xstrip: int
    pol1: float
    brem: float
    pol2: float


@dataclass(frozen=True)
class FluxBinRecord:
    """Store raw and net flux for one run and energy bin."""

    binning: str
    run_number: int
    source_period: str
    target: str
    beam_type: str
    group: str
    energy_low_gev: float
    energy_high_gev: float
    pol1: float
    brem: float
    pol2: float
    pol1_net: float
    pol2_net: float
    total_net: float
    status: str


@dataclass(frozen=True)
class GroupFluxBinRecord:
    """Store aggregated raw and net flux for one group and energy bin."""

    binning: str
    target: str
    beam_type: str
    group: str
    energy_low_gev: float
    energy_high_gev: float
    pol1: float
    brem: float
    pol2: float
    pol1_net: float
    pol2_net: float
    total_net: float
    status: str


def _write_csv(
    path: Path,
    fields: tuple[str, ...],
    rows: Iterable[dict[str, object]],
) -> None:
    """Write dictionaries to a CSV file with a fixed schema."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_lookup_csv(
    path: Path,
    records: Sequence[StripEnergyRecord],
    manifest_by_run: dict[int, RunRecord],
) -> None:
    """Write strip-energy records with manifest metadata."""
    def rows() -> Iterator[dict[str, object]]:
        for record in sorted(
            records,
            key=lambda record: (record.run_number, record.xstrip),
        ):
            manifest = manifest_by_run[record.run_number]
            yield {
                "run_number": record.run_number,
                "source_period": manifest.source_period,
                "target": manifest.target,
                "beam_type": manifest.beam_type,
                "group": manifest.group,
                **asdict(record),
            }

    _write_csv(path, LOOKUP_FIELDS, rows())


def write_run_flux_csv(path: Path, records: Sequence[FluxBinRecord]) -> None:
    """Write sorted per-run flux-bin records."""
    _write_csv(
        path,
        RUN_FLUX_FIELDS,
        (
            asdict(record)
            for record in sorted(
                records,
                key=lambda record: (
                    record.binning,
                    record.run_number,
                    record.energy_low_gev,
                    record.energy_high_gev,
                    record.source_period,
                    record.target,
                    record.beam_type,
                    record.group,
                ),
            )
        ),
    )


def write_group_flux_csv(path: Path, records: Sequence[GroupFluxBinRecord]) -> None:
    """Write sorted group-level flux-bin records."""
    _write_csv(
        path,
        GROUP_FLUX_FIELDS,
        (
            asdict(record)
            for record in sorted(
                records,
                key=lambda record: (
                    record.binning,
                    record.target,
                    record.beam_type,
                    record.group,
                    record.energy_low_gev,
                    record.energy_high_gev,
                ),
            )
        ),
    )


def write_qa_json(path: Path, qa: object) -> None:
    """Write JSON QA data with stable indentation and a trailing newline."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(qa, indent=2, sort_keys=True) + "\n")


@contextmanager
def atomic_output_directory(destination: Path) -> Iterator[Path]:
    """Yield a staging directory and publish it atomically on success."""
    destination = Path(destination)
    if destination.exists() and not destination.is_dir():
        raise StripEnergyFluxError(f"destination is not a directory: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent)
    )
    backup: Path | None = None
    try:
        yield staging
        if destination.exists():
            # Move the previous output aside before publishing the new tree.
            backup = Path(
                tempfile.mkdtemp(
                    prefix=f".{destination.name}.previous.",
                    dir=destination.parent,
                )
            )
            backup.rmdir()
            destination.replace(backup)
        try:
            staging.replace(destination)
        except BaseException:
            # Restore the previous output if publication fails.
            if backup is not None and backup.exists() and not destination.exists():
                backup.replace(destination)
            raise
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    if backup is not None:
        try:
            shutil.rmtree(backup)
        except OSError:
            pass


def normalize_xstrip(value: float) -> int:
    """Round and validate a detector strip number."""
    if not isfinite(value):
        raise StripEnergyFluxError("Xstrip must be finite")
    strip = floor(value + 0.5)
    if not 1 <= strip <= 128:
        raise StripEnergyFluxError(f"Xstrip outside 1..128: {value}")
    return strip


def _validated_energy_sample(sample: EnergySample) -> tuple[int, int, float]:
    """Normalize and validate one energy sample."""
    if isinstance(sample.run_number, Integral) and not isinstance(
        sample.run_number, bool
    ):
        run_number = int(sample.run_number)
    else:
        try:
            run_value = float(sample.run_number)
        except (TypeError, ValueError, OverflowError):
            raise StripEnergyFluxError("run_number must be an integer") from None
        if not isfinite(run_value) or not run_value.is_integer():
            raise StripEnergyFluxError("run_number must be an integer")
        run_number = int(run_value)
    if run_number <= 0:
        raise StripEnergyFluxError("run_number must be positive")

    try:
        xstrip = normalize_xstrip(float(sample.xstrip))
    except StripEnergyFluxError:
        raise
    except (TypeError, ValueError, OverflowError):
        raise StripEnergyFluxError("Xstrip must be numeric") from None
    try:
        energy_gev = float(sample.energy_gev)
    except (TypeError, ValueError, OverflowError):
        raise StripEnergyFluxError(
            "beam energy must be finite and positive"
        ) from None
    if not isfinite(energy_gev) or energy_gev <= 0:
        raise StripEnergyFluxError("beam energy must be finite and positive")
    return run_number, xstrip, energy_gev


def validate_energy_sample(sample: EnergySample) -> EnergySample:
    """Return a normalized sample or raise ``StripEnergyFluxError``."""
    run_number, xstrip, energy_gev = _validated_energy_sample(sample)
    return EnergySample(run_number, xstrip, energy_gev)


def energy_bin_index(energy_gev: float, binning: EnergyBinning) -> int | None:
    """Return the bin containing an energy, or ``None`` when out of range."""
    if not isfinite(energy_gev):
        raise StripEnergyFluxError("energy must be finite")
    if energy_gev < binning.edges_gev[0] or energy_gev > binning.edges_gev[-1]:
        return None
    for index, (low, high) in enumerate(zip(binning.edges_gev, binning.edges_gev[1:])):
        if low <= energy_gev < high:
            return index
    return len(binning.edges_gev) - 2


def build_strip_energy_lookup(
    samples: Iterable[EnergySample],
) -> tuple[StripEnergyRecord, ...]:
    """Build in-memory median and MAD statistics per run and strip."""
    grouped: dict[tuple[int, int], list[float]] = defaultdict(list)
    for sample in samples:
        run_number, xstrip, energy_gev = _validated_energy_sample(sample)
        grouped[(run_number, xstrip)].append(energy_gev)

    records = []
    for (run_number, strip), energies in sorted(grouped.items()):
        center = median(energies)
        records.append(
            StripEnergyRecord(
                run_number,
                strip,
                len(energies),
                center,
                median(abs(value - center) for value in energies),
                min(energies),
                max(energies),
            )
        )
    return tuple(records)


def _spooled_order_statistic(
    connection: sqlite3.Connection,
    run_number: int,
    xstrip: int,
    event_count: int,
    *,
    center: float | None = None,
) -> float:
    """Read a median or median absolute deviation from SQLite."""
    limit = 1 if event_count % 2 else 2
    offset = (event_count - 1) // 2
    if center is None:
        rows = connection.execute(
            """
            SELECT energy_gev
            FROM energy_samples
            WHERE run_number = ? AND xstrip = ?
            ORDER BY energy_gev
            LIMIT ? OFFSET ?
            """,
            (run_number, xstrip, limit, offset),
        )
    else:
        rows = connection.execute(
            """
            SELECT ABS(energy_gev - ?) AS deviation
            FROM energy_samples
            WHERE run_number = ? AND xstrip = ?
            ORDER BY deviation
            LIMIT ? OFFSET ?
            """,
            (center, run_number, xstrip, limit, offset),
        )
    middle = tuple(float(row[0]) for row in rows)
    if len(middle) != limit:
        raise StripEnergyFluxError(
            f"run {run_number} strip {xstrip}: incomplete energy spool"
        )
    return float(median(middle))


def build_strip_energy_lookup_on_disk(
    samples: Iterable[EnergySample],
    database: Path,
    *,
    run_numbers: Iterable[int] | None = None,
    batch_size: int = 4096,
) -> StripEnergyLookupBuild:
    """Build exact per-strip statistics while spooling samples to SQLite.

    ``run_numbers`` limits the returned records to requested runs while still
    reporting all observed runs in the QA counts.
    """
    if batch_size < 1:
        raise StripEnergyFluxError("energy spool batch size must be at least 1")
    database = Path(database)
    if database.exists():
        raise StripEnergyFluxError(f"energy spool already exists: {database}")
    database.parent.mkdir(parents=True, exist_ok=True)

    requested_runs = None
    if run_numbers is not None:
        requested_runs = tuple(sorted(set(run_numbers)))
        if any(run_number <= 0 for run_number in requested_runs):
            raise StripEnergyFluxError("requested run_number must be positive")

    connection = sqlite3.connect(str(database))
    try:
        connection.execute("PRAGMA journal_mode = OFF")
        connection.execute("PRAGMA synchronous = OFF")
        connection.execute("PRAGMA temp_store = FILE")
        connection.execute(
            """
            CREATE TABLE energy_samples (
                run_number INTEGER NOT NULL,
                xstrip INTEGER NOT NULL,
                energy_gev REAL NOT NULL
            )
            """
        )
        pending: list[tuple[int, int, float]] = []
        event_count = 0
        for sample in samples:
            pending.append(_validated_energy_sample(sample))
            event_count += 1
            if len(pending) >= batch_size:
                connection.executemany(
                    "INSERT INTO energy_samples VALUES (?, ?, ?)",
                    pending,
                )
                pending.clear()
        if pending:
            connection.executemany(
                "INSERT INTO energy_samples VALUES (?, ?, ?)",
                pending,
            )
        connection.execute(
            """
            CREATE INDEX energy_samples_order
            ON energy_samples (run_number, xstrip, energy_gev)
            """
        )

        if requested_runs is None:
            # Without a filter, every distinct run contributes to the lookup.
            observed_runs = tuple(
                int(row[0])
                for row in connection.execute(
                    """
                    SELECT DISTINCT run_number
                    FROM energy_samples
                    ORDER BY run_number
                    """
                )
            )
            observed_run_count = len(observed_runs)
            unrequested_runs: tuple[int, ...] = ()
            unrequested_run_count = 0
            group_query = """
                SELECT run_number, xstrip, COUNT(*), MIN(energy_gev), MAX(energy_gev)
                FROM energy_samples
                GROUP BY run_number, xstrip
                ORDER BY run_number, xstrip
            """
        else:
            # Keep the full input spool for QA, but join only requested runs.
            connection.execute(
                "CREATE TEMP TABLE requested_runs (run_number INTEGER PRIMARY KEY)"
            )
            connection.executemany(
                "INSERT INTO requested_runs VALUES (?)",
                ((run_number,) for run_number in requested_runs),
            )
            observed_runs = tuple(
                int(row[0])
                for row in connection.execute(
                    """
                    SELECT DISTINCT samples.run_number
                    FROM energy_samples AS samples
                    JOIN requested_runs USING (run_number)
                    ORDER BY samples.run_number
                    """
                )
            )
            unrequested_run_count = int(
                connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM (
                        SELECT DISTINCT samples.run_number
                        FROM energy_samples AS samples
                        WHERE NOT EXISTS (
                            SELECT 1
                            FROM requested_runs
                            WHERE requested_runs.run_number =
                                  samples.run_number
                        )
                    )
                    """
                ).fetchone()[0]
            )
            unrequested_runs = tuple(
                int(row[0])
                for row in connection.execute(
                    """
                    SELECT DISTINCT samples.run_number
                    FROM energy_samples AS samples
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM requested_runs
                        WHERE requested_runs.run_number =
                              samples.run_number
                    )
                    ORDER BY samples.run_number
                    LIMIT ?
                    """,
                    (MAX_UNREQUESTED_RUN_DIAGNOSTICS,),
                )
            )
            observed_run_count = len(observed_runs) + unrequested_run_count
            group_query = """
                SELECT samples.run_number,
                       samples.xstrip,
                       COUNT(*),
                       MIN(samples.energy_gev),
                       MAX(samples.energy_gev)
                FROM energy_samples AS samples
                JOIN requested_runs USING (run_number)
                GROUP BY samples.run_number, samples.xstrip
                ORDER BY samples.run_number, samples.xstrip
            """

        groups = connection.execute(group_query)
        records = []
        for run_number, xstrip, count, minimum, maximum in groups:
            # Two ordered queries yield the exact median and MAD without loading
            # all samples for a strip into Python.
            center = _spooled_order_statistic(
                connection,
                int(run_number),
                int(xstrip),
                int(count),
            )
            records.append(
                StripEnergyRecord(
                    int(run_number),
                    int(xstrip),
                    int(count),
                    center,
                    _spooled_order_statistic(
                        connection,
                        int(run_number),
                        int(xstrip),
                        int(count),
                        center=center,
                    ),
                    float(minimum),
                    float(maximum),
                )
            )
        return StripEnergyLookupBuild(
            tuple(records),
            observed_runs,
            event_count,
            observed_run_count,
            unrequested_runs,
            unrequested_run_count,
            unrequested_run_count > len(unrequested_runs),
        )
    finally:
        connection.close()


def integrate_run_flux(
    manifest: RunRecord,
    lookup: Sequence[StripEnergyRecord],
    strips: Sequence[StripFlux],
    binning: EnergyBinning,
) -> tuple[FluxBinRecord, ...]:
    """Assign strip flux to energy bins and compute net polarization flux."""
    energy_by_strip = {
        record.xstrip: record.energy_median_gev
        for record in lookup
        if record.run_number == manifest.run_number
    }
    sums = [[0.0, 0.0, 0.0] for _ in binning.edges_gev[:-1]]
    for strip in strips:
        if strip.run_number != manifest.run_number:
            raise StripEnergyFluxError(
                f"run {manifest.run_number} strip {strip.xstrip}: "
                "flux run conflicts with manifest"
            )
        values = (strip.pol1, strip.brem, strip.pol2)
        if not all(isfinite(value) for value in values):
            raise StripEnergyFluxError(
                f"run {manifest.run_number} strip {strip.xstrip}: "
                "flux contents must be finite"
            )
        if strip.xstrip not in energy_by_strip:
            if any(value != 0.0 for value in values):
                raise StripEnergyFluxError(
                    f"run {manifest.run_number} strip {strip.xstrip}: "
                    "nonzero flux without lookup"
                )
            continue
        index = energy_bin_index(energy_by_strip[strip.xstrip], binning)
        if index is not None:
            for state, value in enumerate(values):
                sums[index][state] += value

    result = []
    for index, (low, high) in enumerate(
        zip(binning.edges_gev, binning.edges_gev[1:])
    ):
        pol1, brem, pol2 = sums[index]
        pol1_net = pol1 - brem
        pol2_net = pol2 - brem
        # Negative net components mark a bin whose raw fluxes are inconsistent.
        status = "invalid" if pol1_net < 0 or pol2_net < 0 else "valid"
        result.append(
            FluxBinRecord(
                binning.name,
                manifest.run_number,
                manifest.source_period,
                manifest.target,
                manifest.beam_type,
                manifest.group,
                low,
                high,
                pol1,
                brem,
                pol2,
                pol1_net,
                pol2_net,
                pol1_net + pol2_net,
                status,
            )
        )
    return tuple(result)


def aggregate_group_flux(
    records: Sequence[FluxBinRecord],
) -> tuple[GroupFluxBinRecord, ...]:
    """Sum run-level flux records by group and energy bin."""
    sums: dict[tuple[str, str, str, str, float, float], list[float]] = defaultdict(
        lambda: [0.0, 0.0, 0.0]
    )
    invalid_keys: set[tuple[str, str, str, str, float, float]] = set()
    for record in records:
        key = (
            record.binning,
            record.target,
            record.beam_type,
            record.group,
            record.energy_low_gev,
            record.energy_high_gev,
        )
        values = sums[key]
        for index, value in enumerate((record.pol1, record.brem, record.pol2)):
            values[index] += value
        if record.status != "valid":
            invalid_keys.add(key)

    grouped = []
    for (binning, target, beam_type, group, low, high), values in sorted(sums.items()):
        pol1, brem, pol2 = values
        pol1_net = pol1 - brem
        pol2_net = pol2 - brem
        key = (binning, target, beam_type, group, low, high)
        status = (
            "invalid"
            if key in invalid_keys or pol1_net < 0 or pol2_net < 0
            else "valid"
        )
        grouped.append(
            GroupFluxBinRecord(
                binning,
                target,
                beam_type,
                group,
                low,
                high,
                pol1,
                brem,
                pol2,
                pol1_net,
                pol2_net,
                pol1_net + pol2_net,
                status,
            )
        )
    return tuple(grouped)


def check_flux_conservation(
    run_records: Sequence[FluxBinRecord],
    group_records: Sequence[GroupFluxBinRecord],
    strips: Sequence[StripFlux],
    out_of_range_raw: dict[tuple[str, int], tuple[float, float, float]],
    *,
    relative_tolerance: float = 1e-12,
    absolute_tolerance: float = 1e-9,
) -> dict[str, object]:
    """Check raw-flux conservation for runs and manifest groups."""
    if relative_tolerance < 0 or absolute_tolerance < 0:
        raise StripEnergyFluxError("conservation tolerances must be nonnegative")

    states = ("pol1", "brem", "pol2")
    physical_parts: dict[int, list[list[float]]] = defaultdict(
        lambda: [[], [], []]
    )
    for strip in strips:
        for index, value in enumerate((strip.pol1, strip.brem, strip.pol2)):
            physical_parts[strip.run_number][index].append(value)
    physical_totals = {
        run_number: tuple(fsum(parts) for parts in state_parts)
        for run_number, state_parts in physical_parts.items()
    }

    # Compare binned flux plus out-of-range flux with the physical strip total.
    included_parts: dict[tuple[str, int], list[list[float]]] = defaultdict(
        lambda: [[], [], []]
    )
    for record in run_records:
        key = (record.binning, record.run_number)
        for index, value in enumerate((record.pol1, record.brem, record.pol2)):
            included_parts[key][index].append(value)
    included_totals = {
        key: tuple(fsum(parts) for parts in state_parts)
        for key, state_parts in included_parts.items()
    }

    failures: list[dict[str, object]] = []
    run_keys = sorted(set(out_of_range_raw) | set(included_totals))
    for binning, run_number in run_keys:
        included = included_totals.get((binning, run_number), (0.0, 0.0, 0.0))
        excluded = out_of_range_raw.get(
            (binning, run_number), (0.0, 0.0, 0.0)
        )
        physical = physical_totals.get(run_number, (0.0, 0.0, 0.0))
        for index, state in enumerate(states):
            observed = fsum((included[index], excluded[index]))
            expected = physical[index]
            if isclose(
                observed,
                expected,
                rel_tol=relative_tolerance,
                abs_tol=absolute_tolerance,
            ):
                continue
            failures.append(
                {
                    "scope": "run",
                    "binning": binning,
                    "run_number": run_number,
                    "state": state,
                    "included": included[index],
                    "out_of_range": excluded[index],
                    "physical_total": expected,
                    "difference": observed - expected,
                }
            )

    expected_group_parts: dict[
        tuple[str, str, str, str, float, float], list[list[float]]
    ] = defaultdict(lambda: [[], [], []])
    for record in run_records:
        key = (
            record.binning,
            record.target,
            record.beam_type,
            record.group,
            record.energy_low_gev,
            record.energy_high_gev,
        )
        for index, value in enumerate((record.pol1, record.brem, record.pol2)):
            expected_group_parts[key][index].append(value)
    expected_group_totals = {
        key: tuple(fsum(parts) for parts in state_parts)
        for key, state_parts in expected_group_parts.items()
    }

    # Compare aggregated output with the sum of its contributing run records.
    observed_group_parts: dict[
        tuple[str, str, str, str, float, float], list[list[float]]
    ] = defaultdict(lambda: [[], [], []])
    for record in group_records:
        key = (
            record.binning,
            record.target,
            record.beam_type,
            record.group,
            record.energy_low_gev,
            record.energy_high_gev,
        )
        for index, value in enumerate((record.pol1, record.brem, record.pol2)):
            observed_group_parts[key][index].append(value)
    observed_group_totals = {
        key: tuple(fsum(parts) for parts in state_parts)
        for key, state_parts in observed_group_parts.items()
    }

    group_keys = sorted(set(expected_group_totals) | set(observed_group_totals))
    for key in group_keys:
        expected = expected_group_totals.get(key, (0.0, 0.0, 0.0))
        observed = observed_group_totals.get(key, (0.0, 0.0, 0.0))
        binning, target, beam_type, group, low, high = key
        for index, state in enumerate(states):
            if isclose(
                observed[index],
                expected[index],
                rel_tol=relative_tolerance,
                abs_tol=absolute_tolerance,
            ):
                continue
            failures.append(
                {
                    "scope": "group",
                    "binning": binning,
                    "target": target,
                    "beam_type": beam_type,
                    "group": group,
                    "energy_low_gev": low,
                    "energy_high_gev": high,
                    "state": state,
                    "group_total": observed[index],
                    "contributing_run_total": expected[index],
                    "difference": observed[index] - expected[index],
                }
            )

    return {
        "relative_tolerance": relative_tolerance,
        "absolute_tolerance": absolute_tolerance,
        "run_state_check_count": len(run_keys) * len(states),
        "group_bin_state_check_count": len(group_keys) * len(states),
        "failures": failures,
        "valid": not failures,
    }


def find_monotonic_inversions(
    records: Sequence[StripEnergyRecord],
) -> tuple[dict[str, object], ...]:
    """Find adjacent strip steps that contradict each run's global slope."""
    by_run: dict[int, list[StripEnergyRecord]] = defaultdict(list)
    for record in records:
        by_run[record.run_number].append(record)

    inversions: list[dict[str, object]] = []
    for run_number, run_records in sorted(by_run.items()):
        ordered = sorted(run_records, key=lambda record: record.xstrip)
        if len(ordered) < 2:
            continue

        mean_strip = sum(record.xstrip for record in ordered) / len(ordered)
        mean_energy = sum(record.energy_median_gev for record in ordered) / len(ordered)
        # Covariance gives the least-squares slope sign without fitting a model.
        covariance = sum(
            (record.xstrip - mean_strip) * (record.energy_median_gev - mean_energy)
            for record in ordered
        )
        if covariance == 0:
            inversions.append(
                {"run_number": run_number, "direction": "undetermined"}
            )
            continue
        direction = "increasing" if covariance > 0 else "decreasing"

        for left, right in zip(ordered, ordered[1:]):
            delta = right.energy_median_gev - left.energy_median_gev
            if (direction == "increasing" and delta < 0) or (
                direction == "decreasing" and delta > 0
            ):
                inversions.append(
                    {
                        "run_number": run_number,
                        "direction": direction,
                        "left_strip": left.xstrip,
                        "right_strip": right.xstrip,
                        "left_energy_gev": left.energy_median_gev,
                        "right_energy_gev": right.energy_median_gev,
                        "delta_gev": delta,
                    }
                )
    return tuple(inversions)
