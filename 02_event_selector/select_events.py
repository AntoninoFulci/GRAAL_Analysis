#!/usr/bin/env python3
# ============================================================
# Event preselection step.
#
# Runs AFTER the pre-analysis and BEFORE the reconstruct_* scripts.
# Reads the pre-analysis ROOT files (tree "h80", named "pre_*.root"),
# keeps only the events that can feed the two-meson reconstruction
# (more than one photon and exactly one forward charged track), and writes the
# surviving events to a new file as tree "h85", dropping the "pre_"
# filename prefix.
# ============================================================

import argparse
import os
from pathlib import Path

import ROOT

from graal_common.io.filesystem import atomic_output_directory

INPUT_TREE = "h80"   # written by 01_pre_analysis/PreAnalysis.C
OUTPUT_TREE = "h85"  # read by 05_reconstruction/runtime/reco_core.py


def parse_args():
    p = argparse.ArgumentParser(
        description="Preselect events for the two-meson reconstruction"
    )
    p.add_argument("--input-dir", default="data/02_pre_analyzed/pre_analisi",
                   help="folder with the pre_*.root files")
    p.add_argument("--output-dir", default="data/03_selected",
                   help="folder for the preselected files")
    p.add_argument(
        "--threads",
        type=int,
        default=os.cpu_count() or 1,
        help="RDataFrame worker threads (default: all available cores)",
    )
    return p.parse_args()


def _select_file(input_path: Path, output_path: Path) -> None:
    print(f"\nProcessing: {input_path.name} -> {output_path.name}")

    input_file = ROOT.TFile.Open(str(input_path))
    if not input_file or input_file.IsZombie():
        raise RuntimeError(f"cannot open {input_path}")
    try:
        tree = input_file.Get(INPUT_TREE)
        if not tree:
            keys = [k.GetName() for k in input_file.GetListOfKeys()]
            raise RuntimeError(
                f"tree '{INPUT_TREE}' not found in {input_path}; found: {keys}"
            )

        required = (
            "gammas",
            "fcharged_theta",
            "RunNumber",
            "Polarization",
            "Xstrip",
        )
        missing = [name for name in required if not tree.GetBranch(name)]
        if missing:
            raise RuntimeError(
                f"{input_path}: tree '{INPUT_TREE}' is missing branches: "
                + ", ".join(missing)
            )
        n_entries = int(tree.GetEntries())
    finally:
        input_file.Close()
    print(f"  Number of events: {n_entries}")

    frame = ROOT.RDataFrame(INPUT_TREE, str(input_path))
    selected = frame.Filter(
        "gammas.size() > 1 && fcharged_theta.size() == 1",
        "event preselection",
    )
    selected.Snapshot(OUTPUT_TREE, str(output_path))

    output_file = ROOT.TFile.Open(str(output_path), "READ")
    if not output_file or output_file.IsZombie():
        raise RuntimeError(f"cannot validate selected output {output_path}")
    try:
        output_tree = output_file.Get(OUTPUT_TREE)
        if not output_tree:
            raise RuntimeError(
                f"tree '{OUTPUT_TREE}' not found in selected output {output_path}"
            )
        n_selected = int(output_tree.GetEntries())
    finally:
        output_file.Close()
    print(f"  Selected events: {n_selected}")


def run(input_dir: Path, output_dir: Path, *, threads: int = 1) -> None:
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    if threads < 1:
        raise ValueError("threads must be at least 1")
    if ROOT.IsImplicitMTEnabled():
        ROOT.DisableImplicitMT()
    if threads > 1:
        ROOT.EnableImplicitMT(threads)
    print(f"RDataFrame implicit multithreading: {threads} threads")

    root_files = sorted(
        path
        for path in input_dir.iterdir()
        if path.is_file() and path.suffix == ".root" and path.name.startswith("pre_")
    )

    print(f"Found {len(root_files)} ROOT files")

    if not root_files:
        all_entries = sorted(path.name for path in input_dir.iterdir())
        if all_entries:
            sample = ", ".join(all_entries[:10])
            found_desc = f"found {len(all_entries)} other entries instead: {sample}"
        else:
            found_desc = "the directory is empty"
        raise RuntimeError(
            f"no files matching 'pre_*.root' in {str(input_dir)!r}; {found_desc}. "
            "Refusing to let the reconstruction run against stale files already in "
            f"{str(output_dir)!r}."
        )

    with atomic_output_directory(output_dir) as staging:
        for input_path in root_files:
            output_name = input_path.name.replace("pre_", "", 1)
            _select_file(input_path, staging / output_name)

    print("\nSelection complete")


def main():
    args = parse_args()
    run(Path(args.input_dir), Path(args.output_dir), threads=args.threads)


if __name__ == "__main__":
    main()
