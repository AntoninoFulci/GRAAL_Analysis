"""Read reconstructed ROOT trees into detached NumPy arrays."""

from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Mapping

import numpy as np
import ROOT
from calibration.run_quality import excluded_run_numbers
from observable_extraction.core.models import FluxExposure
from reconstruction.runtime.provenance import validate_no_fit


def read_run_universe(path: Path, *, allow_missing: bool = False):
    """Read inclusive run identities before reconstruction cuts, never from filenames."""
    source = ROOT.TFile.Open(str(path), "READ")
    if not source or source.IsZombie():
        raise RuntimeError(f"cannot open reconstructed ROOT file: {path}")
    try:
        record = source.Get("reconstruction_provenance")
        metadata = json.loads(record.GetTitle()) if record else {}
        rows = metadata.get("counts_by_run_state")
        if rows is None and allow_missing:
            return None, []
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"{path}: inclusive cutflow missing; supply --run-universe-manifest")
        keys = set()
        for row in rows:
            run, state = row.get("run"), row.get("polarization")
            if (type(run) is not int or run <= 0 or type(state) is not int
                    or type(row.get("input")) is not int or row["input"] < 0
                    or (run, state) in keys):
                raise ValueError(f"{path}: invalid or duplicate run/state cutflow")
            keys.add((run, state))
        return {run for run, _ in keys}, rows
    finally:
        source.Close()


def _vector(value) -> np.ndarray:
    return np.array(
        [value.Px(), value.Py(), value.Pz(), value.E()], dtype=np.float64
    )


def _mass(vector: np.ndarray) -> float:
    mass_squared = vector[3] ** 2 - float(np.dot(vector[:3], vector[:3]))
    return float(np.sqrt(max(mass_squared, 0.0)))


@dataclass(frozen=True)
class EventArrays:
    run_number: np.ndarray
    xstrip: np.ndarray
    polarization: np.ndarray
    beam_energy_gev: np.ndarray
    eta: np.ndarray
    pi0: np.ndarray
    proton: np.ndarray
    missing_mass_gev: np.ndarray
    eta_mass_gev: np.ndarray
    pi0_mass_gev: np.ndarray
    bdt_score: np.ndarray
    n_photons_input: np.ndarray

    def __len__(self) -> int:
        return len(self.run_number)

    def take(self, selection: np.ndarray) -> "EventArrays":
        selection = np.asarray(selection)
        if selection.shape != (len(self),):
            raise ValueError("selection shape does not match events")
        return EventArrays(
            **{field.name: getattr(self, field.name)[selection] for field in fields(self)}
        )


def read_reconstructed(
    path: Path,
    tree_name: str,
    *,
    vector_mode: str,
    require_no_fit: bool = False,
) -> EventArrays:
    if vector_mode not in {"raw", "fit"}:
        raise ValueError("vector_mode must be 'raw' or 'fit'")
    path = Path(path)
    source = ROOT.TFile.Open(str(path), "READ")
    if not source or source.IsZombie():
        raise RuntimeError(f"cannot open reconstructed ROOT file: {path}")
    try:
        tree = source.Get(tree_name)
        if not tree or not tree.InheritsFrom("TTree"):
            raise RuntimeError(f"missing TTree {tree_name!r} in {path}")
        if require_no_fit:
            if vector_mode != "raw":
                raise ValueError("no-fit baseline requires raw vectors")
            validate_no_fit(source, tree)
        branches = {branch.GetName() for branch in tree.GetListOfBranches()}
        required = {
            "RunNumber", "Xstrip", "Polarization", "beam", "eta", "pi0",
            "proton", "missing", "eta_mass", "pi0_mass", "n_photons_input",
        }
        if vector_mode == "fit":
            required.update({"eta_fit", "pi0_fit", "proton_fit"})
        missing = sorted(required - branches)
        if missing:
            raise RuntimeError(f"{path}:{tree_name}: missing branches {missing}")

        values: dict[str, list] = {
            name: []
            for name in (
                "run_number", "xstrip", "polarization", "beam_energy_gev",
                "eta", "pi0", "proton", "missing_mass_gev", "eta_mass_gev",
                "pi0_mass_gev", "bdt_score", "n_photons_input",
            )
        }
        for event in tree:
            beam = _vector(event.beam)
            eta = _vector(event.eta_fit if vector_mode == "fit" else event.eta)
            pi0 = _vector(event.pi0_fit if vector_mode == "fit" else event.pi0)
            proton = _vector(
                event.proton_fit if vector_mode == "fit" else event.proton
            )
            raw_missing = _vector(event.missing)
            values["run_number"].append(int(event.RunNumber))
            values["xstrip"].append(int(float(event.Xstrip)))
            values["polarization"].append(int(event.Polarization))
            values["beam_energy_gev"].append(float(beam[3]))
            values["eta"].append(eta)
            values["pi0"].append(pi0)
            values["proton"].append(proton)
            values["missing_mass_gev"].append(_mass(raw_missing))
            values["eta_mass_gev"].append(float(event.eta_mass))
            values["pi0_mass_gev"].append(float(event.pi0_mass))
            values["bdt_score"].append(
                float(event.bdt_score) if "bdt_score" in branches else np.nan
            )
            values["n_photons_input"].append(int(event.n_photons_input))
    finally:
        source.Close()

    scalar_int = {"run_number", "xstrip", "polarization", "n_photons_input"}
    arrays = {
        name: np.asarray(items, dtype=np.int64 if name in scalar_int else np.float64)
        for name, items in values.items()
    }
    for name in ("eta", "pi0", "proton"):
        arrays[name] = np.asarray(values[name], dtype=np.float64).reshape(-1, 4)
    return EventArrays(**arrays)


def _select_by_polarization(
    events: EventArrays,
    exposures: Mapping[tuple[int, int], FluxExposure],
    accepted_polarizations: tuple[int, ...],
    *,
    energy_range: tuple[float, float],
    drop_missing: bool = False,
    audit: dict | None = None,
) -> EventArrays:
    low, high = energy_range
    if not np.isfinite((low, high)).all() or high <= low:
        raise ValueError("energy range must be finite and increasing")
    base = (
        ~np.isin(events.run_number, sorted(excluded_run_numbers()))
        & np.isin(events.polarization, accepted_polarizations)
        & (events.beam_energy_gev >= low)
        & (events.beam_energy_gev <= high)
    )
    missing = sorted(
        {
            (int(run), int(strip))
            for run, strip in zip(events.run_number[base], events.xstrip[base])
            if (int(run), int(strip)) not in exposures
        }
    )
    if audit is not None:
        missing_counts = Counter(
            (int(run), int(strip))
            for run, strip in zip(events.run_number[base], events.xstrip[base])
            if (int(run), int(strip)) not in exposures
        )
        eligible = int(np.count_nonzero(base))
        lost = sum(missing_counts.values())
        audit.update(
            input_events=len(events),
            eligible_events=eligible,
            rejected_before_exposure=len(events) - eligible,
            missing_exposure_events=lost,
            missing_exposure_strata=[
                {"run": run, "strip": strip, "events": count}
                for (run, strip), count in sorted(missing_counts.items())
            ],
            selected_events=eligible - lost,
        )
    if missing:
        if drop_missing:
            has_exposure = np.array(
                [
                    (int(run), int(strip)) in exposures
                    for run, strip in zip(events.run_number, events.xstrip)
                ],
                dtype=bool,
            )
            dropped = int(np.count_nonzero(base & ~has_exposure))
            noun = "event" if dropped == 1 else "events"
            print(
                f"warning: dropped {dropped} {noun} across {len(missing)} "
                "run/strip without valid flux exposure",
                file=sys.stderr,
            )
            return events.take(base & has_exposure)
        raise ValueError(f"missing exposure for selected run/strip: {missing}")
    return events.take(base)


def select_sigma_events(
    events: EventArrays,
    exposures: Mapping[tuple[int, int], FluxExposure],
    *,
    energy_range: tuple[float, float] = (1.1, 1.5),
    drop_missing: bool = False,
    audit: dict | None = None,
) -> EventArrays:
    return _select_by_polarization(
        events,
        exposures,
        (1, 2),
        energy_range=energy_range,
        drop_missing=drop_missing,
        audit=audit,
    )


def select_brem_control(
    events: EventArrays,
    exposures: Mapping[tuple[int, int], FluxExposure],
    *,
    energy_range: tuple[float, float] = (1.1, 1.5),
    drop_missing: bool = False,
) -> EventArrays:
    return _select_by_polarization(
        events,
        exposures,
        (0,),
        energy_range=energy_range,
        drop_missing=drop_missing,
    )
