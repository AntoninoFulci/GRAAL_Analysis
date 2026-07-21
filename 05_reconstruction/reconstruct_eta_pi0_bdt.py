#!/usr/bin/env python3
"""Reconstruction of gamma p -> p eta pi0 behind the stage-1 BDT gate.

Identical to reconstruct_eta_pi0_chi2.py except that every event must first be
accepted by the stage-1 BDT. Both scripts share reco_core, so any difference
between their outputs is the gate and nothing else.

Run:
    python -m reconstruction.reconstruct_eta_pi0_bdt --input-dir data/selected
"""
import argparse
from pathlib import Path

from reconstruction.reco_core import AUTO_TREE, RecoConfig, run_reconstruction
from reconstruction.reco_physics import ETA_PI0, PARTNER_MASSES, partner_mass
from reconstruction.stage1_gate import DEFAULT_MODEL_DIR, Stage1Gate


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input-dir", type=Path, default=Path("data/selected"),
                   help="folder with the preselected ROOT files")
    p.add_argument("--output-file", type=Path,
                   default=Path("results/reco/reco_eta_pi0_bdt.root"))
    p.add_argument("--input-tree", default=AUTO_TREE,
                   help="tree inside the selected files; 'auto' takes whichever "
                        "known preselection tree is there (h85, or the older h80)")
    p.add_argument("--chi2-cut", type=float, default=10.0)
    p.add_argument("--partner", choices=sorted(PARTNER_MASSES), default="proton",
                   help="recoil partner of the eta-pi0 system; sets the missing-"
                        "mass the cut centres on (default proton)")
    p.add_argument("--missing-mass-window", type=float, default=0.06,
                   help="half-width [GeV] of the missing-mass window around the "
                        "partner; <= 0 disables the cut (default 0.06)")
    p.add_argument("--no-fit", action="store_true",
                   help="disable the kinematic fit; fall back to the missing-mass "
                        "cut for selection")
    p.add_argument("--fit-cl", type=float, default=0.01,
                   help="keep events whose kinematic-fit confidence level is above "
                        "this (default 0.01)")
    p.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR,
                   help="folder with bdt_stage1.json and stage1_threshold.txt")
    args = p.parse_args()

    gate = Stage1Gate.load(args.model_dir)
    # The model must have been trained to find what this script reconstructs.
    # It would score a model trained on any other final state just as happily.
    gate.check_hypothesis(ETA_PI0.hypothesis)

    cfg = RecoConfig(
        input_dir=args.input_dir,
        output_file=args.output_file,
        input_tree=args.input_tree,
        output_tree="reco_eta_pi0_bdt",
        chi2_cut=args.chi2_cut,
        partner_mass=partner_mass(args.partner),
        missing_mass_window=args.missing_mass_window,
        do_fit=not args.no_fit,
        fit_cl=args.fit_cl,
    )
    run_reconstruction(cfg, ETA_PI0, gate=gate)


if __name__ == "__main__":
    main()
