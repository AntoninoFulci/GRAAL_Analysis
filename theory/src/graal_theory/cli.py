"""Command-line prediction and validation entry points."""

from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
from importlib import resources
from pathlib import Path
import sys

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
    args = parser.parse_args(argv)
    try:
        if args.command == "predict":
            return _predict(args)
        if args.command == "validate":
            result = validate_bundle(args.bundle, _REFERENCES)
            print(f"scientific validation: {result['status']}; bundle {args.bundle}")
            return 0 if result["status"] == "validated" else 2
    except (ValueError, OSError, InvalidOperation, KeyError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
