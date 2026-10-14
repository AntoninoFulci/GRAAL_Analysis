"""Real ROOT serial/process equivalence and atomic worker failure handling."""
from array import array
from dataclasses import replace
import json
import os

import numpy as np
import pytest
import ROOT

from graal_common.io.raw_tracks import RawTrackWriter, snapshot_raw_tracks
from reconstruction.core.reco_physics import ETA_PI0
from reconstruction.runtime.provenance import KEY, file_identities
from reconstruction.runtime.reco_core import RecoConfig, run_reconstruction


def _selected(path, event_ids):
    source = ROOT.TFile(str(path), "RECREATE")
    tree = ROOT.TTree("h85", "h85")
    beam = ROOT.TLorentzVector()
    tree.Branch("beam", beam)
    vectors = {name: ROOT.std.vector("TLorentzVector")()
               for name in ("gammas", "protons", "neutrons")}
    for name, vector in vectors.items():
        tree.Branch(name, vector)
    scalars = {"RunNumber": array("i", [0]), "Polarization": array("i", [0]),
               "Xstrip": array("f", [0])}
    for name, value in scalars.items():
        tree.Branch(name, value, f"{name}/{'F' if name == 'Xstrip' else 'I'}")
    raw = RawTrackWriter(tree)
    for index in event_ids:
        energy = 1.2 + index*.01
        beam.SetPxPyPzE(0, 0, energy, energy)
        vectors["gammas"].clear()
        for values in ((.1, 0, .2, .25), (-.1, 0, .2, .25),
                       (0, .05, .1, .12), (0, -.05, .1, .12)):
            vectors["gammas"].push_back(ROOT.TLorentzVector(*values))
        vectors["protons"].clear()
        if index % 4 != 1:
            vectors["protons"].push_back(ROOT.TLorentzVector(0, 0, .1, .95))
        scalars["RunNumber"][0] = 0 if index % 2 else 42
        scalars["Polarization"][0] = index % 2 + 1
        scalars["Xstrip"][0] = index
        raw.assign(dict(Nass_3=2, Nparf=2, N_traf=1, Nparf_strange=index,
            RawSourceEntry=100+index, RawSourceFile=f"raw/{path.name}",
            Itipo_track=(11, -3), Index_trf=(0, 255), Iass_trf=(7,)))
        tree.Fill()
    tree.Write()
    source.Close()


def _read(path):
    source = ROOT.TFile.Open(str(path))
    try:
        tree = source.Get("reco")
        names = [branch.GetName() for branch in tree.GetListOfBranches()]
        rows = []
        for row in tree:
            vectors = {}
            for branch in tree.GetListOfBranches():
                if branch.GetClassName() == "TLorentzVector":
                    value = getattr(row, branch.GetName())
                    vectors[branch.GetName()] = (value.Px(), value.Py(), value.Pz(), value.E())
            rows.append((vectors, snapshot_raw_tracks(row), float(row.chi2),
                         float(row.eta_mass), float(row.pi0_mass), int(row.RunNumber),
                         int(row.Polarization), float(row.Xstrip), int(row.n_photons_input),
                         float(row.bdt_score) if "bdt_score" in names else None))
        metadata = json.loads(source.Get(KEY).GetTitle())
        return names, rows, metadata
    finally:
        source.Close()


@pytest.mark.parametrize("groups", [((0, 1, 2), (), (3, 4, 5)),
                                     ((0, 1, 2, 3, 4, 5),), ((), ()), ((1,), (5,))])
@pytest.mark.parametrize("gated", [False, True])
def test_parallel_matches_serial_rows_raw_identity_and_cutflow(tmp_path, groups, gated):
    inputs = tmp_path / "selected"
    inputs.mkdir()
    for index, group in enumerate(groups):
        _selected(inputs/f"{index}.root", group)

    class Gate:
        threshold = .5
        def scores_many(self, photons, protons, beams):
            return np.where(beams[:, 3] >= 1.22, .9, .1)

    gate = Gate() if gated else None
    serial = RecoConfig(inputs, tmp_path/"serial.root", chi2_cut=1000,
                        missing_mass_window=None)
    parallel = replace(serial, output_file=tmp_path/"parallel.root", workers=2)
    assert run_reconstruction(parallel, ETA_PI0, gate) == run_reconstruction(serial, ETA_PI0, gate)
    names, rows, metadata = _read(parallel.output_file)
    serial_names, serial_rows, serial_metadata = _read(serial.output_file)
    assert names == serial_names
    assert rows == serial_rows
    execution = metadata.pop("execution")
    assert metadata == serial_metadata
    assert metadata["inputs"] == file_identities(inputs.glob("*.root"))
    assert execution["workers_requested"] == 2
    assert len(execution["shards"]) >= min(2, sum(map(len, groups)))
    assert all(shard["process_id"] != os.getpid() for shard in execution["shards"])
    assert sum(shard["entries_written"] for shard in execution["shards"]) == len(rows)
    assert sorted(path.name for path in tmp_path.iterdir()) == ["parallel.root", "selected", "serial.root"]


def test_worker_failure_preserves_existing_output_and_cleans_shards(tmp_path):
    inputs = tmp_path/"selected"
    inputs.mkdir()
    _selected(inputs/"events.root", (0, 2, 3, 4))
    output = tmp_path/"result.root"
    output.write_bytes(b"previous result")
    parent_pid = os.getpid()

    class BrokenGate:
        threshold = .5
        def scores_many(self, photons, protons, beams):
            assert os.getpid() != parent_pid
            raise RuntimeError("intentional worker failure")

    config = RecoConfig(inputs, output, chi2_cut=1000, missing_mass_window=None, workers=2)
    with pytest.raises(RuntimeError, match="intentional worker failure"):
        run_reconstruction(config, ETA_PI0, BrokenGate())
    assert output.read_bytes() == b"previous result"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["result.root", "selected"]


@pytest.mark.parametrize("fail_merge", [False, True])
@pytest.mark.parametrize("implicit_mt", [False, True])
def test_repeated_merges_release_owned_output_before_reopening(tmp_path, monkeypatch, fail_merge, implicit_mt):
    from reconstruction.runtime.parallel import _merge_shards

    inputs = tmp_path/"selected"
    inputs.mkdir()
    _selected(inputs/"events.root", (0, 2))
    shard = tmp_path/"shard.root"
    count = run_reconstruction(RecoConfig(inputs, shard, chi2_cut=1000,
                                          missing_mass_window=None), ETA_PI0)
    expected = _read(shard)[:2]
    execution = {"shards": [{"entries_written": count}]}
    real_merger = ROOT.TFileMerger
    mergers = []

    class FailedMerge:
        def __init__(self, merger):
            self.merger = merger

        def __getattr__(self, name):
            return getattr(self.merger, name)

        def Merge(self):
            return False

    def track_merger(*args):
        assert not ROOT.IsImplicitMTEnabled(), "merge must not inherit a ROOT thread pool"
        merger = real_merger(*args)
        mergers.append(merger)
        return FailedMerge(merger) if fail_merge else merger

    monkeypatch.setattr(ROOT, "TFileMerger", track_merger)
    try:
        for index in range(3):
            if implicit_mt:
                ROOT.EnableImplicitMT(2)
            merged = tmp_path/f"merged-{index}.root"
            if fail_merge:
                with pytest.raises(OSError, match="merge failed"):
                    _merge_shards([shard], merged, "reco", execution, [])
            else:
                assert _merge_shards([shard], merged, "reco", execution, []) == count
            # A closed-but-owned TFile can be deleted during later ROOT cleanup
            # while the merger still holds it, causing RecursiveRemove to abort.
            assert not mergers[-1].GetOutputFile()
            if not fail_merge:
                assert _read(merged)[:2] == expected
    finally:
        if ROOT.IsImplicitMTEnabled():
            ROOT.DisableImplicitMT()
        for merger in mergers:
            merger.CloseOutputFile()


@pytest.mark.parametrize("workers", [0, -1, True, 1.5])
def test_invalid_worker_count_rejected_before_output(tmp_path, workers):
    with pytest.raises(ValueError, match="workers.*positive integer"):
        run_reconstruction(RecoConfig(tmp_path, tmp_path/"result.root", workers=workers), ETA_PI0)
    assert not (tmp_path/"result.root").exists()


def test_real_bdt_serial_parallel_scores_and_model_identity_match(tmp_path):
    import xgboost as xgb
    from graal_common.physics.channels import TAGGER_FWHM_GEV, TAGGER_SIGMA_GEV
    from graal_common.stage1.artifacts import Stage1Provenance
    from graal_common.stage1.features import FEATURE_NAMES_S1
    from reconstruction.runtime.stage1_gate import Stage1Gate

    model_dir = tmp_path/"model"
    model_dir.mkdir()
    rng = np.random.default_rng(17)
    features = rng.normal(size=(32, 26))
    model = xgb.XGBClassifier(n_estimators=2, max_depth=2, n_jobs=2)
    model.fit(features, np.arange(32) % 2)
    model.save_model(model_dir/"bdt_stage1.json")
    (model_dir/"stage1_threshold.txt").write_text("0.0\n")
    provenance = Stage1Provenance("eta_pi0", "eta_pi0", None, None,
        "weighted", TAGGER_FWHM_GEV, TAGGER_SIGMA_GEV, "closure", tuple(FEATURE_NAMES_S1))
    (model_dir/"stage1_provenance.json").write_text(provenance.to_json())
    gate = Stage1Gate.load(model_dir)
    assert gate.model.get_params()["n_jobs"] == 1
    assert json.loads(gate.model.get_booster().save_config())["learner"]["generic_param"]["nthread"] == "1"
    inputs = tmp_path/"selected"
    inputs.mkdir()
    _selected(inputs/"events.root", (0, 1, 2, 3, 4, 5))
    serial = RecoConfig(inputs, tmp_path/"serial.root", chi2_cut=1000,
                        missing_mass_window=None, model_dir=model_dir)
    parallel = replace(serial, output_file=tmp_path/"parallel.root", workers=2)
    assert run_reconstruction(serial, ETA_PI0, gate) == run_reconstruction(parallel, ETA_PI0, gate)
    names, rows, metadata = _read(parallel.output_file)
    serial_names, serial_rows, serial_metadata = _read(serial.output_file)
    metadata.pop("execution")
    assert (names, rows, metadata) == (serial_names, serial_rows, serial_metadata)
    assert metadata["model_inputs"] == file_identities(model_dir.glob("*"))


@pytest.mark.parametrize("workers", [1, 2, 3])
@pytest.mark.parametrize("events", [(), (0, 1, 2, 3)])
def test_raw_run_universe_and_counters_are_added_once_per_input_file(tmp_path, workers, events):
    inputs = tmp_path/"selected"
    inputs.mkdir()
    for index in range(2):
        path = inputs/f"{index}.root"
        _selected(path, events)
        source = ROOT.TFile.Open(str(path), "UPDATE")
        ROOT.TNamed("preanalysis_provenance", json.dumps({"input_run_states": [
            {"run": 42, "polarization": 1, "input": 6, "skipped_no_tagger": 2},
            {"run": 0, "polarization": 2, "input": 4, "skipped_no_tagger": 2},
            {"run": 8, "polarization": 1, "input": 3, "skipped_no_tagger": 3},
        ]})).Write()
        source.Close()
    config = RecoConfig(inputs, tmp_path/"reco.root", chi2_cut=1000,
                        missing_mass_window=None, workers=workers)
    run_reconstruction(config, ETA_PI0)
    metadata = _read(config.output_file)[2]
    counts = {(record["run"], record["polarization"]): record
              for record in metadata["counts_by_run_state"]}
    assert set(counts) == {(42, 1), (0, 2), (8, 1)}
    assert counts[(42, 1)]["raw_input"] == 12
    assert counts[(42, 1)]["skipped_no_tagger"] == 4
    assert counts[(0, 2)]["raw_input"] == 8
    assert counts[(0, 2)]["skipped_no_tagger"] == 4
    assert counts[(8, 1)] == dict(run=8, polarization=1, input=0,
                                  raw_input=6, skipped_no_tagger=6)
    assert counts[(42, 1)]["input"] == (4 if events else 0)
    assert counts[(0, 2)]["input"] == (4 if events else 0)
