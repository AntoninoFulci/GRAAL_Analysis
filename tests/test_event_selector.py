"""Publication behavior for event-selection outputs."""

from array import array
from pathlib import Path
import sys

import pytest

from event_selector import select_events


def _write_preanalysis_fixture(path: Path) -> None:
    import ROOT

    output = ROOT.TFile(str(path), "RECREATE")
    tree = ROOT.TTree("h80", "h80")
    vector_type = "ROOT::Math::LorentzVector<ROOT::Math::PxPyPzE4D<double> >"
    vector = getattr(ROOT, vector_type)
    vector_list = ROOT.std.vector(vector_type)
    gammas = vector_list()
    charged_theta = ROOT.std.vector("float")()
    run_number = array("i", [1321])
    polarization = array("i", [1])
    xstrip = array("f", [3.75])
    tree.Branch("gammas", vector_list.__cpp_name__, gammas)
    tree.Branch("fcharged_theta", charged_theta)
    tree.Branch("RunNumber", run_number, "RunNumber/I")
    tree.Branch("Polarization", polarization, "Polarization/I")
    tree.Branch("Xstrip", xstrip, "Xstrip/F")

    charged_theta.push_back(0.1)
    for px in (0.1, -0.1):
        photon = vector()
        photon.SetPxPyPzE(px, 0.0, 0.2, 0.3)
        gammas.push_back(photon)
    tree.Fill()
    gammas.resize(1)
    tree.Fill()
    tree.Write()
    output.Close()


def test_cli_defaults_follow_numbered_data_layout(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["select_events"])

    args = select_events.parse_args()

    assert args.input_dir == "data/02_pre_analyzed/pre_analisi"
    assert args.output_dir == "data/03_selected"
    assert args.threads >= 1


def test_cli_accepts_explicit_rdataframe_thread_count(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["select_events", "--threads", "3"])

    args = select_events.parse_args()

    assert args.threads == 3


def test_rdataframe_selection_preserves_metadata_in_h85(tmp_path):
    input_dir = tmp_path / "pre"
    input_dir.mkdir()
    _write_preanalysis_fixture(input_dir / "pre_sample.root")
    output_dir = tmp_path / "selected"

    select_events.run(input_dir, output_dir, threads=2)

    import ROOT

    selected = ROOT.TFile.Open(str(output_dir / "sample.root"), "READ")
    try:
        tree = selected.Get("h85")
        assert tree and tree.GetEntries() == 1
        branches = {branch.GetName() for branch in tree.GetListOfBranches()}
        assert {"RunNumber", "Polarization", "Xstrip"} <= branches
        assert "RVec" not in tree.GetBranch("gammas").GetClassName()
        tree.GetEntry(0)
        assert tree.RunNumber == 1321
        assert tree.Polarization == 1
        assert tree.Xstrip == pytest.approx(3.75)
    finally:
        selected.Close()


def test_successful_selection_replaces_stale_output_dataset(tmp_path, monkeypatch):
    input_dir = tmp_path / "pre_analisi"
    input_dir.mkdir()
    (input_dir / "pre_analisi_1998_uv.root").touch()
    (input_dir / "pre_analisi_2002_vis1.root").touch()

    output_dir = tmp_path / "selected"
    output_dir.mkdir()
    (output_dir / "analisi_obsoleta.root").write_text("stale")

    def select_file(input_path: Path, output_path: Path) -> None:
        output_path.write_text(input_path.name)

    monkeypatch.setattr(select_events, "_select_file", select_file)

    select_events.run(input_dir, output_dir)

    assert sorted(path.name for path in output_dir.iterdir()) == [
        "analisi_1998_uv.root",
        "analisi_2002_vis1.root",
    ]


def test_failed_selection_preserves_previous_output_dataset(tmp_path, monkeypatch):
    input_dir = tmp_path / "pre_analisi"
    input_dir.mkdir()
    (input_dir / "pre_analisi_1998_uv.root").touch()
    (input_dir / "pre_analisi_2002_vis1.root").touch()

    output_dir = tmp_path / "selected"
    output_dir.mkdir()
    sentinel = output_dir / "analisi_verificata.root"
    sentinel.write_text("previous complete dataset")

    def fail_on_second_file(input_path: Path, output_path: Path) -> None:
        if input_path.name == "pre_analisi_2002_vis1.root":
            raise RuntimeError("broken ROOT input")
        output_path.write_text(input_path.name)

    monkeypatch.setattr(select_events, "_select_file", fail_on_second_file)

    with pytest.raises(RuntimeError, match="broken ROOT input"):
        select_events.run(input_dir, output_dir)

    assert sorted(path.name for path in output_dir.iterdir()) == [sentinel.name]
    assert sentinel.read_text() == "previous complete dataset"
