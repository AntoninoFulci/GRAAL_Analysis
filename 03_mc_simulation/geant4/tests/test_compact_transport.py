"""Compact storage must leave transport physics and source identities unchanged."""
import json
import os
from pathlib import Path
import subprocess

import numpy as np
import pytest
import uproot


@pytest.fixture
def native():
    binary, geometry = os.environ.get("GRAAL_G4_EXE"), os.environ.get("GRAAL_GDML")
    if not binary or not geometry:
        pytest.skip("Set native transport executable and geometry")
    return binary, geometry


def run_modes(native, tmp_path, commands):
    macro = tmp_path / "input.mac"
    macro.write_text("/random/setSeeds 12345 67890\n/run/initialize\n" + commands)
    paths = []
    for mode in ("full", "compact"):
        output = tmp_path / mode
        result = subprocess.run([*native, str(macro), str(output), "--storage", mode],
                                capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]
        paths.append(output / "transport.root")
    return paths


def equal_tree(left, right):
    assert left.keys() == right.keys()
    for name in left.keys():
        np.testing.assert_array_equal(left[name].array(library="np"), right[name].array(library="np"))


@pytest.mark.parametrize("particle", ["gamma", "chargedgeantino"])
def test_compact_preserves_physics_empty_events_and_cross_run_identity(native, tmp_path, particle):
    full, compact = run_modes(native, tmp_path,
        f"/gps/particle {particle}\n/gps/energy 200 MeV\n"
        "/gps/position 0 0 0 mm\n/gps/direction 1 0 0\n/run/beamOn 2\n"
        "/gps/position 1000 1000 -3000 mm\n/gps/direction 0 0 -1\n/run/beamOn 1\n"
        "/gps/position 0 0 0 mm\n/gps/direction 0.15 0.1 1\n/run/beamOn 1\n")
    with uproot.open(full) as f, uproot.open(compact) as c:
        for name in ("events", "primaries", "bgo_hits", "channels", "vertices", "cylinder_step_context"):
            equal_tree(f[name], c[name])
        sf, sc = (json.loads(str(root["summary"])) for root in (f, c))
        assert sf["hit_schema_version"] == 2 and sc["hit_schema_version"] == 3
        assert sc["storage_mode"] == "compact"
        for key in ("events", "attempted_events", "detector_steps", "all_callbacks", "passive_callbacks"):
            assert sf[key] == sc[key]
        channels = f["channels"].arrays(library="np")
        roles = dict(zip(channels["path"], channels["sensitive"]))
        fs = f["detector_steps"].arrays(library="np")
        cs = c["detector_steps"].arrays(library="np")
        retained = np.array([roles[p] != 1 for p in fs["path"]])
        np.testing.assert_array_equal(cs["source_step_entry"], np.flatnonzero(retained))
        for name, values in cs.items():
            if name != "source_step_entry":
                np.testing.assert_array_equal(values, fs[name][retained])
        assert "pre_dir_x" not in cs and "post_local_x_mm" not in cs
        assert sc["stored_detector_steps"] == len(cs["run"])
        ledger = c["events"].arrays(library="np")
        storage = c["storage_events"].arrays(library="np")
        for key in ("run", "event"):
            np.testing.assert_array_equal(ledger[key], storage[key])
        np.testing.assert_array_equal(storage["stored_steps"] + storage["bgo_steps"], ledger["hit_steps"])
        assert storage["stored_steps"][2] == storage["bgo_steps"][2] == 0
        assert json.loads(str(c["cylinder_context_metadata"]))["source_index"] == "original_sensitive_step"
        assert json.loads(str(c["storage_metadata"]))["response_scope"] == "current_response_no_step_quenching"
    if particle == "gamma":
        assert compact.stat().st_size < full.stat().st_size / 2


def test_invalid_storage_mode_fails_before_output(native, tmp_path):
    macro = tmp_path / "input.mac"
    macro.write_text("/run/initialize\n/run/beamOn 1\n")
    output = tmp_path / "invalid"
    result = subprocess.run([*native, str(macro), str(output), "--storage", "invalid"],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode != 0
    assert not output.exists()


def test_compact_aborted_event_keeps_complete_partial_accounting(native, tmp_path):
    binary = Path(native[0]).with_name("graal_abort_check")
    macro = tmp_path / "abort.mac"
    macro.write_text("/run/initialize\n/test/abortInBarrel\n/gps/particle proton\n"
                     "/gps/energy 200 MeV\n/gps/direction 1 0 0\n/run/beamOn 2\n")
    output = tmp_path / "aborted"
    result = subprocess.run([str(binary), native[1], str(macro), str(output), "--storage", "compact"],
                            capture_output=True, text=True, timeout=120)
    assert result.returncode != 0 and "aborted events" in result.stderr
    assert not (output / "transport.root").exists()
    with uproot.open(output / "transport.partial.root") as root:
        events = root["events"].arrays(library="np")
        storage = root["storage_events"].arrays(library="np")
        assert len(events["run"]) == root["primaries"].num_entries == 2
        assert np.all(events["aborted"] == 1)
        for key in ("run", "event"):
            np.testing.assert_array_equal(events[key], storage[key])
        np.testing.assert_array_equal(events["hit_steps"], storage["stored_steps"] + storage["bgo_steps"])
        assert int(storage["stored_steps"].sum()) == root["detector_steps"].num_entries
        assert "summary" not in root


def test_native_compact_input_contract_rejects_malformed_storage(native, tmp_path):
    binary = Path(native[0]).with_name("graal_compact_input_check")
    assert binary.is_file(), "Build compact input contract test harness"
    result = subprocess.run([str(binary), str(tmp_path)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
