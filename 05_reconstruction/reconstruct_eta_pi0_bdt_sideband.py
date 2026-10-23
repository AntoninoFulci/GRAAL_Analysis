#!/usr/bin/env python3
"""Broad BDT-gated eta-pi0 reconstruction for background sidebands.

Keeps same topology guards, Stage-1 model, and best-pairing algorithm as
nominal BDT reconstruction. Disables the chi-square ceiling and
missing-mass window so raw eta mass, pi0 mass, and proton missing-mass
sidebands remain available downstream.
"""

import argparse
from pathlib import Path

from graal_common.physics.beam_profiles import BEAM_PROFILES, get_beam_profile
from graal_common.physics.energy_binning import add_energy_arguments, energy_binning_from_args
from reconstruction.core.reco_physics import ETA_PI0
from reconstruction.runtime.cli_options import (
    add_common_reconstruction_arguments,
    reco_config_from_args,
)
from reconstruction.runtime.reco_core import run_reconstruction
from reconstruction.runtime.stage1_gate import DEFAULT_MODEL_DIR, Stage1Gate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_reconstruction_arguments(
        parser,
        default_output_file=Path(
            "results/reco/reco_eta_pi0_bdt_sideband.root"
        ),
        partner_help="recoil partner of the eta-pi0 system",
    )
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=DEFAULT_MODEL_DIR,
        help="folder with bdt_stage1.json and stage1_threshold.txt",
    )
    parser.set_defaults(
        chi2_cut=float("inf"),
        missing_mass_window=0.0,
    )
    parser.add_argument("--profile", choices=BEAM_PROFILES, default=None)
    add_energy_arguments(parser)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    gate = Stage1Gate.load(args.model_dir)
    gate.check_hypothesis(ETA_PI0.hypothesis)
    config = reco_config_from_args(
        args,
        output_tree="reco_eta_pi0_bdt_sideband",
    )
    grid = energy_binning_from_args(args, args.profile)
    config.model_dir = args.model_dir
    if grid is not None:
        gate.check_profile(get_beam_profile(args.profile), energy_range_gev=grid.energy_range_gev)
        config.energy_range_gev = grid.energy_range_gev
        config.beam_profile = args.profile
    run_reconstruction(config, ETA_PI0, gate=gate)


if __name__ == "__main__":
    main()
