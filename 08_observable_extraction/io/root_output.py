"""ROOT-only public storage for beam-asymmetry results and diagnostics."""

from __future__ import annotations

from array import array
from dataclasses import dataclass, field
import math
import json
import os
from pathlib import Path
import tempfile
from typing import Mapping, Sequence

import numpy as np
import ROOT

from observable_extraction.core.models import SigmaPoint
from observable_extraction.core.binning import PHI_EDGES_RAD, PHI_BIN_DIVISORS, phi_edges_rad, validate_edges
from observable_extraction.core.systematics import validate_covariance, PairedBootstrapResult


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
    uncertainty_kind: str = "conditional_statistical"
    phi_bins: int = 0  # 0: unbinned likelihood or legacy unknown binning


@dataclass(frozen=True)
class RatioObject:
    pair: str
    energy_bin: int
    mass_bin: int
    phi: np.ndarray
    value: np.ndarray
    error: np.ndarray
    sigma: float
    phi_bins: int = 0
    c0: float = 0.0
    s2: float = 0.0


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
    phi_edges: np.ndarray = field(default_factory=lambda: PHI_EDGES_RAD.copy())
    point_context: Mapping[str, str] = field(default_factory=dict)
    uncertainty_metadata: Mapping[str, object] = field(default_factory=dict)
    bootstrap_diagnostics: PairedBootstrapResult | None = None
    extraction_metadata: Mapping[str, object] = field(default_factory=dict)
    binning_candidates: Sequence[OutputPoint] = ()
    candidate_ratio_objects: Sequence[RatioObject] = ()


def ordered_point_keys(points, context):
    """Identity is explicit, including unknown context; never inferred as independence."""
    common = {name: context.get(name, "unspecified")
              for name in ("campaign", "selection", "profile", "period")}
    keys = [dict(common, sample=item.sample, estimator=item.estimator,
                 pair=item.point.pair, energy_bin=item.point.energy_bin,
                 mass_bin=item.point.mass_bin) for item in points]
    if len({point_key_label(key) for key in keys}) != len(keys):
        raise ValueError("duplicate output point keys")
    return keys


def point_key_label(key):
    return json.dumps(key, sort_keys=True, separators=(",", ":"))


def _validate_payload(payload):
    for point in (*payload.points, *payload.binning_candidates):
        if point.phi_bins not in (0, *PHI_BIN_DIVISORS):
            raise ValueError("invalid per-point phi_bins")
        if point.estimator == "likelihood" and point.phi_bins:
            raise ValueError("likelihood must be unbinned")
        if ("phi_bins=best-binning" in payload.provenance.splitlines()
                and point.estimator == "ratio" and not point.phi_bins):
            raise ValueError("best-binning requires per-point phi_bins")
    keys = ordered_point_keys(payload.points, payload.point_context)
    if not keys and payload.extraction_metadata.get("status") != "not_estimable":
        raise ValueError("at least one output point is required")
    total = validate_covariance(payload.covariance_total, size=len(keys))
    for matrix in payload.systematic_covariances.values():
        validate_covariance(matrix, size=len(keys))
    if payload.statistical_covariance is not None:
        stat = validate_covariance(payload.statistical_covariance, size=len(keys))
        expected = stat + sum(payload.systematic_covariances.values(), np.zeros_like(stat))
        if not np.allclose(total, expected, rtol=1e-10, atol=1e-12):
            raise ValueError("total covariance must equal statistical plus systematic components")
    if payload.bootstrap_covariance is not None:
        validate_covariance(payload.bootstrap_covariance, size=len(keys))
    diagnostic = payload.bootstrap_diagnostics
    if diagnostic is not None:
        if diagnostic.point_keys != tuple(point_key_label(key) for key in keys):
            raise ValueError("diagnostic bootstrap point keys mismatch")
        if diagnostic.replicas.shape != (len(diagnostic.run_draws), len(keys)):
            raise ValueError("diagnostic bootstrap replica dimensions mismatch")
        if diagnostic.covariance is not None:
            if diagnostic.failures:
                raise ValueError("failed bootstrap replicas cannot publish a covariance")
            validate_covariance(diagnostic.covariance, size=len(keys))
    return keys


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


def _write_matrix(directory, name: str, values: np.ndarray, point_keys) -> None:
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 2 or values.shape[0] != values.shape[1]:
        raise ValueError(f"matrix {name!r} must be square")
    size = values.shape[0]
    if size == 0:
        return  # An unestimable result has no covariance, never a dummy zero bin.
    histogram = ROOT.TH2D(name, name, size, 0, size, size, 0, size)
    for index, key in enumerate(point_keys, 1):
        histogram.GetXaxis().SetBinLabel(index, point_key_label(key))
        histogram.GetYaxis().SetBinLabel(index, point_key_label(key))
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
    root_file.cd()
    tree = ROOT.TTree("sigma_points", "beam-asymmetry points")
    integer_names = (
        "sample_id", "estimator_id", "pair_id", "energy_bin", "mass_bin",
        "count_vertical", "count_horizontal", "fit_ndf", "fit_converged",
        "used_fallback", "phi_bins",
    )
    float_names = (
        "energy_low_gev", "energy_high_gev", "mass_low_gev", "mass_high_gev",
        "mass_center_gev", "mass_mean_gev", "sigma_uncorrected", "sigma",
        "stat_low", "stat_high", "syst_total", "background_fraction",
        "flux_vertical", "flux_horizontal", "polarization_vertical",
        "polarization_horizontal", "fit_chi2", "fit_p_value", "c0", "s2", "phi_bin_divisor",
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
            "phi_bins": output.phi_bins,
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
            "phi_bin_divisor": PHI_BIN_DIVISORS[output.phi_bins] if output.phi_bins else 1.0,
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


def _write_bootstrap_diagnostics(root_file, result, point_keys):
    directory = _directory(root_file, "diagnostics/paired_bootstrap")
    directory.cd()
    metadata = dict(
        point_keys=result.point_keys, seed=result.seed, failures=result.failures,
        rank=result.rank, effective_runs=result.effective_runs,
        zero_event_runs=result.zero_event_runs, replicas=len(result.replicas),
        covariance_available=result.covariance is not None,
        draws_per_replica=len(result.run_draws[0]),
        ensemble="run blocks within explicit profile/period strata; exposures resampled",
        use="diagnostic only; not combined with fit or systematic covariance",
        mc_error="approximate IID-replica Monte Carlo standard error of covariance",
    )
    ROOT.TNamed("metadata", json.dumps(metadata)).Write()
    tree = ROOT.TTree("replicas", "all requested replicas, including non-estimable points")
    replica, point_index, value = array("i", [0]), array("i", [0]), array("d", [0.])
    tree.Branch("replica", replica, "replica/I")
    tree.Branch("point_index", point_index, "point_index/I")
    tree.Branch("sigma", value, "sigma/D")
    for row, values in enumerate(result.replicas):
        for column, sigma in enumerate(values):
            replica[0], point_index[0], value[0] = row, column, float(sigma)
            tree.Fill()
    tree.Write()
    draws = ROOT.TTree("run_draws", "run draws with repeated identities retained")
    draw_index, run = array("i", [0]), array("i", [0])
    draws.Branch("replica", replica, "replica/I")
    draws.Branch("draw_index", draw_index, "draw_index/I")
    draws.Branch("run_number", run, "run_number/I")
    for row, draw in enumerate(result.run_draws):
        for column, identity in enumerate(draw):
            replica[0], draw_index[0], run[0] = row, column, identity
            draws.Fill()
    draws.Write()
    if result.covariance is not None:
        _write_matrix(directory, "covariance", result.covariance, point_keys)
        _write_matrix(directory, "correlation", _correlation(result.covariance), point_keys)
        _write_matrix(directory, "covariance_mc_error", result.covariance_standard_error, point_keys)


def _write_payload(path: Path, payload: RootOutputPayload) -> None:
    output = ROOT.TFile(str(path), "RECREATE")
    if not output or output.IsZombie():
        raise RuntimeError(f"cannot create ROOT output: {path}")
    was_batch = ROOT.gROOT.IsBatch()
    try:
        _write_points(output, payload.points)
        _write_diagnostics(output, payload.points)
        if "phi_bins=best-binning" in payload.provenance.splitlines():
            for bins in PHI_BIN_DIVISORS:
                directory = _directory(output, f"binning_candidates/{bins}")
                _write_points(directory, [p for p in payload.binning_candidates if p.phi_bins == bins])
                _write_vector(directory, "phi_edges", phi_edges_rad(bins))
            output.cd()
            ROOT.TNamed("binning_selection", json.dumps(dict(
                candidates=[8, 12, 16], p_value_threshold=0.01,
                order=["acceptable_fit", "nominal_fit", "abs(chi2/ndf - 1)", "tie:12,8,16"],
                missing_candidates="not_estimable",
                candidate_sigma="finite-bin corrected, before background correction",
                phi_edges="binning/phi_edges is for control plots only; use per-point phi_bins",
            ))).Write()
        binning = _directory(output, "binning")
        _write_vector(binning, "energy_edges", payload.energy_edges)
        _write_vector(binning, "phi_edges", validate_edges(payload.phi_edges))
        for pair, edges in payload.mass_edges.items():
            _write_vector(binning, f"{pair}_mass_edges", edges)

        point_keys = ordered_point_keys(payload.points, payload.point_context)
        covariance = _directory(output, "covariance")
        covariance.cd()
        ROOT.TNamed("point_keys", json.dumps(point_keys)).Write()
        ROOT.TNamed("uncertainty_metadata", json.dumps(dict(payload.uncertainty_metadata))).Write()
        output.cd()
        ROOT.TNamed("point_uncertainty_kinds", json.dumps([item.uncertainty_kind for item in payload.points])).Write()
        ROOT.TNamed("extraction_metadata", json.dumps(dict(payload.extraction_metadata), allow_nan=False)).Write()
        matrices = {"total": payload.covariance_total}
        if payload.statistical_covariance is not None:
            matrices["statistical"] = payload.statistical_covariance
        if payload.bootstrap_covariance is not None:
            matrices["bootstrap_run"] = payload.bootstrap_covariance
        for name, matrix in matrices.items():
            _write_matrix(covariance, name, matrix, point_keys)
            _write_matrix(covariance, "correlation_" + name, _correlation(matrix), point_keys)
        systematic = _directory(output, "covariance/systematic")
        correlations = _directory(output, "covariance/correlation_systematic")
        for name, matrix in payload.systematic_covariances.items():
            _write_matrix(systematic, name, matrix, point_keys)
            _write_matrix(correlations, name, _correlation(matrix), point_keys)
        if payload.bootstrap_diagnostics is not None:
            _write_bootstrap_diagnostics(output, payload.bootstrap_diagnostics, point_keys)

        if payload.ratio_objects or payload.candidate_ratio_objects:
            ROOT.gROOT.SetBatch(True)
        objects = [("", item) for item in payload.ratio_objects]
        objects.extend((f"binning_candidates/{item.phi_bins}/", item)
                       for item in payload.candidate_ratio_objects)
        for prefix, item in objects:
            directory = _directory(
                output,
                f"{prefix}ratio_objects/{item.pair}/e{item.energy_bin}/m{item.mass_bin}",
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
            fit = ROOT.TF1("fit", "[0]*cos(2*x)+[1]+[2]*sin(2*x)", 0.0, 2.0 * math.pi)
            fit.SetParameter(0, item.sigma)
            fit.SetParameter(1, item.c0)
            fit.SetParameter(2, item.s2)
            directory.cd()
            graph.Write()
            fit.Write()

            canvas = ROOT.TCanvas(
                f"overlay_{item.pair}_e{item.energy_bin}_m{item.mass_bin}",
                "Azimuthal ratio and fit", 800, 600,
            )
            graph.SetTitle("Azimuthal ratio and fit;#phi [rad];ratio")
            graph.SetMarkerStyle(20)
            graph.SetMinimum(min(float(np.min(value - error)), -abs(item.sigma)) - 0.05)
            graph.SetMaximum(max(float(np.max(value + error)), abs(item.sigma)) + 0.05)
            graph.Draw("AP")
            graph.GetXaxis().SetLimits(0.0, 2.0 * math.pi)
            fit.SetLineColor(ROOT.kRed)
            fit.SetNpx(200)
            fit.Draw("SAME")
            canvas.Update()
            overlay_directory = _directory(
                output,
                f"{prefix}ratio_overlays/{item.pair}/e{item.energy_bin}/m{item.mass_bin}",
            )
            overlay_directory.cd()
            canvas.Write("overlay")
            canvas.Close()

        output.cd()
        ROOT.TNamed("provenance", payload.provenance).Write()
    finally:
        output.Close()
        ROOT.gROOT.SetBatch(was_batch)


def write_root_output(path: Path, payload: RootOutputPayload) -> None:
    _validate_payload(payload)
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


def write_comparison_root(path, report):
    sample_names = report.get("sample_names", ("pairing", "bdt"))
    output = ROOT.TFile(str(path), "RECREATE")
    if output.IsZombie():
        raise OSError(f"cannot write {path}")
    try:
        ROOT.TNamed("comparison_metadata", json.dumps(report, allow_nan=False, sort_keys=True)).Write()
        tree = ROOT.TTree("comparison", "Full grid; missing values are NaN, status in metadata")
        names = ("row", *(f"sigma_{name}" for name in sample_names), "delta", "delta_run_error")
        buffers = {name: array("d", [0.]) for name in names}
        for name, buffer in buffers.items():
            tree.Branch(name, buffer, f"{name}/D")
        for index, row in enumerate(report["rows"]):
            values = [index, *[row[name]["point"]["sigma"] if row[name] else None for name in sample_names],
                      row["delta"], row.get("delta_run_error")]
            for name, value in zip(names, values):
                buffers[name][0] = float(value) if value is not None else float("nan")
            tree.Fill()
        tree.Write()
        diagnostic = report["bootstrap"]
        for name in ("joint_covariance", "cross_covariance", "difference_covariance", "difference_covariance_mc_se"):
            values = diagnostic.get(name)
            if values is None:
                continue
            matrix = np.asarray(values)
            hist = ROOT.TH2D(name, name, len(matrix), 0, len(matrix), len(matrix), 0, len(matrix))
            labels = diagnostic["available_keys"]
            if name == "joint_covariance":
                labels = [f"{sample}:{key}" for sample in sample_names for key in labels]
            for i, label in enumerate(labels):
                hist.GetXaxis().SetBinLabel(i + 1, label)
                hist.GetYaxis().SetBinLabel(i + 1, label)
                for j in range(len(matrix)):
                    hist.SetBinContent(i + 1, j + 1, float(matrix[i, j]))
            hist.Write()
    finally:
        output.Close()
