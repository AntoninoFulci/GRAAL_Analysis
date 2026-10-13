"""Raw detector labels survive selection and buffered reconstruction unchanged."""
from array import array
from pathlib import Path

import numpy as np
import pytest
import ROOT

from event_selector import select_events
from reconstruction.runtime import reco_core
from reconstruction.core.reco_physics import ETA_PI0


FIELDS = ("Nass_3", "Itipo_track", "Nparf", "Nparf_strange", "N_traf",
          "Index_trf", "Iass_trf", "RawSourceFile", "RawSourceEntry")


def ints(values):
    return [ord(v) if isinstance(v, str) else int(v) for v in values]


@pytest.fixture
def raw_contract():
    header = Path(__file__).resolve().parents[1] / "01_pre_analysis/RawTrackContract.h"
    assert header.exists(), "raw-track bounds must be checked before reading fixed buffers"
    assert ROOT.gInterpreter.Declare(f'#include "{header}"')
    return ROOT.graal_raw_tracks


def test_raw_counts_checked_before_fixed_array_read(raw_contract):
    raw_contract.CheckCounts(0, 0, 0)
    raw_contract.CheckCounts(291, 90, 90)
    for args in ((-1, 0, 0), (292, 0, 0), (0, -1, 0), (0, 91, 0),
                 (0, 0, -1), (0, 0, 91)):
        with pytest.raises(Exception, match="capacity"):
            raw_contract.CheckCounts(*args)


def test_tagger_count_checked_before_fixed_array_read(raw_contract):
    for count in (0, 1, 128):
        raw_contract.CheckTaggerCount(count)
    for count in (-1, 129):
        with pytest.raises(Exception, match="tagger.*capacity"):
            raw_contract.CheckTaggerCount(count)


def test_forward_lookup_bounds_without_reinterpreting_zero(raw_contract):
    assert raw_contract.LegacyAssociationIndex(1, 2) == 0
    assert raw_contract.LegacyAssociationIndex(2, 2) == 1
    assert raw_contract.LegacyAssociationIndex(0, 2) == 0
    for index, count in ((0, 0), (1, 0), (3, 2), (255, 90)):
        with pytest.raises(Exception, match="sentinel definition"):
            raw_contract.LegacyAssociationIndex(index, count)


@pytest.mark.parametrize("counts", [(0, 0, 0), (291, 90, 90)])
def test_metadata_snapshot_preserves_empty_and_capacity_arrays(counts):
    from types import SimpleNamespace
    from graal_common.io.raw_tracks import snapshot_raw_tracks

    nc, nf, na = counts
    row = SimpleNamespace(Nass_3=nc, Nparf=nf, N_traf=na, Nparf_strange=255,
                          Itipo_track=[-5] * nc, Index_trf=[255] * nf,
                          Iass_trf=[0] * na, RawSourceFile="raw.root", RawSourceEntry=17)
    saved = snapshot_raw_tracks(row)
    row.Itipo_track[:] = []
    assert saved["Itipo_track"] == (-5,) * nc
    assert saved["Index_trf"] == (255,) * nf
    row.Nparf += 1
    with pytest.raises(ValueError, match="length/count|invalid"):
        snapshot_raw_tracks(row)


def write_fixture(path, *, metadata=True, partial=False, wrong_type=False):
    f = ROOT.TFile(str(path), "RECREATE")
    t = ROOT.TTree("h80", "h80")
    beam = ROOT.TLorentzVector(0, 0, 1.2, 1.2)
    t.Branch("beam", beam)
    vector_type = "ROOT::Math::LorentzVector<ROOT::Math::PxPyPzE4D<double> >"
    four_vector = getattr(ROOT, vector_type)
    vectors = {n: ROOT.std.vector(vector_type)() for n in ("gammas", "protons", "neutrons")}
    for n, v in vectors.items():
        t.Branch(n, v)
    charged = ROOT.std.vector("double")([0.1])
    t.Branch("fcharged_theta", charged)
    scalars = {"RunNumber": array("i", [1321]), "Polarization": array("i", [1]),
               "Xstrip": array("f", [17])}
    if metadata:
        scalars.update(Nass_3=array("i", [3]), Nparf=array("i", [3]),
                       N_traf=array("i", [2]), Nparf_strange=array("B", [1]),
                       RawSourceEntry=array("q", [0]))
        if wrong_type:
            scalars["Nparf_strange"] = array("f", [1.7])
    for n, v in scalars.items():
        code = {"i": "I", "f": "F", "B": "b", "q": "L"}[v.typecode]
        t.Branch(n, v, f"{n}/{code}")
    if metadata:
        source = ROOT.std.string("raw/run1321.root")
        t.Branch("RawSourceFile", source)
        labels = ROOT.std.vector("int")([11, 99, -3])
        indices = ROOT.std.vector("unsigned char")([0, 1, 2])
        associations = ROOT.std.vector("unsigned char")([7, 255])
        t.Branch("Itipo_track", labels)
        t.Branch("Index_trf", indices)
        if not partial:
            t.Branch("Iass_trf", associations)
    for i in range(4):
        vectors["gammas"].clear()
        for p in ((.1, 0, .2, .25), (-.1, 0, .2, .25), (0, .05, .1, .12), (0, -.05, .1, .12)):
            vectors["gammas"].push_back(four_vector(*p))
        vectors["protons"].clear()
        vectors["protons"].push_back(four_vector(0, 0, .1, .95))
        if i == 1:
            vectors["gammas"].resize(1)
        if metadata:
            scalars["RawSourceEntry"][0] = 101 + i
            scalars["Nparf_strange"][0] = i
        t.Fill()
    t.Write()
    f.Close()


@pytest.mark.parametrize("gated", [False, True])
def test_labels_and_source_identity_survive_selection_and_buffered_reco(tmp_path, monkeypatch, gated):
    pre = tmp_path / "pre"
    pre.mkdir()
    write_fixture(pre / "pre_sample.root")
    selected = tmp_path / "selected"
    select_events.run(pre, selected, threads=2)
    monkeypatch.setattr(reco_core, "_GATE_CHUNK", 2)

    class Gate:
        threshold = .5
        calls = 0

        def scores_many(self, photons, protons, beams):
            self.calls += 1
            return np.array([.9, .1]) if self.calls == 1 else np.array([.9])

    cfg = reco_core.RecoConfig(selected, tmp_path / "reco.root", chi2_cut=1000,
                               missing_mass_window=None)
    count = reco_core.run_reconstruction(cfg, ETA_PI0, Gate() if gated else None)
    assert count == (2 if gated else 3)
    f = ROOT.TFile.Open(str(cfg.output_file))
    try:
        t = f.Get("reco")
        assert all(t.GetBranch(n) for n in FIELDS)
        seen = {}
        for row in t:
            assert str(row.RawSourceFile) == "raw/run1321.root"
            assert list(row.Itipo_track) == [11, 99, -3]
            assert ints(row.Index_trf) == [0, 1, 2]
            assert ints(row.Iass_trf) == [7, 255]
            assert (row.Nass_3, row.Nparf, row.N_traf) == (3, 3, 2)
            value = row.Nparf_strange
            seen[int(row.RawSourceEntry)] = ord(value) if isinstance(value, str) else int(value)
        # Snapshot may reorder entries with MT: identity, never position, is the key.
        assert set(seen) <= {101, 103, 104}
        assert all(value == entry - 101 for entry, value in seen.items())
        if not gated:
            assert seen == {101: 0, 103: 2, 104: 3}
    finally:
        f.Close()


@pytest.mark.parametrize("partial", [False, True])
def test_mixed_or_partial_metadata_rejected_before_output(tmp_path, partial):
    source = tmp_path / "input"
    source.mkdir()
    write_fixture(source / "a.root", partial=partial)
    if not partial:
        write_fixture(source / "b.root", metadata=False)
    cfg = reco_core.RecoConfig(source, tmp_path / "output.root", input_tree="h80")
    with pytest.raises(ValueError, match="raw.track|Raw.track"):
        reco_core.run_reconstruction(cfg, ETA_PI0)
    assert not cfg.output_file.exists()


def test_legacy_inputs_do_not_gain_fake_zero_metadata(tmp_path):
    source = tmp_path / "input"
    source.mkdir()
    write_fixture(source / "a.root", metadata=False)
    cfg = reco_core.RecoConfig(source, tmp_path / "output.root", input_tree="h80",
                               chi2_cut=1000, missing_mass_window=None)
    assert reco_core.run_reconstruction(cfg, ETA_PI0) == 3
    f = ROOT.TFile.Open(str(cfg.output_file))
    try:
        assert not f.Get("reco").GetBranch("Nparf_strange")
    finally:
        f.Close()


def test_wrong_metadata_type_rejected_before_output(tmp_path):
    source = tmp_path / "input"
    source.mkdir()
    write_fixture(source / "a.root", wrong_type=True)
    cfg = reco_core.RecoConfig(source, tmp_path / "output.root", input_tree="h80")
    with pytest.raises(ValueError, match="raw-track.*Nparf_strange"):
        reco_core.run_reconstruction(cfg, ETA_PI0)
    assert not cfg.output_file.exists()


def test_audit_bounds_sample_and_counts_unknown_values(tmp_path):
    from scripts.audit_raw_tracks import audit

    source = tmp_path / "input.root"
    write_fixture(source)
    info = audit(source, entries=2, sha256=True)
    assert len(info["sha256"]) == 64
    sample = info["trees"]["h80"]["sample"]
    assert sample["entry_stop"] == 2
    assert sample["nonzero_strange_events"] == 1
    assert sample["zero_forward_indices"] == 2
    assert sample["count_length_mismatches"] == {"Itipo_track": 0, "Index_trf": 0, "Iass_trf": 0}
    assert sample["values"]["Iass_trf"] == {"7": 2, "255": 2}


@pytest.fixture(scope="module")
def preanalysis_macro():
    repo = Path(__file__).resolve().parents[1]
    if not (repo / "test_data/raw/1998_uv/run1321.root").exists():
        pytest.skip("local raw sample unavailable")
    ROOT.gROOT.LoadMacro(str(repo / "01_pre_analysis/PreAnalysis.C"))
    ROOT.gInterpreter.ProcessLine(f'BuildCutMap("{repo / "test_data/raw"}", "{repo / "01_pre_analysis/cuts"}");')


@pytest.mark.parametrize("only_untagged", [False, True])
def test_raw_h70_round_trip(tmp_path, capfd, only_untagged, preanalysis_macro):
    repo = Path(__file__).resolve().parents[1]
    raw = repo / "test_data/raw/1998_uv/run1321.root"
    if not raw.exists():
        pytest.skip("local raw sample unavailable")
    original = ROOT.TFile.Open(str(raw))
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    sample = raw_dir / "part1.root"
    subset = ROOT.TFile(str(sample), "RECREATE")
    source = original.Get("h70")
    source.GetEntry(21)
    assert source.Ncstrip == 0
    clone = source.CloneTree(0)
    # Start each chain file without a tag, and exercise a valid -> absent tag
    # transition inside the mixed sample. These rows must never reach h80.
    entries = [21, 21] if only_untagged else [21, *range(512)]
    for entry in entries:
        source.GetEntry(entry)
        clone.Fill()
    clone.Write()
    subset.Close()
    original.Close()
    import shutil
    second = raw_dir / "part2.root"
    shutil.copyfile(sample, second)
    output = tmp_path / "pre_sample.root"
    ROOT.gInterpreter.ProcessLine(f'PreAnalysis("{raw_dir}/*.root", "{output}");')
    f = ROOT.TFile.Open(str(output))
    r = ROOT.TFile.Open(str(sample))
    try:
        t, h70 = f.Get("h80"), r.Get("h70")
        tagged_entries = []
        for entry in range(h70.GetEntries()):
            h70.GetEntry(entry)
            if h70.Ncstrip > 0:
                tagged_entries.append(entry)
        skipped = 2 * (h70.GetEntries() - len(tagged_entries))
        assert t.GetEntries() == 2 * len(tagged_entries)
        assert f.Get("preanalysis_skipped_no_tagger").GetVal() == skipped
        assert f"skipped_no_tagger={skipped}" in capfd.readouterr().out
        assert all(t.GetBranch(n) for n in FIELDS)
        expected = {}
        expected_rows = [(path, entry) for path in (sample, second)
                         for entry in tagged_entries]
        for i, (path, entry) in enumerate(expected_rows):
            t.GetEntry(i)
            h70.GetEntry(entry)
            assert int(t.RawSourceEntry) == entry
            assert str(t.RawSourceFile) == str(path)
            assert t.beam.E() == h70.Eg_tag_strip[0]
            assert t.Xstrip == h70.Xstrip[0]
            for n in ("Nass_3", "Nparf", "N_traf", "Nparf_strange"):
                assert getattr(t, n) == getattr(h70, n)
            for n in ("Itipo_track", "Index_trf", "Iass_trf"):
                assert ints(getattr(t, n)) == ints(getattr(h70, n))
            expected[(str(t.RawSourceFile), int(t.RawSourceEntry))] = ints(t.Itipo_track)
    finally:
        f.Close()
        r.Close()
    if only_untagged:
        return
    selected = tmp_path / "selected"
    selected.mkdir()
    select_events._select_file(output, selected / "sample.root")
    cfg = reco_core.RecoConfig(selected, tmp_path / "reco.root", chi2_cut=1000,
                               missing_mass_window=None)
    assert reco_core.run_reconstruction(cfg, ETA_PI0) > 0
    for path, name in ((selected / "sample.root", "h85"), (cfg.output_file, "reco")):
        f = ROOT.TFile.Open(str(path))
        try:
            seen = set()
            for row in f.Get(name):
                key = (str(row.RawSourceFile), int(row.RawSourceEntry))
                assert key not in seen
                seen.add(key)
                assert ints(row.Itipo_track) == expected[key]
            assert seen
        finally:
            f.Close()
