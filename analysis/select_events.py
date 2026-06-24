#!/usr/bin/env python3
# ============================================================
# Event preselection step.
#
# Runs AFTER the pre-analysis and BEFORE the reconstruct_* scripts.
# Reads the pre-analysis ROOT files (tree "h80", named "pre_*.root"),
# keeps only the events that can feed the two-meson reconstruction
# (more than one photon and exactly one recoil baryon), and writes
# the surviving events to a new file with the same tree structure,
# dropping the "pre_" filename prefix.
# ============================================================

import ROOT
import os

# Input/output folders
input_dir  = "pre_analyzed"   # pre-analysis output files (pre_*.root)
output_dir = "selected"       # preselected output files

# TTree name (set by the pre-analysis)
tree_name = "h80"

# Create the output folder if missing
os.makedirs(output_dir, exist_ok=True)

# All ROOT files starting with "pre_"
root_files = [
    f for f in os.listdir(input_dir)
    if f.endswith(".root") and f.startswith("pre_")
]

print(f"Found {len(root_files)} ROOT files")

for filename in root_files:

    input_path = os.path.join(input_dir, filename)

    # Drop the "pre_" prefix for the output name
    output_filename = filename.replace("pre_", "", 1)
    output_path = os.path.join(output_dir, output_filename)

    print(f"\nProcessing: {filename} -> {output_filename}")

    # Open input file
    input_file = ROOT.TFile.Open(input_path)
    if not input_file or input_file.IsZombie():
        print("  [ERROR] Cannot open file")
        continue

    tree = input_file.Get(tree_name)
    if not tree:
        print(f"  [ERROR] TTree '{tree_name}' not found")
        input_file.Close()
        continue

    # Output file
    output_file = ROOT.TFile(output_path, "RECREATE")

    # Clone the tree structure (no entries yet)
    selected_tree = tree.CloneTree(0)

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

    # Write and close
    selected_tree.Write("", ROOT.TObject.kOverwrite)  # reuse the key, avoid extra ;N cycles
    output_file.Close()
    input_file.Close()

print("\nSelection complete")
