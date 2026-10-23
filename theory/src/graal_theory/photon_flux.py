"""Run-atomic calibrated UV flux, independent of the analysis stages."""

from __future__ import annotations

import csv
import hashlib
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
    source_fingerprint: str | None = None


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
    root_path: Path, manifest_path: Path, energy_range_gev: tuple[float, float],
    *, selected_run_numbers: frozenset[int] | None = None,
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
    if selected_run_numbers is not None and (
            not isinstance(selected_run_numbers, frozenset) or not selected_run_numbers
            or any(isinstance(run, bool) or not isinstance(run, int) or run <= 0
                   for run in selected_run_numbers)):
        raise ValueError("selected run numbers must be a nonempty frozenset of positive integers")
    selected: set[int] = set()
    with manifest_path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if row["target"] == "P" and row["beam_type"] == "UV":
                run = int(row["run_number"])
                if selected_run_numbers is not None and run not in selected_run_numbers:
                    continue
                if run in selected:
                    raise ValueError(f"duplicate selected run {run} in manifest")
                selected.add(run)
    if not selected:
        raise ValueError("manifest has no P/UV runs")
    if selected_run_numbers is not None and selected != selected_run_numbers:
        raise ValueError("selected reconstructed run missing from P/UV manifest")

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
            if any(len(run_keys.get(state, ())) > 1 for state in _REQUIRED):
                raise ValueError(f"duplicate ROOT cycles for selected run {run}")
            if any(len(run_keys.get(state, ())) != 1 for state in _REQUIRED):
                if selected_run_numbers is not None:
                    raise ValueError(f"selected run {run} has no complete POL1/POL2/BREM triplet")
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


def selected_uv_runs(reco_root: Path) -> frozenset[int]:
    """Read only run numbers from the nominal raw BDT reconstruction tree."""
    import uproot

    with uproot.open(reco_root) as source:
        if "reco_eta_pi0_bdt" not in source:
            raise ValueError("missing reco_eta_pi0_bdt tree")
        tree = source["reco_eta_pi0_bdt"]
        if "RunNumber" not in tree.keys():
            raise ValueError("missing RunNumber branch")
        values = tree["RunNumber"].array(library="np")
    if values.ndim != 1 or values.dtype.kind not in "iu" or not len(values) \
            or np.any(values <= 0):
        raise ValueError("RunNumber requires nonempty positive integer values")
    return frozenset(int(value) for value in np.unique(values))


def inclusive_uv_runs(reco_root: Path) -> frozenset[int]:
    """Run universe before reconstruction cuts, including zero-survivor runs."""
    import json
    import uproot
    with uproot.open(reco_root) as source:
        try:
            record=source['reconstruction_provenance']
            text=str(record) if record.classname=='TObjString' else record.member('fTitle')
            rows=json.loads(text).get('counts_by_run_state')
        except (KeyError,AttributeError,ValueError) as exc:
            raise ValueError('missing or invalid reconstruction cutflow') from exc
    if not isinstance(rows,list) or not rows:
        raise ValueError('inclusive reconstruction cutflow must be nonempty')
    keys=set()
    for row in rows:
        if not isinstance(row,dict):
            raise ValueError('invalid inclusive cutflow row')
        run,state,count=row.get('run'),row.get('polarization'),row.get('input')
        if (type(run) is not int or run<=0 or type(state) is not int
                or type(count) is not int or count<0 or (run,state) in keys):
            raise ValueError('invalid or duplicate inclusive cutflow row')
        keys.add((run,state))
    runs=frozenset(run for run,_ in keys)
    if not selected_uv_runs(reco_root)<=runs:
        raise ValueError('reconstructed events outside inclusive cutflow')
    return runs


def native_flux_spectrum(flux_root: Path, manifest: Path, reco_root: Path,
                         energy_range_gev: tuple[float, float], *,
                         use_inclusive_cutflow: bool = False) -> FluxSpectrum:
    """Match measured exposure to nominal reconstruction runs and inputs."""
    from dataclasses import replace
    import uproot

    if type(use_inclusive_cutflow) is not bool:
        raise ValueError("use_inclusive_cutflow must be boolean")
    reconstructed = inclusive_uv_runs(reco_root) if use_inclusive_cutflow else selected_uv_runs(reco_root)
    with Path(manifest).open(newline="", encoding="utf-8") as stream:
        manifest_runs = {int(row["run_number"]) for row in csv.DictReader(stream)
                         if row["target"] == "P" and row["beam_type"] == "UV"}
    with uproot.open(flux_root) as source:
        states: dict[int, dict[str, int]] = {}
        for name in source.keys(cycle=True, recursive=False):
            match = _RUN_HISTOGRAM.fullmatch(name.split(";", 1)[0])
            if match is not None and int(match[1]) in reconstructed:
                counts = states.setdefault(int(match[1]), {})
                counts[match[2]] = counts.get(match[2], 0) + 1
    # Stage 07 ignores incomplete/duplicate run triplets before selecting events.
    selected = frozenset(run for run in reconstructed & manifest_runs
                         if all(states.get(run, {}).get(state) == 1 for state in _REQUIRED))
    if not selected:
        raise ValueError("no complete reconstructed P/UV runs in calibrated flux")
    spectrum = load_calibrated_flux(flux_root, manifest, energy_range_gev,
                                    selected_run_numbers=selected)
    digest = hashlib.sha256()
    if use_inclusive_cutflow:
        digest.update(b"inclusive_reconstruction_cutflow")
    for label, path in (("reco", reco_root), ("flux", flux_root), ("manifest", manifest)):
        digest.update(label.encode("ascii"))
        with Path(path).open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024*1024), b""):
                digest.update(chunk)
    return replace(spectrum, source_fingerprint=digest.hexdigest())


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
