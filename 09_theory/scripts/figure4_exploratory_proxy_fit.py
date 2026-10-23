"""Fit current 12-phi UV pilot data with a closely matched old p6 basis.

This is an explicitly approximate recovery path. Original basis input ROOTs
are unavailable; flux and energy-node differences are measured, not bounded
as errors on Sigma. Never use this result as a final physics estimate.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
import tempfile

import numpy as np

from figure4_exploratory_fit import _comparison_rows
from graal_theory.figure4_fit import build_exploratory_gls, fit_delta_em
from graal_theory.figure4_fit_output import BasisCheckpoint
from graal_theory.native_sigma import load_native_sigma_root
from graal_theory.photon_flux import group_flux_by_energy, native_flux_spectrum


POLICY = "preliminary_uncertified_p6"
MAX_RELATIVE_FLUX_CHANGE = .005
MAX_POLARIZATION_CHANGE = 1e-4
MAX_ENERGY_NODE_SHIFT_GEV = 1e-4
PHI12_DIVISOR = .9549


@dataclass(frozen=True)
class CorrectedRatioMoment:
    """Present raw 12-bin theory in Stage 07's corrected ratio convention."""

    raw: object
    divisor: float

    def __getattr__(self, name):
        return getattr(self.raw, name)

    def evaluate(self, coefficients):
        prediction = self.raw.evaluate(coefficients)
        if prediction.ratio_sigma is None:
            raise ValueError("native ratio prediction missing")
        return replace(prediction, ratio_sigma=prediction.ratio_sigma/self.divisor)


def _plot_proxy(path: Path, rows: list[dict]):
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    figure = Figure(figsize=(13, 13))
    FigureCanvasAgg(figure)
    axes = figure.subplots(4, 3, sharey=True)
    for energy in range(4):
        for column, pair in enumerate(("p_pi0", "p_eta", "eta_pi0")):
            axis = axes[energy, column]
            panel = [row for row in rows if row["energy_bin"] == energy and row["pair"] == pair]
            axis.errorbar([row["mass_center_gev"] for row in panel],
                          [row["measured_sigma"] for row in panel],
                          yerr=[row["stat_error"] for row in panel],
                          fmt="o", markersize=3, color="black", label="GRAAL phi12 pilot")
            for field, color, label in (("source_sigma", "#bf4b25", "published couplings"),
                                        ("fitted_sigma", "#005c99", "proxy fit")):
                axis.plot([row["mass_center_gev"] if row[field] is not None else np.nan
                           for row in panel],
                          [row[field] if row[field] is not None else np.nan for row in panel],
                          "o-", markersize=3, linewidth=1.2, color=color, label=label)
            axis.set_ylim(-1.05, 1.05)
            axis.set_title(f"Eγ {1.1+.1*energy:.1f}–{1.2+.1*energy:.1f} GeV · {pair}")
            axis.set_xlabel("Pair mass (GeV)")
            if column == 0:
                axis.set_ylabel("Σ")
            if energy == 0 and column == 0:
                axis.legend(fontsize=8)
    figure.suptitle("EXPLORATORY PROXY FIT — stale flux basis; p6 uncertified")
    figure.tight_layout(rect=(0, 0, 1, .97))
    figure.savefig(path, format="pdf")


def load_proxy_basis(basis_dir, data, flux_root, reco_root, run_manifest):
    """Read every saved bin and gate approximate reuse against current data."""
    basis_dir = Path(basis_dir)
    manifest = json.loads((basis_dir/"manifest.json").read_text(encoding="utf-8"))
    if (manifest.get("target") != "native" or manifest.get("policy") != POLICY
            or data.status != "pilot" or data.provenance.get("phi_bins") != "12"
            or data.provenance.get("phi_bin_correction") != "ratio_only_rounded"
            or data.provenance.get("phi_bin_divisor") != "0.9549"):
        raise ValueError("proxy requires native p6 basis and corrected 12-phi pilot data")
    expected = {f"{energy}_{pair}_{mass}.npz" for pair, energy, mass in data.keys}
    if len(expected) != len(data.keys) or set(manifest.get("keys", ())) != expected:
        raise ValueError("proxy basis keys differ from current data")
    checkpoint = BasisCheckpoint(basis_dir, manifest)
    if checkpoint.pending_keys():
        raise ValueError("proxy basis has missing or corrupt bins")
    spectra = {
        energy: native_flux_spectrum(
            Path(flux_root), Path(run_manifest), Path(reco_root),
            tuple(map(float, data.energy_edges_gev[energy:energy+2])))
        for energy in sorted({key[1] for key in data.keys})
    }
    fingerprints = {item.source_fingerprint for item in spectra.values()}
    if len(fingerprints) != 1 or None in fingerprints:
        raise ValueError("current flux/reco/manifest identity inconsistent")
    moments = {}
    max_flux = max_polarization = max_node = 0.
    calculated = 0
    for pair, energy, mass in data.keys:
        certificate = checkpoint.read((energy, pair, mass))
        moment = certificate.moment
        if (certificate.status != ("preliminary_uncertified" if moment.status == "calculated"
                                   else moment.status)
                or moment.energy_rule != "native_flux" or moment.pair != pair
                or not np.allclose(moment.energy_range_gev,
                                   data.energy_edges_gev[energy:energy+2], rtol=0, atol=1e-12)
                or not np.allclose(moment.mass_range_gev,
                                   data.mass_edges_gev[pair][mass:mass+2], rtol=0, atol=1e-12)):
            raise ValueError("proxy basis certificate or bin identity mismatch")
        moments[(pair, energy, mass)] = (CorrectedRatioMoment(moment, PHI12_DIVISOR)
                                         if moment.status == "calculated" else moment)
        if moment.status != "calculated":
            continue
        calculated += 1
        spectrum = spectra[energy]
        vertical = sum(item.flux_vertical for item in spectrum.exposures)
        horizontal = sum(item.flux_horizontal for item in spectrum.exposures)
        if (vertical <= 0 or horizontal <= 0 or moment.flux_vertical is None
                or moment.flux_horizontal is None or moment.flux_vertical <= 0
                or moment.flux_horizontal <= 0 or moment.accessible_energy_gev is None):
            raise ValueError("proxy flux normalization or accessible range missing")
        polarization_vertical = sum(
            item.flux_vertical*item.polarization_vertical for item in spectrum.exposures
        )/vertical
        polarization_horizontal = sum(
            item.flux_horizontal*item.polarization_horizontal for item in spectrum.exposures
        )/horizontal
        max_flux = max(max_flux, abs(vertical/moment.flux_vertical-1),
                       abs(horizontal/moment.flux_horizontal-1))
        max_polarization = max(max_polarization,
                               abs(polarization_vertical-moment.polarization_vertical),
                               abs(polarization_horizontal-moment.polarization_horizontal))
        eligible = tuple(item for item in spectrum.exposures
                         if moment.accessible_energy_gev[0] <= item.energy_gev
                         < moment.energy_range_gev[1])
        grouped = group_flux_by_energy(
            replace(spectrum, energy_range_gev=moment.accessible_energy_gev,
                    exposures=eligible), 4)
        nodes = np.array([item.energy_gev for item in grouped])
        if nodes.shape != moment.energy_nodes_gev.shape:
            raise ValueError("proxy energy-node count differs from saved basis")
        max_node = max(max_node, float(np.max(np.abs(nodes-moment.energy_nodes_gev))))
    if calculated < 3:
        raise ValueError("proxy fit needs at least three calculated bins")
    if not np.isfinite((max_flux, max_polarization, max_node)).all():
        raise ValueError("proxy flux comparison is nonfinite")
    if max_flux > MAX_RELATIVE_FLUX_CHANGE:
        raise ValueError(f"proxy flux change exceeds {MAX_RELATIVE_FLUX_CHANGE:g}: {max_flux:g}")
    if max_polarization > MAX_POLARIZATION_CHANGE:
        raise ValueError("proxy polarization change exceeds exploratory gate")
    if max_node > MAX_ENERGY_NODE_SHIFT_GEV:
        raise ValueError("proxy energy-node shift exceeds exploratory gate")
    audit = {
        "basis_original_data_sha256": manifest.get("data_sha256"),
        "basis_fingerprint": manifest["fingerprint"],
        "basis_manifest_complete": bool(manifest.get("complete")),
        "fit_data_sha256": data.source_sha256,
        "flux_source_fingerprint": next(iter(fingerprints)),
        "max_relative_flux_change": max_flux,
        "max_polarization_change": max_polarization,
        "max_energy_node_shift_gev": max_node,
        "reused_calculated_bins": calculated,
        "theory_ratio_divisor": PHI12_DIVISOR,
        "gates": {
            "relative_flux": MAX_RELATIVE_FLUX_CHANGE,
            "polarization": MAX_POLARIZATION_CHANGE,
            "energy_node_gev": MAX_ENERGY_NODE_SHIFT_GEV,
        },
        "interpretation": "proxy input proximity only; no bound on Sigma prediction error",
    }
    return moments, audit


def fit_proxy(output_dir, data_root, basis_dir, flux_root, reco_root, run_manifest):
    output = Path(output_dir)
    if output.exists():
        raise FileExistsError(f"proxy fit output already exists: {output}")
    data = load_native_sigma_root(Path(data_root))
    moments, audit = load_proxy_basis(basis_dir, data, flux_root, reco_root, run_manifest)
    objective = build_exploratory_gls(data, moments)
    source_theta = np.array([objective.anchor_g1, objective.anchor_g2])
    result = fit_delta_em(objective, source_theta)
    rows = _comparison_rows(data, objective, result)
    report = {
        "status": ("exploratory_pilot_proxy" if result.status == "exploratory_pilot"
                   else result.status),
        "purpose": "cross_campaign_proxy_fit_only",
        "data_status": data.status,
        "data_provenance": data.provenance,
        "data_sha256": data.source_sha256,
        "model_fingerprint": objective.model_fingerprint,
        "proxy_audit": audit,
        "input_paths": {"data_root": str(Path(data_root).resolve()),
                        "basis_dir": str(Path(basis_dir).resolve()),
                        "flux_root": str(Path(flux_root).resolve()),
                        "reco_root": str(Path(reco_root).resolve()),
                        "run_manifest": str(Path(run_manifest).resolve())},
        "included_bins": len(objective.data.keys),
        "excluded_bins": [{"key": list(key), "reason": reason}
                          for key, reason in objective.excluded],
        "source_couplings_internal": result.source_internal.tolist(),
        "fitted_couplings_internal": result.theta_internal.tolist(),
        "source_couplings_source_units": result.source_source_units.tolist(),
        "fitted_couplings_source_units": result.theta_source_units.tolist(),
        "chi_square": result.chi_square,
        "degrees_of_freedom": result.degrees_of_freedom,
        "jacobian_singular_values": (None if result.jacobian_singular_values is None else
                                      result.jacobian_singular_values.tolist()),
        "conditional_parameter_covariance": (None if result.parameter_covariance is None else
                                              result.parameter_covariance.tolist()),
        "optimizer_message": result.message,
        "optimizer_evaluations": result.nfev,
        "limitations": ["original campaign data ROOT unavailable",
                        "old basis flux weighting differs from current campaign",
                        "flux proximity is not a bound on Sigma error",
                        "p6 basis uncertified", "background uncorrected",
                        "run bootstrap absent", "best quartet unresolved"],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        (staging/"fit.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n",
                                        encoding="utf-8")
        with (staging/"native_comparison.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=tuple(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        _plot_proxy(staging/"native_comparison.pdf", rows)
        os.replace(staging, output)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    print(f"Proxy pilot fit: {report['status']}; included={len(objective.data.keys)}/"
          f"{len(data.keys)}; chi2={result.chi_square}; {output}", flush=True)
    return 0 if result.status == "exploratory_pilot" else 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--basis-dir", type=Path, required=True)
    parser.add_argument("--flux-root", type=Path, required=True)
    parser.add_argument("--reco-root", type=Path, required=True)
    parser.add_argument("--run-manifest", type=Path, required=True)
    args = parser.parse_args(argv)
    return fit_proxy(args.output_dir, args.data_root, args.basis_dir,
                     args.flux_root, args.reco_root, args.run_manifest)


if __name__ == "__main__":
    raise SystemExit(main())
