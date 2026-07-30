from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from math import isfinite
from statistics import median
from typing import Iterable, Sequence


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
