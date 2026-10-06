"""Run-atomic calibrated UV flux, independent of the analysis stages."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

import numpy as np

_RUN_HISTOGRAM = re.compile(r"run([1-9][0-9]*)_(POL1|POL2|BREM)")
_REQUIRED = frozenset(("POL1", "POL2", "BREM"))


@dataclass(frozen=True)
class PhotonExposure:
    energy_gev: float
    flux_vertical: float
    flux_horizontal: float
    polarization_vertical: float
    polarization_horizontal: float


@dataclass(frozen=True)
class FluxSpectrum:
    energy_range_gev: tuple[float, float]
    exposures: tuple[PhotonExposure, ...]
    selected_runs: int
    complete_runs: int
    skipped_nonpositive_strips: int
    root_path: Path
    manifest_path: Path


def _uv_polarization(energy_gev: float) -> float:
    """GRAAL UV Compton transfer; constants match 00_common/physics/compton.py."""
    electron_energy_mev = 6027.6
    electron_mass_mev = 0.51099895
    laser_energy_mev = 1.239841984e-3 / 351.0
    x = 4.0 * electron_energy_mev * laser_energy_mev / electron_mass_mev**2
    y = energy_gev * 1000.0 / electron_energy_mev
    if not 0.0 <= y <= x / (1.0 + x):
        raise ValueError("photon energy outside UV Compton range")
    r = y / (x * (1.0 - y))
    return 2.0 * r * r / (1.0 / (1.0 - y) + (1.0 - y) - 4.0 * r * (1.0 - r))


def load_calibrated_flux(
    root_path: Path, manifest_path: Path, energy_range_gev: tuple[float, float]
) -> FluxSpectrum:
    """Use only manifest P/UV runs with one POL1/POL2/BREM ROOT triplet."""
    try:
        import uproot
    except ImportError as exc:
        raise RuntimeError("calibrated ROOT flux requires uproot (install graal-theory[flux])") from exc

    root_path, manifest_path = Path(root_path), Path(manifest_path)
    low, high = energy_range_gev
    if not np.isfinite(low) or not np.isfinite(high) or high <= low:
        raise ValueError("energy range must be finite and increasing")
    selected: set[int] = set()
    with manifest_path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if row["target"] == "P" and row["beam_type"] == "UV":
                run = int(row["run_number"])
                if run in selected:
                    raise ValueError(f"duplicate selected run {run} in manifest")
                selected.add(run)
    if not selected:
        raise ValueError("manifest has no P/UV runs")

    exposures: list[PhotonExposure] = []
    complete_runs = 0
    skipped_nonpositive = 0
    with uproot.open(root_path) as source:
        keys: dict[int, dict[str, list[str]]] = {}
        for name in source.keys(cycle=True, recursive=False):
            bare = name.split(";", 1)[0]
            match = _RUN_HISTOGRAM.fullmatch(bare)
            if match is not None and int(match[1]) in selected:
                keys.setdefault(int(match[1]), {}).setdefault(match[2], []).append(name)
        for run in sorted(selected):
            run_keys = keys.get(run, {})
            if any(len(run_keys.get(state, ())) != 1 for state in _REQUIRED):
                continue
            complete_runs += 1
            histograms = {state: source[run_keys[state][0]] for state in _REQUIRED}
            for state, histogram in histograms.items():
                if not histogram.classname.startswith("TH1") or len(histogram.values()) != 128:
                    raise ValueError(f"run{run}_{state} must be a 128-bin TH1")
            v, h, b = (histograms[state] for state in ("POL1", "POL2", "BREM"))
            centers_v = v.axis().centers()
            centers_h = h.axis().centers()
            values_v, values_h, values_b = v.values(), h.values(), b.values()
            for index in range(128):
                energy_v, energy_h = float(centers_v[index]), float(centers_h[index])
                energy = 0.5 * (energy_v + energy_h)
                if not low <= energy < high:
                    continue
                flux_v, flux_h, flux_b = (float(values[index]) for values in (values_v, values_h, values_b))
                if not all(np.isfinite(value) for value in (energy_v, energy_h, flux_v, flux_h, flux_b)):
                    raise ValueError(f"nonfinite calibrated flux in run {run}, strip {index + 1}")
                if flux_v <= 0.0 or flux_h <= 0.0 or flux_b < 0.0:
                    skipped_nonpositive += 1
                    continue
                try:
                    pol_v, pol_h = _uv_polarization(energy_v), _uv_polarization(energy_h)
                except ValueError:
                    continue
                exposures.append(PhotonExposure(energy, flux_v, flux_h, pol_v, pol_h))
    if not exposures:
        raise ValueError("no complete P/UV exposures in energy range")
    return FluxSpectrum(
        (low, high), tuple(exposures), len(selected), complete_runs,
        skipped_nonpositive, root_path, manifest_path,
    )


def group_flux_by_energy(spectrum: FluxSpectrum, bins: int) -> tuple[PhotonExposure, ...]:
    """Piecewise-constant measured flux with a flux-centroid model energy."""
    if isinstance(bins, bool) or not isinstance(bins, int) or bins <= 0:
        raise ValueError("energy bins must be a positive integer")
    low, high = spectrum.energy_range_gev
    edges = np.linspace(low, high, bins + 1)
    grouped = []
    for left, right in pairwise(edges):
        items = [item for item in spectrum.exposures if left <= item.energy_gev < right]
        if not items:
            continue
        fv = sum(item.flux_vertical for item in items)
        fh = sum(item.flux_horizontal for item in items)
        grouped.append(PhotonExposure(
            sum(item.energy_gev * (item.flux_vertical + item.flux_horizontal) for item in items) / (fv + fh),
            fv, fh,
            sum(item.flux_vertical * item.polarization_vertical for item in items) / fv,
            sum(item.flux_horizontal * item.polarization_horizontal for item in items) / fh,
        ))
    return tuple(grouped)
