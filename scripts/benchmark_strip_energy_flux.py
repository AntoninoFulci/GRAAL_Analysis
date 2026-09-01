#!/usr/bin/env python3
"""Generate a reproducible multi-file/multi-run strip-flux benchmark fixture."""
from __future__ import annotations

import argparse
from array import array
from pathlib import Path

from graal_common.run_manifest import RunRecord, write_manifest


RUNS = (7001, 7002, 7003, 7004)
FILE_COUNT = 4


def _import_root():
    try:
        import ROOT
    except ImportError as exc:
        raise SystemExit("ROOT is required to generate the benchmark") from exc
    return ROOT


def _write_h80(path: Path, entries) -> None:
    root = _import_root()
    output = root.TFile(str(path), "RECREATE")
    tree = root.TTree("h80", "h80")
    vector_type = "ROOT::Math::LorentzVector<ROOT::Math::PxPyPzE4D<double> >"
    vector = getattr(root, vector_type)()
    run_number = array("i", [0])
    xstrip = array("f", [0.0])
    tree.Branch("beam", vector_type, vector)
    tree.Branch("RunNumber", run_number, "RunNumber/I")
    tree.Branch("Xstrip", xstrip, "Xstrip/F")
    for run, strip, energy in entries:
        run_number[0] = run
        xstrip[0] = strip
        vector.SetPxPyPzE(0.0, 0.0, energy, energy)
        tree.Fill()
    tree.Write()
    output.Close()


def _write_flux(path: Path) -> None:
    root = _import_root()
    output = root.TFile(str(path), "RECREATE")
    for run_number in RUNS:
        for suffix, value in (("POL1", 10.0), ("POL2", 8.0), ("BREM", 1.0)):
            histogram = root.TH1D(
                f"run{run_number}_{suffix}",
                "",
                128,
                0.0,
                128.0,
            )
            for xstrip in range(1, 129):
                histogram.SetBinContent(xstrip, value)
            histogram.Write()
    output.Close()


def _entries(file_index: int, events_per_file: int):
    for event_index in range(events_per_file):
        run_number = RUNS[(event_index + file_index) % len(RUNS)]
        xstrip = event_index % 128 + 1
        energy = (
            1.0
            + (xstrip - 1) * 0.5 / 127
            + ((event_index // 128) % 5 - 2) * 0.0001
        )
        yield run_number, xstrip, energy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate four ROOT files whose four runs span every file, "
            "plus matching flux and manifest inputs."
        )
    )
    parser.add_argument("destination", type=Path)
    parser.add_argument("events_per_file", type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.events_per_file < 1:
        raise SystemExit("events_per_file must be positive")
    if args.destination.exists():
        raise SystemExit(f"destination already exists: {args.destination}")

    preanalysis = args.destination / "pre"
    preanalysis.mkdir(parents=True)
    for file_index in range(FILE_COUNT):
        _write_h80(
            preanalysis / f"events-{file_index}.root",
            _entries(file_index, args.events_per_file),
        )

    _write_flux(args.destination / "flux.root")
    write_manifest(
        [
            RunRecord(
                run_number,
                f"benchmark_{run_number}",
                "P",
                "UV",
                "P_UV",
                "manual",
                f"benchmark/run{run_number}.root",
            )
            for run_number in RUNS
        ],
        args.destination / "manifest.csv",
    )
    print(FILE_COUNT * args.events_per_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
