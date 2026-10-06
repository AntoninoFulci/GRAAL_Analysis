"""Conservative Ajaka Figure 4 theory-line residual and claim gate."""

from __future__ import annotations

from dataclasses import dataclass
import csv
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Mapping

import numpy as np

from .figure4_integration import Figure4PanelResult
from .figure4_reference import EXPECTED_PANELS, PublishedCurvePoint


@dataclass(frozen=True)
class Figure4Residual:
    pair: str
    energy_bin: int
    mass_gev: float
    published_sigma: float
    predicted_sigma: float | None
    residual: float | None
    reading_bound: float
    numerical_bound: float | None
    status: str
    reason: str | None


@dataclass(frozen=True)
class Figure4Comparison:
    residuals: tuple[Figure4Residual, ...]
    status: str
    panel_status: Mapping[tuple[int, str], str]


def _interpolated(panel: Figure4PanelResult, mass: float):
    bins = panel.bins
    positions = np.array([item.moment.weighted_mass_gev for item in bins])
    for index, item in enumerate(bins):
        if item.status == "calculated" and np.isclose(mass, positions[index], rtol=0, atol=1e-12):
            return item.sigma, item.numerical_error_bound, None
    for index in range(len(bins)-1):
        left, right = bins[index:index+2]
        x_left, x_right = positions[index:index+2]
        if (not np.isfinite(x_left) or not np.isfinite(x_right)
                or not x_left < mass < x_right):
            continue
        if left.status != "calculated" or right.status != "calculated":
            return None, None, "masked_neighbor"
        fraction = (mass-x_left)/(x_right-x_left)
        sigma = (1-fraction)*left.sigma+fraction*right.sigma
        bound = max(left.numerical_error_bound, right.numerical_error_bound)
        return float(sigma), float(bound), None
    return None, None, "outside_adjacent_calculated_support"


def compare_figure4(
        prediction: Mapping[tuple[int, str], Figure4PanelResult],
        published: tuple[PublishedCurvePoint, ...]) -> Figure4Comparison:
    if not isinstance(prediction, Mapping):
        raise ValueError("prediction requires a panel mapping")
    panel_status = {}
    for key, panel in prediction.items():
        if (not isinstance(key, tuple) or len(key) != 2 or key not in
                {(energy, pair) for pair, energy in EXPECTED_PANELS}
                or not isinstance(panel, Figure4PanelResult)
                or panel.pair != key[1]
                or not np.allclose(panel.energy_range_gev,
                                   (1.10+.10*key[0], 1.20+.10*key[0]),
                                   rtol=0, atol=1e-12)):
            raise ValueError(f"invalid Figure 4 panel key: {key}")
        panel_status[key] = ("complete" if all(item.status in
            ("calculated", "masked_kinematic") for item in panel.bins)
            else "incomplete")

    rows = []
    for point in published:
        if not isinstance(point, PublishedCurvePoint):
            raise ValueError("published points require PublishedCurvePoint")
        key = (point.energy_bin, point.pair)
        panel = prediction.get(key)
        reason = None
        predicted = residual = numerical = None
        if point.status == "unresolved":
            status, reason = "unresolved", "ambiguous_source_mapping"
        elif point.status != "resolved":
            raise ValueError(f"unknown published point status: {point.status}")
        elif panel is None:
            status, reason = "masked", "missing_panel"
        elif not panel.mass_edges_gev[0] <= point.mass_gev <= panel.mass_edges_gev[-1]:
            status, reason = "masked", "outside_nominal_panel"
        else:
            support = [item.moment.accessible_mass_gev for item in panel.bins
                       if item.moment.accessible_mass_gev is not None]
            if not support or point.mass_gev < min(bounds[0] for bounds in support) or (
                    point.mass_gev > max(bounds[1] for bounds in support)):
                status, reason = "masked", "outside_physical_support"
            else:
                predicted, numerical, reason = _interpolated(panel, point.mass_gev)
                if predicted is None:
                    status = "masked"
                else:
                    residual = predicted-point.sigma
                    status = ("compatible" if abs(residual) <=
                              point.reading_error+numerical+1e-12 else "discrepant")
        rows.append(Figure4Residual(point.pair, point.energy_bin, point.mass_gev,
            point.sigma, predicted, residual, point.reading_error, numerical,
            status, reason))

    expected = {(energy, pair) for pair, energy in EXPECTED_PANELS}
    incomplete = (set(prediction) != expected or
                  any(status != "complete" for status in panel_status.values()) or
                  { (row.energy_bin, row.pair) for row in rows } != expected or
                  any((row.status == "masked" and row.reason != "outside_physical_support")
                      or row.status == "unresolved"
                      for row in rows))
    if incomplete:
        overall = "incomplete"
    elif any(row.status == "discrepant" for row in rows):
        overall = "calculated_discrepant"
    else:
        overall = "reproduced"
    return Figure4Comparison(tuple(rows), overall, panel_status)


def _json_safe(value):
    if isinstance(value, np.ndarray):
        return _json_safe(value.tolist())
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if np.isfinite(value) else None
    return value


def write_figure4_run(output_dir, panels: Mapping[tuple[int, str], Figure4PanelResult],
                      comparison: Figure4Comparison, provenance: Mapping[str, str], *,
                      experimental_points=None, replace_existing: bool = False) -> Path:
    """Write one immutable, reviewable Figure 4 calculation bundle."""
    if not isinstance(comparison, Figure4Comparison):
        raise ValueError("comparison requires Figure4Comparison")
    required = ("source_sha256", "parameters_sha256", "code_sha256")
    if not isinstance(provenance, Mapping) or any(not provenance.get(key) for key in required):
        raise ValueError("provenance requires source, parameter, and code fingerprints")
    destination = Path(output_dir)
    if destination.exists() and not replace_existing:
        raise FileExistsError(f"output already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent))
    try:
        rows = []
        covariance = {}
        for energy in range(4):
            for pair in ("p_pi0", "p_eta", "eta_pi0"):
                panel = panels.get((energy, pair))
                if panel is None or len(panel.bins) != 10:
                    raise ValueError(f"missing ten-bin panel {(energy, pair)}")
                covariance[f"{energy}:{pair}"] = {
                    "sigma_covariance": panel.covariance,
                    "denominator_replica_se": panel.denominator_replica_se,
                    "vertical_replica_se": panel.vertical_replica_se,
                    "horizontal_replica_se": panel.horizontal_replica_se,
                }
                for index, item in enumerate(panel.bins):
                    moment = item.moment
                    rows.append({
                        "energy_bin": energy, "pair": pair, "mass_bin": index,
                        "energy_low_gev": panel.energy_range_gev[0],
                        "energy_high_gev": panel.energy_range_gev[1],
                        "nominal_mass_low_gev": moment.mass_range_gev[0],
                        "nominal_mass_high_gev": moment.mass_range_gev[1],
                        "accessible_energy_low_gev": (moment.accessible_energy_gev or (None,None))[0],
                        "accessible_energy_high_gev": (moment.accessible_energy_gev or (None,None))[1],
                        "accessible_mass_low_gev": (moment.accessible_mass_gev or (None,None))[0],
                        "accessible_mass_high_gev": (moment.accessible_mass_gev or (None,None))[1],
                        "weighted_mass_gev": moment.weighted_mass_gev,
                        "sigma": item.sigma, "numerical_error_bound": item.numerical_error_bound,
                        "numerator": moment.numerator, "denominator": moment.denominator,
                        "vertical_normalization": moment.vertical_normalization,
                        "horizontal_normalization": moment.horizontal_normalization,
                        "source_used_extension_fraction": moment.source_used_extension_fraction,
                        "status": item.status, "reason": "; ".join(item.reason),
                        "energy_order": panel.energy_order, "sobol_power": panel.sobol_power,
                        "replica_seeds": ",".join(map(str,panel.replica_seeds)),
                        "covariance_row_id": f"{energy}:{pair}:{index}",
                        "mode": panel.mode,
                        "source_sha256": provenance["source_sha256"],
                        "parameters_sha256": provenance["parameters_sha256"],
                        "code_sha256": provenance["code_sha256"],
                        "error_components": item.error_components,
                    })
        fieldnames = tuple(rows[0])
        with (staging/"predictions.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({key: json.dumps(_json_safe(value), sort_keys=True)
                                 if isinstance(value, dict) else
                                 "" if value is None or isinstance(value, float) and not np.isfinite(value)
                                 else value for key, value in row.items()})
        (staging/"predictions.json").write_text(
            json.dumps(_json_safe(rows), indent=2, allow_nan=False)+"\n", encoding="utf-8")
        (staging/"covariance.json").write_text(
            json.dumps(_json_safe(covariance), indent=2, allow_nan=False)+"\n", encoding="utf-8")
        residual_fields = tuple(Figure4Residual.__dataclass_fields__)
        with (staging/"residuals.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=residual_fields)
            writer.writeheader()
            for residual in comparison.residuals:
                writer.writerow({key: "" if getattr(residual,key) is None else getattr(residual,key)
                                 for key in residual_fields})

        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        fig = Figure(figsize=(13, 13))
        FigureCanvasAgg(fig)
        axes = fig.subplots(4, 3, sharey=True)
        for energy in range(4):
            for column, pair in enumerate(("p_pi0", "p_eta", "eta_pi0")):
                ax = axes[energy, column]
                panel = panels[(energy, pair)]
                x = [item.moment.weighted_mass_gev if item.status == "calculated" else np.nan
                     for item in panel.bins]
                y = [item.sigma if item.status == "calculated" else np.nan
                     for item in panel.bins]
                ax.plot(x, y, color="#005c99", linewidth=1.5, label="calculated")
                reference = sorted((row for row in comparison.residuals
                                    if row.energy_bin == energy and row.pair == pair),
                                   key=lambda row: row.mass_gev)
                if reference:
                    ax.plot([row.mass_gev for row in reference],
                            [row.published_sigma for row in reference],
                            color="#bf4b25", linewidth=1.2, linestyle="--",
                            label="Ajaka theory")
                if experimental_points is not None:
                    selected = [point for point in experimental_points
                                if point.pair == pair and point.energy_bin == energy]
                    if selected:
                        ax.scatter([point.mass_gev for point in selected],
                                   [point.sigma for point in selected],
                                   marker="o", s=12, color="black", label="experiment")
                ax.set_title(f"E bin {energy+1}, {pair}")
                ax.set_xlim(panel.mass_edges_gev[0], panel.mass_edges_gev[-1])
                ax.set_ylim(-1.05, 1.05)
                ax.grid(alpha=.25)
                if energy == 3:
                    ax.set_xlabel("pair mass [GeV]")
                if column == 0:
                    ax.set_ylabel(r"$\Sigma$")
        axes[0,0].legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(staging/"figure4_comparison.pdf")
        counts = {status: sum(row.status == status for row in comparison.residuals)
                  for status in ("compatible", "discrepant", "unresolved", "masked")}
        report = ["# Ajaka Figure 4 full-model validation", "",
                  f"Overall status: **{comparison.status}**", "",
                  f"Residual counts: {counts}", "",
                  "Physically accessible bins require all numerical gates before a reproduction claim.",
                  "", "## Provenance", ""]
        report.extend(f"- {key}: `{value}`" for key, value in provenance.items())
        (staging/"validation.md").write_text("\n".join(report)+"\n", encoding="utf-8")
        (staging/"manifest.json").write_text(json.dumps(_json_safe({
            "status": comparison.status, "provenance": dict(provenance),
            "prediction_rows": len(rows), "residual_rows": len(comparison.residuals),
            "experimental_points_included": experimental_points is not None,
        }), indent=2, allow_nan=False)+"\n", encoding="utf-8")
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(staging, destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return destination
