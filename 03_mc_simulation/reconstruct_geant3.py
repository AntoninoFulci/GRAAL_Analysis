"""Apply unchanged data reconstruction to a period21 GEANT3 signal sample.

Persist unique truth/selected identities and kinematics without treating this
bridge as a validated detector response. Input PREAN must first be converted
with h2root. Polarization conventions are mapped before current preanalysis.
"""

import argparse
import json
import subprocess
import sys
from array import array
from pathlib import Path

import numpy as np
import ROOT
from mc_simulation.native_validation import bind_reconstruction, validate_native_sample
from observable_extraction.io.cross_section import (
    reconstruction_metadata,
    selection_signature,
)
from reconstruction.runtime.provenance import file_identities


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", type=Path, required=True)
    parser.add_argument("--converted", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[1]
    pilot, converted, output = (
        args.pilot.resolve(),
        args.converted.resolve(),
        args.output.resolve(),
    )
    truth, validation = validate_native_sample(pilot, converted)
    output.mkdir(parents=True, exist_ok=False)
    raw_dir = output / "raw" / "2002_uv1"
    raw_dir.mkdir(parents=True)
    raw_path = raw_dir / "run3629.root"
    ROOT.DisableImplicitMT()
    source_file = ROOT.TFile.Open(str(converted))
    if not source_file or source_file.IsZombie():
        raise ValueError("cannot open converted PREAN file")
    source = source_file.Get("h70")
    if not source:
        raise ValueError("converted PREAN file has no h70 tree")
    # Preserve h2root variable-length leaf layouts; generic RDF Snapshot cannot
    # reliably round-trip this legacy branch schema.
    ids, polarizations = [], []
    for event in source:
        state = int(source.GetLeaf("Ipol").GetValue())
        if int(event.Idrun) != 3629 or state not in (1, 2):
            raise ValueError("unexpected technical pilot run or polarization")
        ids.append(int(event.Idevt))
        polarizations.append(state)
    ids = np.asarray(ids, dtype=np.int64)
    if len(ids) != validation["counts"]["digitized"]:
        raise ValueError(
            "converted h70 count differs from completed digitizer/PREAN chain"
        )
    if len(np.unique(ids)) != len(ids) or not np.all(np.isin(ids, truth[:, 1])):
        raise ValueError(
            "h70 identities not a unique subset of complete generated truth"
        )
    # LAGGEN 1=horizontal/2=vertical; current analysis 1=vertical/2=horizontal.
    source.SetBranchStatus("Ipol", 0)

    mapped_file = ROOT.TFile(str(raw_path), "RECREATE")
    mapped = source.CloneTree(-1, "fast")
    state_buffer = array("B", [0])
    state_branch = mapped.Branch("Ipol", state_buffer, "Ipol/b")
    for state in polarizations:
        state_buffer[0] = 3 - state
        state_branch.Fill()
    mapped.Write()
    ROOT.TNamed("mc_polarization_mapping", "LAGGEN 1H/2V -> analysis 2H/1V").Write()
    mapped_file.Close()
    source_file.Close()
    commands = [
        [
            sys.executable,
            "-m",
            "scripts.run_preanalysis",
            "--raw-dir",
            str(output / "raw"),
            "--output-dir",
            str(output / "prean"),
            "--cpus",
            "1",
        ],
        [
            sys.executable,
            "-m",
            "event_selector.select_events",
            "--input-dir",
            str(output / "prean"),
            "--output-dir",
            str(output / "selected"),
            "--threads",
            "1",
        ],
        [
            sys.executable,
            "-m",
            "reconstruction.reconstruct_eta_pi0_bdt",
            "--input-dir",
            str(output / "selected"),
            "--output-file",
            str(output / "reconstructed.root"),
            "--model-dir",
            str(repo / "results/cross-section-inputs-20261021/models/uv"),
            "--profile",
            "uv",
            "--workers",
            "1",
        ],
    ]
    for i, command in enumerate(commands):
        with (output / f"stage{i + 1}.log").open("w") as log:
            subprocess.run(
                command, cwd=repo, stdout=log, stderr=subprocess.STDOUT, check=True
            )
    raw_file = ROOT.TFile.Open(str(raw_path))
    raw = raw_file.Get("h70")
    reco_file = ROOT.TFile.Open(str(output / "reconstructed.root"))
    reco = reco_file.Get("reco_eta_pi0_bdt")
    selected_ids, selected_energy, selected_vectors, selected_strips = [], [], [], []
    for event in reco:
        if Path(str(event.RawSourceFile)).resolve() != raw_path:
            raise ValueError("selected raw source differs from converted pilot")
        row = int(event.RawSourceEntry)
        if not 0 <= row < raw.GetEntries():
            raise ValueError("invalid raw entry identity")
        raw.GetEntry(row)
        if int(event.RunNumber) != int(raw.Idrun):
            raise ValueError("run identity mismatch")
        selected_ids.append(int(raw.Idevt))
        selected_energy.append(float(event.beam.E()))
        selected_strips.append(int(event.Xstrip))
        selected_vectors.append(
            [
                [float(v.Px()), float(v.Py()), float(v.Pz()), float(v.E())]
                for v in (event.eta, event.pi0, event.proton)
            ]
        )
    reco_file.Close()
    raw_file.Close()

    selected_ids = np.asarray(selected_ids, dtype=np.int64)
    if len(np.unique(selected_ids)) != len(selected_ids) or not np.all(
        np.isin(selected_ids, truth[:, 1])
    ):
        raise ValueError("final selected identities are not a unique truth subset")
    metadata = reconstruction_metadata(output / "reconstructed.root")
    data_metadata = reconstruction_metadata(
        repo / "results/uv/reco/reco_eta_pi0_bdt.root"
    )
    if selection_signature(metadata) != selection_signature(data_metadata):
        raise ValueError("MC and data reconstruction/BDT selection signatures differ")
    np.savez_compressed(
        output / "matched_events.npz",
        generated_ids=truth[:, 1].astype(np.int64),
        generated_energy_gev=truth[:, 4],
        generated_p4=truth[:, 8:].reshape(-1, 3, 4),
        selected_ids=selected_ids,
        selected_energy_gev=np.asarray(selected_energy),
        selected_p4=np.asarray(selected_vectors).reshape(-1, 3, 4),
        selected_strip=np.asarray(selected_strips, dtype=np.int64),
    )
    summary = {
        "schema_version": 1,
        "status": "matched_reconstruction_not_yet_response_validation",
        "period": "2002_uv1",
        "representative_run": 3629,
        "counts": {
            "generated": len(truth),
            "prean_h70": len(ids),
            "selected_bdt": len(selected_ids),
        },
        "energy_range_generated_gev": [
            float(truth[:, 4].min()),
            float(truth[:, 4].max()),
        ],
        "selection_signature": selection_signature(metadata),
        "polarization_mapping": "LAGGEN 1H/2V -> analysis 2H/1V before preanalysis",
        "p4_order": ["eta", "pi0", "proton"],
        "p4_components": ["px", "py", "pz", "E"],
        "commands": commands,
        "inputs": file_identities(
            [Path(__file__), pilot / "generated_signal.dat", converted]
        ),
        "limitations": [
            "provisional period21 OLD_CYL, 12cm LH2, BGO trigger and calibrations",
            "migration-domain and statistical-support checks required before inference",
            "unweighted phase-space production model; model systematic pending",
        ],
    }
    (output / "selection_audit.json").write_text(json.dumps(summary, indent=2) + "\n")
    bind_reconstruction(output, validation)
    print(json.dumps(summary["counts"]))


if __name__ == "__main__":
    main()
