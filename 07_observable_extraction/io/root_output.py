"""ROOT-only public storage for beam-asymmetry results and diagnostics."""

from __future__ import annotations

from array import array
from dataclasses import dataclass
import math
import os
from pathlib import Path
import tempfile
from typing import Mapping, Sequence

import numpy as np
import ROOT

from observable_extraction.core.models import SigmaPoint


@dataclass(frozen=True)
class OutputPoint:
    sample: str
    estimator: str
    point: SigmaPoint
    sigma_uncorrected: float
    systematic_total: float
    background_fraction: float
    count_vertical: int
    count_horizontal: int
    flux_vertical: float
    flux_horizontal: float
    polarization_vertical: float
    polarization_horizontal: float


@dataclass(frozen=True)
class RatioObject:
    pair: str
    energy_bin: int
    mass_bin: int
    phi: np.ndarray
    value: np.ndarray
    error: np.ndarray
    sigma: float


@dataclass(frozen=True)
class RootOutputPayload:
    points: Sequence[OutputPoint]
    energy_edges: np.ndarray
    mass_edges: Mapping[str, np.ndarray]
    covariance_total: np.ndarray
    systematic_covariances: Mapping[str, np.ndarray]
    ratio_objects: Sequence[RatioObject]
    provenance: str
    statistical_covariance: np.ndarray | None = None
    bootstrap_covariance: np.ndarray | None = None


def _directory(root_file, path: str):
    current = root_file
    for part in path.split("/"):
        child = current.GetDirectory(part)
        current = child if child else current.mkdir(part)
    return current


def _write_vector(directory, name: str, values: np.ndarray) -> None:
    values = np.asarray(values, dtype=np.float64)
    vector = ROOT.TVectorD(len(values))
    for index, value in enumerate(values):
        vector[index] = float(value)
    directory.cd()
    vector.Write(name)


def _write_matrix(directory, name: str, values: np.ndarray) -> None:
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 2 or values.shape[0] != values.shape[1]:
        raise ValueError(f"matrix {name!r} must be square")
    size = values.shape[0]
    histogram = ROOT.TH2D(name, name, size, 0, size, size, 0, size)
    for row in range(size):
        for column in range(size):
            histogram.SetBinContent(row + 1, column + 1, float(values[row, column]))
    directory.cd()
    histogram.Write()


def _correlation(values: np.ndarray) -> np.ndarray:
    covariance = np.asarray(values, dtype=np.float64)
    scale = np.sqrt(np.clip(np.diag(covariance), 0.0, None))
    denominator = np.outer(scale, scale)
    return np.divide(
        covariance,
        denominator,
        out=np.zeros_like(covariance),
        where=denominator > 0.0,
    )


def _write_points(root_file, points: Sequence[OutputPoint]) -> None:
    tree = ROOT.TTree("sigma_points", "beam-asymmetry points")
    integer_names = (
        "sample_id", "estimator_id", "pair_id", "energy_bin", "mass_bin",
        "count_vertical", "count_horizontal", "fit_ndf", "fit_converged",
        "used_fallback",
    )
    float_names = (
        "energy_low_gev", "energy_high_gev", "mass_low_gev", "mass_high_gev",
        "mass_center_gev", "mass_mean_gev", "sigma_uncorrected", "sigma",
        "stat_low", "stat_high", "syst_total", "background_fraction",
        "flux_vertical", "flux_horizontal", "polarization_vertical",
        "polarization_horizontal", "fit_chi2", "fit_p_value", "c0", "s2",
    )
    integers = {name: array("i", [0]) for name in integer_names}
    floats = {name: array("d", [0.0]) for name in float_names}
    for name, value in integers.items():
        tree.Branch(name, value, f"{name}/I")
    for name, value in floats.items():
        tree.Branch(name, value, f"{name}/D")

    sample_ids = {name: index for index, name in enumerate(sorted({p.sample for p in points}))}
    estimator_ids = {
        name: index for index, name in enumerate(sorted({p.estimator for p in points}))
    }
    pair_ids = {"p_pi0": 0, "p_eta": 1, "eta_pi0": 2}
    for output in points:
        point = output.point
        diagnostics = point.diagnostics
        integer_values = {
            "sample_id": sample_ids[output.sample],
            "estimator_id": estimator_ids[output.estimator],
            "pair_id": pair_ids[point.pair],
            "energy_bin": point.energy_bin,
            "mass_bin": point.mass_bin,
            "count_vertical": output.count_vertical,
            "count_horizontal": output.count_horizontal,
            "fit_ndf": diagnostics.ndf,
            "fit_converged": int(diagnostics.converged),
            "used_fallback": int(diagnostics.used_fallback),
        }
        float_values = {
            "energy_low_gev": point.energy_low_gev,
            "energy_high_gev": point.energy_high_gev,
            "mass_low_gev": point.mass_low_gev,
            "mass_high_gev": point.mass_high_gev,
            "mass_center_gev": 0.5 * (point.mass_low_gev + point.mass_high_gev),
            "mass_mean_gev": point.mass_mean_gev,
            "sigma_uncorrected": output.sigma_uncorrected,
            "sigma": point.sigma,
            "stat_low": point.stat_low,
            "stat_high": point.stat_high,
            "syst_total": output.systematic_total,
            "background_fraction": output.background_fraction,
            "flux_vertical": output.flux_vertical,
            "flux_horizontal": output.flux_horizontal,
            "polarization_vertical": output.polarization_vertical,
            "polarization_horizontal": output.polarization_horizontal,
            "fit_chi2": diagnostics.chi2,
            "fit_p_value": diagnostics.p_value,
            "c0": diagnostics.c0 if diagnostics.c0 is not None else math.nan,
            "s2": diagnostics.s2 if diagnostics.s2 is not None else math.nan,
        }
        for name, value in integer_values.items():
            integers[name][0] = int(value)
        for name, value in float_values.items():
            floats[name][0] = float(value)
        tree.Fill()
    root_file.cd()
    tree.Write()
    mapping = "\n".join(
        [*(f"sample {value} {key}" for key, value in sample_ids.items()),
         *(f"estimator {value} {key}" for key, value in estimator_ids.items()),
         *(f"pair {value} {key}" for key, value in pair_ids.items())]
    )
    ROOT.TNamed("id_mapping", mapping).Write()


def _write_diagnostics(root_file, points: Sequence[OutputPoint]) -> None:
    directory = _directory(root_file, "diagnostics")
    likelihood = {
        (
            item.sample,
            item.point.pair,
            item.point.energy_bin,
            item.point.mass_bin,
        ): item
        for item in points
        if item.estimator == "likelihood"
    }
    pairs = []
    for item in points:
        if item.estimator != "ratio":
            continue
        key = (
            item.sample,
            item.point.pair,
            item.point.energy_bin,
            item.point.mass_bin,
        )
        counterpart = likelihood.get(key)
        if counterpart is not None:
            pairs.append((item, counterpart))
    graph = ROOT.TGraphErrors() if not pairs else ROOT.TGraphErrors(len(pairs))
    graph.SetName("ratio_vs_likelihood")
    graph.SetTitle("ratio versus conditional-likelihood Sigma")
    for index, (ratio, conditional) in enumerate(pairs):
        graph.SetPoint(index, ratio.point.sigma, conditional.point.sigma)
        graph.SetPointError(
            index,
            0.5 * (ratio.point.stat_low + ratio.point.stat_high),
            0.5 * (conditional.point.stat_low + conditional.point.stat_high),
        )
    directory.cd()
    graph.Write()

    correction = ROOT.TGraph(len(points))
    correction.SetName("uncorrected_vs_corrected")
    correction.SetTitle("uncorrected versus background-corrected Sigma")
    for index, item in enumerate(points):
        correction.SetPoint(index, item.sigma_uncorrected, item.point.sigma)
    correction.Write()


def _write_payload(path: Path, payload: RootOutputPayload) -> None:
    output = ROOT.TFile(str(path), "RECREATE")
    if not output or output.IsZombie():
        raise RuntimeError(f"cannot create ROOT output: {path}")
    try:
        _write_points(output, payload.points)
        _write_diagnostics(output, payload.points)
        binning = _directory(output, "binning")
        _write_vector(binning, "energy_edges", payload.energy_edges)
        for pair, edges in payload.mass_edges.items():
            _write_vector(binning, f"{pair}_mass_edges", edges)

        covariance = _directory(output, "covariance")
        _write_matrix(covariance, "total", payload.covariance_total)
        _write_matrix(
            covariance,
            "correlation_total",
            _correlation(payload.covariance_total),
        )
        if payload.statistical_covariance is not None:
            _write_matrix(
                covariance,
                "statistical",
                payload.statistical_covariance,
            )
        if payload.bootstrap_covariance is not None:
            _write_matrix(
                covariance,
                "bootstrap_run",
                payload.bootstrap_covariance,
            )
            _write_matrix(
                covariance,
                "correlation_bootstrap_run",
                _correlation(payload.bootstrap_covariance),
            )
        systematic = _directory(output, "covariance/systematic")
        for name, matrix in payload.systematic_covariances.items():
            _write_matrix(systematic, name, matrix)

        for item in payload.ratio_objects:
            directory = _directory(
                output,
                f"ratio_objects/{item.pair}/e{item.energy_bin}/m{item.mass_bin}",
            )
            phi = np.asarray(item.phi, dtype=np.float64)
            value = np.asarray(item.value, dtype=np.float64)
            error = np.asarray(item.error, dtype=np.float64)
            if phi.shape != value.shape or phi.shape != error.shape:
                raise ValueError("ratio object arrays must have matching shape")
            zeros = np.zeros_like(phi)
            graph = ROOT.TGraphErrors(
                len(phi),
                array("d", phi),
                array("d", value),
                array("d", zeros),
                array("d", error),
            )
            graph.SetName("ratio")
            fit = ROOT.TF1("fit", "[0]*cos(2*x)", 0.0, 2.0 * math.pi)
            fit.SetParameter(0, item.sigma)
            directory.cd()
            graph.Write()
            fit.Write()

        output.cd()
        ROOT.TNamed("provenance", payload.provenance).Write()
    finally:
        output.Close()


def write_root_output(path: Path, payload: RootOutputPayload) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        _write_payload(temporary, payload)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
