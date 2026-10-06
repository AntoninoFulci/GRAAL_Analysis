"""Standalone, explicitly partial Figure 4 panel-5 comparison."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .beam_asymmetry import BeamAsymmetryPrediction
from .models.eta_pi0_p import EtaPi0PModel
from .photon_flux import FluxSpectrum
from .run_output import _git_revision, _physical_parameters

AJAKA_FIGURE4_CSV_SHA256 = "aab73cc23c54f137eb46f37949911af83f266c50ef5e7f4ae6d33a9b68bedfa7"


def _published_panel5(path: Path) -> list[dict[str, float]]:
    points = []
    with path.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            if row["pair"] == "p_eta" and row["energy_bin"] == "1":
                point = {name: float(row[name]) for name in ("mass_gev", "sigma", "stat_low", "stat_high")}
                if not all(np.isfinite(value) for value in point.values()):
                    raise ValueError("panel-5 published points must be finite")
                if point["stat_low"] < 0 or point["stat_high"] < 0:
                    raise ValueError("published statistical uncertainties must be nonnegative")
                points.append(point)
    if not points:
        raise ValueError("no published panel-5 points found")
    return sorted(points, key=lambda point: point["mass_gev"])


def write_pilot_panel5(
    destination: Path,
    prediction: BeamAsymmetryPrediction,
    published_csv: Path,
    model: EtaPi0PModel,
    *,
    flux_spectrum: FluxSpectrum | None = None,
) -> None:
    if prediction.pair != "eta_p" or prediction.energy_range_gev != (1.20, 1.30):
        raise ValueError("panel 5 requires p eta and E_gamma in [1.20, 1.30] GeV")
    if (prediction.sigma_phi_fit is None) != (flux_spectrum is None):
        raise ValueError("measured-flux prediction and source must be supplied together")
    if flux_spectrum is not None and flux_spectrum.energy_range_gev != prediction.energy_range_gev:
        raise ValueError("flux source energy interval differs from prediction")
    if flux_spectrum is not None and prediction.energy_weighting != "measured_P_UV_flux":
        raise ValueError("flux source requires measured-flux prediction")
    destination = Path(destination)
    published_csv = Path(published_csv)
    if destination.exists():
        raise FileExistsError(f"output already exists: {destination}")
    published_digest = hashlib.sha256(published_csv.read_bytes()).hexdigest()
    if published_digest != AJAKA_FIGURE4_CSV_SHA256:
        raise ValueError("Ajaka Figure 4 digitization checksum differs from reviewed CSV")
    points = _published_panel5(published_csv)
    centers = (prediction.mass_edges_gev[:-1] + prediction.mass_edges_gev[1:]) / 2.0
    parameters = _physical_parameters(model)
    parameter_bytes = json.dumps(
        parameters, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    payload = {
        "scope": "partial:delta1700_eta_delta_tree_eq43",
        "status": "exploratory_not_full_ajaka_theory",
        "code_revision": _git_revision(Path(__file__).resolve().parents[3]),
        "theory_parameters": parameters,
        "theory_parameters_sha256": hashlib.sha256(parameter_bytes).hexdigest(),
        "pair": "p_eta",
        "energy_range_gev": [1.20, 1.30],
        "energy_weighting": prediction.energy_weighting,
        "energy_quadrature": "Gauss-Legendre",
        "energy_nodes_gev": prediction.energy_nodes_gev.tolist(),
        "azimuth": "eta_plus_proton_pair_momentum_around_photon_axis",
        "beam_asymmetry_sign": "vertical_minus_horizontal",
        "sobol": vars(prediction.sobol_config),
        "mass_edges_gev": prediction.mass_edges_gev.tolist(),
        "mass_centers_gev": centers.tolist(),
        "sigma": [float(value) if np.isfinite(value) else None for value in prediction.sigma],
        "sigma_phi_fit": None if prediction.sigma_phi_fit is None else [
            float(value) if np.isfinite(value) else None for value in prediction.sigma_phi_fit
        ],
        "published_csv_sha256": published_digest,
        "published_source": {
            "doi": "10.1103/PhysRevLett.100.052003",
            "figure": 4,
            "panel": 5,
            "uncertainties": "statistical only",
            "reported_binning": "4 energy x 10 mass x 12 azimuth bins; fit method cites Ajaka 1998",
        },
        "phi_fit_convention": None if prediction.sigma_phi_fit is None else (
            "Stage 07 nominal inverse-Poisson-variance fit to cos(2phi) at 12 bin centers; "
            "no data-dependent fallback; not established as exact Ajaka 2008 convention"
        ),
        "published_points": points,
        "limitations": [
            "Eq. 43 tree term only",
            "no detector acceptance",
            "no parameter fit",
            "Ajaka azimuth-bin fit abscissa and corrections not specified in 2008 article",
        ],
    }
    if flux_spectrum is None:
        payload["limitations"].append("uniform photon-energy weighting")
    else:
        def digest(path: Path) -> str:
            sha = hashlib.sha256()
            with path.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    sha.update(chunk)
            return sha.hexdigest()

        payload["energy_quadrature"] = "equal-width energy slices at combined-flux centroid"
        payload["flux_source"] = {
            "root_path": str(flux_spectrum.root_path.resolve()),
            "root_sha256": digest(flux_spectrum.root_path),
            "manifest_path": str(flux_spectrum.manifest_path.resolve()),
            "manifest_sha256": digest(flux_spectrum.manifest_path),
            "selected_runs": flux_spectrum.selected_runs,
            "complete_runs": flux_spectrum.complete_runs,
            "exposures": len(flux_spectrum.exposures),
            "skipped_nonpositive_strips": flux_spectrum.skipped_nonpositive_strips,
            "flux_vertical": sum(item.flux_vertical for item in flux_spectrum.exposures),
            "flux_horizontal": sum(item.flux_horizontal for item in flux_spectrum.exposures),
            "effective_polarization_vertical": (
                sum(item.flux_vertical * item.polarization_vertical for item in flux_spectrum.exposures)
                / sum(item.flux_vertical for item in flux_spectrum.exposures)
            ),
            "effective_polarization_horizontal": (
                sum(item.flux_horizontal * item.polarization_horizontal for item in flux_spectrum.exposures)
                / sum(item.flux_horizontal for item in flux_spectrum.exposures)
            ),
        }
        payload["limitations"].append("calibrated ROOT lacks complete triplets for some manifest runs")
        payload["limitations"].append("high-mass edge requires an independent Sobol convergence check")

    figure, axis = plt.subplots(figsize=(7.0, 4.7), constrained_layout=True)
    axis.errorbar(
        [point["mass_gev"] for point in points],
        [point["sigma"] for point in points],
        yerr=np.array([
            [point["stat_low"] for point in points],
            [point["stat_high"] for point in points],
        ]),
        fmt="D", color="#d62728", markerfacecolor="white", capsize=2,
        label="Ajaka et al. (2008), digitized; stat. only",
    )
    weighting_label = "measured flux" if flux_spectrum is not None else "uniform energy"
    axis.plot(
        centers, prediction.sigma, "o-", color="#1f77b4",
        label=f"Partial Eq. 43; continuous ({weighting_label})",
    )
    if prediction.sigma_phi_fit is not None:
        axis.plot(
            centers, prediction.sigma_phi_fit, "s--", color="#2ca02c",
            label="Partial Eq. 43; Stage 07 center fit",
        )
        populated = np.flatnonzero(np.isfinite(prediction.sigma))
        if len(populated):
            edge_bin = int(populated[-1])
            axis.axvspan(
                prediction.mass_edges_gev[edge_bin], prediction.mass_edges_gev[edge_bin + 1],
                color="0.92", alpha=0.5, zorder=0,
            )
            axis.text(
                0.98, 0.04, "High-mass edge: check numerical convergence",
                transform=axis.transAxes, ha="right", va="bottom", fontsize=8, color="0.35",
            )
    axis.axhline(0.0, color="0.7", linewidth=0.8)
    axis.set(xlim=(1.40, 1.80), ylim=(-1.0, 1.0), xlabel=r"$M(p\eta)$ [GeV]", ylabel=r"$\Sigma$")
    axis.set_title(r"Panel 5: $1.20\leq E_\gamma<1.30$ GeV")
    axis.grid(alpha=0.2)
    axis.legend()

    temp: Path | None = None
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temp = Path(tempfile.mkdtemp(prefix=f".{destination.name}.tmp-", dir=destination.parent))
        figure.savefig(temp / "panel5.pdf")
        (temp / "prediction.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        if destination.exists():
            raise FileExistsError(f"output already exists: {destination}")
        os.replace(temp, destination)
    finally:
        plt.close(figure)
        if temp is not None and temp.exists():
            shutil.rmtree(temp)
