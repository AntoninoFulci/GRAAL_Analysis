"""Native transport checks; diagnostic energy deposits are not detector validation."""
import csv
import json
import math
import os
from pathlib import Path
import subprocess

import pytest


@pytest.fixture
def native():
    binary = os.environ.get("GRAAL_G4_EXE")
    geometry = os.environ.get("GRAAL_GDML")
    if not binary or not geometry:
        pytest.skip("Set GRAAL_G4_EXE and GRAAL_GDML for native transport tests")
    assert Path(binary).is_file(), "Build graal_g4 before native transport tests"
    return binary, geometry


def run(native, macro, output):
    return subprocess.run([*native, str(macro), str(output)], capture_output=True,
                          text=True, timeout=120)


def test_gamma_transport_scores_energy_and_records_diagnostic_scope(native, tmp_path):
    macro = tmp_path / "gamma input.mac"
    macro.write_text("/random/setSeeds 12345 67890\n/run/initialize\n"
                     "/gps/particle gamma\n/gps/energy 200 MeV\n"
                     "/gps/position 0 0 0 cm\n/gps/direction 1 0 0\n/run/beamOn 10\n")
    output = tmp_path / "events"
    result = run(native, macro, output)
    assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-4000:]
    with (output / "events.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 10
    deposits = [float(row["bgo_edep_MeV"]) for row in rows]
    assert all(math.isfinite(value) and value >= 0 for value in deposits)
    assert sum(deposits) > 0
    assert all(float(row["total_edep_MeV"]) >= float(row["bgo_edep_MeV"]) for row in rows)
    summary = json.loads((output / "summary.json").read_text())
    assert summary["events"] == 10
    assert summary["status"] == "diagnostic_transport_only"
    assert summary["physics_list"] == "FTFP_BERT_HP_EMZ"
    assert summary["em_range_cut_mm"] == 0.1
    assert summary["proton_range_cut_mm"] == 0
    materials = json.loads((output / "materials.json").read_text())["materials"]
    for material in materials:
        assert math.isclose(sum(e["fraction"] for e in material["elements"]), 1.)
        assert all(e["Z"] == int(e["Z"]) for e in material["elements"])
    deuterium = next(m for m in materials if m["id"] == 1)
    assert deuterium["elements"][0]["isotopes"] == [{"A": 2, "abundance": 1}]
    gas = next(m for m in materials if m["id"] == 18)
    assert {e["Z"] for e in gas["elements"]} == {1, 6, 18}
    stesa = next(m for m in materials if m["id"] == 22)
    assert {e["Z"] for e in stesa["elements"]} == {1, 6, 8, 14}
    repeated = tmp_path / "repeated"
    result = run(native, macro, repeated)
    assert result.returncode == 0, result.stderr
    assert (output / "events.csv").read_bytes() == (repeated / "events.csv").read_bytes()
    assert (output / "bgo_hits.csv").read_bytes() == (repeated / "bgo_hits.csv").read_bytes()


def test_existing_output_is_preserved(native, tmp_path):
    sentinel = tmp_path / "sentinel"
    sentinel.write_text("preserve")
    macro = tmp_path / "run.mac"
    macro.write_text("/run/initialize\n/run/beamOn 1\n")
    result = run(native, macro, tmp_path)
    assert result.returncode != 0
    assert "refusing overwrite" in result.stderr
    assert sentinel.read_text() == "preserve"


def test_bad_macro_does_not_report_success(native, tmp_path):
    macro = tmp_path / "bad.mac"
    macro.write_text("/this/command/does/not/exist\n")
    output = tmp_path / "failed"
    result = run(native, macro, output)
    assert result.returncode != 0
    assert not (output / "summary.json").exists()


def test_different_target_requires_explicit_material_policy(native, tmp_path):
    import xml.etree.ElementTree as ET

    tree = ET.parse(native[1])
    elements = tree.getroot().findall("materials/element")
    target = next(e for e in elements if e.attrib["name"].startswith("G3_1_E1"))
    target.find("atom").set("value", "1.008")
    geometry = tmp_path / "hydrogen.gdml"
    tree.write(geometry)
    macro = tmp_path / "run.mac"
    macro.write_text("/run/initialize\n/run/beamOn 1\n")
    result = run((native[0], str(geometry)), macro, tmp_path / "rejected")
    assert result.returncode != 0
    assert "Expected frozen deuterium target" in result.stderr
    assert not (tmp_path / "rejected/summary.json").exists()


@pytest.mark.parametrize("contents", ["", "2\n1 2212 0 0 0 0 0 .938272\n",
    "2\n1 2212 0 0 0 0 0 .938272\n1 11 0 0 1 0 0 0\n",
    "2\n1 2212 0 0 0 0 0 .938272\n1 22 0 0 nan 0 0 0\n",
    "2\n1 2212 0 0 0 0 0 .938272\n1 22 0 0 1 0 0 0\njunk\n"])
def test_invalid_hepevt_fails_without_success(native, tmp_path, contents):
    primary = tmp_path / "primaries.dat"
    primary.write_text(contents)
    output = tmp_path / "failed"
    result = subprocess.run([*native, "--hepevt", str(primary), str(output)], capture_output=True,
                            text=True, timeout=120)
    assert result.returncode != 0
    assert "HEPEvt" in result.stderr
    assert not (output / "summary.json").exists()


def test_replay_is_repeatable_and_preserves_existing_output(native, tmp_path):
    primary = tmp_path / "primaries with spaces.dat"
    primary.write_text("2\n1 2212 0 0 0 0 0 .938272\n1 22 0 0 .2 0 0 0\n" * 2)
    for name in ("one", "two"):
        result = subprocess.run([*native, "--hepevt", str(primary), str(tmp_path / name)],
                                capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, result.stderr
    for name in ("events.csv", "bgo_hits.csv", "run-0.rndm"):
        assert (tmp_path / "one" / name).read_bytes() == (tmp_path / "two" / name).read_bytes()
    result = subprocess.run([*native, "--hepevt", str(primary), str(tmp_path / "one")],
                            capture_output=True, text=True, timeout=120)
    assert result.returncode != 0 and "refusing overwrite" in result.stderr
