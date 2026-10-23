"""ROOT input adapters and installed RDataFrame resource loading."""
from __future__ import annotations

from datetime import datetime
from importlib.resources import files
from math import isfinite
from pathlib import Path
import re
import sys
import time
from typing import Sequence

from calibration.strip_energy_flux import (
    CalibrationCell, CalibrationEnergyBin, StripEnergyRecord,
    StripEnergyFluxError, StripFlux,
)

_FLUX_NAME = re.compile(r"^run([0-9]+)_(POL1|POL2|BREM)$")
_FLUX_SUFFIXES = ("POL1", "POL2", "BREM")


def _declare_rdataframe_helpers(root) -> None:
    # Cling, unlike a Python module, lives for the process. Its namespace survives
    # module reloads and imports under aliases, so it is the declaration authority.
    if hasattr(root, "GraalStripEnergyRDF"):
        return
    code = files("calibration").joinpath("native/strip_energy_rdf.hxx").read_text()
    if not root.gInterpreter.Declare(code):
        raise StripEnergyFluxError("cannot compile RDataFrame strip-energy helpers")


class ProgressReporter:
    """Timestamped, flushed progress messages for long ROOT scans."""

    def __init__(self) -> None:
        self._started = time.monotonic()

    def log(self, message: str) -> None:
        timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
        elapsed = time.monotonic() - self._started
        print(
            f"[{timestamp}] [+{elapsed:,.1f}s] {message}",
            file=sys.stderr,
            flush=True,
        )

    @property
    def elapsed_seconds(self) -> float:
        return time.monotonic() - self._started



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



def _configure_implicit_mt(root, threads: int) -> None:
    if threads < 1:
        raise StripEnergyFluxError("threads must be at least 1")
    if root.IsImplicitMTEnabled():
        root.DisableImplicitMT()
    if threads > 1:
        root.EnableImplicitMT(threads)



def _validated_h80_paths(preanalysis_dir: Path) -> list[Path]:
    preanalysis_dir = Path(preanalysis_dir)
    if not preanalysis_dir.is_dir():
        raise StripEnergyFluxError(f"preanalysis directory not found: {preanalysis_dir}")
    paths = sorted(path for path in preanalysis_dir.rglob("*.root") if path.is_file())
    if not paths:
        raise StripEnergyFluxError(f"no ROOT files below: {preanalysis_dir}")
    for path in paths:
        source = _open_root_file(path)
        try:
            tree = source.Get("h80")
            if not tree:
                raise StripEnergyFluxError(f"{path}: missing h80 tree")
            if not tree.InheritsFrom("TTree"):
                raise StripEnergyFluxError(f"{path}: h80 is not a TTree")
            for branch_name in ("RunNumber", "Xstrip", "beam"):
                if not tree.GetBranch(branch_name):
                    raise StripEnergyFluxError(f"{path}: missing branch {branch_name}")
            if not tree.GetBranch("beam").GetClassName():
                raise StripEnergyFluxError(
                    f"{path}: h80 entry 0: "
                    "cannot convert RunNumber/Xstrip/beam.E()"
                )
        finally:
            source.Close()
    return paths



def _root_string_vector(root, values: Sequence[Path]):
    result = root.std.vector("string")()
    for value in values:
        result.push_back(str(value))
    return result



def _root_int_vector(root, values: Sequence[int]):
    result = root.std.vector("int")()
    for value in values:
        result.push_back(int(value))
    return result



def read_h80_lookup(
    preanalysis_dir: Path,
    *,
    run_numbers: Sequence[int],
    samples_per_run_strip: int,
    threads: int,
    progress: ProgressReporter | None = None,
    progress_every_events: int = 1_000_000,
) -> tuple[tuple[StripEnergyRecord, ...], dict[str, object]]:
    """Build sampled run/strip energy statistics in one RDataFrame scan."""
    if progress_every_events < 0:
        raise StripEnergyFluxError("progress-every-events must be nonnegative")
    if samples_per_run_strip < 1:
        raise StripEnergyFluxError("samples-per-run-strip must be at least 1")
    ordered_runs = sorted(set(int(run) for run in run_numbers))
    if not ordered_runs:
        raise StripEnergyFluxError("run number list is empty")
    root = _import_root()
    _configure_implicit_mt(root, threads)
    _declare_rdataframe_helpers(root)
    paths = _validated_h80_paths(preanalysis_dir)
    if progress is not None:
        progress.log(f"h80 files discovered: {len(paths)}")
        progress.log(f"RDataFrame implicit multithreading: {threads} threads")
        for file_index, path in enumerate(paths, start=1):
            progress.log(
                f"h80 file {file_index}/{len(paths)}: {path} (validated)"
            )
        progress.log(
            "starting single h80 event loop; "
            f"sample capacity: {samples_per_run_strip} per run/strip"
        )
    try:
        result = root.GraalStripEnergyRDF.BuildSampledLookup(
            _root_string_vector(root, paths),
            _root_int_vector(root, ordered_runs),
            samples_per_run_strip,
            progress_every_events,
            progress.elapsed_seconds if progress is not None else 0.0,
        )
    except Exception as exc:
        raise StripEnergyFluxError(
            f"RDataFrame strip-energy build failed: {exc}"
        ) from exc

    lookup = tuple(
        StripEnergyRecord(
            int(summary.run_number),
            int(summary.xstrip),
            int(summary.event_count),
            float(summary.energy_median_gev),
            float(summary.energy_mad_gev),
            float(summary.energy_min_gev),
            float(summary.energy_max_gev),
            "sampled",
        )
        for summary in result.summaries
    )
    qa = {
        "entries": int(result.entries),
        "file_count": len(paths),
        "sample_capacity": samples_per_run_strip,
        "sampled_entries": int(result.sampled_entries),
        "fractional_xstrip_entries": int(result.fractional_xstrip_entries),
        "invalid_xstrip_entries": int(result.invalid_xstrip_entries),
        "extra_runs": [int(run) for run in result.extra_runs],
    }
    return lookup, qa



def read_calibration_cells(
    preanalysis_dir: Path,
    *,
    run_numbers: Sequence[int],
    threads: int,
) -> tuple[tuple[CalibrationCell, ...], tuple[CalibrationEnergyBin, ...]]:
    """Average Xstrip and beam energy for every run/polarization/strip cell."""
    ordered_runs = sorted(set(int(run) for run in run_numbers))
    if not ordered_runs:
        raise StripEnergyFluxError("run number list is empty")
    root = _import_root()
    _configure_implicit_mt(root, threads)
    _declare_rdataframe_helpers(root)
    paths = _validated_h80_paths(preanalysis_dir)
    for path in paths:
        source = _open_root_file(path)
        try:
            tree = source.Get("h80")
            if not tree.GetBranch("Polarization"):
                raise StripEnergyFluxError(f"{path}: missing branch Polarization")
        finally:
            source.Close()
    try:
        result = root.GraalStripEnergyRDF.BuildCalibrationCells(
            _root_string_vector(root, paths),
            _root_int_vector(root, ordered_runs),
        )
    except Exception as exc:
        raise StripEnergyFluxError(
            f"RDataFrame polarization calibration build failed: {exc}"
        ) from exc
    cells = tuple(
        CalibrationCell(
            int(cell.run_number),
            int(cell.polarization),
            int(cell.xstrip),
            int(cell.event_count),
            float(cell.xstrip_mean),
            float(cell.energy_mean_gev),
        )
        for cell in result.cells
    )
    energy_bins = tuple(
        CalibrationEnergyBin(
            int(item.run_number),
            int(item.polarization),
            int(item.xstrip),
            int(item.energy_bin),
            int(item.event_count),
        )
        for item in result.energy_bins
    )
    return cells, energy_bins



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
    path: Path,
    run_numbers: Sequence[int],
    *,
    progress: ProgressReporter | None = None,
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
        sorted_runs = sorted(requested_runs)
        for run_index, run in enumerate(sorted_runs, start=1):
            if progress is not None:
                progress.log(f"flux run {run_index}/{len(sorted_runs)}: {run}")
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
                        float(histograms["POL2"].GetBinContent(strip)),
                        float(histograms["BREM"].GetBinContent(strip)),
                    )
                )
    finally:
        source.Close()

    return strips, qa
