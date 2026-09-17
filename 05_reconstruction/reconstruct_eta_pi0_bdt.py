#!/usr/bin/env python3
"""Reconstruction of gamma p -> p eta pi0 behind the stage-1 BDT gate.

Identical to reconstruct_eta_pi0_chi2.py except that every event must first be
accepted by the stage-1 BDT. Both scripts share reco_core, so any difference
between their outputs is the gate and nothing else.

Run:
    python -m reconstruction.reconstruct_eta_pi0_bdt --input-dir data/03_selected
"""
import argparse
from pathlib import Path

from reconstruction.runtime.cli_options import (
    add_common_reconstruction_arguments,
    reco_config_from_args,
)
from reconstruction.runtime.reco_core import AUTO_TREE, RecoConfig, run_reconstruction
from reconstruction.core.reco_physics import ETA_PI0, PARTNER_MASSES, partner_mass
from reconstruction.runtime.stage1_gate import DEFAULT_MODEL_DIR, Stage1Gate


def main():
    p = argparse.ArgumentParser(description=__doc__)
    add_common_reconstruction_arguments(
        p,
        default_output_file=Path("results/reco/reco_eta_pi0_bdt.root"),
        partner_help="recoil partner of the eta-pi0 system; sets the missing-"
        "mass the cut centres on (default proton)",
        fit_options_exposed=True,
    )
    p.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR,
                   help="folder with bdt_stage1.json and stage1_threshold.txt")
    args = p.parse_args()

    gate = Stage1Gate.load(args.model_dir)
    # The model must have been trained to find what this script reconstructs.
    # It would score a model trained on any other final state just as happily.
    gate.check_hypothesis(ETA_PI0.hypothesis)

    cfg = reco_config_from_args(
        args,
        output_tree="reco_eta_pi0_bdt",
        fit_options_exposed=True,
    )
    run_reconstruction(cfg, ETA_PI0, gate=gate)


if __name__ == "__main__":
    main()
