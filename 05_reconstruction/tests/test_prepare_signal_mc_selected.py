"""Detector-like adapter contract for generated eta-pi0 signal MC."""

from pathlib import Path
import subprocess
import sys

import ROOT


ROOT_DIR = Path(__file__).parents[2]


def _write_signal_mc(path: Path) -> None:
    output = ROOT.TFile(str(path), "RECREATE")
    tree = ROOT.TTree("mc", "mc")
    names = (
        "beam",
        "eta_gamma1",
        "eta_gamma2",
        "pi0_gamma1",
        "pi0_gamma2",
        "proton",
    )
    vectors = {name: ROOT.TLorentzVector() for name in names}
    for name, vector in vectors.items():
        tree.Branch(name, "TLorentzVector", vector)
    for event in range(2):
        energy = 1.2 + 0.1 * event
        vectors["beam"].SetPxPyPzE(0.0, 0.0, energy, energy)
        vectors["eta_gamma1"].SetPxPyPzE(0.1, 0.0, 0.2, 0.25)
        vectors["eta_gamma2"].SetPxPyPzE(-0.1, 0.0, 0.2, 0.25)
        vectors["pi0_gamma1"].SetPxPyPzE(0.0, 0.05, 0.1, 0.12)
        vectors["pi0_gamma2"].SetPxPyPzE(0.0, -0.05, 0.1, 0.12)
        vectors["proton"].SetPxPyPzE(0.0, 0.0, 0.1, 0.95)
        tree.Fill()
    tree.Write()
    output.Close()


def test_cli_writes_detector_like_h85_for_signal_reconstruction(tmp_path):
    source = tmp_path / "eta_pi0_mc.root"
    output_dir = tmp_path / "selected"
    _write_signal_mc(source)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "reconstruction.prepare_signal_mc_selected",
            "--input-file",
            str(source),
            "--output-dir",
            str(output_dir),
            "--threads",
            "1",
        ],
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    output_path = output_dir / "eta_pi0_mc_selected.root"
    assert output_path.is_file()
    output = ROOT.TFile.Open(str(output_path), "READ")
    try:
        tree = output.Get("h85")
        assert tree and tree.GetEntries() == 2
        branches = {branch.GetName() for branch in tree.GetListOfBranches()}
        assert branches == {
            "beam",
            "gammas",
            "protons",
            "neutrons",
            "RunNumber",
            "Polarization",
            "Xstrip",
        }
        tree.GetEntry(0)
        assert tree.gammas.size() == 4
        assert tree.protons.size() == 1
        assert tree.neutrons.empty()
        assert tree.gammas[0].E() == 0.25
        assert tree.protons[0].E() == 0.95
        assert tree.RunNumber == -1
        assert tree.Polarization == -1
        assert tree.Xstrip == -1.0
    finally:
        output.Close()
