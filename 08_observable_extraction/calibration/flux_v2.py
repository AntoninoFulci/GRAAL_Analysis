"""Load paired POL exposures and independently qualified BREM controls.

POL1/POL2 availability remains paired by run/strip. Missing or defective BREM
is explicitly recorded and cannot alter the polarized exposure denominator.
This policy is specific to beam asymmetry, not cross-section normalization.
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
from calibration.run_quality import load_run_quality
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
_POL_STATES = ("POL1", "POL2")
_STATES = (*_POL_STATES, "BREM")


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
    audit: dict | None = None,
    allow_empty: bool = False,
    run_quality: dict | None = None,
) -> dict[tuple[int, int], FluxExposure]:
    quality = load_run_quality() if run_quality is None else run_quality
    excluded = {item["run"]: item for item in quality["excluded_runs"]}
    if audit is not None:
        audit["_run_quality"] = quality
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
            audit=audit,
            allow_empty=allow_empty,
            quality_exclusions=excluded,
        )

    exposures: dict[tuple[int, int], FluxExposure] = {}
    skipped_invalid = 0
    manifest = ({record.run_number: record for record in validate_manifest(manifest_path)}
                if manifest_path is not None else None)
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
            if requested_runs is not None and run_number not in requested_runs:
                continue
            if run_number in excluded:
                if audit is not None:
                    audit[str(run_number)] = _quality_audit(excluded[run_number])
                continue
            if manifest is not None:
                record = manifest.get(run_number)
                if record is None or any(row[name] != getattr(record, name)
                                         for name in ("source_period", "target", "beam_type", "group")):
                    raise ValueError(f"{path}:{line_number}: flux row conflicts with run manifest")
            if row["target"] != target or row["beam_type"] != beam_type:
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
                flux_brem, brem_status = _brem_value(row["flux_brem"])
                exposures[key] = FluxExposure(
                    run_number=run_number,
                    xstrip=xstrip,
                    energy_gev=energy_gev,
                    flux_vertical=float(row["flux_pol1"]),
                    flux_horizontal=float(row["flux_pol2"]),
                    flux_brem=flux_brem,
                    brem_status=brem_status,
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
    for run, status in sorted({(item.run_number, item.brem_status)
                               for item in exposures.values() if not item.has_measured_brem}):
        print(f"warning: run {run}: {status} BREM; polarized exposures retained independently",
              file=sys.stderr)
    if audit is not None:
        for run in sorted(requested_runs or {key[0] for key in exposures}):
            if run in excluded:
                audit[str(run)] = _quality_audit(excluded[run])
                continue
            count = sum(key[0] == run for key in exposures)
            values = [item for item in exposures.values() if item.run_number == run]
            audit[str(run)] = dict(status="valid" if count else "no_valid_exposure",
                                   problems=[f"{status} BREM" for status in _brem_counts(values)
                                             if status != "measured_valid"], valid_strata=count,
                                   brem_valid_strata=sum(item.has_measured_brem for item in values),
                                   brem_status_counts=_brem_counts(values))
    if not exposures and not allow_empty:
        raise ValueError(
            f"no selected {target}/{beam_type} exposures in energy range"
        )
    return exposures


def _quality_audit(record):
    return dict(status="quality_excluded", problems=[record["reason"]],
                evidence=record["evidence"], valid_strata=0)


def _load_root_exposures(
    path: Path,
    manifest_path: Path,
    polarization_model: Callable[[float], float],
    *,
    target: str,
    beam_type: str,
    energy_range: tuple[float, float],
    run_numbers: Iterable[int] | None,
    quality_exclusions: dict,
    audit: dict | None = None,
    allow_empty: bool = False,
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
            if run_number in quality_exclusions:
                if audit is not None:
                    audit[str(run_number)] = _quality_audit(quality_exclusions[run_number])
                continue
            run_keys = keys.get(run_number, {})
            loaded = {state: _histogram_state(run_keys.get(state, ())) for state in _STATES}
            states = {state: result[1] for state, result in loaded.items()}
            problems = tuple(f"{states[state]['status']} {state}" for state in _POL_STATES
                             if loaded[state][0] is None)
            if problems:
                incomplete.append((run_number, problems))
                if audit is not None:
                    audit[str(run_number)] = dict(status="missing_flux", problems=list(problems),
                                                  states=states, valid_strata=0, brem_valid_strata=0)
                continue
            vertical, horizontal = (loaded[state][0] for state in _POL_STATES)
            brem = loaded["BREM"][0]
            brem_state = states["BREM"]["status"]
            if brem_state != "measured_valid":
                print(f"warning: run {run_number}: {brem_state} BREM; "
                      "polarized exposures retained independently", file=sys.stderr)
            run_values = []
            for xstrip in range(1, 129):
                energy_vertical = float(vertical.GetXaxis().GetBinCenter(xstrip))
                energy_horizontal = float(horizontal.GetXaxis().GetBinCenter(xstrip))
                energy = 0.5 * (energy_vertical + energy_horizontal)
                if not low <= energy <= high:
                    continue
                flux_vertical = float(vertical.GetBinContent(xstrip))
                flux_horizontal = float(horizontal.GetBinContent(xstrip))
                if not all(math.isfinite(value) for value in (flux_vertical, flux_horizontal)):
                    skipped_nonfinite += 1
                    continue
                if flux_vertical <= 0.0 or flux_horizontal <= 0.0:
                    skipped_nonpositive += 1
                    continue
                if brem is None:
                    flux_brem, brem_status = None, brem_state
                else:
                    flux_brem, brem_status = _brem_value(brem.GetBinContent(xstrip))
                try:
                    polarization_vertical = float(polarization_model(energy_vertical))
                    polarization_horizontal = float(polarization_model(energy_horizontal))
                    if not all(math.isfinite(value) and 0.0 <= value <= 1.0
                               for value in (polarization_vertical, polarization_horizontal)):
                        raise ValueError("invalid polarization")
                except ValueError:
                    skipped_polarization_domain += 1
                    continue
                item = FluxExposure(
                    run_number=run_number,
                    xstrip=xstrip,
                    energy_gev=energy,
                    flux_vertical=flux_vertical,
                    flux_horizontal=flux_horizontal,
                    flux_brem=flux_brem,
                    polarization_vertical=polarization_vertical,
                    polarization_horizontal=polarization_horizontal,
                    brem_status=brem_status,
                )
                exposures[(run_number, xstrip)] = item
                run_values.append(item)
            if audit is not None:
                count = len(run_values)
                audit[str(run_number)] = dict(status="valid" if count else "no_valid_exposure",
                    problems=[f"{brem_state} BREM"] if brem_state != "measured_valid" else [],
                    states=states, valid_strata=count,
                    brem_valid_strata=sum(item.has_measured_brem for item in run_values),
                    brem_status_counts=_brem_counts(run_values))
    finally:
        source.Close()

    if incomplete:
        if len(incomplete) == 1:
            run_number, problems = incomplete[0]
            print(
                f"warning: skipped run {run_number}: missing or duplicate "
                f"flux ({', '.join(problems)}); complete POL1/POL2 "
                "pair required",
                file=sys.stderr,
            )
        else:
            examples = "; ".join(
                f"run {run}: {', '.join(problems)}"
                for run, problems in incomplete[:10]
            )
            print(
                f"warning: skipped {len(incomplete)} runs without complete "
                f"POL1/POL2 pair; first: {examples}",
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
            "non-positive POL1/POL2 flux",
            file=sys.stderr,
        )
    if skipped_polarization_domain:
        print(
            f"warning: skipped {skipped_polarization_domain} run/strip exposures "
            "outside polarization domain",
            file=sys.stderr,
        )
    if not exposures and not allow_empty:
        raise ValueError(
            f"no complete {target}/{beam_type} exposures in energy range"
        )
    return exposures


def _brem_value(value):
    """Keep absent/defective BREM distinct from an actual measured zero."""
    if value is None or value == "":
        return None, "missing"
    try:
        flux = float(value)
    except (ValueError, TypeError):
        return None, "invalid_content"
    if not math.isfinite(flux) or flux < 0.0:
        return None, "invalid_content"
    return flux, "measured_valid"


def _brem_counts(values):
    return {status: sum(item.brem_status == status for item in values)
            for status in sorted({item.brem_status for item in values})}


def _histogram_state(keys):
    """Validate each measured state independently, retaining valid content bins."""
    if len(keys) != 1:
        return None, dict(status="missing" if not keys else "duplicate")
    histogram = keys[0].ReadObj()
    if (not histogram.InheritsFrom("TH1") or histogram.GetDimension() != 1
            or histogram.GetNbinsX() != 128):
        return None, dict(status="invalid_histogram")
    axis = histogram.GetXaxis()
    edges = [float(axis.GetBinLowEdge(index)) for index in range(1, 130)]
    if (not all(math.isfinite(edge) and edge > 0.0 for edge in edges)
            or any(right <= left for left, right in zip(edges, edges[1:]))):
        return None, dict(status="invalid_axis")
    invalid_bins = [index for index in range(1, 129)
                    if _brem_value(histogram.GetBinContent(index))[1] != "measured_valid"]
    return histogram, dict(status="invalid_content" if invalid_bins else "measured_valid",
                           invalid_bins=invalid_bins)
