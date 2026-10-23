#!/usr/bin/env python3
"""Parse the strip-calibration CLI and report external failures."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

from calibration.run_manifest import ManifestError
from calibration.strip_energy_flux import StripEnergyFluxError
from calibration.flux_build import run

_DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "results_test/calibration"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build calibrated run-specific flux ROOT histograms.",
        allow_abbrev=False,
    )
    parser.add_argument("--preanalysis-dir", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--flux", required=True, type=Path)
    parser.add_argument(
        "--target",
        choices=("P", "D"),
        help="calibrate only runs with this manifest target",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_DEFAULT_OUTPUT_DIR,
        help=f"directory for flux_calibrated.root; default: {_DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument("--min-events-per-strip", type=int, default=1)
    parser.add_argument("--max-mad-gev", type=float, default=0.005)
    parser.add_argument("--monotonic-tolerance-gev", type=float, default=0.002)
    parser.add_argument(
        "--progress-every-events",
        type=int,
        default=1_000_000,
        help="emit h80 event progress every N entries; 0 disables inner updates",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=os.cpu_count() or 1,
        help="RDataFrame worker threads; default: all available CPU cores",
    )
    parser.add_argument(
        "--samples-per-run-strip",
        type=int,
        default=256,
        help="maximum beam-energy samples retained per run/strip",
    )
    parser.add_argument("--binning", action="append", default=[])
    parser.add_argument("--cache-root", type=Path, help="content-addressed ROOT+QA cache")
    parser.add_argument("--cache-scope", choices=("production", "diagnostic"), default="production")
    return parser.parse_args()



def main() -> int:
    args = parse_args()
    try:
        if args.cache_root is not None:
            from calibration.calibration_cache import run_cached_calibration
            return run_cached_calibration(args, run, driver=Path(__file__))
        return run(args)
    except (ManifestError, StripEnergyFluxError, OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
