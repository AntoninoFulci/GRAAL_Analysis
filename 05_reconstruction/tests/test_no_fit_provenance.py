"""Real ROOT round trip of no-fit selection, counters, and input identity."""
from array import array
import hashlib
import json

import ROOT
import numpy as np
import pytest

from reconstruction.core import reco_physics as rp
from reconstruction.runtime import reco_core
from observable_extraction.io.reconstructed_events import read_reconstructed


@pytest.mark.parametrize("mutate_model", [False, True])
def test_no_fit_root_records_selection_and_reopens_without_fit_branches(tmp_path, monkeypatch, mutate_model):
    selected = tmp_path / "selected"
    selected.mkdir()
    path = selected / "input.root"
    source = ROOT.TFile(str(path), "RECREATE")
    tree = ROOT.TTree("h85", "h85")
    beam = ROOT.TLorentzVector(0, 0, 1.2, 1.2)
    vectors = {name: ROOT.std.vector("TLorentzVector")() for name in ("gammas", "protons", "neutrons")}
    for name, value in vectors.items():
        tree.Branch(name, value)
    tree.Branch("beam", beam)
    scalars = {"RunNumber": array("i", [811]), "Polarization": array("i", [1]), "Xstrip": array("f", [17])}
    for name, value in scalars.items():
        tree.Branch(name, value, f"{name}/{'F' if name == 'Xstrip' else 'I'}")
    for vector in ((.1, 0, .2, .25), (-.1, 0, .2, .25), (0, .05, .1, .12), (0, -.05, .1, .12)):
        vectors["gammas"].push_back(ROOT.TLorentzVector(*vector))
    vectors["protons"].push_back(ROOT.TLorentzVector(0, 0, .1, .95))
    tree.Fill()
    vectors["protons"].clear()
    tree.Fill()
    tree.Write()
    source.Close()
    def forbidden(*args, **kwargs):
        raise AssertionError("fitter called")
    monkeypatch.setattr(reco_core, "fit_event", forbidden)
    cfg = reco_core.RecoConfig(selected, tmp_path / "reco.root", output_tree="reco",
                               chi2_cut=1000, missing_mass_window=None)
    gate = None
    if mutate_model:
        cfg.model_dir = tmp_path / "model"
        cfg.model_dir.mkdir()
        for name in ("bdt_stage1.json", "stage1_threshold.txt", "stage1_provenance.json"):
            (cfg.model_dir / name).write_bytes(b"original")
        class Gate:
            threshold = 0.5
            def scores_many(self, *args):
                (cfg.model_dir / "bdt_stage1.json").write_bytes(b"changed during reconstruction")
                return np.array([0.9])
        gate = Gate()
    assert reco_core.run_reconstruction(cfg, rp.ETA_PI0, gate=gate) == 1
    output = ROOT.TFile.Open(str(cfg.output_file))
    metadata = json.loads(output.Get("reconstruction_provenance").GetTitle())
    if mutate_model:
        assert metadata["model_inputs"][0]["sha256"] == hashlib.sha256(b"original").hexdigest()
    assert metadata["do_fit"] is False
    assert metadata["input_tree"] == "h85"
    assert metadata["selection"]["chi2_cut"] == 1000
    assert metadata["selection"]["chi2_resolution_relative"] == .08
    assert metadata["selection"]["missing_mass_window_gev"] is None
    assert metadata["inputs"][0]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert metadata["counts_by_run_state"] == [{"run": 811, "polarization": 1, "input": 2, "written": 1, "not_one_proton": 1}]
    assert not any("fit" in b.GetName() for b in output.Get("reco").GetListOfBranches())
    output.Close()
    assert len(read_reconstructed(cfg.output_file, "reco", vector_mode="raw", require_no_fit=True)) == 1
