"""Standalone extraction of gamma p -> eta pi0 p beam asymmetry."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from calibration.run_quality import DEFAULT_RUN_QUALITY_PATH
from graal_common.physics.beam_profiles import BEAM_PROFILES
from graal_common.parallel import validate_workers
from graal_common.physics.energy_binning import add_energy_arguments
from observable_extraction.samples import SAMPLES
from observable_extraction.core.binning import PHI_BIN_CHOICES
from observable_extraction import workflow, period_workflow


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw",
        type=Path,
        default=Path("results/reco/reco_eta_pi0_chi2_raw.root"),
    )
    parser.add_argument(
        "--raw-bdt",
        type=Path,
        default=Path("results/reco/reco_eta_pi0_bdt_raw.root"),
    )
    parser.add_argument("--sideband", type=Path)
    parser.add_argument("--signal-mc", type=Path)
    parser.add_argument(
        "--flux-file",
        type=Path,
        default=Path("data/00_external/flux_calibrated.root"),
    )
    parser.add_argument(
        "--run-manifest",
        type=Path,
        default=Path("config/support/run_manifest.csv"),
    )
    parser.add_argument("--run-quality", type=Path, default=DEFAULT_RUN_QUALITY_PATH,
                        help="explicit frozen run-quality policy JSON")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/beam_asymmetry"),
    )
    parser.add_argument("--plots-dir", type=Path, help="directory for diagnostic PDFs (default: output-dir)")
    parser.add_argument(
        "--nominal-sample",
        choices=tuple(SAMPLES),
        default="raw_bdt",
    )
    parser.add_argument(
        "--estimator",
        choices=("ratio", "likelihood", "both"),
        default="both",
    )
    parser.add_argument("--profile", choices=BEAM_PROFILES, default="uv")
    add_energy_arguments(parser)
    parser.add_argument("--phi-bins", type=int, choices=PHI_BIN_CHOICES, default=12)
    parser.add_argument("--best-binning", action="store_true",
                        help="fit 8/12/16 phi bins together and select each ratio point by fit quality; overrides --phi-bins")
    parser.add_argument("--mass-bins", type=int, default=10)
    parser.add_argument("--workers", type=lambda value: validate_workers(int(value)), default=1,
                        help="processes for independent fits or bootstrap replicas; default: 1")
    parser.add_argument("--bootstrap-replicas", type=int, default=0)
    parser.add_argument("--bootstrap-seed", type=int, default=1208)
    parser.add_argument(
        "--candle-mass-half-width",
        type=float,
        help="inclusive raw eta/pi0 candidate-mass half-width in GeV",
    )
    parser.add_argument(
        "--candle-balance-seed",
        type=int,
        default=20261024,
        help="fixed seed for equal-count candle core sampling",
    )
    parser.add_argument("--bootstrap-diagnostics-replicas", type=int, default=0,
                        help="paired run diagnostic only; never added to published covariance")
    parser.add_argument("--bootstrap-universe-manifest", type=Path,
                        help="explicit inclusive run universe, including zero-yield runs; standard manifest schema")
    parser.add_argument("--by-period", action="store_true",
                        help="extract exact manifest periods and pooled union with inclusive run accounting")
    parser.add_argument("--run-universe-manifest", type=Path,
                        help="inclusive input runs; otherwise use reconstruction run/state cutflow")
    return parser


def run(args: argparse.Namespace) -> int:
    """Dispatch parsed command options to their application workflow."""
    if args.by_period:
        return period_workflow.run_periods(args)
    return workflow.run_single(args)


def main(argv: Sequence[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
