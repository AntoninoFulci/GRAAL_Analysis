#!/usr/bin/env python3
"""Reconstruction of gamma p -> p pi0 pi0: chi2 pairing, no BDT gate.

Reads the preselected tree and pairs the first four photons into the two
pi0 candidates that best match the pi0 mass.

There is no BDT variant of this channel: the stage-1 model is trained with 2pi0
as a background, so gating 2pi0 on it would be meaningless.

Run:
    python -m reconstruction.reconstruct_2pi0 --input-dir data/selected
"""
import argparse
from pathlib import Path

from reconstruction.runtime.cli_options import (
    add_common_reconstruction_arguments,
    reco_config_from_args,
)
from reconstruction.runtime.reco_core import AUTO_TREE, RecoConfig, run_reconstruction
from reconstruction.core.reco_physics import PARTNER_MASSES, TWO_PI0, partner_mass


def main():
    p = argparse.ArgumentParser(description=__doc__)
    # gamma p -> p pi0 pi0 is also single-proton recoil, so the same
    # missing-mass cut applies. Exposed here too, rather than inherited silently.
    add_common_reconstruction_arguments(
        p,
        default_output_file=Path("results/reco/reco_2pi0.root"),
        partner_help="recoil partner of the pi0 pi0 system (default proton)",
        fit_options_exposed=False,
    )
    args = p.parse_args()

    cfg = reco_config_from_args(
        args,
        output_tree="reco_2pi0",
        fit_options_exposed=False,
    )
    run_reconstruction(cfg, TWO_PI0, gate=None)


if __name__ == "__main__":
    main()
