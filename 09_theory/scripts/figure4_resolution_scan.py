"""Save deterministic p5..p8 raw moments for one interior bin per Figure 4 panel.

Diagnostic only: these moments do not certify any bin or panel. Completed
panel files survive interruption and are skipped on a rerun.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import os
from pathlib import Path
import tempfile
from time import monotonic

import numpy as np

from graal_theory.cli import _figure4_model
from graal_theory.figure4_integration import _safe_predict
from graal_theory.figure4_reference import PAIR_MASS_AXES
from graal_theory.phase_space import SobolConfig


REFERENCES = Path(__file__).resolve().parents[1]/"references"
POWERS = (5, 6, 7, 8)
PAIRS = ("p_pi0", "p_eta", "eta_pi0")


def scan_bin(energy_bin: int, pair: str, mass_bin: int) -> dict:
    """Return raw physical moments; keep numerical gates for certification."""
    energy = (round(1.1+.1*energy_bin, 2), round(1.2+.1*energy_bin, 2))
    edges = np.linspace(*PAIR_MASS_AXES[pair], 11)
    mass = (float(edges[mass_bin]), float(edges[mass_bin+1]))
    model = _figure4_model(REFERENCES, "grid", 64, 48)
    start = monotonic()
    rows = []
    for power in POWERS:
        moment = _safe_predict(model, pair, energy, mass, 4, SobolConfig(power))
        rows.append({
            "power": power,
            "status": moment.status,
            "reason": moment.reason,
            "numerator": moment.numerator,
            "denominator": moment.denominator,
            "vertical_normalization": moment.vertical_normalization,
            "horizontal_normalization": moment.horizontal_normalization,
            "mass_numerator": moment.mass_numerator,
            "source_used_denominator": moment.source_used_denominator,
            "sigma": moment.sigma if moment.denominator > 0 else None,
            "accessible_energy_gev": moment.accessible_energy_gev,
            "accessible_mass_gev": moment.accessible_mass_gev,
            "energy_nodes_gev": moment.energy_nodes_gev.tolist(),
        })
    return {
        "purpose": "deterministic_resolution_diagnostic_only",
        "energy_bin": energy_bin,
        "pair": pair,
        "mass_bin": mass_bin,
        "energy_range_gev": list(energy),
        "mass_range_gev": list(mass),
        "energy_order": 4,
        "q_order": 64,
        "angle_order": 48,
        "mode": "grid",
        "moments": rows,
        "elapsed_seconds": monotonic()-start,
    }


def _path(output_dir: Path, energy_bin: int, pair: str, mass_bin: int) -> Path:
    return output_dir/f"e{energy_bin}-{pair}-b{mass_bin}.json"


def _save(path: Path, report: dict) -> None:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                     prefix=".figure4-scan-", suffix=".json",
                                     delete=False) as stream:
        temp = Path(stream.name)
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    os.replace(temp, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args(argv)
    if not 1 <= args.workers <= 14:
        parser.error("--workers must be between 1 and 14")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    tasks = [(energy, pair, 3) for energy in range(4) for pair in PAIRS]
    pending = []
    incomplete = False
    for task in tasks:
        path = _path(args.output_dir, *task)
        if path.exists():
            report = json.loads(path.read_text(encoding="utf-8"))
            if ((report["energy_bin"], report["pair"], report["mass_bin"]) != task
                    or [row["power"] for row in report["moments"]] != list(POWERS)
                    or report.get("purpose") != "deterministic_resolution_diagnostic_only"
                    or report.get("energy_order") != 4
                    or report.get("q_order") != 64
                    or report.get("angle_order") != 48
                    or report.get("mode") != "grid"):
                raise ValueError(f"incompatible existing scan file: {path}")
            incomplete |= any(row["status"] != "calculated" for row in report["moments"])
        else:
            pending.append(task)
    print(f"Figure 4 deterministic scan: {len(pending)} pending of 12; "
          f"powers p5..p8; workers={args.workers}", flush=True)
    if args.workers == 1:
        reports = (scan_bin(*task) for task in pending)
        for task, report in zip(pending, reports):
            _save(_path(args.output_dir, *task), report)
            incomplete |= any(row["status"] != "calculated" for row in report["moments"])
            print(f"Saved {task}: {report['elapsed_seconds']:.1f} s", flush=True)
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(scan_bin, *task): task for task in pending}
            for future in as_completed(futures):
                task = futures[future]
                report = future.result()
                _save(_path(args.output_dir, *task), report)
                incomplete |= any(row["status"] != "calculated" for row in report["moments"])
                print(f"Saved {task}: {report['elapsed_seconds']:.1f} s", flush=True)
    print(f"Saved 12 diagnostic bins in {args.output_dir}; "
          f"{'some moments masked' if incomplete else 'all moments calculated'}", flush=True)
    return 2 if incomplete else 0


if __name__ == "__main__":
    raise SystemExit(main())
