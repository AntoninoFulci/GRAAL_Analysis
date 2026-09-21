"""Load schema-v2 run/strip final exposures for asymmetry extraction."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Callable

from graal_common.calibration.strip_energy_flux import (
    FLUX_SCHEMA_VERSION,
    STRIP_EXPOSURE_FIELDS,
)
from graal_common.physics.compton import (
    ELECTRON_ENERGY_MEV,
    UV_WAVELENGTH_NM,
    linear_polarization_transfer,
)
from observable_extraction.core.models import FluxExposure


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
    target: str = "P",
    beam_type: str = "UV",
    energy_range: tuple[float, float] = (1.1, 1.5),
) -> dict[tuple[int, int], FluxExposure]:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"strip exposure file not found: {path}")
    low, high = energy_range
    if high <= low:
        raise ValueError("energy_range must be increasing")

    exposures: dict[tuple[int, int], FluxExposure] = {}
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
            if not low <= energy_gev <= high:
                continue
            if row["status"] != "valid":
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
    if not exposures:
        raise ValueError("no selected proton/UV exposures in energy range")
    return exposures
