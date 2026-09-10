#!/usr/bin/env python3
"""Build hash-bound complete-run inventory for polarization reconstruction."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

from contracts import PolarizationContractError, sha256_file, validate_gate0_handoff
from figure4_config import load_figure4_config
from inventory_builder import build_reco_inventory
from reco_inventory import load_gate0_run_numbers
from root_events import scan_reco_run_numbers


CANONICAL_RUNS = "results/observable_runs/run_manifest_observables.csv"


def _inside(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reco", type=Path, nargs="+", required=True)
    parser.add_argument("--processed-runs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--config", type=Path, default=Path("config/physics/polarization_v1.json")
    )
    parser.add_argument(
        "--handoff", type=Path, default=Path("results/observable_runs/HANDOFF.json")
    )
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    root = args.repository_root.resolve()
    config = _inside(root, args.config)
    handoff = _inside(root, args.handoff)
    reco = tuple(_inside(root, path) for path in args.reco)
    ledger = _inside(root, args.processed_runs)
    output = _inside(root, args.output)
    try:
        validate_gate0_handoff(handoff, root)
        layout = load_figure4_config(config)
        expected_runs = load_gate0_run_numbers(
            root / CANONICAL_RUNS, target=layout.target
        )
        observed_runs = scan_reco_run_numbers(
            reco, tree_name=layout.tree, vectors=layout.vectors
        )
        commit = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        payload = build_reco_inventory(
            repository_root=root,
            output_path=output,
            reco_paths=reco,
            processed_run_ledger=ledger,
            gate0_handoff_sha256=sha256_file(handoff),
            gate0_run_numbers=expected_runs,
            observed_event_run_numbers=observed_runs,
            tree=layout.tree,
            vectors=layout.vectors,
            producer_commit=commit,
        )
    except (
        OSError,
        subprocess.CalledProcessError,
        PolarizationContractError,
    ) as exc:
        print(f"Reconstruction inventory blocked: {exc}", file=sys.stderr)
        return 1
    print(
        f"Wrote reconstruction inventory: {output} "
        f"({len(payload['run_numbers'])} processed runs, "
        f"{len(payload['zero_selected_event_run_numbers'])} zero-event runs)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
