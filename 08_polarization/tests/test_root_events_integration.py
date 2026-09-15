from __future__ import annotations

from array import array

import numpy as np
import pytest

ROOT = pytest.importorskip("ROOT")

from contracts import PolarizationContractError, sha256_file
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


def write_kinematic_tree(path):
    output = ROOT.TFile(str(path), "RECREATE")
    tree = ROOT.TTree("reco_eta_pi0_chi2", "reco_eta_pi0_chi2")
    run = array("i", [7])
    state = array("i", [2])
    xstrip = array("f", [42.0])
    fit_converged = array("i", [1])
    tree.Branch("RunNumber", run, "RunNumber/I")
    tree.Branch("Polarization", state, "Polarization/I")
    tree.Branch("Xstrip", xstrip, "Xstrip/F")
    tree.Branch("fit_converged", fit_converged, "fit_converged/I")
    vectors = {
        "beam": ROOT.TLorentzVector(0.0, 0.0, 1.2, 1.2),
        "proton_fit": ROOT.TLorentzVector(0.1, 0.0, 0.2, 0.97),
        "eta_fit": ROOT.TLorentzVector(0.1, 0.1, 0.1, 0.59),
        "pi0_fit": ROOT.TLorentzVector(-0.1, 0.1, 0.1, 0.22),
    }
    for name, vector in vectors.items():
        tree.Branch(name, "TLorentzVector", vector)
    tree.Fill()
    run[0] = 8
    fit_converged[0] = 0
    tree.Fill()
    run[0] = 9
    fit_converged[0] = 1
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
    np.testing.assert_allclose(sample.beam, [[0.0, 0.0, 1.2, 1.2]])
    assert scan_reco_run_numbers(
        [good], tree_name="reco_eta_pi0_chi2", vectors="raw"
    ) == {7}
    with pytest.raises(PolarizationContractError, match="Xstrip"):
        read_reco_root(
            [good, bad], tree_name="reco_eta_pi0_chi2", vectors="raw"
        )


def test_scan_kinematic_runs_matches_fit_converged_reader_selection(tmp_path):
    path = tmp_path / "kinematic.root"
    write_kinematic_tree(path)

    sample = read_reco_root(
        [path], tree_name="reco_eta_pi0_chi2", vectors="kinematic_fit"
    )
    runs = scan_reco_run_numbers(
        [path], tree_name="reco_eta_pi0_chi2", vectors="kinematic_fit"
    )

    assert sample.run_number.tolist() == [7, 9]
    assert runs == {7, 9}


def test_root_reader_preserves_file_hash_and_local_entry_before_selection(tmp_path):
    first = tmp_path / "first.root"
    second = tmp_path / "second.root"
    write_kinematic_tree(first)
    write_kinematic_tree(second)

    sample = read_reco_root(
        [first, second],
        tree_name="reco_eta_pi0_chi2",
        vectors="kinematic_fit",
    )

    assert sample.tree_entry.tolist() == [0, 2, 0, 2]
    assert sample.file_sha256.tolist() == [
        sha256_file(first),
        sha256_file(first),
        sha256_file(second),
        sha256_file(second),
    ]
