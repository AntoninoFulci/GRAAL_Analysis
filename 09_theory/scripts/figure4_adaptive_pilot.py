"""Run one measured Figure 4 control bin with adaptive Sobol resolution.

This command runs the full physical model. It is intentionally a user-run,
long calculation; each invocation writes one durable result after completion.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile
from time import monotonic

from graal_theory.cli import _figure4_model
from graal_theory.figure4_integration import (
    adaptive_figure4_bin_checks, assemble_figure4_panel,
)


CONTROLS = {
    "lower": ((1.10, 1.20), (1.52, 1.56)),
    "upper": ((1.40, 1.50), (1.60, 1.64)),
}
REFERENCES = Path(__file__).resolve().parents[1]/"references"
SEEDS = tuple(range(2026, 2034))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control", choices=tuple(CONTROLS), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--min-power", type=int, default=5)
    parser.add_argument("--max-power", type=int, default=8)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error(f"output already exists: {args.output}")

    energy, mass = CONTROLS[args.control]
    print(f"Starting {args.control}: E={energy}, M={mass}, "
          f"Sobol p{args.min_power}..p{args.max_power}", flush=True)
    start = monotonic()
    model = _figure4_model(REFERENCES, "grid", 64, 48)
    checks = adaptive_figure4_bin_checks(model, "p_eta", energy, mass,
        energy_order=4, min_power=args.min_power, max_power=args.max_power,
        replica_seeds=SEEDS)
    panel = assemble_figure4_panel("p_eta", energy, mass, (checks,),
        energy_order=4, sobol_power=args.max_power,
        replica_seeds=SEEDS, mode="grid")
    certified = panel.bins[0]
    report = {
        "control": args.control,
        "pair": "p_eta",
        "energy_range_gev": energy,
        "mass_range_gev": mass,
        "selected_power": checks.selected_power,
        "confirmation_power": (checks.selected_power+2
                               if checks.confirmation is not None else None),
        "resolution_policy": "two_nested_refinements_and_span",
        "min_power": args.min_power,
        "max_power": args.max_power,
        "energy_order": 4,
        "q_order": 64,
        "angle_order": 48,
        "replica_seeds": SEEDS,
        "mode": "grid",
        "status": certified.status,
        "reason": certified.reason,
        "sigma": certified.sigma if certified.moment.denominator > 0 else None,
        "denominator": certified.moment.denominator,
        "numerical_error_bound": (certified.numerical_error_bound
                                  if certified.status == "calculated" else None),
        "checks": certified.error_components,
        "elapsed_seconds": monotonic()-start,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=args.output.parent,
                                     prefix=".figure4-pilot-", suffix=".json",
                                     delete=False) as stream:
        temp = Path(stream.name)
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    os.replace(temp, args.output)
    print(f"Finished {args.control}: {certified.status}, p{checks.selected_power}, "
          f"{report['elapsed_seconds']:.1f} s; {args.output}", flush=True)
    return 0 if certified.status == "calculated" else 2


if __name__ == "__main__":
    raise SystemExit(main())
