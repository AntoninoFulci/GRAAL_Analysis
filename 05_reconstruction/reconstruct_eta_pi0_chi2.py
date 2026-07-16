#!/usr/bin/env python3
"""Standard reconstruction of gamma p -> p eta pi0: chi2 pairing, no BDT gate.

Reads the preselected tree and pairs the first four photons into an eta
and a pi0 by minimising the chi2 over the combination table.

Run:
    python -m reconstruction.reconstruct_eta_pi0_chi2 --input-dir data/selected
"""
import argparse
from pathlib import Path

from reconstruction.reco_core import AUTO_TREE, RecoConfig, run_reconstruction
from reconstruction.reco_physics import ETA_PI0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input-dir", type=Path, default=Path("data/selected"),
                   help="folder with the preselected ROOT files")
    p.add_argument("--output-file", type=Path,
                   default=Path("data/analyzed/reco_eta_pi0_chi2.root"))
    p.add_argument("--input-tree", default=AUTO_TREE,
                   help="tree inside the selected files; 'auto' takes whichever "
                        "known preselection tree is there (h85, or the older h80)")
    p.add_argument("--chi2-cut", type=float, default=10.0)
    args = p.parse_args()

    cfg = RecoConfig(
        input_dir=args.input_dir,
        output_file=args.output_file,
        input_tree=args.input_tree,
        output_tree="reco_eta_pi0_chi2",
        chi2_cut=args.chi2_cut,
    )
    run_reconstruction(cfg, ETA_PI0, gate=None)


if __name__ == "__main__":
    main()
