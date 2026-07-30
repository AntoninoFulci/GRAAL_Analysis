#!/usr/bin/env python3
"""Read inclusive h80 energies and tagger-flux ROOT histograms."""
from __future__ import annotations

from math import isfinite
from pathlib import Path
import re
from typing import Sequence

from graal_common.strip_energy_flux import (
    EnergySample,
    StripEnergyFluxError,
    StripFlux,
)


_FLUX_NAME = re.compile(r"^run([0-9]+)_(POL1|POL2|BREM)$")
_FLUX_SUFFIXES = ("POL1", "POL2", "BREM")


def _import_root():
    try:
        import ROOT
    except ImportError as exc:
        raise StripEnergyFluxError("ROOT is required to read ROOT inputs") from exc
    return ROOT


def _open_root_file(path: Path):
    root = _import_root()
    try:
        source = root.TFile.Open(str(path), "READ")
    except OSError as exc:
        raise StripEnergyFluxError(f"zombie ROOT file: {path}") from exc
    if not source:
        raise StripEnergyFluxError(f"zombie ROOT file: {path}")
    if source.IsZombie():
        try:
            source.Close()
        except Exception:
            pass
        raise StripEnergyFluxError(f"zombie ROOT file: {path}")
    return source


def read_h80_samples(preanalysis_dir: Path) -> tuple[list[EnergySample], dict[str, object]]:
    """Read the required h80 branches from every ROOT file below a directory."""
    preanalysis_dir = Path(preanalysis_dir)
    if not preanalysis_dir.is_dir():
        raise StripEnergyFluxError(f"preanalysis directory not found: {preanalysis_dir}")
    paths = sorted(path for path in preanalysis_dir.rglob("*.root") if path.is_file())
    if not paths:
        raise StripEnergyFluxError(f"no ROOT files below: {preanalysis_dir}")

    samples: list[EnergySample] = []
    for path in paths:
        source = _open_root_file(path)
        try:
            tree = source.Get("h80")
            if not tree:
                raise StripEnergyFluxError(f"{path}: missing h80 tree")
            if not tree.InheritsFrom("TTree"):
                raise StripEnergyFluxError(f"{path}: h80 is not a TTree")
            for branch in ("RunNumber", "Xstrip", "beam"):
                if not tree.GetBranch(branch):
                    raise StripEnergyFluxError(f"{path}: missing branch {branch}")

            tree.SetBranchStatus("*", 0)
            for branch in ("RunNumber", "Xstrip", "beam"):
                tree.SetBranchStatus(branch, 1)
            for entry in tree:
                samples.append(
                    EnergySample(
                        int(entry.RunNumber),
                        float(entry.Xstrip),
                        float(entry.beam.E()),
                    )
                )
        finally:
            source.Close()

    return samples, {"entries": len(samples), "file_count": len(paths)}


def _triplet_qa(
    objects: dict[int, dict[str, list[object]]], requested_runs: set[int]
) -> dict[str, object]:
    complete_runs = {
        run
        for run, suffixes in objects.items()
        if all(
            len(suffixes.get(suffix, [])) == 1
            and suffixes[suffix][0].GetName() == f"run{run}_{suffix}"
            for suffix in _FLUX_SUFFIXES
        )
    }
    malformed = []
    matching_keys = []
    for run, suffixes in sorted(objects.items()):
        for suffix, keys in suffixes.items():
            matching_keys.extend(
                {
                    "name": key.GetName(),
                    "cycle": int(key.GetCycle()),
                    "run_number": run,
                    "suffix": suffix,
                }
                for key in keys
            )
        missing = [suffix for suffix in _FLUX_SUFFIXES if suffix not in suffixes]
        aliases = sorted(
            key.GetName()
            for suffix, keys in suffixes.items()
            for key in keys
            if key.GetName() != f"run{run}_{suffix}"
        )
        duplicates = {
            suffix: len(keys) for suffix, keys in suffixes.items() if len(keys) != 1
        }
        if missing or aliases or duplicates:
            problem = {
                "run_number": run,
                "missing": missing,
                "present": [
                    suffix for suffix in _FLUX_SUFFIXES if suffix in suffixes
                ],
            }
            if aliases:
                problem["noncanonical"] = aliases
            if duplicates:
                problem["key_counts"] = duplicates
            malformed.append(problem)
    return {
        "run_count": len(requested_runs),
        "extra_runs": sorted(complete_runs - requested_runs),
        "malformed_triplets": malformed,
        "matching_keys": sorted(
            matching_keys,
            key=lambda item: (
                item["run_number"],
                item["suffix"],
                item["name"],
                item["cycle"],
            ),
        ),
        "underflow_overflow": [],
    }


def _required_histogram(key, run: int, suffix: str):
    name = f"run{run}_{suffix}"
    histogram = key.ReadObj()
    if not histogram:
        raise StripEnergyFluxError(f"missing required flux histogram: {name}")
    if not histogram.InheritsFrom("TH1"):
        raise StripEnergyFluxError(f"{name} is not a TH1 histogram")
    if histogram.GetDimension() != 1:
        raise StripEnergyFluxError(f"{name} is not one-dimensional")
    if histogram.GetNbinsX() != 128:
        raise StripEnergyFluxError(f"{name} must have 128 bins")

    axis = histogram.GetXaxis()
    for edge_index in range(129):
        edge = (
            axis.GetBinLowEdge(edge_index + 1)
            if edge_index < 128
            else axis.GetBinUpEdge(128)
        )
        if not isfinite(float(edge)):
            raise StripEnergyFluxError(
                f"{name} x-axis edge {edge_index} is not finite"
            )
        if abs(edge - edge_index) > 1e-6:
            raise StripEnergyFluxError(
                f"{name} x-axis edge {edge_index} must be {edge_index}"
            )
    for bin_number in range(130):
        if not isfinite(float(histogram.GetBinContent(bin_number))):
            raise StripEnergyFluxError(f"{name} bin {bin_number} is not finite")
    return histogram


def read_flux_histograms(
    path: Path, run_numbers: Sequence[int]
) -> tuple[list[StripFlux], dict[str, object]]:
    """Read one validated POL1/POL2/BREM triplet per requested run."""
    path = Path(path)
    requested_runs = set(run_numbers)
    source = _open_root_file(path)
    try:
        objects: dict[int, dict[str, list[object]]] = {}
        for key in source.GetListOfKeys():
            match = _FLUX_NAME.fullmatch(key.GetName())
            if match:
                run, suffix = match.groups()
                objects.setdefault(int(run), {}).setdefault(suffix, []).append(key)
        qa = _triplet_qa(objects, requested_runs)

        strips: list[StripFlux] = []
        for run in sorted(requested_runs):
            suffixes = objects.get(run, {})
            if not suffixes:
                raise StripEnergyFluxError(f"requested flux run {run} is absent")
            histograms = {}
            for suffix in _FLUX_SUFFIXES:
                name = f"run{run}_{suffix}"
                keys = suffixes.get(suffix, [])
                aliases = [key.GetName() for key in keys if key.GetName() != name]
                if aliases:
                    raise StripEnergyFluxError(
                        f"noncanonical flux histogram name: {aliases[0]} "
                        f"(expected {name})"
                    )
                if len(keys) != 1:
                    raise StripEnergyFluxError(
                        f"{name} must have exactly one ROOT key "
                        f"(found {len(keys)})"
                    )
                histograms[suffix] = _required_histogram(keys[0], run, suffix)
            for suffix, histogram in histograms.items():
                underflow = float(histogram.GetBinContent(0))
                overflow = float(histogram.GetBinContent(129))
                if underflow != 0.0 or overflow != 0.0:
                    qa["underflow_overflow"].append(
                        {
                            "histogram": f"run{run}_{suffix}",
                            "underflow": underflow,
                            "overflow": overflow,
                        }
                    )
            for strip in range(1, 129):
                strips.append(
                    StripFlux(
                        run,
                        strip,
                        float(histograms["POL1"].GetBinContent(strip)),
                        float(histograms["BREM"].GetBinContent(strip)),
                        float(histograms["POL2"].GetBinContent(strip)),
                    )
                )
    finally:
        source.Close()

    return strips, qa
