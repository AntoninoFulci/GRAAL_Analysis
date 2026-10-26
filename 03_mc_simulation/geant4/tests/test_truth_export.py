"""Exercise the ROOT-to-HEPEvt boundary using real generator files."""
import importlib.util
import json
import csv
import math
import os
from pathlib import Path
import subprocess

import pytest
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
    report = json.loads((output / "manifest.json").read_text())
    assert report["events"] == 3 and report["source_events"] == 4
    assert report["source_sha256"] == exporter.sha256(source)
    assert report["primary_sha256"] == exporter.sha256(output / "primaries.dat")
    assert report["weight_policy"] == "unit_unweighted_no_flux_or_cross_section_normalization"
    assert report["polarization"] == "not_modeled"
    lines = (output / "primaries.dat").read_text().splitlines()
    assert len(lines) == 3 * 6
    with ROOT.TFile.Open(str(source)) as handle:
        tree = handle.Get("mc")
        for index in range(3):
            tree.GetEntry(index)
            assert lines[index * 6] == "5"
            vectors = [tree.proton_true, tree.eta_gamma1_true, tree.eta_gamma2_true,
                       tree.pi0_gamma1_true, tree.pi0_gamma2_true]
            for part, vector in enumerate(vectors):
                fields = lines[index * 6 + part + 1].split()
                assert list(map(int, fields[:4])) == [1, 2212 if part == 0 else 22, 0, 0]
                assert list(map(float, fields[4:7])) == [vector.Px(), vector.Py(), vector.Pz()]
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
def test_all_channels_export_and_transport(exporter, channel, tmp_path):
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
    binary, gdml = os.environ.get("GRAAL_G4_EXE"), os.environ.get("GRAAL_GDML")
    if not binary or not gdml:
        pytest.skip("Export passed; native replay requires GRAAL_G4_EXE and GRAAL_GDML")
    result = subprocess.run([binary, gdml, "--hepevt", str(output / "primaries.dat"),
                             str(tmp_path / "transport")], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-4000:]
    summary = json.loads((tmp_path / "transport/summary.json").read_text())
    assert summary["events"] == 2 and summary["source_mode"] == "hepevt"
    with (tmp_path / "transport/events.csv").open() as stream:
        events = list(csv.DictReader(stream))
    with (tmp_path / "transport/bgo_hits.csv").open() as stream:
        hits = list(csv.DictReader(stream))
    assert hits
    for hit in hits:
        assert 1 <= int(hit["crystal"]) <= 480
        assert math.isfinite(float(hit["edep_MeV"])) and float(hit["edep_MeV"]) > 0
        assert math.isfinite(float(hit["first_time_ns"])) and float(hit["first_time_ns"]) >= 0
    assert len(events) == 2
    for event in events:
        energy = math.fsum(float(h["edep_MeV"]) for h in hits if h["event"] == event["event"])
        assert math.isclose(energy, float(event["bgo_edep_MeV"]), rel_tol=1.e-12, abs_tol=1.e-10)
