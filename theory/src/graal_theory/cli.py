"""Command-line prediction and validation entry points."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from functools import lru_cache
import hashlib
import json
import sys
import time
from decimal import Decimal, InvalidOperation
from importlib import resources
from pathlib import Path

from .beam_asymmetry import predict_beam_asymmetry, predict_flux_weighted_asymmetry
from .convergence import compare_resolutions
from .models.eta_pi0_p import EtaPi0PModel
from .observables import HistogramSpec, predict_energy
from .phase_space import SobolConfig
from .run_output import RunBundle, write_run_bundle
from .sources import load_source_registry
from .validation import validate_bundle

_SOURCE_REFERENCES = Path(__file__).resolve().parents[2] / "references"
_REFERENCES = (
    _SOURCE_REFERENCES if _SOURCE_REFERENCES.is_dir()
    else resources.files("graal_theory.references")
)


def _energies(args: argparse.Namespace) -> list[float]:
    explicit = args.energy or []
    grid = (args.energy_min, args.energy_max, args.energy_step)
    if explicit and any(value is not None for value in grid):
        raise ValueError("choose either repeated --energy values or a complete grid")
    if explicit:
        values = [Decimal(value) for value in explicit]
    elif all(value is not None for value in grid):
        minimum, maximum, step = (Decimal(value) for value in grid)
        if step <= 0 or minimum > maximum:
            raise ValueError("energy grid requires positive step and min <= max")
        count = int((maximum - minimum) // step) + 1
        if count > 1000:
            raise ValueError("energy grid exceeds 1000 points")
        values = [minimum + index * step for index in range(count)]
    else:
        raise ValueError("provide --energy or all of --energy-min, --energy-max, --energy-step")
    if any(not value.is_finite() or value <= 0 for value in values):
        raise ValueError("all photon energies must be finite and positive")
    if len(set(values)) != len(values):
        raise ValueError("duplicate photon energy")
    return [float(value) for value in values]


def _predict(args: argparse.Namespace) -> int:
    energies = _energies(args)
    if not 4 <= args.sobol_power <= 23:
        raise ValueError("--sobol-power must be between 4 and 23 for nested convergence")
    model = EtaPi0PModel.from_files(
        _REFERENCES / "central_parameters.json", _REFERENCES / "sources.json"
    )
    low_config = SobolConfig(power=args.sobol_power)
    high_config = SobolConfig(power=args.sobol_power + 1)
    spec = HistogramSpec(bins=16)
    predictions = []
    reports = []
    for energy in energies:
        low = predict_energy(energy, model, low_config, spec)
        high = predict_energy(energy, model, high_config, spec)
        predictions.append(high)
        reports.append(compare_resolutions(low, high))
    bundle = RunBundle(
        model=model,
        predictions=tuple(predictions),
        convergence=tuple(reports),
        source_registry=load_source_registry(_REFERENCES / "sources.json"),
    )
    write_run_bundle(args.output, bundle, replace=args.replace)
    passed = sum(report.passed for report in reports)
    print(f"Eq. 43 partial prediction: {len(energies)} energies; convergence {passed}/{len(energies)}; bundle {args.output}")
    return 0


def _pilot_panel5(args: argparse.Namespace) -> int:
    import numpy as np

    from .photon_flux import load_calibrated_flux
    from .pilot_panel5 import write_pilot_panel5

    if args.sobol_power < 14:
        raise ValueError("--sobol-power must be at least 14 for the panel-5 pilot")
    if args.energy_nodes < 9:
        raise ValueError("--energy-nodes must be at least 9 for the panel-5 pilot")
    model = EtaPi0PModel.from_files(
        _REFERENCES / "central_parameters.json", _REFERENCES / "sources.json"
    )
    if (args.flux_root is None) != (args.run_manifest is None):
        raise ValueError("--flux-root and --run-manifest must be supplied together")
    config = SobolConfig(power=args.sobol_power, scramble=True, seed=args.seed)
    edges = np.linspace(1.40, 1.80, 11)
    if args.flux_root is None:
        spectrum = None
        prediction = predict_beam_asymmetry(
            1.20, 1.30, "eta_p", edges, model, config, energy_nodes=args.energy_nodes,
        )
    else:
        spectrum = load_calibrated_flux(args.flux_root, args.run_manifest, (1.20, 1.30))
        prediction = predict_flux_weighted_asymmetry(
            spectrum, "eta_p", edges, model, config, energy_bins=args.energy_nodes,
        )
    write_pilot_panel5(args.output, prediction, args.published_csv, model, flux_spectrum=spectrum)
    print(f"Eq. 43 partial panel-5 pilot: {args.output}")
    return 0


@lru_cache(maxsize=4)
def _figure4_model(references, mode, q_order, angle_order):
    from .amplitudes.nstar1535_grid import build_strong_t_grid
    from .amplitudes.production_loops import QuadratureSettings
    from .models.eta_pi0_p_full import EtaPi0PFullModel

    model = EtaPi0PFullModel.from_files(Path(references))
    parameters = model.parameters
    production = replace(parameters.production, quadrature=QuadratureSettings(
        q_order=q_order, angle_order=angle_order))
    model = replace(model, parameters=replace(parameters, production=production))
    if mode == "grid":
        grid = build_strong_t_grid(model.parameters.strong, model.parameters.vector_masses)
        model = replace(model, strong_grid=grid)
    return model


def _figure4_panel_task(task):
    import numpy as np
    from .figure4_integration import certify_figure4_panel
    from .figure4_reference import PAIR_MASS_AXES

    references, energy, pair, order, power, seeds, mode, q_order, angle_order = task
    model = _figure4_model(references, mode, q_order, angle_order)
    low, high = PAIR_MASS_AXES[pair]
    edges = np.linspace(low, high, 11)
    energy_range = (1.10+.10*energy, 1.20+.10*energy)
    panel = certify_figure4_panel(model, pair, energy_range, edges,
        energy_order=order, sobol_power=power, replica_seeds=seeds)
    return (energy, pair), panel


def _figure4_full(args: argparse.Namespace) -> int:
    from .figure4_comparison import compare_figure4, write_figure4_run
    from .figure4_integration import apply_pair_total_gate
    from .figure4_reference import load_published_theory_curves

    if not 1 <= args.energy_order <= 64:
        raise ValueError("--energy-order must be between 1 and 64")
    if not 4 <= args.sobol_power <= 23:
        raise ValueError("--sobol-power must be between 4 and 23")
    if not 8 <= args.replicas <= 64:
        raise ValueError("--replicas must be between 8 and 64")
    if not 1 <= args.workers <= 14:
        raise ValueError("--workers must be between 1 and 14")
    if args.q_order < 16 or args.angle_order < 16:
        raise ValueError("quadrature orders must be at least 16")
    if args.output.exists() and not args.replace:
        raise FileExistsError(f"output already exists: {args.output}")
    references = Path(_REFERENCES)
    seeds = tuple(range(2026, 2026+args.replicas))
    tasks = [(references, energy, pair, args.energy_order, args.sobol_power,
              seeds, args.mode, args.q_order, args.angle_order)
             for energy in range(4)
             for pair in ("p_pi0", "p_eta", "eta_pi0")]
    if args.workers == 1:
        results = map(_figure4_panel_task, tasks)
        panels = dict(results)
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            panels = dict(pool.map(_figure4_panel_task, tasks))

    panels = apply_pair_total_gate(panels)
    csv_path = references/"ajaka2008_figure4_theory.csv"
    metadata_path = references/"ajaka2008_figure4_theory.json"
    published = load_published_theory_curves(csv_path, metadata_path)
    comparison = compare_figure4(panels, published)
    source_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    parameter_hasher = hashlib.sha256()
    for name in ("sources.json", "central_parameters.json",
                 "nstar1535_reduced_parameters.json", "nstar1535_final_subtractions.json",
                 "nstar1535_vmd_masses.json", "eta_pi0_p_full_parameters.json"):
        parameter_hasher.update(name.encode())
        parameter_hasher.update((references/name).read_bytes())
    code_hasher = hashlib.sha256()
    for path in sorted(Path(__file__).resolve().parent.rglob("*.py")):
        code_hasher.update(str(path.relative_to(Path(__file__).resolve().parent)).encode())
        code_hasher.update(path.read_bytes())
    provenance = {
        "source_sha256": source_metadata["source_pdf_sha256"],
        "parameters_sha256": parameter_hasher.hexdigest(),
        "code_sha256": code_hasher.hexdigest(),
        "reference_csv_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
        "energy_weighting": "uniform",
        "azimuth_integration": "analytic_global_rotation",
    }
    write_figure4_run(args.output, panels, comparison, provenance,
                      replace_existing=args.replace)
    print(f"Figure 4 full-model calculation: {comparison.status}; bundle {args.output}")
    return 0 if comparison.status == "reproduced" else 2


def _basis_bin_task(task):
    from .figure4_basis import certify_basis_bin

    (references, key, energy_range, mass_range, rule, energy_order, power,
     seeds, mode, q_order, angle_order, spectrum, stat_error) = task
    model = _figure4_model(references, mode, q_order, angle_order)
    certificate = certify_basis_bin(
        model, key[1], energy_range, mass_range, energy_rule=rule,
        energy_order=energy_order, sobol_power=power, replica_seeds=seeds,
        flux_spectrum=spectrum, data_stat_error=stat_error)
    return key, certificate


def _ajaka_basis_inputs(references: Path) -> dict[str, Path]:
    inputs = {str(path.relative_to(references)): path
              for path in references.rglob("*.json")}
    inputs["ajaka2008_figure4_theory.csv"] = references/"ajaka2008_figure4_theory.csv"
    inputs.update({str(path.relative_to(Path(__file__).parent)): path
                   for path in Path(__file__).parent.rglob("*.py")})
    return inputs


def _figure4_basis_build(args: argparse.Namespace) -> int:
    import numpy as np
    from .figure4_fit_output import BasisCheckpoint, fingerprint_inputs
    from .figure4_reference import PAIR_MASS_AXES
    from .native_sigma import load_native_sigma_root
    from .photon_flux import native_flux_spectrum

    native_paths = (args.data_root, args.reco_root, args.flux_root, args.run_manifest)
    if args.target == "native" and any(path is None for path in native_paths):
        raise ValueError("native basis requires --data-root, --reco-root, --flux-root and --run-manifest")
    if args.target == "ajaka" and any(path is not None for path in native_paths):
        raise ValueError("Ajaka basis rejects native data inputs")
    if (not 1 <= args.workers <= 14 or not 1 <= args.energy_order <= 64
            or not 4 <= args.sobol_power <= 23 or not 8 <= args.replicas <= 64
            or args.q_order < 16 or args.angle_order < 16):
        raise ValueError("invalid basis numerical settings")
    references = Path(_REFERENCES)
    data = None
    spectra = {}
    if args.target == "native":
        data = load_native_sigma_root(args.data_root)
        keys = tuple((energy, pair, mass) for pair, energy, mass in data.keys)
        for energy in sorted({key[0] for key in keys}):
            energy_range = tuple(map(float, data.energy_edges_gev[energy:energy+2]))
            spectra[energy] = native_flux_spectrum(
                args.flux_root, args.run_manifest, args.reco_root, energy_range)
    else:
        keys = tuple((energy, pair, mass) for energy in range(4)
                     for pair in PAIR_MASS_AXES for mass in range(10))
    settings = {"energy_rule": "native_flux" if data is not None else "uniform",
                "energy_order": args.energy_order, "sobol_power": args.sobol_power,
                "replicas": args.replicas, "mode": args.mode,
                "q_order": args.q_order, "angle_order": args.angle_order,
                "keys": keys}
    inputs = _ajaka_basis_inputs(references)
    if data is not None:
        inputs.update({name: path for name, path in zip(
            ("data_root", "reco_root", "flux_root", "run_manifest"), native_paths)})
    fingerprint = fingerprint_inputs(args.target, inputs, settings)
    checkpoint = BasisCheckpoint.open(args.output, target=args.target, keys=keys,
                                      fingerprint=fingerprint, resume=args.resume)
    recorded_settings = json.loads(json.dumps(settings))
    if args.resume and checkpoint.manifest.get("settings") != recorded_settings:
        raise ValueError("basis run numerical settings mismatch")
    checkpoint.manifest["settings"] = recorded_settings
    code_hasher = hashlib.sha256()
    for path in sorted(Path(__file__).resolve().parent.rglob("*.py")):
        code_hasher.update(str(path.relative_to(Path(__file__).resolve().parent)).encode())
        code_hasher.update(path.read_bytes())
    code_sha256 = code_hasher.hexdigest()
    if args.resume and checkpoint.manifest.get("code_sha256") != code_sha256:
        raise ValueError("basis run code fingerprint mismatch")
    checkpoint.manifest["code_sha256"] = code_sha256
    if data is not None:
        if args.resume and checkpoint.manifest.get("data_sha256") != data.source_sha256:
            raise ValueError("basis run input ROOT hash mismatch")
        checkpoint.manifest["data_sha256"] = data.source_sha256
    checkpoint._write_manifest()
    pending = checkpoint.pending_keys()
    if not pending:
        checkpoint.finish()
        print(f"Figure 4 {args.target} basis already complete: {args.output}")
        return 0
    stat = dict(zip(keys, data.stat_error)) if data is not None else {}
    seeds = tuple(range(2026, 2026+args.replicas))
    tasks = []
    for key in pending:
        energy, pair, mass = key
        if data is None:
            energy_range = (1.10+.10*energy, 1.20+.10*energy)
            low, high = PAIR_MASS_AXES[pair]
            edges = np.linspace(low, high, 11)
            spectrum = None
        else:
            energy_range = tuple(map(float, data.energy_edges_gev[energy:energy+2]))
            edges = data.mass_edges_gev[pair]
            spectrum = spectra[energy]
        tasks.append((references, key, energy_range,
                      (float(edges[mass]), float(edges[mass+1])),
                      settings["energy_rule"], args.energy_order, args.sobol_power,
                      seeds, args.mode, args.q_order, args.angle_order,
                      spectrum, None if data is None else float(stat[key])))
    start = time.monotonic()
    completed = 0
    def save(result):
        nonlocal completed
        key, certificate = result
        checkpoint.write(key, certificate)
        completed += 1
        print(f"{completed}/{len(tasks)} {key} {certificate.status} elapsed={time.monotonic()-start:.1f}s", flush=True)
    try:
        if args.workers == 1:
            for task in tasks:
                save(_basis_bin_task(task))
        else:
            with ProcessPoolExecutor(max_workers=args.workers) as pool:
                for offset in range(0, len(tasks), args.workers):
                    futures = [pool.submit(_basis_bin_task, task)
                               for task in tasks[offset:offset+args.workers]]
                    for future in as_completed(futures):
                        save(future.result())
        if fingerprint_inputs(args.target, inputs, settings) != fingerprint:
            raise ValueError("basis inputs or code changed during calculation")
    except Exception:
        pending_now = checkpoint.pending_keys()
        print(f"basis interrupted: {completed}/{len(tasks)} new bins, "
              f"next missing={pending_now[0] if pending_now else 'none'}, "
              f"elapsed={time.monotonic()-start:.1f}s", file=sys.stderr, flush=True)
        raise
    checkpoint.finish()
    statuses = {}
    for record in checkpoint.manifest["bins"].values():
        statuses[record["status"]] = statuses.get(record["status"], 0) + 1
    print(f"Figure 4 {args.target} basis complete: {statuses}; {args.output}")
    return 0 if set(statuses) <= {"calculated", "masked_kinematic"} else 2


def _figure4_fit_command(args: argparse.Namespace) -> int:
    import numpy as np
    from .figure4_fit import build_gls, fit_delta_em
    from .figure4_fit_output import (BasisCheckpoint, basis_panels,
                                      fingerprint_inputs, write_fit_bundle)
    from .figure4_comparison import compare_figure4
    from .figure4_reference import load_published_theory_curves
    from .native_sigma import load_native_sigma_root

    if args.data_root.suffix.lower() != ".root":
        raise ValueError("fit data must be Stage 07 ROOT, never digitized theory CSV")
    if args.basis_native.resolve() == args.basis_ajaka.resolve():
        raise ValueError("native and Ajaka basis inputs must be distinct")
    if args.output.resolve() in (args.basis_native.resolve(), args.basis_ajaka.resolve()):
        raise ValueError("fit output must be distinct from basis input")
    checkpoints = []
    for path, target in ((args.basis_native, "native"), (args.basis_ajaka, "ajaka")):
        manifest = json.loads((path/"manifest.json").read_text(encoding="utf-8"))
        if manifest.get("target") != target or not manifest.get("complete"):
            raise ValueError(f"{target} basis manifest incomplete or wrong target")
        checkpoint = BasisCheckpoint(path, manifest)
        if checkpoint.pending_keys():
            raise ValueError(f"{target} basis manifest incomplete or corrupt")
        checkpoints.append(checkpoint)
    native, ajaka = checkpoints
    if native.manifest.get("code_sha256") != ajaka.manifest.get("code_sha256"):
        raise ValueError("native and Ajaka basis code fingerprint mismatch")
    references = Path(_REFERENCES)
    if fingerprint_inputs("ajaka", _ajaka_basis_inputs(references),
                          ajaka.manifest.get("settings", {})) != ajaka.manifest["fingerprint"]:
        raise ValueError("Ajaka basis source or code fingerprint differs from current checkout")
    data = load_native_sigma_root(args.data_root, require_final=args.require_final)
    if native.manifest.get("data_sha256") != data.source_sha256:
        raise ValueError("native basis input ROOT hash differs from fit data")
    native_certificates = {
        (pair, energy, mass): native.read((energy, pair, mass))
        for pair, energy, mass in data.keys}
    if set(native.manifest["keys"]) != {
            f"{energy}_{pair}_{mass}.npz" for pair, energy, mass in data.keys}:
        raise ValueError("native basis keys differ from selected Stage 07 rows")
    objective = build_gls(data, native_certificates)
    source_theta = np.array([objective.anchor_g1, objective.anchor_g2])
    fit = fit_delta_em(objective, source_theta)
    ajaka_certificates = {
        ajaka._key_from_name(name): ajaka.read(ajaka._key_from_name(name))
        for name in ajaka.manifest["keys"]}
    for certificate in ajaka_certificates.values():
        moment = certificate.moment
        if (moment.status == "calculated" and
                (moment.model_fingerprint != objective.model_fingerprint
                 or not np.allclose((moment.anchor_g1, moment.anchor_g2), source_theta))):
            raise ValueError("Ajaka and native basis model or source anchor mismatch")
    ajaka_settings = ajaka.manifest.get("settings", {})
    order = ajaka_settings.get("energy_order", 4)
    power = ajaka_settings.get("sobol_power", 8)
    seeds = tuple(range(2026, 2026+ajaka_settings.get("replicas", 8)))
    sourced = basis_panels(ajaka_certificates, np.array([1., 0., 0.]),
                          energy_order=order, sobol_power=power,
                          replica_seeds=seeds, mode=ajaka_settings.get("mode", "grid"))
    published = load_published_theory_curves(
        references/"ajaka2008_figure4_theory.csv",
        references/"ajaka2008_figure4_theory.json")
    sourced_comparison = compare_figure4(sourced, published)
    fitted = fitted_comparison = None
    if fit.status in ("fit_computed", "exploratory_pilot"):
        coefficients = np.array([1., fit.theta_internal[0]-source_theta[0],
                                 fit.theta_internal[1]-source_theta[1]])
        fitted = basis_panels(ajaka_certificates, coefficients,
                              energy_order=order, sobol_power=power,
                              replica_seeds=seeds, mode=ajaka_settings.get("mode", "grid"))
        fitted_comparison = compare_figure4(fitted, published)
    metadata = json.loads((references/"ajaka2008_figure4_theory.json").read_text())
    parameter_hasher = hashlib.sha256()
    for name in ("sources.json", "central_parameters.json",
                 "nstar1535_reduced_parameters.json", "nstar1535_final_subtractions.json",
                 "nstar1535_vmd_masses.json", "eta_pi0_p_full_parameters.json"):
        parameter_hasher.update(name.encode())
        parameter_hasher.update((references/name).read_bytes())
    provenance = {
        "source_sha256": metadata["source_pdf_sha256"],
        "parameters_sha256": parameter_hasher.hexdigest(),
        "code_sha256": ajaka.manifest["code_sha256"],
        "basis_ajaka_fingerprint": ajaka.manifest["fingerprint"],
        "basis_native_fingerprint": native.manifest["fingerprint"],
        "data_sha256": data.source_sha256,
        "energy_weighting": "uniform for Ajaka; measured flux for native fit",
        "data_status": data.status,
    }
    write_fit_bundle(args.output, sourced, fitted, sourced_comparison,
                     fitted_comparison, fit, provenance, data.covariance)
    print(f"Figure 4 source={sourced_comparison.status}; fit={fit.status}; bundle {args.output}")
    return 0 if fit.status == "fit_computed" and sourced_comparison.status == "reproduced" else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="graal-theory")
    commands = parser.add_subparsers(dest="command", required=True)
    predict = commands.add_parser("predict", help="calculate Eq. 43 partial observables")
    predict.add_argument("--energy", action="append")
    predict.add_argument("--energy-min")
    predict.add_argument("--energy-max")
    predict.add_argument("--energy-step")
    predict.add_argument("--sobol-power", type=int, default=15)
    predict.add_argument("--output", type=Path, required=True)
    predict.add_argument("--replace", action="store_true")
    validate = commands.add_parser("validate", help="compare a prediction bundle with published theory")
    validate.add_argument("--bundle", type=Path, required=True)
    pilot = commands.add_parser("pilot-panel5", help="plot partial beam asymmetry against Ajaka panel 5")
    pilot.add_argument("--published-csv", type=Path, required=True)
    pilot.add_argument("--sobol-power", type=int, default=15)
    pilot.add_argument("--energy-nodes", type=int, default=9)
    pilot.add_argument("--seed", type=int, default=2026)
    pilot.add_argument("--flux-root", type=Path)
    pilot.add_argument("--run-manifest", type=Path)
    pilot.add_argument("--output", type=Path, required=True)
    figure4 = commands.add_parser("figure4-full", help="certify full coherent Figure 4 curves")
    figure4.add_argument("--output", type=Path, required=True)
    figure4.add_argument("--energy-order", type=int, default=4)
    figure4.add_argument("--sobol-power", type=int, default=8)
    figure4.add_argument("--replicas", type=int, default=8)
    figure4.add_argument("--workers", type=int, default=4)
    figure4.add_argument("--q-order", type=int, default=64)
    figure4.add_argument("--angle-order", type=int, default=48)
    figure4.add_argument("--mode", choices=("direct", "grid"), default="grid")
    figure4.add_argument("--replace", action="store_true")
    basis = commands.add_parser("figure4-basis-build", help="build resumable Ajaka or native basis")
    basis.add_argument("--target", choices=("ajaka", "native"), required=True)
    basis.add_argument("--output", type=Path, required=True)
    basis.add_argument("--data-root", type=Path)
    basis.add_argument("--reco-root", type=Path)
    basis.add_argument("--flux-root", type=Path)
    basis.add_argument("--run-manifest", type=Path)
    basis.add_argument("--energy-order", type=int, default=4)
    basis.add_argument("--sobol-power", type=int, default=8)
    basis.add_argument("--replicas", type=int, default=8)
    basis.add_argument("--workers", type=int, default=1)
    basis.add_argument("--q-order", type=int, default=64)
    basis.add_argument("--angle-order", type=int, default=48)
    basis.add_argument("--mode", choices=("direct", "grid"), default="grid")
    basis.add_argument("--resume", action="store_true")
    fit = commands.add_parser("figure4-fit", help="fit certified native basis and compare Ajaka curves")
    fit.add_argument("--data-root", type=Path, required=True)
    fit.add_argument("--basis-native", type=Path, required=True)
    fit.add_argument("--basis-ajaka", type=Path, required=True)
    fit.add_argument("--output", type=Path, required=True)
    fit.add_argument("--require-final", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "predict":
            return _predict(args)
        if args.command == "validate":
            result = validate_bundle(args.bundle, _REFERENCES)
            print(f"scientific validation: {result['status']}; bundle {args.bundle}")
            return 0 if result["status"] == "validated" else 2
        if args.command == "pilot-panel5":
            return _pilot_panel5(args)
        if args.command == "figure4-full":
            return _figure4_full(args)
        if args.command == "figure4-basis-build":
            return _figure4_basis_build(args)
        if args.command == "figure4-fit":
            return _figure4_fit_command(args)
    except (ValueError, OSError, InvalidOperation, KeyError, TypeError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
