from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
import csv
from dataclasses import asdict, dataclass
import json
from math import isfinite
from pathlib import Path
import shutil
from statistics import median
import tempfile
from typing import Iterable, Iterator, Sequence

from .run_manifest import RunRecord


class StripEnergyFluxError(ValueError):
    pass


@dataclass(frozen=True)
class EnergyBinning:
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
    run_number: int
    xstrip: float
    energy_gev: float


@dataclass(frozen=True)
class StripEnergyRecord:
    run_number: int
    xstrip: int
    event_count: int
    energy_median_gev: float
    energy_mad_gev: float
    energy_min_gev: float
    energy_max_gev: float
    provenance: str = "observed"


@dataclass(frozen=True)
class StripFlux:
    run_number: int
    xstrip: int
    pol1: float
    brem: float
    pol2: float


@dataclass(frozen=True)
class FluxBinRecord:
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
    rows = []
    for record in sorted(records, key=lambda record: (record.run_number, record.xstrip)):
        manifest = manifest_by_run[record.run_number]
        rows.append(
            {
                "run_number": record.run_number,
                "source_period": manifest.source_period,
                "target": manifest.target,
                "beam_type": manifest.beam_type,
                "group": manifest.group,
                **asdict(record),
            }
        )
    _write_csv(path, LOOKUP_FIELDS, rows)


def write_run_flux_csv(path: Path, records: Sequence[FluxBinRecord]) -> None:
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
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(qa, indent=2, sort_keys=True) + "\n")


@contextmanager
def atomic_output_directory(destination: Path) -> Iterator[Path]:
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
    if not isfinite(value):
        raise StripEnergyFluxError("Xstrip must be finite")
    strip = round(value)
    if abs(value - strip) > 1e-6:
        raise StripEnergyFluxError(f"Xstrip is not integral: {value}")
    if not 1 <= strip <= 128:
        raise StripEnergyFluxError(f"Xstrip outside 1..128: {value}")
    return strip


def energy_bin_index(energy_gev: float, binning: EnergyBinning) -> int | None:
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
    grouped: dict[tuple[int, int], list[float]] = defaultdict(list)
    for sample in samples:
        if sample.run_number <= 0:
            raise StripEnergyFluxError("run_number must be positive")
        if not isfinite(sample.energy_gev) or sample.energy_gev <= 0:
            raise StripEnergyFluxError("beam energy must be finite and positive")
        grouped[(sample.run_number, normalize_xstrip(sample.xstrip))].append(
            sample.energy_gev
        )

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


def integrate_run_flux(
    manifest: RunRecord,
    lookup: Sequence[StripEnergyRecord],
    strips: Sequence[StripFlux],
    binning: EnergyBinning,
) -> tuple[FluxBinRecord, ...]:
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
        if pol1_net < 0 or pol2_net < 0:
            raise StripEnergyFluxError(
                f"run {manifest.run_number} bin {index}: negative net flux"
            )
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
                "valid",
            )
        )
    return tuple(result)


def aggregate_group_flux(
    records: Sequence[FluxBinRecord],
) -> tuple[GroupFluxBinRecord, ...]:
    sums: dict[tuple[str, str, str, str, float, float], list[float]] = defaultdict(
        lambda: [0.0, 0.0, 0.0]
    )
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

    grouped = []
    for (binning, target, beam_type, group, low, high), values in sorted(sums.items()):
        pol1, brem, pol2 = values
        pol1_net = pol1 - brem
        pol2_net = pol2 - brem
        if pol1_net < 0 or pol2_net < 0:
            raise StripEnergyFluxError(
                f"group {group} bin {binning} ({low}, {high}): negative net flux"
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
                "valid",
            )
        )
    return tuple(grouped)


def find_monotonic_inversions(
    records: Sequence[StripEnergyRecord],
) -> tuple[dict[str, object], ...]:
    """Return adjacent run-strip steps that contradict the run's global slope."""
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
