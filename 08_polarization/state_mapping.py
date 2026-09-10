"""Authoritative run/state-code to polarization-orientation mapping."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from contracts import (
    PolarizationContractError,
    load_json,
    validate_source,
)


ORIENTATIONS = frozenset({"parallel", "perpendicular"})
FLUX_COMPONENTS = frozenset({"pol1_net", "pol2_net"})


@dataclass(frozen=True)
class StateInterval:
    """One closed run interval for one recorded Polarization state code."""

    run_start: int
    run_end: int
    state_code: int
    orientation: str
    source_period: str
    flux_component: str

    def __post_init__(self) -> None:
        if (
            isinstance(self.run_start, bool)
            or isinstance(self.run_end, bool)
            or not isinstance(self.run_start, int)
            or not isinstance(self.run_end, int)
            or self.run_start <= 0
            or self.run_end < self.run_start
        ):
            raise PolarizationContractError("state interval has invalid run range")
        if isinstance(self.state_code, bool) or not isinstance(self.state_code, int):
            raise PolarizationContractError("state_code must be an integer")
        if self.orientation not in ORIENTATIONS:
            raise PolarizationContractError(
                "orientation must be exactly 'parallel' or 'perpendicular'"
            )
        if not isinstance(self.source_period, str) or not self.source_period.strip():
            raise PolarizationContractError("source_period must be non-empty")
        if self.flux_component not in FLUX_COMPONENTS:
            raise PolarizationContractError(
                "flux_component must be exactly 'pol1_net' or 'pol2_net'"
            )


def validate_intervals(intervals: Iterable[StateInterval]) -> tuple[StateInterval, ...]:
    """Return sorted intervals after proving `(run, state)` uniqueness."""
    ordered = tuple(
        sorted(
            intervals,
            key=lambda item: (item.state_code, item.run_start, item.run_end),
        )
    )
    if not ordered:
        raise PolarizationContractError("state mapping has no intervals")
    for left, right in zip(ordered, ordered[1:]):
        if left.state_code == right.state_code and right.run_start <= left.run_end:
            raise PolarizationContractError(
                "state mapping intervals overlap for state_code "
                f"{left.state_code}: {left.run_start}-{left.run_end} and "
                f"{right.run_start}-{right.run_end}"
            )
    return ordered


def resolve_orientation(
    run_number: int,
    state_code: int,
    intervals: Iterable[StateInterval],
) -> str:
    """Resolve one measured state; reject gaps and ambiguity."""
    return _resolve_interval(run_number, state_code, intervals).orientation


def resolve_flux_component(
    run_number: int,
    state_code: int,
    intervals: Iterable[StateInterval],
) -> str:
    """Resolve explicitly approved flux column for one measured state."""
    return _resolve_interval(run_number, state_code, intervals).flux_component


def _resolve_interval(
    run_number: int,
    state_code: int,
    intervals: Iterable[StateInterval],
) -> StateInterval:
    matches = [
        interval
        for interval in intervals
        if interval.state_code == state_code
        and interval.run_start <= run_number <= interval.run_end
    ]
    if not matches:
        raise PolarizationContractError(
            f"unmapped polarization state: run={run_number}, state_code={state_code}"
        )
    if len(matches) != 1:
        raise PolarizationContractError(
            f"ambiguous polarization state: run={run_number}, state_code={state_code}"
        )
    return matches[0]


def _interval_from_mapping(raw: object) -> StateInterval:
    if not isinstance(raw, Mapping):
        raise PolarizationContractError("state interval must be a JSON object")
    try:
        return StateInterval(
            run_start=raw["run_start"],
            run_end=raw["run_end"],
            state_code=raw["state_code"],
            orientation=raw["orientation"],
            source_period=raw["source_period"],
            flux_component=raw["flux_component"],
        )
    except KeyError as exc:
        raise PolarizationContractError(
            f"state interval missing field: {exc.args[0]}"
        ) from exc


def load_state_mapping(config_path: Path, repository_root: Path) -> tuple[StateInterval, ...]:
    """Load only an authority-approved state map from configuration."""
    config = load_json(config_path)
    section = config.get("state_mapping")
    if not isinstance(section, Mapping):
        raise PolarizationContractError("config state_mapping must be a JSON object")
    if section.get("status") != "ready":
        raise PolarizationContractError("state mapping is blocked; authoritative source missing")
    source = section.get("source")
    if not isinstance(source, Mapping):
        raise PolarizationContractError("state mapping requires source provenance")
    validate_source(source, repository_root)
    raw_intervals = section.get("intervals")
    if not isinstance(raw_intervals, list):
        raise PolarizationContractError("state mapping intervals must be a JSON array")
    return validate_intervals(_interval_from_mapping(raw) for raw in raw_intervals)
