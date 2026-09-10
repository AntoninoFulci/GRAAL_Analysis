from __future__ import annotations

from array import array

import pytest

ROOT = pytest.importorskip("ROOT")

from contracts import PolarizationContractError
from root_events import read_reco_root, scan_reco_run_numbers


def write_tree(path, *, include_xstrip=True):
    output = ROOT.TFile(str(path), "RECREATE")
    tree = ROOT.TTree("reco_eta_pi0_chi2", "reco_eta_pi0_chi2")
    run = array("i", [7])
    state = array("i", [2])
    xstrip = array("f", [42.0])
    tree.Branch("RunNumber", run, "RunNumber/I")
    tree.Branch("Polarization", state, "Polarization/I")
    if include_xstrip:
        tree.Branch("Xstrip", xstrip, "Xstrip/F")
    vectors = {
        "beam": ROOT.TLorentzVector(0.0, 0.0, 1.2, 1.2),
        "proton": ROOT.TLorentzVector(0.1, 0.0, 0.2, 0.97),
        "eta": ROOT.TLorentzVector(0.1, 0.1, 0.1, 0.59),
        "pi0": ROOT.TLorentzVector(-0.1, 0.1, 0.1, 0.22),
    }
    for name, vector in vectors.items():
        tree.Branch(name, "TLorentzVector", vector)
    tree.Fill()
    tree.Write()
    output.Close()


def test_read_reco_root_reads_metadata_and_rejects_each_incompatible_file(tmp_path):
    good = tmp_path / "good.root"
    bad = tmp_path / "bad.root"
    write_tree(good)
    write_tree(bad, include_xstrip=False)
    sample = read_reco_root([good], tree_name="reco_eta_pi0_chi2", vectors="raw")
    assert sample.run_number.tolist() == [7]
    assert sample.state_code.tolist() == [2]
    assert sample.xstrip.tolist() == pytest.approx([42.0])
    assert sample.beam_energy.tolist() == pytest.approx([1.2])
    assert scan_reco_run_numbers(
        [good], tree_name="reco_eta_pi0_chi2", vectors="raw"
    ) == {7}
    with pytest.raises(PolarizationContractError, match="Xstrip"):
        read_reco_root(
            [good, bad], tree_name="reco_eta_pi0_chi2", vectors="raw"
        )
