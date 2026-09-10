"""Flux and polarization exposures for Sigma energy panels."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from compton import PolarizationCurve
from contracts import PolarizationContractError
from figure4_analysis import PanelExposure
from state_mapping import StateInterval, validate_intervals


_REQUIRED_COLUMNS = {
    "binning",
    "run_number",
    "source_period",
    "target",
    "energy_low_gev",
    "energy_high_gev",
    "pol1_net",
    "pol2_net",
    "status",
}


def _validate_orientation_signs(raw: Mapping[str, int]) -> dict[str, int]:
    if set(raw) != {"parallel", "perpendicular"}:
        raise PolarizationContractError(
            "orientation_signs must define exactly parallel and perpendicular"
        )
    signs = dict(raw)
    invalid_type = any(
        isinstance(value, bool) or not isinstance(value, int)
        for value in signs.values()
    )
    if invalid_type or set(signs.values()) != {-1, 1}:
        raise PolarizationContractError(
            "orientation_signs must assign opposite signs -1 and +1"
        )
    return signs


def _validate_component_assignments(intervals: Sequence[StateInterval]) -> None:
    for index, left in enumerate(intervals):
        for right in intervals[index + 1 :]:
            overlaps = max(left.run_start, right.run_start) <= min(
                left.run_end, right.run_end
            )
            if (
                overlaps
                and left.source_period == right.source_period
                and left.flux_component == right.flux_component
            ):
                raise PolarizationContractError(
                    "duplicate flux_component assignment for overlapping run range: "
                    f"{left.source_period} {left.flux_component}"
                )


def build_panel_exposures(
    flux_csv: Path,
    intervals: Sequence[StateInterval],
    curves: Mapping[str, PolarizationCurve],
    *,
    orientation_signs: Mapping[str, int],
    energy_ranges: Sequence[tuple[float, float]],
    target: str,
    run_numbers: set[int] | frozenset[int],
) -> list[PanelExposure]:
    """Aggregate accepted run flux and flux-weighted Compton polarization."""
    signs = _validate_orientation_signs(orientation_signs)
    approved = validate_intervals(intervals)
    _validate_component_assignments(approved)
    ranges = tuple((float(low), float(high)) for low, high in energy_ranges)
    if not ranges or any(
        not np.isfinite(low) or not np.isfinite(high) or high <= low
        for low, high in ranges
    ):
        raise PolarizationContractError("energy_ranges must contain positive finite bins")
    if not isinstance(target, str) or not target:
        raise PolarizationContractError("target must be non-empty")
    selected_runs = frozenset(run_numbers)
    if not selected_runs or any(
        isinstance(run, bool) or not isinstance(run, int) or run <= 0
        for run in selected_runs
    ):
        raise PolarizationContractError("run_numbers must contain positive integers")

    totals = [{-1: [0.0, 0.0, 0.0], 1: [0.0, 0.0, 0.0]} for _ in ranges]
    covered = [set() for _ in ranges]
    path = Path(flux_csv)
    try:
        handle = path.open(newline="")
    except OSError as exc:
        raise PolarizationContractError(f"cannot read flux CSV: {path}") from exc
    with handle:
        reader = csv.DictReader(handle)
        missing = _REQUIRED_COLUMNS - set(reader.fieldnames or ())
        if missing:
            raise PolarizationContractError(
                "flux CSV missing columns: " + ", ".join(sorted(missing))
            )
        for row_number, row in enumerate(reader, start=2):
            if row["binning"] != "ajaka_sigma" or row["target"] != target:
                continue
            if row["status"] != "valid":
                raise PolarizationContractError(
                    f"selected flux row {row_number} has status {row['status']!r}"
                )
            try:
                run_number = int(row["run_number"])
                low = float(row["energy_low_gev"])
                high = float(row["energy_high_gev"])
            except (TypeError, ValueError) as exc:
                raise PolarizationContractError(
                    f"flux row {row_number} has invalid numeric fields"
                ) from exc
            if run_number not in selected_runs:
                continue
            energy_index = next(
                (
                    index
                    for index, (expected_low, expected_high) in enumerate(ranges)
                    if np.isclose(low, expected_low, rtol=0.0, atol=1e-12)
                    and np.isclose(high, expected_high, rtol=0.0, atol=1e-12)
                ),
                None,
            )
            if energy_index is None:
                continue
            period = row["source_period"]
            curve = curves.get(period)
            if curve is None:
                raise PolarizationContractError(
                    f"authoritative Compton curve missing for source_period {period}"
                )
            polarization, _ = curve.bin_average(1000.0 * low, 1000.0 * high)
            low_mev = 1000.0 * low
            high_mev = 1000.0 * high
            extrema_energies = [low_mev, high_mev]
            extrema_energies.extend(
                float(energy)
                for energy in curve.energies_mev
                if low_mev < energy < high_mev
            )
            extrema_values = [
                curve.evaluate(energy)[0] for energy in extrema_energies
            ]
            weighting_bound = max(
                abs(value - polarization) for value in extrema_values
            )
            matching = tuple(
                interval
                for interval in approved
                if interval.source_period == period
                and interval.run_start <= run_number <= interval.run_end
            )
            if not matching:
                raise PolarizationContractError(
                    f"no state mapping covers flux row run={run_number}, period={period}"
                )
            for interval in matching:
                try:
                    flux = float(row[interval.flux_component])
                except (KeyError, TypeError, ValueError) as exc:
                    raise PolarizationContractError(
                        f"flux row {row_number} has invalid {interval.flux_component}"
                    ) from exc
                if not np.isfinite(flux) or flux < 0.0:
                    raise PolarizationContractError(
                        f"flux row {row_number} has negative or non-finite net flux"
                    )
                sign = signs[interval.orientation]
                totals[energy_index][sign][0] += flux
                totals[energy_index][sign][1] += flux * polarization
                totals[energy_index][sign][2] += flux * weighting_bound
            covered[energy_index].add(run_number)

    exposures = []
    for index, total in enumerate(totals):
        missing_runs = selected_runs - covered[index]
        if missing_runs:
            preview = ", ".join(str(run) for run in sorted(missing_runs)[:5])
            raise PolarizationContractError(
                f"energy bin {index} missing flux for reconstruction runs: {preview}"
            )
        horizontal_flux, horizontal_weighted, horizontal_bound = total[-1]
        vertical_flux, vertical_weighted, vertical_bound = total[1]
        if horizontal_flux <= 0.0 or vertical_flux <= 0.0:
            raise PolarizationContractError(
                f"energy bin {index} lacks positive flux for both orientations"
            )
        exposures.append(
            PanelExposure(
                vertical_flux=vertical_flux,
                horizontal_flux=horizontal_flux,
                vertical_polarization=vertical_weighted / vertical_flux,
                horizontal_polarization=horizontal_weighted / horizontal_flux,
                vertical_polarization_weighting_bound=vertical_bound / vertical_flux,
                horizontal_polarization_weighting_bound=horizontal_bound / horizontal_flux,
            )
        )
    return exposures
