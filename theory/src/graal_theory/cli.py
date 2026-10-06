"""Command-line prediction and validation entry points."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
import hashlib
import json
import sys
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


def _figure4_panel_task(task):
    import numpy as np
    from .amplitudes.nstar1535_grid import build_strong_t_grid
    from .amplitudes.production_loops import QuadratureSettings
    from .figure4_integration import certify_figure4_panel
    from .figure4_reference import PAIR_MASS_AXES
    from .models.eta_pi0_p_full import EtaPi0PFullModel

    references, energy, pair, order, power, seeds, mode, q_order, angle_order = task
    model = EtaPi0PFullModel.from_files(Path(references))
    parameters = model.parameters
    production = replace(parameters.production, quadrature=QuadratureSettings(
        q_order=q_order, angle_order=angle_order))
    model = replace(model, parameters=replace(parameters, production=production))
    if mode == "grid":
        grid = build_strong_t_grid(model.parameters.strong, model.parameters.vector_masses)
        model = replace(model, strong_grid=grid)
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
    except (ValueError, OSError, InvalidOperation, KeyError, TypeError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
