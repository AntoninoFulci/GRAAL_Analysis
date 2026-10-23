"""Fit strip-to-energy calibration and publish ROOT flux histograms."""
from __future__ import annotations

from array import array
from collections import defaultdict
from math import isfinite, sqrt
import os
from pathlib import Path
import tempfile
from typing import Callable, Sequence

from calibration.strip_energy_flux import CalibrationCell, CalibrationEnergyBin, StripEnergyFluxError
from calibration.strip_energy_root import _FLUX_NAME, _import_root, _open_root_file, _required_histogram

_CALIBRATION_ENERGY_BINS = 2048
_CALIBRATION_ENERGY_LOW_GEV = 0.5
_CALIBRATION_ENERGY_HIGH_GEV = 2.0


_POLARIZATION_SUFFIX = {0: "BREM", 1: "POL1", 2: "POL2"}


def has_full_calibration_span(cells: Sequence[CalibrationCell]) -> bool:
    strips = {cell.xstrip for cell in cells}
    return 1 in strips and 128 in strips



def minimum_pol4_derivative(fit, low: float, high: float) -> float:
    """Return exact minimum derivative using all stationary points of f'."""
    p2 = float(fit.GetParameter(2))
    p3 = float(fit.GetParameter(3))
    p4 = float(fit.GetParameter(4))
    a = 12.0 * p4
    b = 6.0 * p3
    c = 2.0 * p2
    candidates = [float(low), float(high)]
    scale = max(abs(a), abs(b), abs(c), 1.0)
    tolerance = 1.0e-14 * scale
    if abs(a) <= tolerance:
        if abs(b) > tolerance:
            root = -c / b
            if low <= root <= high:
                candidates.append(root)
    else:
        discriminant = b * b - 4.0 * a * c
        if discriminant >= 0.0:
            root_delta = sqrt(discriminant)
            for root in ((-b - root_delta) / (2.0 * a),
                         (-b + root_delta) / (2.0 * a)):
                if low <= root <= high:
                    candidates.append(root)
    return min(float(fit.Derivative(xstrip)) for xstrip in candidates)



def _fit_calibration_group(root, run: int, suffix: str, cells, energy_bins):
    """Create calibration diagnostics and a quartic strip-to-energy fit."""
    object_prefix = f"run{run}_{suffix}"
    histogram = root.TH2D(
        f"{object_prefix}_h2",
        f"{object_prefix};Xstrip;E_{{#gamma}} [GeV]",
        128,
        0.5,
        128.5,
        _CALIBRATION_ENERGY_BINS,
        _CALIBRATION_ENERGY_LOW_GEV,
        _CALIBRATION_ENERGY_HIGH_GEV,
    )
    histogram.SetDirectory(0)
    profile = root.TProfile(
        f"{object_prefix}_profile",
        f"{object_prefix};Xstrip;#LT E_{{#gamma}} #GT [GeV]",
        128,
        0.5,
        128.5,
    )
    profile.SetDirectory(0)
    for item in energy_bins:
        histogram.SetBinContent(
            item.xstrip,
            item.energy_bin,
            float(item.event_count),
        )
    for cell in cells:
        weight = float(cell.event_count)
        profile.Fill(float(cell.xstrip), cell.energy_mean_gev, weight)

    fit = root.TF1(f"{object_prefix}_fit", "pol4", 0.5, 128.5)
    fit_result = profile.Fit(fit, "QSWN")
    if int(fit_result) != 0:
        raise StripEnergyFluxError(
            f"{object_prefix}: quartic calibration fit failed with status "
            f"{int(fit_result)}"
        )
    minimum_derivative = minimum_pol4_derivative(fit, 0.5, 128.5)
    if not isfinite(minimum_derivative) or minimum_derivative <= 0.0:
        raise StripEnergyFluxError(
            f"{object_prefix}: fitted energy is not strictly increasing"
        )
    edges = tuple(float(fit.Eval(0.5 + index)) for index in range(129))
    if not all(isfinite(edge) for edge in edges):
        raise StripEnergyFluxError(
            f"{object_prefix}: fitted energy edges must be finite"
        )
    if not all(left < right for left, right in zip(edges, edges[1:])):
        raise StripEnergyFluxError(
            f"{object_prefix}: fitted energy edges must be strictly increasing"
        )
    return histogram, profile, fit, edges



def write_calibrated_flux_root(
    input_path: Path,
    output_path: Path,
    cells: Sequence[CalibrationCell],
    energy_bins: Sequence[CalibrationEnergyBin],
) -> dict[str, object]:
    """Write canonical flux histograms on fitted E_gamma axes plus fit QA."""
    root = _import_root()
    grouped = defaultdict(list)
    for cell in cells:
        grouped[(cell.run_number, cell.polarization)].append(cell)
    distributions = defaultdict(list)
    for item in energy_bins:
        distributions[(item.run_number, item.polarization)].append(item)

    models = {}
    insufficient_coverage = []
    calibration_coverage = []
    for (run, polarization), group in sorted(grouped.items()):
        distinct_strips = {cell.xstrip for cell in group}
        accepted = len(distinct_strips) >= 5 and has_full_calibration_span(group)
        coverage = {
            "run_number": run,
            "polarization": polarization,
            "observed_strip_count": len(distinct_strips),
            "first_strip": min(distinct_strips),
            "last_strip": max(distinct_strips),
            "missing_strips": sorted(set(range(1, 129)) - distinct_strips),
            "accepted": accepted,
        }
        calibration_coverage.append(coverage)
        if not accepted:
            insufficient_coverage.append(coverage)
            continue
        suffix = _POLARIZATION_SUFFIX[polarization]
        models[(run, suffix)] = _fit_calibration_group(
            root,
            run,
            suffix,
            sorted(group, key=lambda cell: cell.xstrip),
            distributions[(run, polarization)],
        )

    source = _open_root_file(input_path)
    output = root.TFile.Open(str(output_path), "RECREATE")
    if not output or output.IsZombie():
        source.Close()
        raise StripEnergyFluxError(
            f"cannot create calibrated ROOT file: {output_path}"
        )
    written = []
    skipped_without_calibration = []
    ignored_calcerr = []
    try:
        calibration_dir = output.mkdir("calibration")
        for key in source.GetListOfKeys():
            name = key.GetName()
            if "calcerr" in name:
                ignored_calcerr.append(name)
                continue
            match = _FLUX_NAME.fullmatch(name)
            if not match:
                continue
            run_text, suffix = match.groups()
            run = int(run_text)
            model = models.get((run, suffix))
            if model is None:
                skipped_without_calibration.append(name)
                continue
            calibration, profile, fit, edges = model
            source_histogram = _required_histogram(key, run, suffix)
            output.cd()
            calibrated = root.TH1D(
                name,
                source_histogram.GetTitle(),
                128,
                array("d", edges),
            )
            calibrated.GetXaxis().SetTitle("E_{#gamma} [GeV]")
            calibrated.GetYaxis().SetTitle(source_histogram.GetYaxis().GetTitle())
            calibrated.Sumw2()
            for bin_number in range(130):
                calibrated.SetBinContent(
                    bin_number,
                    max(0.0, float(source_histogram.GetBinContent(bin_number))),
                )
                calibrated.SetBinError(
                    bin_number,
                    float(source_histogram.GetBinError(bin_number)),
                )
            calibrated.SetEntries(source_histogram.GetEntries())
            calibrated.Write()
            written.append(name)

        calibration_dir.cd()
        for calibration, profile, fit, unused_edges in models.values():
            calibration.Write()
            profile.Write()
            fit.Write()
    finally:
        output.Close()
        source.Close()
    if not written:
        raise StripEnergyFluxError("no flux histogram had a matching calibration")
    return {
        "written_histograms": len(written),
        "calibration_groups": len(models),
        "ignored_calcerr": sorted(ignored_calcerr),
        "skipped_without_calibration": sorted(skipped_without_calibration),
        "calibration_coverage": calibration_coverage,
        "insufficient_coverage": insufficient_coverage,
        "fit_model": "pol4",
    }



def _write_calibrated_flux_root_atomic(
    input_path: Path,
    output_path: Path,
    calibration_cells,
    calibration_energy_bins,
    *,
    before_publish: Callable[[], None] | None = None,
):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output_path.name}.",
        suffix=".tmp",
        dir=output_path.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        qa = write_calibrated_flux_root(
            input_path,
            temporary,
            calibration_cells,
            calibration_energy_bins,
        )
        if before_publish is not None:
            before_publish()
        temporary.replace(output_path)
        return qa
    finally:
        temporary.unlink(missing_ok=True)
