"""Resumable raw p6 basis and explicitly exploratory fit to UV pilot data.

Basis calculation is long and intended for user execution. It never creates
certified Figure 4 points or a final GRAAL parameter estimate.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import csv
from functools import lru_cache
import json
import os
from pathlib import Path
import shutil
import tempfile
from time import monotonic

import numpy as np

from graal_theory.cli import _figure4_model
from graal_theory.figure4_basis import (BasisBinCertificate, BasisBinMoment,
                                        integrate_basis_bin)
from graal_theory.figure4_fit import build_exploratory_gls, fit_delta_em
from graal_theory.figure4_fit_output import BasisCheckpoint, fingerprint_inputs
from graal_theory.native_sigma import load_native_sigma_root
from graal_theory.phase_space import SobolConfig
from graal_theory.photon_flux import native_flux_spectrum


REFERENCES = Path(__file__).resolve().parents[1]/"references"
POWER = 6
ENERGY_ORDER = 4
Q_ORDER = 64
ANGLE_ORDER = 48
POLICY = "preliminary_uncertified_p6"


@lru_cache(maxsize=1)
def _model():
    return _figure4_model(REFERENCES, "grid", Q_ORDER, ANGLE_ORDER)


def _failed_moment(pair, energy_range, mass_range, reason):
    zero = np.zeros((3, 3), dtype=np.complex128)
    return BasisBinMoment(
        pair, tuple(energy_range), tuple(mass_range), "native_flux",
        zero, zero.copy(), np.zeros((2, 12, 3, 3), dtype=np.complex128),
        None, None, None, None, zero.copy(), np.empty(0),
        "masked_nonconverged", reason,
    )


def _calculate(task):
    key, energy_range, mass_range, spectrum = task
    try:
        moment = integrate_basis_bin(
            _model(), key[1], energy_range, mass_range,
            energy_rule="native_flux", energy_order=ENERGY_ORDER,
            sobol=SobolConfig(POWER), flux_spectrum=spectrum)
    except (ValueError, FloatingPointError) as exc:
        moment = _failed_moment(key[1], energy_range, mass_range,
                                f"inner_quadrature_or_input: {exc}")
    return key, moment


def _input_paths(data_root, reco_root, flux_root, run_manifest) -> dict[str, Path]:
    package = Path(__file__).resolve().parents[1]/"src"/"graal_theory"
    files = {f"code/{path.relative_to(package)}": path
             for path in package.rglob("*.py")}
    files.update({f"references/{path.name}": path for path in REFERENCES.glob("*.json")})
    files["workflow_script"] = Path(__file__).resolve()
    files.update({"data_root": Path(data_root), "reco_root": Path(reco_root),
                  "flux_root": Path(flux_root), "run_manifest": Path(run_manifest)})
    return files


def build_pilot_basis(output_dir, data_root, reco_root, flux_root, run_manifest,
                      *, workers: int) -> int:
    """Store every native raw moment; rerun same command to resume."""
    if not 1 <= workers <= 14:
        raise ValueError("workers must be between 1 and 14")
    inputs = _input_paths(data_root, reco_root, flux_root, run_manifest)
    data = load_native_sigma_root(Path(data_root))
    if data.status != "pilot":
        raise ValueError("exploratory workflow expects explicitly pilot Stage 07 data")
    keys = tuple((energy, pair, mass) for pair, energy, mass in data.keys)
    settings = {"policy": POLICY, "sobol_power": POWER, "energy_order": ENERGY_ORDER,
                "q_order": Q_ORDER, "angle_order": ANGLE_ORDER, "mode": "grid",
                "keys": keys}
    fingerprint = fingerprint_inputs("native", inputs, settings)
    output = Path(output_dir)
    checkpoint = BasisCheckpoint.open(output, target="native", keys=keys,
                                      fingerprint=fingerprint,
                                      resume=(output/"manifest.json").exists())
    if checkpoint.manifest.get("policy", POLICY) != POLICY:
        raise ValueError("basis policy differs from exploratory p6")
    if checkpoint.manifest.get("data_sha256", data.source_sha256) != data.source_sha256:
        raise ValueError("basis data fingerprint differs")
    checkpoint.manifest.update({"policy": POLICY, "settings": settings,
                                "input_paths": {name: str(path.resolve())
                                                for name, path in inputs.items()},
                                "data_sha256": data.source_sha256})
    checkpoint._write_manifest()
    pending = checkpoint.pending_keys()
    print(f"Exploratory native p6 basis: {len(pending)} pending of {len(keys)}; "
          f"workers={workers}", flush=True)
    if pending:
        spectra = {}
        for energy in sorted({key[0] for key in pending}):
            interval = tuple(map(float, data.energy_edges_gev[energy:energy+2]))
            spectra[energy] = native_flux_spectrum(
                Path(flux_root), Path(run_manifest), Path(reco_root), interval)
        tasks = []
        for key in pending:
            energy, pair, mass = key
            interval = tuple(map(float, data.energy_edges_gev[energy:energy+2]))
            edges = data.mass_edges_gev[pair]
            mass_range = (float(edges[mass]), float(edges[mass+1]))
            tasks.append((key, interval, mass_range, spectra[energy]))
        started = monotonic()
        def save(result):
            key, moment = result
            status = "preliminary_uncertified" if moment.status == "calculated" else moment.status
            reason = ("p6_only_no_convergence_check",) if moment.status == "calculated" else (
                moment.reason or moment.status,)
            certificate = BasisBinCertificate(moment, status, reason,
                                              float("nan"), None, (), 0, None)
            checkpoint.write(key, certificate)
            print(f"Saved {key}: {status}; elapsed={monotonic()-started:.1f}s", flush=True)
        if workers == 1:
            for task in tasks:
                save(_calculate(task))
        else:
            with ProcessPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(_calculate, task): task[0] for task in tasks}
                for future in as_completed(futures):
                    save(future.result())
        if fingerprint_inputs("native", inputs, settings) != fingerprint:
            raise ValueError("basis inputs changed during calculation")
    checkpoint.finish()
    counts = {}
    for item in checkpoint.manifest["bins"].values():
        counts[item["status"]] = counts.get(item["status"], 0)+1
    print(f"Exploratory native basis complete: {counts}; {output}", flush=True)
    return 0


def _load_basis(path: Path, data, data_root: Path) -> dict:
    manifest = json.loads((Path(path)/"manifest.json").read_text(encoding="utf-8"))
    if (manifest.get("target") != "native" or manifest.get("policy") != POLICY
            or not manifest.get("complete")
            or manifest.get("data_sha256") != data.source_sha256):
        raise ValueError("exploratory native basis manifest incomplete or incompatible")
    settings = manifest.get("settings")
    inputs = {name: Path(value) for name, value in manifest.get("input_paths", {}).items()}
    if (not settings or not inputs or
            fingerprint_inputs("native", inputs, settings) != manifest.get("fingerprint")):
        raise ValueError("exploratory basis input or code fingerprint changed")
    if "data_root" not in inputs or inputs["data_root"].resolve() != Path(data_root).resolve():
        raise ValueError("basis ROOT path differs from fit data")
    expected = {f"{energy}_{pair}_{mass}.npz" for pair, energy, mass in data.keys}
    if set(manifest.get("keys", ())) != expected:
        raise ValueError("basis keys differ from Stage 07 points")
    checkpoint = BasisCheckpoint(Path(path), manifest)
    if checkpoint.pending_keys():
        raise ValueError("exploratory basis has missing or corrupt bins")
    moments = {}
    for pair, energy, mass in data.keys:
        certificate = checkpoint.read((energy, pair, mass))
        moment = certificate.moment
        energy_range = data.energy_edges_gev[energy:energy+2]
        mass_range = data.mass_edges_gev[pair][mass:mass+2]
        if (certificate.status != ("preliminary_uncertified" if moment.status == "calculated"
                                   else moment.status)
                or moment.energy_rule != "native_flux" or moment.pair != pair
                or not np.allclose(moment.energy_range_gev, energy_range, rtol=0, atol=1e-12)
                or not np.allclose(moment.mass_range_gev, mass_range, rtol=0, atol=1e-12)):
            raise ValueError("basis certificate status, weighting or bin identity mismatch")
        moments[(pair, energy, mass)] = moment
    return moments


def _comparison_rows(data, objective, result):
    excluded = dict(objective.excluded)
    source = np.array([1., 0., 0.])
    fitted = (None if result.status != "exploratory_pilot" else
              np.array([1., result.theta_internal[0]-objective.anchor_g1,
                        result.theta_internal[1]-objective.anchor_g2]))
    rows = []
    for index, key in enumerate(data.keys):
        pair, energy, mass = key
        edges = data.mass_edges_gev[pair]
        moment = objective.moments.get(key)
        rows.append({
            "pair": pair, "energy_bin": energy, "mass_bin": mass,
            "mass_center_gev": float((edges[mass]+edges[mass+1])/2),
            "measured_sigma": float(data.sigma[index]),
            "stat_error": float(data.stat_error[index]),
            "source_sigma": None if moment is None else moment.evaluate(source).sigma,
            "fitted_sigma": None if moment is None or fitted is None else moment.evaluate(fitted).sigma,
            "status": "included" if moment is not None else "excluded",
            "reason": excluded.get(key),
        })
    return rows


def _plot(path: Path, rows: list[dict]):
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
                          fmt="o", markersize=3, color="black", label="GRAAL UV pilot")
            for field, color, label in (("source_sigma", "#bf4b25", "published couplings"),
                                        ("fitted_sigma", "#005c99", "pilot fit")):
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
    figure.suptitle("EXPLORATORY UV PILOT FIT — uncorrected background; p6 unverified")
    figure.tight_layout(rect=(0, 0, 1, .97))
    figure.savefig(path, format="pdf")


def fit_pilot(output_dir, data_root, basis_dir) -> int:
    """Fit two couplings to all available raw pilot moments; never certify."""
    output = Path(output_dir)
    if output.exists():
        raise FileExistsError(f"fit output already exists: {output}")
    data = load_native_sigma_root(Path(data_root))
    if data.status != "pilot":
        raise ValueError("exploratory fit requires pilot Stage 07 data")
    moments = _load_basis(Path(basis_dir), data, Path(data_root))
    objective = build_exploratory_gls(data, moments)
    source_theta = np.array([objective.anchor_g1, objective.anchor_g2])
    result = fit_delta_em(objective, source_theta)
    rows = _comparison_rows(data, objective, result)
    report = {
        "status": result.status,
        "purpose": "exploratory_p6_fit_only",
        "data_status": data.status,
        "data_provenance": data.provenance,
        "data_sha256": data.source_sha256,
        "model_fingerprint": objective.model_fingerprint,
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
        "limitations": ["background uncorrected", "run bootstrap absent",
                        "best quartet unresolved", "p6 convergence unchecked",
                        "excluded numerical masks are reported, not fitted"],
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
        _plot(staging/"native_comparison.pdf", rows)
        os.replace(staging, output)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    print(f"Exploratory pilot fit: {result.status}; included={len(objective.data.keys)}/"
          f"{len(data.keys)}; chi2={result.chi_square}; {output}", flush=True)
    return 0 if result.status == "exploratory_pilot" else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    basis = commands.add_parser("basis", help="compute resumable p6 native basis")
    basis.add_argument("--output-dir", type=Path, required=True)
    basis.add_argument("--data-root", type=Path, required=True)
    basis.add_argument("--reco-root", type=Path, required=True)
    basis.add_argument("--flux-root", type=Path, required=True)
    basis.add_argument("--run-manifest", type=Path, required=True)
    basis.add_argument("--workers", type=int, default=8)
    fit = commands.add_parser("fit", help="fit pilot ROOT from completed raw basis")
    fit.add_argument("--output-dir", type=Path, required=True)
    fit.add_argument("--data-root", type=Path, required=True)
    fit.add_argument("--basis-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "basis":
        return build_pilot_basis(args.output_dir, args.data_root, args.reco_root,
                                 args.flux_root, args.run_manifest, workers=args.workers)
    return fit_pilot(args.output_dir, args.data_root, args.basis_dir)


if __name__ == "__main__":
    raise SystemExit(main())
