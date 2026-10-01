"""Load run/strip final exposures for asymmetry extraction.

The calibrated ROOT contract is run-atomic: a run contributes only when all
three top-level histograms ``POL1``, ``POL2``, and ``BREM`` are present exactly
once.  An incomplete run is skipped in full, never polarization by
polarization, so event counts and exposure normalisation cannot drift apart.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
import math
from pathlib import Path
import re
import sys
from typing import Callable

from calibration.run_manifest import validate_manifest
from calibration.strip_energy_flux import (
    FLUX_SCHEMA_VERSION,
    STRIP_EXPOSURE_FIELDS,
)
from graal_common.physics.compton import (
    ELECTRON_ENERGY_MEV,
    UV_WAVELENGTH_NM,
    linear_polarization_transfer,
)
from observable_extraction.core.models import FluxExposure


_FLUX_NAME = re.compile(r"^run([1-9][0-9]*)_(POL1|POL2|BREM)$")
_REQUIRED_STATES = ("POL1", "POL2", "BREM")


def uv_polarization(energy_gev: float) -> float:
    return linear_polarization_transfer(
        energy_gev * 1000.0,
        ELECTRON_ENERGY_MEV,
        UV_WAVELENGTH_NM,
    )


def load_exposures(
    path: Path,
    polarization_model: Callable[[float], float] = uv_polarization,
    *,
    manifest_path: Path | None = None,
    run_numbers: Iterable[int] | None = None,
    target: str = "P",
    beam_type: str = "UV",
    energy_range: tuple[float, float] = (1.1, 1.5),
    skip_invalid: bool = False,
) -> dict[tuple[int, int], FluxExposure]:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"strip exposure file not found: {path}")
    low, high = energy_range
    if high <= low:
        raise ValueError("energy_range must be increasing")
    requested_runs = (
        None
        if run_numbers is None
        else {int(run_number) for run_number in run_numbers}
    )

    if path.suffix.lower() == ".root":
        if manifest_path is None:
            raise ValueError("manifest_path is required for calibrated ROOT flux")
        return _load_root_exposures(
            path,
            Path(manifest_path),
            polarization_model,
            target=target,
            beam_type=beam_type,
            energy_range=energy_range,
            run_numbers=requested_runs,
        )

    exposures: dict[tuple[int, int], FluxExposure] = {}
    skipped_invalid = 0
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != STRIP_EXPOSURE_FIELDS:
            raise ValueError("invalid flux_by_run_strip schema")
        for line_number, row in enumerate(reader, start=2):
            try:
                schema_version = int(row["schema_version"])
            except ValueError as exc:
                raise ValueError(
                    f"{path}:{line_number}: schema_version must be integer"
                ) from exc
            if schema_version != FLUX_SCHEMA_VERSION:
                raise ValueError(
                    f"{path}:{line_number}: expected schema version 2"
                )
            try:
                run_number = int(row["run_number"])
                xstrip = int(row["xstrip"])
                energy_gev = float(row["energy_median_gev"])
            except ValueError as exc:
                raise ValueError(
                    f"{path}:{line_number}: invalid run/strip/energy"
                ) from exc
            if row["target"] != target or row["beam_type"] != beam_type:
                continue
            if requested_runs is not None and run_number not in requested_runs:
                continue
            if not low <= energy_gev <= high:
                continue
            if row["status"] != "valid":
                if skip_invalid:
                    skipped_invalid += 1
                    continue
                raise ValueError(
                    f"{path}:{line_number}: selected exposure is invalid"
                )
            key = (run_number, xstrip)
            if key in exposures:
                raise ValueError(f"duplicate exposure for run/strip {key}")
            try:
                polarization = float(polarization_model(energy_gev))
                exposures[key] = FluxExposure(
                    run_number=run_number,
                    xstrip=xstrip,
                    energy_gev=energy_gev,
                    flux_vertical=float(row["flux_pol1"]),
                    flux_horizontal=float(row["flux_pol2"]),
                    flux_brem=float(row["flux_brem"]),
                    polarization_vertical=polarization,
                    polarization_horizontal=polarization,
                )
            except ValueError as exc:
                raise ValueError(f"{path}:{line_number}: {exc}") from exc
    if skipped_invalid:
        noun = "exposure" if skipped_invalid == 1 else "exposures"
        print(
            f"warning: skipped {skipped_invalid} invalid selected flux {noun}",
            file=sys.stderr,
        )
    if not exposures:
        raise ValueError(
            f"no selected {target}/{beam_type} exposures in energy range"
        )
    return exposures


def _load_root_exposures(
    path: Path,
    manifest_path: Path,
    polarization_model: Callable[[float], float],
    *,
    target: str,
    beam_type: str,
    energy_range: tuple[float, float],
    run_numbers: Iterable[int] | None,
) -> dict[tuple[int, int], FluxExposure]:
    import ROOT

    selected_runs = {
        record.run_number
        for record in validate_manifest(manifest_path)
        if record.target == target and record.beam_type == beam_type
    }
    if run_numbers is not None:
        selected_runs &= {int(run_number) for run_number in run_numbers}
    if not selected_runs:
        raise ValueError(f"manifest has no selected {target}/{beam_type} runs")

    source = ROOT.TFile.Open(str(path), "READ")
    if not source or source.IsZombie():
        raise RuntimeError(f"cannot open calibrated flux ROOT file: {path}")
    try:
        keys: dict[int, dict[str, list[object]]] = {}
        for key in source.GetListOfKeys():
            match = _FLUX_NAME.fullmatch(key.GetName())
            if match is None:
                continue
            run_number, state = match.groups()
            keys.setdefault(int(run_number), {}).setdefault(state, []).append(key)

        incomplete: list[tuple[int, tuple[str, ...]]] = []
        exposures: dict[tuple[int, int], FluxExposure] = {}
        skipped_nonfinite = 0
        skipped_nonpositive = 0
        skipped_polarization_domain = 0
        low, high = energy_range
        for run_number in sorted(selected_runs):
            run_keys = keys.get(run_number, {})
            problems = tuple(
                f"missing {state}"
                if len(run_keys.get(state, ())) == 0
                else f"duplicate {state}"
                for state in _REQUIRED_STATES
                if len(run_keys.get(state, ())) != 1
            )
            if problems:
                incomplete.append((run_number, problems))
                continue

            histograms = {
                state: run_keys[state][0].ReadObj() for state in _REQUIRED_STATES
            }
            for state, histogram in histograms.items():
                if not histogram.InheritsFrom("TH1") or histogram.GetDimension() != 1:
                    raise ValueError(f"run{run_number}_{state} is not a 1D TH1")
                if histogram.GetNbinsX() != 128:
                    raise ValueError(f"run{run_number}_{state} must have 128 bins")

            vertical = histograms["POL1"]
            horizontal = histograms["POL2"]
            brem = histograms["BREM"]
            for xstrip in range(1, 129):
                energy_vertical = float(vertical.GetXaxis().GetBinCenter(xstrip))
                energy_horizontal = float(horizontal.GetXaxis().GetBinCenter(xstrip))
                energy = 0.5 * (energy_vertical + energy_horizontal)
                if not low <= energy <= high:
                    continue
                flux_vertical = float(vertical.GetBinContent(xstrip))
                flux_horizontal = float(horizontal.GetBinContent(xstrip))
                flux_brem = float(brem.GetBinContent(xstrip))
                if not all(
                    math.isfinite(value)
                    for value in (flux_vertical, flux_horizontal, flux_brem)
                ):
                    skipped_nonfinite += 1
                    continue
                if flux_vertical <= 0.0 or flux_horizontal <= 0.0 or flux_brem < 0.0:
                    skipped_nonpositive += 1
                    continue
                try:
                    polarization_vertical = float(
                        polarization_model(energy_vertical)
                    )
                    polarization_horizontal = float(
                        polarization_model(energy_horizontal)
                    )
                except ValueError:
                    skipped_polarization_domain += 1
                    continue
                exposures[(run_number, xstrip)] = FluxExposure(
                    run_number=run_number,
                    xstrip=xstrip,
                    energy_gev=energy,
                    flux_vertical=flux_vertical,
                    flux_horizontal=flux_horizontal,
                    flux_brem=flux_brem,
                    polarization_vertical=polarization_vertical,
                    polarization_horizontal=polarization_horizontal,
                )
    finally:
        source.Close()

    if incomplete:
        if len(incomplete) == 1:
            run_number, problems = incomplete[0]
            print(
                f"warning: skipped run {run_number}: missing or duplicate "
                f"flux ({', '.join(problems)}); complete POL1/POL2/BREM "
                "triplet required",
                file=sys.stderr,
            )
        else:
            examples = "; ".join(
                f"run {run}: {', '.join(problems)}"
                for run, problems in incomplete[:10]
            )
            print(
                f"warning: skipped {len(incomplete)} runs without complete "
                f"POL1/POL2/BREM triplet; first: {examples}",
                file=sys.stderr,
            )
    if skipped_nonfinite:
        print(
            f"warning: skipped {skipped_nonfinite} run/strip exposures with "
            "non-finite flux",
            file=sys.stderr,
        )
    if skipped_nonpositive:
        print(
            f"warning: skipped {skipped_nonpositive} run/strip exposures with "
            "non-positive POL1/POL2 flux or negative BREM flux",
            file=sys.stderr,
        )
    if skipped_polarization_domain:
        print(
            f"warning: skipped {skipped_polarization_domain} run/strip exposures "
            "outside polarization domain",
            file=sys.stderr,
        )
    if not exposures:
        raise ValueError(
            f"no complete {target}/{beam_type} exposures in energy range"
        )
    return exposures
