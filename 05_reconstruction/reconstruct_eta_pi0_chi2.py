#!/usr/bin/env python3
"""Standard reconstruction of gamma p -> p eta pi0: chi2 pairing, no BDT gate.

Reads the preselected tree and pairs the first four photons into an eta
and a pi0 by minimising chi2 over pairings derived from the eta-pi0 hypothesis.

Run:
    python -m reconstruction.reconstruct_eta_pi0_chi2 --input-dir results/_cache/03_selected
"""
from graal_common.physics.beam_profiles import BEAM_PROFILES, get_beam_profile
from graal_common.physics.energy_binning import add_energy_arguments, energy_binning_from_args

import argparse
from pathlib import Path

from reconstruction.runtime.cli_options import (
    add_common_reconstruction_arguments,
    reco_config_from_args,
)
from reconstruction.runtime.reco_core import AUTO_TREE, RecoConfig, run_reconstruction
from reconstruction.core.reco_physics import ETA_PI0, PARTNER_MASSES, partner_mass


def main():
    p = argparse.ArgumentParser(description=__doc__)
    add_common_reconstruction_arguments(
        p,
        default_output_file=Path("results/reco/reco_eta_pi0_chi2.root"),
        partner_help="recoil partner of the eta-pi0 system; sets the missing-"
        "mass the cut centres on (default proton)",
        fit_options_exposed=True,
    )
    p.add_argument("--profile", choices=BEAM_PROFILES, default=None)
    add_energy_arguments(p)
    args = p.parse_args()

    cfg = reco_config_from_args(
        args,
        output_tree="reco_eta_pi0_chi2",
        fit_options_exposed=True,
    )
    grid = energy_binning_from_args(args, args.profile)
    if grid is not None:
        cfg.energy_range_gev = grid.energy_range_gev
        cfg.beam_profile = args.profile
    run_reconstruction(cfg, ETA_PI0, gate=None)


if __name__ == "__main__":
    main()
