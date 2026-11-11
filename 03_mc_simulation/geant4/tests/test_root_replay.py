"""Native ROOT replay guards and exact preservation of unsmeared primaries."""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import shlex
import shutil
import subprocess

import numpy as np
import pytest
import uproot

G4 = Path(__file__).resolve().parents[1]
MASS = 0.938272
EVENT_TYPES = dict(event="int32", source_entry="uint64", energy_GeV="float64",
                   generation_weight="float64", nprimaries="int32")
PRIMARY_TYPES = dict(event="int32", primary_index="int32", pdg="int32",
                     **{name + "_GeV": "float64" for name in ("px", "py", "pz", "energy", "mass")})


@pytest.fixture(scope="module")
def reader(tmp_path_factory):
    config = os.environ.get("ROOT_CONFIG") or shutil.which("root-config")
    if not config:
        pytest.skip("Native ROOT root-config required")
    binary = tmp_path_factory.mktemp("root-reader") / "check_root_replay"
    flags = subprocess.check_output([config, "--cflags", "--libs"], text=True)
    result = subprocess.run(["c++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                             "-I", str(G4 / "src"), str(G4 / "tests/check_root_replay.cc"),
                             "-o", str(binary), *shlex.split(flags)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return binary


def fixture():
    events, primaries = [], []
    for event, energy in enumerate((1.0, 1.2)):
        outgoing = energy / (1 + energy / MASS)
        vectors = [(2212, -outgoing, 0., energy, energy + MASS - outgoing, MASS)]
        vectors += [(22, outgoing / (event + 1), 0., 0., outgoing / (event + 1), 0.)] * (event + 1)
        events.append(dict(event=event, source_entry=event, energy_GeV=energy,
                           generation_weight=1., nprimaries=len(vectors)))
        for index, values in enumerate(vectors):
            primaries.append(dict(zip(PRIMARY_TYPES, (event, index, *values))))
    metadata = dict(schema_version=2, status="diagnostic_truth_export", events=2, source_events=2,
                    source="/original/generator.root", source_sha256="a" * 64,
                    generator="generate_eta_pi0_dataset", generator_schema_version=1,
                    sampling="accept-reject-unweighted; TRandom3 shared with TGenPhaseSpace",
                    units="GeV", generation_target="free_proton", geometry_target="period_conditions_required",
                    weight_policy="unit_unweighted_no_flux_or_cross_section_normalization")
    return metadata, events, primaries


def write(path, metadata, events, primaries, event_types=None, primary_types=None):
    with uproot.recreate(path) as root:
        if metadata is not None:
            root["metadata"] = metadata if isinstance(metadata, str) else json.dumps(metadata)
        for name, rows, types in (("events", events, event_types or EVENT_TYPES),
                                  ("primaries", primaries, primary_types or PRIMARY_TYPES)):
            tree = root.mktree(name, types)
            if rows:
                tree.extend({key: np.array([row[key] for row in rows], dtype=dtype.split(" * ")[-1])
                             for key, dtype in types.items()})


def test_native_reader_preserves_double_momenta_and_event_order(reader, tmp_path):
    metadata, events, primaries = fixture()
    path = tmp_path / "truth.root"
    write(path, metadata, events, primaries)
    result = subprocess.run([reader, path], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    decoded = json.loads(result.stdout)
    assert [row["energy"] for row in decoded] == [e["energy_GeV"] for e in events]
    actual = [p for row in decoded for p in row["primaries"]]
    assert actual == [[row[key] for key in list(PRIMARY_TYPES)[2:]] for row in primaries]


CASES = ["missing_metadata", "bad_json", "duplicate_json", "schema", "fractional_schema", "status",
         "metadata_count", "fractional_count", "source_count", "units", "target", "weighted_policy",
         "empty", "event_order", "source_order", "weight", "nan_beam", "negative_beam", "nprimaries",
         "missing_primary", "orphan_primary", "primary_order", "pdg", "nan_momentum", "mass", "off_shell",
         "conservation", "negative_mass", "wrong_type", "array_type", "missing_branch"]


def malformed(case):
    metadata, events, primaries = copy.deepcopy(fixture())
    event_types, primary_types = dict(EVENT_TYPES), dict(PRIMARY_TYPES)
    if case == "missing_metadata": metadata = None
    elif case == "bad_json": metadata = "{bad"
    elif case == "duplicate_json": metadata = json.dumps(metadata)[:-1] + ',"events":2}'
    elif case == "schema": metadata["schema_version"] = 1
    elif case == "fractional_schema": metadata["schema_version"] = 2.0
    elif case == "status": metadata["status"] = "production"
    elif case == "metadata_count": metadata["events"] = 3
    elif case == "fractional_count": metadata["events"] = 2.0
    elif case == "source_count": metadata["source_events"] = 1
    elif case == "units": metadata["units"] = "MeV"
    elif case == "target": metadata["generation_target"] = "deuteron"
    elif case == "weighted_policy": metadata["weight_policy"] = "weighted"
    elif case == "empty": events, primaries = [], []
    elif case == "event_order": events[1]["event"] = 0
    elif case == "source_order": events[1]["source_entry"] = 0
    elif case == "weight": events[1]["generation_weight"] = 0.5
    elif case == "nan_beam": events[1]["energy_GeV"] = math.nan
    elif case == "negative_beam": events[1]["energy_GeV"] = -1.
    elif case == "nprimaries": events[1]["nprimaries"] = 4
    elif case == "missing_primary": primaries.pop()
    elif case == "orphan_primary": primaries.append(dict(primaries[-1], event=2))
    elif case == "primary_order": primaries[1]["primary_index"] = 0
    elif case == "pdg": primaries[0]["pdg"] = 22
    elif case == "nan_momentum": primaries[0]["px_GeV"] = math.nan
    elif case == "mass": primaries[0]["mass_GeV"] += 0.001
    elif case == "negative_mass": primaries[1]["mass_GeV"] = -1e-10
    elif case == "off_shell": primaries[0]["energy_GeV"] += 0.001
    elif case == "conservation": events[0]["energy_GeV"] += 0.01
    elif case == "wrong_type": event_types["source_entry"] = "int64"
    elif case == "array_type":
        event_types["energy_GeV"] = "2 * float64"
        for row in events: row["energy_GeV"] = [row["energy_GeV"], row["energy_GeV"]]
    elif case == "missing_branch": primary_types.pop("energy_GeV")
    return metadata, events, primaries, event_types, primary_types


@pytest.mark.parametrize("case", CASES)
def test_rejects_malformed_truth_before_replay(reader, tmp_path, case):
    path = tmp_path / "truth.root"
    write(path, *malformed(case))
    result = subprocess.run([reader, path], capture_output=True, text=True)
    assert result.returncode == 1, (case, result.stdout, result.stderr)
    assert "ERROR:" in result.stderr
    assert result.stdout == ""


def test_native_transport_rejects_invalid_root_without_creating_output(tmp_path):
    binary, geometry = os.environ.get("GRAAL_G4_EXE"), os.environ.get("GRAAL_GDML")
    conditions = os.environ.get("GRAAL_PERIOD_CONDITIONS")
    if not all((binary, geometry, conditions)):
        pytest.skip("Set native binary, period geometry, and conditions")
    path, output = tmp_path / "truth.root", tmp_path / "output"
    write(path, *malformed("off_shell"))
    result = subprocess.run([binary, geometry, "--root-events", path, output, "--conditions", conditions],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 1
    assert "off shell" in result.stderr
    assert not output.exists()


def test_native_root_transport_preserves_primaries_and_period_vertices(tmp_path):
    binary, geometry = os.environ.get("GRAAL_G4_EXE"), os.environ.get("GRAAL_GDML")
    conditions = os.environ.get("GRAAL_PERIOD_CONDITIONS")
    if not all((binary, geometry, conditions)):
        pytest.skip("Set native binary, period geometry, and conditions")
    metadata, events, primaries = fixture()
    path, output = tmp_path / "truth.root", tmp_path / "output"
    write(path, metadata, events, primaries)
    result = subprocess.run([binary, geometry, "--root-events", path, output, "--conditions", conditions],
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]
    assert {item.name for item in output.iterdir()} == {"transport.root"}
    with uproot.open(output / "transport.root") as root:
        summary = json.loads(str(root["summary"]))
        assert summary["source_mode"] == "root_replay"
        assert summary["events"] == summary["attempted_events"] == len(events)
        assert summary["aborted"] == 0
        assert summary["replay_input_path"] == str(path.resolve())
        assert summary["replay_input_md5"] == hashlib.md5(path.read_bytes()).hexdigest()
        rows = root["primaries"].arrays(library="np")
        assert len(rows["event"]) == len(primaries)
        assert np.all(rows["run"] == 0) and np.all(rows["vertex"] == 0)
        assert np.all(rows["vertex_weight"] == 1) and np.all(rows["particle_weight"] == 1)
        assert np.all(rows["time_ns"] == 0)
        for i, primary in enumerate(primaries):
            assert rows["event"][i] == primary["event"]
            assert rows["particle"][i] == primary["primary_index"]
            assert rows["pdg"][i] == primary["pdg"]
            for axis in ("px", "py", "pz"):
                assert rows[axis + "_MeV"][i] == pytest.approx(primary[axis + "_GeV"] * 1000,
                                                               rel=1e-12, abs=1e-10)
            assert rows["kinetic_MeV"][i] == pytest.approx(
                (primary["energy_GeV"] - primary["mass_GeV"]) * 1000, abs=1e-5)
        vertices = root["vertices"].arrays(library="np")
        assert np.array_equal(vertices["event"], np.arange(len(events)))
        header = Path(conditions).read_text().splitlines()[0].split()
        length, center, diameter = map(float, header[3:6])
        assert np.all(vertices["x_mm"] ** 2 + vertices["y_mm"] ** 2 < (diameter / 2) ** 2)
        assert np.all(np.abs(vertices["z_mm"] - center) <= length / 2)
        for i, primary in enumerate(primaries):
            for axis in ("x", "y", "z"):
                assert rows[axis + "_mm"][i] == vertices[axis + "_mm"][primary["event"]]
