#!/usr/bin/env python3
"""Adapt generated eta-pi0 MC to detector-like h85 reconstruction input."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import tempfile

import ROOT

from graal_common.io.filesystem import atomic_output_directory


INPUT_TREE = "mc"
OUTPUT_TREE = "h85"
OUTPUT_NAME = "eta_pi0_mc_selected.root"
SOURCE_BRANCHES = (
    "beam",
    "eta_gamma1",
    "eta_gamma2",
    "pi0_gamma1",
    "pi0_gamma2",
    "proton",
)
OUTPUT_BRANCHES = (
    "beam",
    "gammas",
    "protons",
    "neutrons",
    "RunNumber",
    "Polarization",
    "Xstrip",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-file",
        type=Path,
        default=Path("03_mc_simulation/data/eta_pi0_mc.root"),
        help="generated signal-MC ROOT file containing tree 'mc'",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/signal_mc_selected"),
        help="atomically published directory containing detector-like h85 input",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=os.cpu_count() or 1,
        help="RDataFrame worker threads (default: all available cores)",
    )
    return parser


def _validate_source(path: Path) -> int:
    if not path.is_file():
        raise FileNotFoundError(f"signal MC input file not found: {path}")
    source = ROOT.TFile.Open(str(path), "READ")
    if not source or source.IsZombie():
        raise RuntimeError(f"cannot open signal MC input file: {path}")
    try:
        tree = source.Get(INPUT_TREE)
        if not tree:
            raise RuntimeError(f"tree '{INPUT_TREE}' not found in {path}")
        available = {branch.GetName() for branch in tree.GetListOfBranches()}
        missing = [name for name in SOURCE_BRANCHES if name not in available]
        if missing:
            raise RuntimeError(
                f"tree '{INPUT_TREE}' in {path} is missing branches: "
                + ", ".join(missing)
            )
        return int(tree.GetEntries())
    finally:
        source.Close()


def prepare_signal_mc(input_file: Path, output_dir: Path, threads: int) -> Path:
    if threads <= 0:
        raise ValueError("--threads must be positive")

    entries = _validate_source(input_file)
    print(f"Signal MC input: {input_file}")
    print(f"Input events: {entries}")
    with tempfile.TemporaryDirectory(prefix="graal-root-dictionary-") as dictionary_dir:
        previous_directory = Path.cwd()
        try:
            os.chdir(dictionary_dir)
            ROOT.gInterpreter.GenerateDictionary(
                "std::vector<TLorentzVector>", "vector;TLorentzVector.h"
            )
        finally:
            os.chdir(previous_directory)

        ROOT.EnableImplicitMT(threads)
        print(f"RDataFrame implicit multithreading: {threads} threads")

        with atomic_output_directory(output_dir) as staging:
            output_file = staging / OUTPUT_NAME
            frame = ROOT.RDataFrame(INPUT_TREE, str(input_file))
            adapted = (
                frame.Define(
                    "gammas",
                    "std::vector<TLorentzVector>{eta_gamma1, eta_gamma2, "
                    "pi0_gamma1, pi0_gamma2}",
                )
                .Define("protons", "std::vector<TLorentzVector>{proton}")
                .Define("neutrons", "std::vector<TLorentzVector>{}")
                .Define("RunNumber", "-1")
                .Define("Polarization", "-1")
                .Define("Xstrip", "-1.0f")
            )
            options = ROOT.RDF.RSnapshotOptions()
            options.fMode = "RECREATE"
            adapted.Snapshot(
                OUTPUT_TREE,
                str(output_file),
                list(OUTPUT_BRANCHES),
                options,
            )

    published = output_dir / OUTPUT_NAME
    print(f"Detector-like signal MC written: {published}")
    return published


def main() -> None:
    args = build_parser().parse_args()
    prepare_signal_mc(args.input_file, args.output_dir, args.threads)


if __name__ == "__main__":
    main()
