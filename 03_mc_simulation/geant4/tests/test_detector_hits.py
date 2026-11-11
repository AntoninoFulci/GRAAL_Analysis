"""Transport records preserve response inputs, not calibrated detector signals."""
from collections import Counter, defaultdict
import math
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

import pytest
from mc_simulation.geant4.root_output import read_json, read_table


@pytest.fixture
def native():
    binary, geometry = os.environ.get("GRAAL_G4_EXE"), os.environ.get("GRAAL_GDML")
    if not binary or not geometry:
        pytest.skip("Set GRAAL_G4_EXE and GRAAL_GDML for native hit tests")
    return binary, geometry


def transport(native, tmp_path, commands, name="output"):
    macro = tmp_path / (name + ".mac")
    macro.write_text("/random/setSeeds 12345 67890\n/run/initialize\n" + commands)
    output = tmp_path / name
    result = subprocess.run([*native, str(macro), str(output)], capture_output=True,
                            text=True, timeout=120)
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]
    return output


def test_zero_deposit_crossings_channels_and_empty_events(native, tmp_path):
    output = transport(native, tmp_path,
        "/gps/particle chargedgeantino\n/gps/energy 200 MeV\n"
        "/gps/position 0 0 0 mm\n/gps/direction 1 0 0\n/run/beamOn 1\n"
        "/gps/direction 0.15 0.1 1\n/run/beamOn 1\n"
        "/gps/position 1000 1000 -3000 mm\n/gps/direction 0 0 -1\n/run/beamOn 1\n")
    assert (output / "transport.root").is_file(), "Sensitive steps are discarded"
    channels = read_table(output / "transport.root", "channels")
    assert len(channels) == len({c["path"] for c in channels}) == 592
    assert Counter(c["detector"] for c in channels) == {
        "bgo": 480, "barrel": 32, "tof_h": 26, "tof_v": 26, "shower": 16,
        "cyl_surface_1": 1, "cyl_surface_2": 1, "plane_1": 2, "plane_2": 2,
        "cyl_gas_1": 2, "cyl_gas_2": 2, "disk_1": 1, "disk_2": 1}
    barrel = [c for c in channels if c["detector"] == "barrel"]
    assert {int(c["legacy_channel"]) for c in barrel} == set(range(1, 33))
    assert all(int(c["copy"]) == int(c["legacy_channel"]) + 100 for c in barrel)
    lookup = {c["path"]: c for c in channels}
    steps = read_table(output / "transport.root", "detector_steps")
    assert steps and all(float(s["edep_MeV"]) == 0 for s in steps)
    crossed = {lookup[s["path"]]["detector"] for s in steps}
    assert {"cyl_surface_1", "cyl_surface_2", "cyl_gas_1", "cyl_gas_2",
            "barrel", "bgo", "plane_1", "plane_2", "tof_h", "tof_v", "shower"} <= crossed
    assert any(s["pre_boundary"] == 1 for s in steps)
    assert any(s["post_boundary"] == 1 for s in steps)
    for step in steps:
        channel = lookup[step["path"]]
        assert step["material"] == channel["material"]
        assert int(step["track"]) == 1 and int(step["parent"]) == 0
        assert float(step["charge_e"]) == 1
        assert float(step["post_time_ns"]) >= float(step["pre_time_ns"])
        assert float(step["step_length_mm"]) >= 0
        for key, value in step.items():
            if key.endswith(("_mm", "_ns", "_MeV")):
                assert math.isfinite(float(value)), (key, value)
    events = read_table(output / "transport.root", "events")
    assert len(events) == 3 and all(e["aborted"] == 0 for e in events)
    assert events[-1]["hit_steps"] == 0
    primaries = read_table(output / "transport.root", "primaries")
    assert len(primaries) == 3
    assert [p["run"] for p in primaries] == [0, 1, 2]
    assert all(float(p["particle_weight"]) == 1 for p in primaries)
    summary = read_json(output / "transport.root")
    assert summary["hit_schema_version"] == 2
    assert summary["attempted_events"] == 3
    assert summary["detector_steps"] == len(steps)


def test_steps_reproduce_bgo_aggregates_and_seeded_output(native, tmp_path):
    commands = "/gps/position 0 0 0 mm\n/gps/direction 1 0 0\n/gps/energy 200 MeV\n"
    for particle in ("gamma", "proton", "pi+", "pi-"):
        commands += f"/gps/particle {particle}\n/run/beamOn 2\n"
    output = transport(native, tmp_path, commands)
    assert (output / "transport.root").is_file(), "Sensitive steps are discarded"
    channels = {c["path"]: c for c in read_table(output / "transport.root", "channels")}
    sums, first, counts = defaultdict(float), {}, Counter()
    steps = read_table(output / "transport.root", "detector_steps")
    assert any(int(s["parent"]) > 0 for s in steps)
    for step in steps:
        counts[step["run"], step["event"]] += 1
        channel = channels[step["path"]]
        if channel["detector"] == "bgo" and float(step["edep_MeV"]) > 0:
            key = step["run"], step["event"], channel["legacy_channel"]
            sums[key] += float(step["edep_MeV"])
            first[key] = min(first.get(key, math.inf), float(step["pre_time_ns"]))
    hits = read_table(output / "transport.root", "bgo_hits")
    assert len(hits) == len(sums)
    for hit in hits:
        key = hit["run"], hit["event"], hit["crystal"]
        assert sums[key] == pytest.approx(float(hit["edep_MeV"]), abs=1e-10)
        assert first[key] == float(hit["first_time_ns"])
    for event in read_table(output / "transport.root", "events"):
        key = event["run"], event["event"]
        assert int(event["hit_steps"]) == counts[key]
        assert sum(v for k, v in sums.items() if k[:2] == key) == pytest.approx(
            float(event["bgo_edep_MeV"]), abs=1e-10)
    repeated = transport(native, tmp_path, commands, "repeated")
    for name in ("detector_steps", "channels", "events", "primaries", "bgo_hits"):
        assert read_table(output / "transport.root", name) == read_table(repeated / "transport.root", name)


def test_missing_sensitivity_metadata_fails_closed(native, tmp_path):
    tree = ET.parse(native[1])
    for volume in tree.findall("structure/volume"):
        for auxiliary in list(volume.findall("auxiliary")):
            if auxiliary.get("auxtype") == "geant3_sensitive":
                volume.remove(auxiliary)
    geometry = tmp_path / "old.gdml"
    tree.write(geometry)
    macro = tmp_path / "run.mac"
    macro.write_text("/run/initialize\n/run/beamOn 1\n")
    output = tmp_path / "failed"
    result = subprocess.run([native[0], str(geometry), str(macro), str(output)],
                            capture_output=True, text=True, timeout=120)
    assert result.returncode != 0
    assert "geant3_sensitive" in result.stderr
    assert not (output / "transport.root").exists()


@pytest.mark.parametrize("fault", ["unknown_sensitivity", "duplicate_crystal", "invalid_tof",
                                 "disabled_bgo", "missing_crystal"])
def test_ambiguous_or_unknown_detector_mapping_is_rejected(native, tmp_path, fault):
    tree = ET.parse(native[1])
    for volume in tree.findall("structure/volume"):
        name = next((a.get("auxvalue") for a in volume.findall("auxiliary")
                     if a.get("auxtype") == "geant3_volume"), "")
        if fault in {"unknown_sensitivity", "disabled_bgo"} and name == "BGO":
            next(a for a in volume.findall("auxiliary")
                 if a.get("auxtype") == "geant3_sensitive").set(
                     "auxvalue", "999" if fault == "unknown_sensitivity" else "0")
        if fault == "duplicate_crystal" and name == "NID2":
            volume.find("physvol").set("copynumber", "1")
        if fault == "invalid_tof" and name == "WAL1":
            volume.find("physvol").set("copynumber", "27")
        if fault == "missing_crystal" and name == "NID2":
            volume.remove(volume.find("physvol"))
    geometry = tmp_path / "invalid.gdml"
    tree.write(geometry)
    macro = tmp_path / "run.mac"
    macro.write_text("/run/initialize\n/gps/particle chargedgeantino\n/gps/energy 1 MeV\n"
                     "/gps/direction 1 0 0\n/run/beamOn 1\n")
    output = tmp_path / "failed"
    result = subprocess.run([native[0], str(geometry), str(macro), str(output)],
                            capture_output=True, text=True, timeout=120)
    assert result.returncode != 0, "Invalid mapping silently accepted"
    assert not (output / "transport.root").exists()


def test_aborted_events_keep_partial_hits_and_primaries_without_success(native, tmp_path):
    binary = Path(native[0]).with_name("graal_abort_check")
    assert binary.is_file(), "Build native abort test harness"
    macro = tmp_path / "abort.mac"
    macro.write_text("/run/initialize\n/test/abortInBarrel\n/gps/particle proton\n"
                     "/gps/energy 200 MeV\n/gps/direction 1 0 0\n/run/beamOn 2\n")
    output = tmp_path / "aborted"
    result = subprocess.run([str(binary), native[1], str(macro), str(output)],
                            capture_output=True, text=True, timeout=120)
    assert result.returncode != 0
    assert "aborted events" in result.stderr
    assert not (output / "transport.root").exists()
    events = read_table(output / "transport.partial.root", "events")
    assert len(events) == 2 and all(e["aborted"] == 1 for e in events)
    assert all(int(e["hit_steps"]) > 0 for e in events)
    primaries = read_table(output / "transport.partial.root", "primaries")
    assert len(primaries) == 2
    counts = Counter((s["run"], s["event"]) for s in read_table(output / "transport.partial.root", "detector_steps"))
    assert all(counts[e["run"], e["event"]] == int(e["hit_steps"]) for e in events)
