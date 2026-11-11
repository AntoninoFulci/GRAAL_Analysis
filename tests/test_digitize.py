"""Real native ROOT response boundary; fixtures are artificial integrity cases."""
from array import array
import copy
import json
import os
from pathlib import Path
import subprocess

import numpy as np
import pytest
import uproot
ROOT = pytest.importorskip("ROOT")

from mc_simulation.geant4 import digitize as launcher
from mc_simulation.geant4.legacy_response import write_response_config

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "docs/reference/fortran/prog/data"
STEP_INTS = "run event track parent pdg track_step pre_status post_status pre_boundary post_boundary track_status".split()
STEP_DOUBLES = "charge_e track_weight edep_MeV nonionizing_edep_MeV step_length_mm pre_time_ns post_time_ns pre_kinetic_MeV post_kinetic_MeV pre_x_mm pre_y_mm pre_z_mm post_x_mm post_y_mm post_z_mm pre_local_x_mm pre_local_y_mm pre_local_z_mm post_local_x_mm post_local_y_mm post_local_z_mm pre_dir_x pre_dir_y pre_dir_z post_dir_x post_dir_y post_dir_z".split()
STEP_STRINGS = "path material process creator_process".split()
SCHEMAS = {
    "events": dict(run="int32", event="int32", total_edep_MeV="float64", bgo_edep_MeV="float64", steps="uint64", aborted="int32", hit_steps="uint64"),
    "channels": {**dict.fromkeys("path detector volume channel_kind material".split(), "string"), **dict.fromkeys("sensitive copy legacy_channel medium material_id".split(), "int32")},
    "detector_steps": {**dict.fromkeys(STEP_INTS, "int32"), **dict.fromkeys(STEP_DOUBLES, "float64"), **dict.fromkeys(STEP_STRINGS, "string")},
    "primaries": {**dict.fromkeys("run event vertex particle pdg".split(), "int32"), **dict.fromkeys("vertex_weight particle_weight x_mm y_mm z_mm time_ns px_MeV py_MeV pz_MeV kinetic_MeV".split(), "float64")},
}


def put_tree(root, name, schema, rows):
    # Match transport's std::string branches exactly. Uproot5.7 mktree strings
    # are TLeafC, and here declare fLen8 even for longer strings; ROOT truncates
    # those malformed fixtures. PyROOT avoids testing a different input schema.
    root.cd()
    tree = ROOT.TTree(name, name)
    types = {"int32": ("i", "I"), "uint64": ("Q", "l"), "float64": ("d", "D"), "float32": ("f", "F")}
    buffers = {}
    for key, kind in schema.items():
        if kind == "string":
            buffers[key] = ROOT.std.string()
            tree.Branch(key, buffers[key])
        else:
            code, leaf = types[kind]
            buffers[key] = array(code, [0])
            tree.Branch(key, buffers[key], f"{key}/{leaf}")
    for row in rows:
        for key, kind in schema.items():
            if kind == "string": buffers[key].assign(row[key])
            else: buffers[key][0] = row[key]
        assert tree.Fill() >= 0
    assert tree.Write() > 0


def fixtures():
    channels = []
    for detector, sensitive, count, offset in [("bgo", 1, 480, 0), ("barrel", 2, 32, 100)]:
        for channel in range(1, count + 1):
            channels.append(dict(path=f"/WORLD:0/{detector}:{channel+offset}", detector=detector,
                                 sensitive=sensitive, volume=detector, copy=channel+offset,
                                 legacy_channel=channel, channel_kind="legacy_scintillator",
                                 medium=1, material_id=1, material="fixture"))
    rows = []
    # BGO between grouped barrel steps must not destroy exact source links.
    for event, detector, channel, energy, z in [(0,"barrel",1,2.,0.), (0,"bgo",1,10.,0.),
                                               (0,"barrel",1,3.,1.), (2,"bgo",480,20.,0.),
                                               (2,"barrel",32,1.,0.)]:
        row = {**dict.fromkeys(STEP_INTS, 0), **dict.fromkeys(STEP_DOUBLES, 0.), **dict.fromkeys(STEP_STRINGS, "")}
        row.update(run=7, event=event, track=1, track_step=len(rows)+1, track_weight=1., edep_MeV=energy,
                   path=f"/WORLD:0/{detector}:{channel+(100 if detector == 'barrel' else 0)}",
                   post_z_mm=z, post_time_ns=2., pre_time_ns=1., material="fixture")
        rows.append(row)
    events = []
    for event in range(3):
        hits = [r for r in rows if r["event"] == event]
        events.append(dict(run=7, event=event, total_edep_MeV=sum(r["edep_MeV"] for r in hits),
                           bgo_edep_MeV=sum(r["edep_MeV"] for r in hits if "/bgo:" in r["path"]),
                           steps=len(hits), hit_steps=len(hits), aborted=0))
    return dict(channels=channels, events=events, detector_steps=rows, primaries=[])


def write_input(path, rows=None, *, summary=None, schemas=None):
    rows = rows if rows is not None else fixtures()
    metadata = dict(status="diagnostic_transport_only", hit_schema_version=2, aborted=0,
                    events=len(rows["events"]), attempted_events=len(rows["events"]),
                    detector_steps=len(rows["detector_steps"]))
    metadata.update(summary or {})
    root = ROOT.TFile(str(path), "CREATE")
    assert root.IsOpen() and not root.IsZombie()
    try:
        for name, schema in (schemas or SCHEMAS).items():
            put_tree(root, name, schema, rows[name])
        root.cd()
        assert ROOT.TObjString(json.dumps(metadata)).Write("summary") > 0
    finally:
        root.Close()
    return path


@pytest.fixture
def native():
    value = os.environ.get("GRAAL_DIGITIZE_EXE")
    if not value:
        pytest.skip("Set GRAAL_DIGITIZE_EXE to run native response integrity checks")
    assert Path(value).is_file()
    return Path(value)


@pytest.fixture
def config(tmp_path):
    path = tmp_path / "config.root"
    write_response_config(DATA, 1321, path)
    return path


def run(native, input_root, config, output, seed=123):
    return subprocess.run([str(native), str(input_root), str(config), str(output), str(seed)],
                          capture_output=True, text=True, timeout=60)


def table(path, name):
    with uproot.open(path) as root:
        return root[name].arrays(library="np")


def test_empty_event_preserved_source_links_and_seed_replay(native, config, tmp_path):
    source = write_input(tmp_path / "input.root")
    for name in ("one", "two"):
        result = run(native, source, config, tmp_path / name)
        assert result.returncode == 0, result.stderr
        assert {p.name for p in (tmp_path / name).iterdir()} == {"response.root"}
    response = tmp_path / "one/response.root"
    events = table(response, "response_events")
    assert events["run"].tolist() == [7, 7, 7]
    assert events["event"].tolist() == [0, 1, 2]
    assert events["historical_run"].tolist() == [1321] * 3
    assert events["bgo_digits"].tolist() == [1, 0, 1]
    assert events["barrel_records"].tolist() == [1, 0, 1]
    assert events["full_trigger_available"].tolist() == [0, 0, 0]
    links = table(response, "barrel_step_links")
    assert links["input_step_entry"].tolist() == [0, 2, 4]
    assert links["record_index"].tolist() == [0, 0, 0]
    assert table(response, "barrel_records")["source_steps"].tolist() == [2, 1]
    with uproot.open(response) as root:
        metadata = json.loads(str(root["metadata"]))
        assert metadata["physics_validation"] is False
        assert metadata["masks"] == "unknown"
        assert metadata["input_md5"] and metadata["config_md5"]
        assert "top52" in metadata["rng"]
        assert root.file.compression == uproot.ZSTD(5)
        names = [key for key, value in root.classnames(cycle=False).items() if value == "TTree"]
    for name in names:
        a, b = table(response, name), table(tmp_path / "two/response.root", name)
        assert a.keys() == b.keys()
        for key in a:
            assert np.array_equal(a[key], b[key]), (name, key)


@pytest.mark.parametrize("case", ["duplicate_event", "orphan", "unknown_path", "duplicate_path", "missing_bgo", "wrong_copy", "wrong_role", "wrong_path_copy", "aborted", "partial_summary", "wrong_schema", "wrong_period", "summary_events", "summary_steps", "count", "negative", "nonfinite", "nonfinite_z", "negative_time", "bad_weight", "bgo_sum", "sensitive_sum", "out_of_order"])
def test_rejects_corrupt_transport_without_success(native, config, tmp_path, case):
    rows = fixtures()
    summary = {}
    if case == "duplicate_event": rows["events"].append(copy.deepcopy(rows["events"][0]))
    elif case == "orphan": rows["detector_steps"][0]["event"] = 999
    elif case == "unknown_path": rows["detector_steps"][0]["path"] = "/unknown:1"
    elif case == "duplicate_path": rows["channels"].append(copy.deepcopy(rows["channels"][0]))
    elif case == "missing_bgo": rows["channels"].pop(0)
    elif case == "wrong_copy": rows["channels"][0]["copy"] = 2
    elif case == "wrong_role": rows["channels"][0]["detector"] = "barrel"
    elif case == "wrong_path_copy": rows["channels"][0]["path"] = "/WORLD:0/bgo:2"
    elif case == "aborted": rows["events"][1]["aborted"] = 1
    elif case == "partial_summary": summary["attempted_events"] = 4
    elif case == "wrong_schema": summary["hit_schema_version"] = 1
    elif case == "wrong_period": summary["period"] = "2003"
    elif case == "summary_events": summary["events"] = 4
    elif case == "summary_steps": summary["detector_steps"] = 6
    elif case == "count": rows["events"][0]["hit_steps"] -= 1
    elif case == "negative": rows["detector_steps"][0]["edep_MeV"] = -1.
    elif case == "nonfinite": rows["detector_steps"][0]["edep_MeV"] = float("nan")
    elif case == "nonfinite_z": rows["detector_steps"][0]["post_z_mm"] = float("inf")
    elif case == "negative_time": rows["detector_steps"][0]["post_time_ns"] = -1.
    elif case == "bad_weight": rows["detector_steps"][0]["track_weight"] = float("nan")
    elif case == "bgo_sum": rows["events"][0]["bgo_edep_MeV"] -= 1.
    elif case == "sensitive_sum": rows["events"][0]["total_edep_MeV"] -= 1.
    elif case == "out_of_order": rows["detector_steps"][2], rows["detector_steps"][3] = rows["detector_steps"][3], rows["detector_steps"][2]
    source = write_input(tmp_path / "input.root", rows, summary=summary)
    result = run(native, source, config, tmp_path / "out")
    assert result.returncode != 0, case
    assert "ERROR:" in result.stderr
    assert not (tmp_path / "out/response.root").exists()


@pytest.mark.parametrize("case", ["missing", "wrong_type", "missing_empty", "wrong_empty_type"])
def test_required_branch_checked_even_when_empty(native, config, tmp_path, case):
    rows, schemas = fixtures(), copy.deepcopy(SCHEMAS)
    if "empty" in case:
        rows["detector_steps"] = []
        for e in rows["events"]: e.update(steps=0, hit_steps=0, total_edep_MeV=0., bgo_edep_MeV=0.)
    if case.startswith("missing"): schemas["detector_steps"].pop("edep_MeV")
    else: schemas["detector_steps"]["edep_MeV"] = "float32"
    source = write_input(tmp_path / "input.root", rows, schemas=schemas)
    result = run(native, source, config, tmp_path / "out")
    assert result.returncode != 0
    assert "branch" in result.stderr
    assert not (tmp_path / "out/response.root").exists()


def test_valid_empty_step_tree(native, config, tmp_path):
    rows = fixtures()
    rows["detector_steps"] = []
    for e in rows["events"]: e.update(steps=0, hit_steps=0, total_edep_MeV=0., bgo_edep_MeV=0.)
    source = write_input(tmp_path / "empty.root", rows)
    result = run(native, source, config, tmp_path / "out")
    assert result.returncode == 0, result.stderr
    assert table(tmp_path / "out/response.root", "response_events")["event"].tolist() == [0,1,2]


def test_overflow_keeps_event_and_all_record_links_without_barrel_digits(native, config, tmp_path):
    rows = fixtures()
    template = rows["detector_steps"][0]
    rows["detector_steps"] = [dict(template, post_z_mm=float(i*20)) for i in range(101)]
    rows["events"] = [dict(rows["events"][0], total_edep_MeV=202., bgo_edep_MeV=0., steps=101, hit_steps=101)]
    source = write_input(tmp_path / "overflow.root", rows)
    result = run(native, source, config, tmp_path / "out")
    assert result.returncode == 0, result.stderr
    response = tmp_path / "out/response.root"
    events = table(response, "response_events")
    assert events["event"].tolist() == [0]
    assert events["status"].tolist() == ["unsupported_barrel_record_overflow"]
    assert events["barrel_records"].tolist() == [101]
    assert len(table(response, "barrel_digits")["channel"]) == 0
    assert len(table(response, "barrel_step_links")["input_step_entry"]) == 101


@pytest.mark.parametrize("case", ["scalar_mismatch", "attenuation_mismatch", "x1_domain", "config_schema", "metadata_json"])
def test_config_metadata_must_describe_applied_trees(native, config, tmp_path, case):
    with uproot.open(config) as root:
        scalars = root["scalars"].arrays(library="np")
        attenuation = root["attenuation"].arrays(library="np")
        metadata = json.loads(str(root["metadata"]))
    if case == "scalar_mismatch": scalars["scbgo"][0] = 1024.
    elif case == "attenuation_mismatch": attenuation["x1"][0] *= .9
    elif case == "x1_domain":
        attenuation["x1"][0] = 2.
        metadata["attenuation"][0][0] = 2.
    elif case == "config_schema": metadata["schema"] = 2
    with uproot.recreate(config) as root:
        for name, columns in [("scalars",scalars),("attenuation",attenuation)]:
            root.mktree(name, {key: value.dtype for key,value in columns.items()}).extend(columns)
        root["metadata"] = "{bad" if case == "metadata_json" else json.dumps(metadata)
    source = write_input(tmp_path / "input.root")
    result = run(native, source, config, tmp_path / "out")
    assert result.returncode != 0
    assert not (tmp_path / "out/response.root").exists()


def test_native_refuses_existing_output_and_partial_input(native, config, tmp_path):
    source = write_input(tmp_path / "input.partial.root")
    result = run(native, source, config, tmp_path / "out")
    assert result.returncode != 0 and "Partial" in result.stderr
    source = source.rename(tmp_path / "input.root")
    output = tmp_path / "out"
    output.mkdir()
    (output / "sentinel").write_text("preserve")
    result = run(native, source, config, output)
    assert result.returncode != 0 and "refusing overwrite" in result.stderr
    assert (output / "sentinel").read_text() == "preserve"


def test_launcher_root_provenance_and_sha256(native, tmp_path):
    source = write_input(tmp_path / "input.root")
    response = launcher.digitize(source,1324,DATA,tmp_path / "launch",native,20261109)
    assert response.is_file()
    output = response.parent.parent
    assert {p.name for p in output.iterdir()} == {"response_config.root","native.log","digits"}
    with uproot.open(response.parent / "provenance.root") as root:
        metadata = json.loads(str(root["metadata"]))
    assert metadata["input_sha256"] == launcher.sha256(source)
    assert metadata["config_sha256"] == launcher.sha256(output / "response_config.root")
    assert metadata["response_sha256"] == launcher.sha256(response)
    assert metadata["executable_sha256"] == launcher.sha256(native)
    assert metadata["historical_run"] == 1324
    with pytest.raises(FileExistsError):
        launcher.digitize(source,1324,DATA,output,native,20261109)


@pytest.mark.parametrize("case", ["manifest_failure", "changed_input", "changed_config"])
def test_launcher_failure_never_publishes_response(native, tmp_path, monkeypatch, case):
    source = write_input(tmp_path / "input.root")
    if case == "manifest_failure":
        def fail(*args): raise OSError("forced provenance write failure")
        monkeypatch.setattr(launcher,"_write_provenance",fail)
    else:
        real_run = launcher.subprocess.run
        def changed(args, **kwargs):
            result = real_run(args, **kwargs)
            target = source if case == "changed_input" else Path(args[2])
            with target.open("ab") as stream: stream.write(b"mutated after native digest")
            return result
        monkeypatch.setattr(launcher.subprocess,"run",changed)
    with pytest.raises((OSError,RuntimeError)):
        launcher.digitize(source,1321,DATA,tmp_path / "launch",native,123)
    assert not (tmp_path / "launch/digits/response.root").exists()
    assert not (tmp_path / "launch/digits.pending/response.root").exists()
    assert (tmp_path / "launch/digits.pending/response.invalid.root").is_file()


def test_corrupt_numeric_basket_fails_without_dereference_or_success(native, config, tmp_path):
    source = write_input(tmp_path / "bad-basket.root")
    with uproot.open(source) as root:
        key = root["detector_steps"]["edep_MeV"].basket_key(0)
        offset, size = key.fSeekKey + key.fKeylen, key.fNbytes - key.fKeylen
        assert size < key.fObjlen, "Fixture must exercise a compressed basket"
    with source.open("r+b") as stream:
        stream.seek(offset)
        stream.write(b"\x00" * size)
    result = run(native, source, config, tmp_path / "out")
    assert result.returncode == 1, result.stderr
    assert "basket read error" in result.stderr
    assert not (tmp_path / "out/response.root").exists()
