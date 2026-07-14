#!/usr/bin/env python3
# ============================================================
# Event preselection step.
#
# Runs AFTER the pre-analysis and BEFORE the reconstruct_* scripts.
# Reads the pre-analysis ROOT files (tree "h80", named "pre_*.root"),
# keeps only the events that can feed the two-meson reconstruction
# (more than one photon and exactly one recoil baryon), and writes the
# surviving events to a new file as tree "h85", dropping the "pre_"
# filename prefix.
# ============================================================

import argparse
import os

import ROOT

INPUT_TREE = "h80"   # written by 01_pre_analysis/PreAnalysis.C
OUTPUT_TREE = "h85"  # read by 03_analysis/reco_core.py


def parse_args():
    p = argparse.ArgumentParser(
        description="Preselect events for the two-meson reconstruction"
    )
    p.add_argument("--input-dir", default="pre_analyzed",
                   help="folder with the pre_*.root files")
    p.add_argument("--output-dir", default="selected",
                   help="folder for the preselected files")
    return p.parse_args()


def main():
    args = parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    root_files = [
        f for f in os.listdir(args.input_dir)
        if f.endswith(".root") and f.startswith("pre_")
    ]

    print(f"Found {len(root_files)} ROOT files")

    if not root_files:
        all_entries = sorted(os.listdir(args.input_dir))
        if all_entries:
            sample = ", ".join(all_entries[:10])
            found_desc = f"found {len(all_entries)} other entries instead: {sample}"
        else:
            found_desc = "the directory is empty"
        raise RuntimeError(
            f"no files matching 'pre_*.root' in {args.input_dir!r}; {found_desc}. "
            "Refusing to let the reconstruction run against stale files already in "
            f"{args.output_dir!r}."
        )

    for filename in root_files:
        input_path = os.path.join(args.input_dir, filename)

        # Drop the "pre_" prefix for the output name
        output_filename = filename.replace("pre_", "", 1)
        output_path = os.path.join(args.output_dir, output_filename)

        print(f"\nProcessing: {filename} -> {output_filename}")

        input_file = ROOT.TFile.Open(input_path)
        if not input_file or input_file.IsZombie():
            raise RuntimeError(f"cannot open {input_path}")

        tree = input_file.Get(INPUT_TREE)
        if not tree:
            keys = [k.GetName() for k in input_file.GetListOfKeys()]
            raise RuntimeError(
                f"tree '{INPUT_TREE}' not found in {input_path}; found: {keys}"
            )

        output_file = ROOT.TFile(output_path, "RECREATE")

        # CloneTree keeps the source name ("h80"), so rename explicitly.
        selected_tree = tree.CloneTree(0)
        selected_tree.SetName(OUTPUT_TREE)
        selected_tree.SetTitle(OUTPUT_TREE)

        n_entries = tree.GetEntries()
        print(f"  Number of events: {n_entries}")

        n_selected = 0
        for event in tree:
            # keep events with >1 photon and exactly one recoil baryon
            if (
                event.gammas.size() > 1 and
                event.protons.size() +
                event.neutrons.size() +
                event.deuterons.size() == 1
            ):
                selected_tree.Fill()
                n_selected += 1

        print(f"  Selected events: {n_selected}")

        selected_tree.Write("", ROOT.TObject.kOverwrite)
        output_file.Close()
        input_file.Close()

    print("\nSelection complete")


if __name__ == "__main__":
    main()
