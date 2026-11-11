"""Exercise ROOT truth export and legacy compatibility using real generator files."""
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess

import pytest
from mc_simulation.geant4.root_output import read_json, read_table
from graal_common.physics.channels import CHANNELS

MODULE = Path(__file__).resolve().parents[1]


@pytest.fixture
def exporter():
    path = MODULE / "export_truth.py"
    assert path.is_file(), "ROOT truth exporter is missing"
    spec = importlib.util.spec_from_file_location("export_truth", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def source(tmp_path):
    ROOT = pytest.importorskip("ROOT")
    macro = MODULE.parent / "generators/generate_eta_pi0_dataset.C"
    if not hasattr(ROOT, macro.stem):
        assert ROOT.gROOT.LoadMacro(str(macro)) == 0
    path = tmp_path / "eta_pi0_mc.root"
    ROOT.generate_eta_pi0_dataset(4, 1.5, 1.6, str(path), 71)
    return path


def test_export_is_unsmeared_and_preserves_source_identity(exporter, source, tmp_path):
    ROOT = pytest.importorskip("ROOT")
    output = tmp_path / "truth"
    exporter.export_truth(source, output, "eta_pi0", 3)
    report = exporter.validate_root_truth(output / "truth.root")
    assert {p.name for p in output.iterdir()} == {"truth.root"}
    assert report["schema_version"] == 2
    assert report["events"] == 3 and report["source_events"] == 4
    assert report["source_sha256"] == exporter.sha256(source)
    assert report["truth_root_sha256"] == exporter.sha256(output / "truth.root")
    assert report["weight_policy"] == "unit_unweighted_no_flux_or_cross_section_normalization"
    assert report["polarization"] == "not_modeled"
    rows = read_table(output / "truth.root", "primaries")
    events = read_table(output / "truth.root", "events")
    assert len(rows) == 15
    with ROOT.TFile.Open(str(source)) as handle:
        tree = handle.Get("mc")
        for index in range(3):
            tree.GetEntry(index)
            assert events[index] == dict(event=index, source_entry=index, energy_GeV=tree.beam_true.E(),
                                         generation_weight=1., nprimaries=5)
            vectors = [tree.proton_true, tree.eta_gamma1_true, tree.eta_gamma2_true,
                       tree.pi0_gamma1_true, tree.pi0_gamma2_true]
            for part, vector in enumerate(vectors):
                row = rows[index * 5 + part]
                assert (row["event"], row["primary_index"], row["pdg"]) == (index, part, 2212 if part == 0 else 22)
                assert [row[k] for k in ("px_GeV", "py_GeV", "pz_GeV", "energy_GeV")] == [
                    vector.Px(), vector.Py(), vector.Pz(), vector.E()]
    with pytest.raises(FileExistsError):
        exporter.export_truth(source, output, "eta_pi0", 3)


def test_wrong_channel_or_missing_truth_does_not_export(exporter, source, tmp_path):
    with pytest.raises(ValueError, match="generator.*channel"):
        exporter.export_truth(source, tmp_path / "wrong", "pi0pi0", 3)
    ROOT = pytest.importorskip("ROOT")
    with ROOT.TFile.Open(str(source), "UPDATE") as handle:
        tree = handle.Get("mc")
        tree.SetBranchStatus("proton_true*", 0)
        replacement = tree.CloneTree()
        replacement.Write("mc", ROOT.TObject.kOverwrite)
    with pytest.raises(ValueError, match="truth branch"):
        exporter.export_truth(source, tmp_path / "missing", "eta_pi0", 3)


def test_corrupt_four_momentum_is_rejected(exporter):
    with pytest.raises(ValueError, match="conservation"):
        exporter.validate_event((0., 0., 1.5, 1.5), (0., 0., 0., .938272),
                                [(0., 0., 1., 1.)] * 4)


@pytest.mark.parametrize("channel", CHANNELS)
def test_all_channels_export_and_optional_transport(exporter, channel, tmp_path):
    ROOT = pytest.importorskip("ROOT")
    macro = MODULE.parent / "generators" / f"generate_{channel}_dataset.C"
    if not hasattr(ROOT, macro.stem):
        assert ROOT.gROOT.LoadMacro(str(macro)) == 0
    source = tmp_path / f"{channel}_mc.root"
    getattr(ROOT, macro.stem)(2, 1.5, 1.6, str(source), 71)
    output = tmp_path / "export"
    report = exporter.export_truth(source, output, max_events=10)
    assert report["events"] == 2
    assert report["channel"] == channel
    assert exporter.validate_root_truth(output / "truth.root")["events"] == 2
    binary, gdml = os.environ.get("GRAAL_G4_EXE"), os.environ.get("GRAAL_GDML")
    conditions = os.environ.get("GRAAL_PERIOD_CONDITIONS")
    if not binary or not gdml or not conditions:
        return  # Native integration is exercised when the three explicit inputs are configured.
    result = subprocess.run([binary, gdml, "--root-events", str(output / "truth.root"),
                             str(tmp_path / "transport"), "--conditions", conditions], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-4000:]
    summary = read_json(tmp_path / "transport/transport.root")
    assert summary["events"] == 2 and summary["source_mode"] == "root_replay"
    events = read_table(tmp_path / "transport/transport.root", "events")
    hits = read_table(tmp_path / "transport/transport.root", "bgo_hits")
    assert hits
    for hit in hits:
        assert 1 <= int(hit["crystal"]) <= 480
        assert math.isfinite(float(hit["edep_MeV"])) and float(hit["edep_MeV"]) > 0
        assert math.isfinite(float(hit["first_time_ns"])) and float(hit["first_time_ns"]) >= 0
    assert len(events) == 2
    for event in events:
        energy = math.fsum(float(h["edep_MeV"]) for h in hits if h["event"] == event["event"])
        assert math.isclose(energy, float(event["bgo_edep_MeV"]), rel_tol=1.e-12, abs_tol=1.e-10)


def test_legacy_export_and_reader_remain_compatible(exporter, source, tmp_path):
    from mc_simulation.geant4.run import validate_truth
    output = tmp_path / "legacy"
    report = exporter.export_truth(source, output, max_events=2, export_format="hepevt")
    assert report["schema_version"] == 1
    assert validate_truth(output) == report
    assert {p.name for p in output.iterdir()} == {"manifest.json", "primaries.dat", "truth.csv"}


def test_invalid_source_leaves_no_published_output(exporter, source, tmp_path, monkeypatch):
    def reject(*args):
        raise ValueError("deliberately invalid truth")
    monkeypatch.setattr(exporter, "validate_event", reject)
    output = tmp_path / "invalid"
    with pytest.raises(ValueError, match="invalid truth"):
        exporter.export_truth(source, output)
    assert not output.exists()
    assert not list(tmp_path.glob(".invalid-*"))


def rewrite_truth(path, *, mutate_metadata=None, mutate_columns=None):
    import uproot
    with uproot.open(path) as handle:
        metadata = json.loads(str(handle["metadata"]))
        arrays = {name: handle[name].arrays(library="np") for name in ("events", "primaries")}
    if mutate_metadata:
        mutate_metadata(metadata)
    if mutate_columns:
        mutate_columns(arrays)
    with uproot.recreate(path) as handle:
        for name, columns in arrays.items():
            handle.mktree(name, {key: values.dtype for key, values in columns.items()})
            handle[name].extend(columns)
        handle["metadata"] = json.dumps(metadata)


@pytest.mark.parametrize("field,value", [("schema_version", True), ("units", "MeV"),
    ("events", 2), ("source_events", 5), ("source_uuid", "00000000-0000-0000-0000-000000000000"),
    ("seed", 72), ("generation_target", "deuterium"), ("source_sha256", "0"*64)])
def test_root_reader_rejects_invalid_metadata(exporter, source, tmp_path, field, value):
    output = tmp_path / "truth"
    exporter.export_truth(source, output, max_events=3)
    rewrite_truth(output / "truth.root", mutate_metadata=lambda report: report.update({field: value}))
    with pytest.raises(ValueError):
        exporter.validate_root_truth(output / "truth.root")


@pytest.mark.parametrize("tree,field,value", [("events", "source_entry", 1),
    ("events", "generation_weight", 0.5), ("events", "nprimaries", 10),
    ("events", "energy_GeV", float("nan")), ("primaries", "primary_index", 1),
    ("primaries", "pdg", 22), ("primaries", "energy_GeV", 4.), ("primaries", "mass_GeV", 0.)])
def test_root_reader_rejects_invalid_scalars(exporter, source, tmp_path, tree, field, value):
    output = tmp_path / "truth"
    exporter.export_truth(source, output)
    def mutate(arrays):
        arrays[tree][field][0] = value
    rewrite_truth(output / "truth.root", mutate_columns=mutate)
    with pytest.raises(ValueError):
        exporter.validate_root_truth(output / "truth.root")


def test_root_reader_rejects_wrong_dtype_and_changed_source(exporter, source, tmp_path):
    output = tmp_path / "truth"
    exporter.export_truth(source, output)
    def mutate(arrays):
        arrays["events"]["source_entry"] = arrays["events"]["source_entry"].astype("int64")
    rewrite_truth(output / "truth.root", mutate_columns=mutate)
    with pytest.raises(ValueError, match="scalar truth branch"):
        exporter.validate_root_truth(output / "truth.root")
    with source.open("ab") as stream:
        stream.write(b"changed")
    with pytest.raises(ValueError, match="source hash mismatch"):
        exporter.validate_root_truth(output / "truth.root")


def test_root_reader_binds_vectors_to_source_entries(exporter, source, tmp_path):
    output = tmp_path / "truth"
    exporter.export_truth(source, output, max_events=2)
    def mutate(arrays):
        # Both events remain individually physical, but the declared source entries are false.
        for field in ("energy_GeV",):
            arrays["events"][field][:] = arrays["events"][field][::-1]
        for field in ("px_GeV", "py_GeV", "pz_GeV", "energy_GeV"):
            arrays["primaries"][field][:] = arrays["primaries"][field].reshape(2, 5)[::-1].ravel()
    rewrite_truth(output / "truth.root", mutate_columns=mutate)
    with pytest.raises(ValueError, match="claimed unsmeared source entry"):
        exporter.validate_root_truth(output / "truth.root")


def test_root_launcher_requires_period_before_build(exporter, source, tmp_path):
    import sys
    output, work = tmp_path / "truth", tmp_path / "transport"
    exporter.export_truth(source, output, max_events=2)
    result = subprocess.run([sys.executable, "-B", str(MODULE / "run.py"), "replay",
                             "--truth-dir", str(output), "--work-dir", str(work)],
                            capture_output=True, text=True)
    assert result.returncode != 0 and "ROOT truth replay requires --period" in result.stderr
    assert not work.exists()


def test_replay_completion_rechecks_original_generator(exporter, source, tmp_path):
    import hashlib
    from mc_simulation.geant4.run import validate_replay_completion
    output = tmp_path / "truth"
    report = exporter.export_truth(source, output, max_events=2)
    path = output / "truth.root"
    summary = dict(events=2, source_mode="root_replay", input_source=str(path),
                   input_md5=hashlib.md5(path.read_bytes()).hexdigest())
    validate_replay_completion(report, path, summary)
    # The replay artifact stays byte-identical while its original source changes.
    with source.open("ab") as stream:
        stream.write(b"changed during build or transport")
    assert exporter.sha256(path) == report["truth_root_sha256"]
    with pytest.raises(ValueError, match="source hash mismatch"):
        validate_replay_completion(report, path, summary)
