"""LAGDIG TRIG oracle and strict all-event ROOT diagnostic publication."""
import dataclasses
import importlib
import itertools
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np
import pytest
import uproot

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "03_mc_simulation/geant4"
ARCHIVE = ROOT / "docs/reference/fortran/prog"


@pytest.fixture
def api():
    return importlib.import_module("mc_simulation.geant4.trigger")


@pytest.fixture
def response(tmp_path, api):
    """Native-shaped response, including a no-hit and unsupported event."""
    transport = tmp_path / "transport.root"
    with uproot.create(transport) as root:
        root.mktree("events", {"run": "int32", "event": "int32"}).extend(
            {"run": np.array([0, 0, 0], dtype="int32"), "event": np.arange(3, dtype="int32")})
    config = api.read_trigger_config(ARCHIVE / "data", "09", 1321)
    types = dict(run="int32", event="int32", historical_run="int32", aborted="int32",
                 bgo_raw_total_GeV="float64", barrel_digits="int32", barrel_records="uint64", status="string")
    values = dict(run=np.zeros(3, dtype="int32"), event=np.arange(3, dtype="int32"),
                  historical_run=np.full(3, 1321, dtype="int32"), aborted=np.zeros(3, dtype="int32"),
                  bgo_raw_total_GeV=np.array([0., float(np.float32(.09)), .2]),
                  barrel_digits=np.array([0, 1, 0], dtype="int32"),
                  barrel_records=np.array([0, 1, 101], dtype="uint64"),
                  status=["diagnostic_only", "diagnostic_only", "unsupported_barrel_record_overflow"])
    objects = dict(metadata=dict(mode="legacy09_diagnostic", historical_run=1321, input_path=str(transport)),
                   config_metadata=dict(legacy_period="09", historical_run=1321,
                                        applied_sources=[dict(path="base/data09.base", sha256=config["source_sha256"])]),
                   launcher_provenance=dict(input_path=str(transport), input_sha256=api.sha256(transport)),
                   summary=dict(status="legacy09_diagnostic_complete", events=3, physics_validation=False))
    path = tmp_path / "response.root"

    def write():
        with uproot.recreate(path) as root:
            tree = root.mktree("response_events", types)
            if len(values["run"]):
                tree.extend(values)
            for name, value in objects.items():
                root[name] = json.dumps(value)
        return path

    return path, values, types, objects, write


@pytest.mark.parametrize("mode,macros", [("none", []), ("bgo", ["GRAAL_T_BGO"]),
                                         ("three_particle", ["GRAAL_T_3PC"]),
                                         ("either", ["GRAAL_T_BGO", "GRAAL_T_3PC"])])
def test_compiled_unmodified_trig_four_profiles(api, tmp_path, mode, macros):
    compiler = shutil.which("gfortran")
    if compiler is None:
        pytest.skip("gfortran unavailable")
    mirror = tmp_path / "lagdig"
    (mirror / "src").mkdir(parents=True)
    shutil.copyfile(ARCHIVE / "lagdig/src/trig.F", mirror / "src/trig.F")
    (mirror / "pilot.h").write_text("\n".join(f"#define {name}" for name in macros) + "\n")
    (mirror / "GRAAL_machine.h").write_text("")
    for name in ("tofwall_nt.inc", "barrel.inc", "nthead.inc", "itrig.inc"):
        shutil.copyfile(ARCHIVE / "lagdig/include" / name, mirror / name)
    executable = tmp_path / "oracle"
    environment = dict(os.environ)
    if sys.platform == "darwin":
        environment["MACOSX_DEPLOYMENT_TARGET"] = "15.0"
    subprocess.run([compiler, "-cpp", "-ffixed-line-length-none", "-I", str(mirror),
                    str(mirror / "src/trig.F"), str(MODULE / "tests/trigger_oracle.F"),
                    "-o", str(executable)], check=True, capture_output=True, text=True, env=environment)
    threshold = np.float32(.090)
    energies = [0., np.nextafter(threshold, np.float32(0)), threshold,
                np.nextafter(threshold, np.float32(1)), np.float32(.5)]
    cases = list(itertools.product(energies, (0, 1, 2, 26), (0, 1, 2, 26), (0, 1, 32)))
    text = str(len(cases)) + "\n" + "\n".join(
        f"{float(energy):.17g} {float(threshold):.17g} {horizontal} {vertical} {barrel}"
        for energy, horizontal, vertical, barrel in cases) + "\n"
    result = subprocess.run([str(executable)], input=text, capture_output=True, text=True, check=True)
    rows = [list(map(int, line.split())) for line in result.stdout.splitlines()]
    assert len(rows) == len(cases)
    for (energy, horizontal, vertical, barrel), (bits, accepted) in zip(cases, rows):
        actual = api.evaluate_trigger(mode, float(energy), float(threshold),
                                      wall_horizontal=horizontal, wall_vertical=vertical, barrel=barrel)
        assert actual.itrig == bits
        assert actual.bit_values == bits
        assert actual.known_bits == 9
        assert actual.accepted is bool(accepted)


def test_max_not_sum_and_partial_bits(api):
    result = api.evaluate_trigger("three_particle", .1, .09, wall_horizontal=1, wall_vertical=1, barrel=1)
    assert result.three_particle is False
    assert result.accepted is False
    assert result.itrig == 1
    result = api.evaluate_trigger("either", .1, .09)
    assert result.accepted is True
    assert result.known_bits == result.bit_values == 1
    assert result.itrig is None
    assert api.evaluate_trigger("either", 0., .09).accepted is None
    assert api.evaluate_trigger("none", None, .09).accepted is True
    result = api.evaluate_trigger("either", None, .09, wall_horizontal=2, wall_vertical=0, barrel=1)
    assert result.accepted is True and result.known_bits == 8 and result.itrig is None


@pytest.mark.parametrize("energy", [None, float("nan"), float("inf"), -1., True, "0.1", 1.e100, 10**1000])
def test_invalid_bgo_is_unavailable(api, energy):
    result = api.evaluate_trigger("bgo", energy, .09)
    assert result.bgo is None and result.accepted is None and result.known_bits == 0


@pytest.mark.parametrize("field,value", [("wall_horizontal", -1), ("wall_vertical", 27),
                                         ("barrel", 33), ("barrel", 1.), ("barrel", True)])
def test_invalid_multiplicity_is_unavailable(api, field, value):
    kwargs = dict(wall_horizontal=2, wall_vertical=0, barrel=1)
    kwargs[field] = value
    result = api.evaluate_trigger("three_particle", 0., .09, **kwargs)
    assert result.three_particle is None and result.accepted is None
    assert result.known_bits == 1


def test_overflow_response_is_unavailable(api):
    result = api.evaluate_trigger("either", .2, .09, wall_horizontal=2, wall_vertical=2,
                                  barrel=1, response_available=False)
    assert dataclasses.asdict(result) == dict(accepted=None, bgo=None, three_particle=None,
                                             bit_values=0, known_bits=0, itrig=None)


@pytest.mark.parametrize("period", ["09", "26"])
def test_source_record_and_binary32(api, period):
    config = api.read_trigger_config(ARCHIVE / "data", period, 1321)
    assert config["threshold_GeV"] == float(np.float32(.090))
    assert config["record"] == 161
    assert config["source_sha256"] == api.sha256(ARCHIVE / f"data/base/data{period}.base")


def test_all_event_root_publication(api, response, tmp_path):
    path, values, _, _, write = response
    write()
    before = api.sha256(path)
    output = tmp_path / "trigger"
    result = api.diagnose_trigger(path, "bgo", "09", 1321, ARCHIVE / "data", output)
    assert api.sha256(path) == before
    with uproot.open(result) as root:
        events = root["trigger_events"].arrays(library="np")
        assert events["event"].tolist() == [0, 1, 2]
        assert events["source_entry"].tolist() == [0, 1, 2]
        assert events["run"].tolist() == [0, 0, 0]
        assert events["historical_run"].tolist() == [1321] * 3
        assert events["accepted"].tolist() == [0, 1, -1]
        assert events["itrig"].tolist() == [-1, -1, -1]
        assert events["known_bits"].tolist() == [1, 1, 0]
        assert events["three_particle"].tolist() == [-1, -1, -1]
        assert events["response_status"].tolist() == values["status"]
        summary = json.loads(str(root["summary"]))
        assert (summary["accepted"], summary["rejected"], summary["unavailable"]) == (1, 1, 1)
    with uproot.open(output / "diagnostic/provenance.root") as root:
        provenance = json.loads(str(root["metadata"]))
        assert provenance["input_sha256"] == before
        assert provenance["result_sha256"] == api.sha256(result)
        assert provenance["historical_run"] == 1321
        assert provenance["hardware_trigger_validation"] is False
    with pytest.raises(FileExistsError):
        api.diagnose_trigger(path, "bgo", "09", 1321, ARCHIVE / "data", output)


def test_empty_ledger(api, response, tmp_path):
    path, values, _, objects, write = response
    for name in values:
        values[name] = values[name][:0]
    objects["summary"]["events"] = 0
    write()
    result = api.diagnose_trigger(path, "none", "09", 1321, ARCHIVE / "data", tmp_path / "empty")
    with uproot.open(result) as root:
        assert root["trigger_events"].num_entries == 0
        assert json.loads(str(root["summary"]))["events"] == 0


@pytest.mark.parametrize("corruption", ["count_type", "count_negative", "count_capacity", "energy_type", "energy_nan",
                                       "event_duplicate", "event_order", "event_type", "event_count", "historical_run",
                                       "overflow", "status", "identity_missing", "identity_hash", "identity_path", "config_hash"])
def test_corrupt_response_refused(api, response, tmp_path, corruption):
    path, values, types, objects, write = response
    if corruption == "count_type":
        types["barrel_digits"] = "float64"
        values["barrel_digits"] = values["barrel_digits"].astype("float64")
    elif corruption == "count_negative":
        values["barrel_digits"][0] = -1
    elif corruption == "count_capacity":
        values["barrel_digits"][0] = 33
    elif corruption == "energy_type":
        types["bgo_raw_total_GeV"] = "int32"
        values["bgo_raw_total_GeV"] = values["bgo_raw_total_GeV"].astype("int32")
    elif corruption == "energy_nan":
        values["bgo_raw_total_GeV"][0] = np.nan
    elif corruption == "event_duplicate":
        values["event"][1] = 0
    elif corruption == "event_order":
        values["event"] = values["event"][::-1]
    elif corruption == "event_type":
        types["event"] = "uint32"
        values["event"] = values["event"].astype("uint32")
    elif corruption == "event_count":
        objects["summary"]["events"] = 2
    elif corruption == "historical_run":
        values["historical_run"][0] = 1324
    elif corruption == "overflow":
        values["barrel_records"][0] = 101
    elif corruption == "status":
        values["status"][0] = "silently_missing"
    elif corruption == "identity_missing":
        objects["launcher_provenance"].pop("input_sha256")
    elif corruption == "identity_hash":
        objects["launcher_provenance"]["input_sha256"] = "0" * 64
    elif corruption == "identity_path":
        objects["metadata"]["input_path"] = "other.root"
    elif corruption == "config_hash":
        objects["config_metadata"]["applied_sources"][0]["sha256"] = "0" * 64
    write()
    output = tmp_path / "bad"
    with pytest.raises((ValueError, OSError)):
        api.diagnose_trigger(path, "bgo", "09", 1321, ARCHIVE / "data", output)
    assert not output.exists()


def test_selected_period_and_historical_run_must_match(api, response, tmp_path):
    path, _, _, _, write = response
    write()
    for period, historical in (("26", 1321), ("09", 1324)):
        with pytest.raises(ValueError):
            api.diagnose_trigger(path, "bgo", period, historical, ARCHIVE / "data", tmp_path / "bad")


def test_failed_provenance_publication_leaves_no_output(api, response, tmp_path, monkeypatch):
    path, _, _, _, write = response
    write()

    def fail(*args):
        raise OSError("injected provenance write failure")

    monkeypatch.setattr(api, "_write_provenance", fail)
    with pytest.raises(OSError, match="injected"):
        api.diagnose_trigger(path, "bgo", "09", 1321, ARCHIVE / "data", tmp_path / "failed")
    assert not (tmp_path / "failed").exists()
    assert not list(tmp_path.glob(".failed.*"))


def test_source_change_before_publication_is_refused(api, response, tmp_path, monkeypatch):
    path, _, _, objects, write = response
    write()
    original = api._write_provenance

    def change(*args):
        original(*args)
        with Path(objects["launcher_provenance"]["input_path"]).open("ab") as stream:
            stream.write(b"changed")

    monkeypatch.setattr(api, "_write_provenance", change)
    with pytest.raises(RuntimeError, match="changed"):
        api.diagnose_trigger(path, "bgo", "09", 1321, ARCHIVE / "data", tmp_path / "changed")
    assert not (tmp_path / "changed").exists()


def test_final_directory_publication_failure_removes_reservation(api, response, tmp_path, monkeypatch):
    path, _, _, _, write = response
    write()
    original = Path.rename

    def fail(self, destination):
        if self.name.endswith(".pending"):
            raise OSError("injected final rename failure")
        return original(self, destination)

    monkeypatch.setattr(Path, "rename", fail)
    with pytest.raises(OSError, match="injected final rename"):
        api.diagnose_trigger(path, "bgo", "09", 1321, ARCHIVE / "data", tmp_path / "failed")
    assert not (tmp_path / "failed").exists()
    assert not list(tmp_path.glob(".failed.*"))


def test_output_symlink_is_never_replaced(api, response, tmp_path):
    path, _, _, _, write = response
    write()
    output = tmp_path / "existing"
    output.symlink_to(tmp_path / "absent")
    with pytest.raises(FileExistsError):
        api.diagnose_trigger(path, "bgo", "09", 1321, ARCHIVE / "data", output)
    assert output.is_symlink()


def test_cli_requires_explicit_mode_period_and_run(api):
    with pytest.raises(SystemExit) as error:
        api.main(["--input", "x", "--output", "y"])
    assert error.value.code == 2


@pytest.fixture
def forward_response(api, response, tmp_path):
    """Native-shaped measured wall ledger with independent response/reco states."""
    response_path, response_values, _, response_objects, response_write = response
    size = 7
    response_values.update(run=np.zeros(size, dtype="int32"), event=np.arange(size, dtype="int32"),
                           historical_run=np.full(size, 1321, dtype="int32"), aborted=np.zeros(size, dtype="int32"),
                           bgo_raw_total_GeV=np.array([0., float(np.float32(.09)), 0., 0., float(np.float32(.09)), 0., .2]),
                           barrel_digits=np.array([0, 1, 1, 1, 1, 1, 0], dtype="int32"),
                           barrel_records=np.array([0, 1, 1, 1, 1, 1, 101], dtype="uint64"),
                           status=["diagnostic_only"] * 6 + ["unsupported_barrel_record_overflow"])
    response_objects["summary"]["events"] = size
    response_write()
    tracking = tmp_path / "tracking.root"
    tracking.write_bytes(b"immutable tracking fixture")
    config_path = tmp_path / "forward_config.root"
    mode = "selected26_forward_reconstruction_diagnostic"
    selected = dict(schema=1, mode=mode, physical_validation=False, physics_validation=False,
                    baseline=["GRAAL_26", "GRAAL_WALL_DEV"], reconstruction=dict(source_run=4300, rf_bunch=0, simulation=True))
    with uproot.recreate(config_path) as root:
        root["metadata"] = json.dumps(selected)
    metadata = dict(schema_version=1, mode=mode, physical_validation=False, physics_validation=False,
                    input_path=response_objects["launcher_provenance"]["input_path"], source_run=4300, seed=20261109,
                    tracking_path=str(tracking), config_path=str(config_path))
    summary = dict(schema_version=1, status="selected26_forward_diagnostic_complete", events=size,
                   unsupported_events=1, particles=0, normal_draws=0, physical_validation=False, physics_validation=False)
    launcher = dict(mode=mode, physical_validation=False, physics_validation=False,
                    input_path=metadata["input_path"], input_sha256=response_objects["launcher_provenance"]["input_sha256"],
                    seed=metadata["seed"], tracking_path=str(tracking), tracking_sha256=api.sha256(tracking),
                    executable_sha256="a" * 64, code_sha256={"forward.py": "b" * 64},
                    legacy_source_sha256={"wall.F": "c" * 64})
    provenance = dict(launcher, config_path=str(config_path), config_sha256=api.sha256(config_path), summary=dict(summary))
    objects = dict(metadata=metadata, config_metadata=selected, summary=summary, launcher_provenance=launcher)
    values = dict(run=np.zeros(size, dtype="int32"), event=np.arange(size, dtype="int32"),
                  source_entry=np.arange(size, dtype="uint64"), wall_response_status=np.array([0, 0, 0, 2, 4, 0, 0], dtype="int32"),
                  wall_response_available=np.array([1, 1, 1, 0, 0, 1, 1], dtype="int32"),
                  wall_h_accepted=np.array([0, 2, 1, 0, 0, 2, 2], dtype="uint64"),
                  wall_v_accepted=np.array([0, 0, 1, 0, 0, 1, 1], dtype="uint64"),
                  association_status=np.array([0, 0, 0, 0, 0, 3, 0], dtype="int32"),
                  wall_reconstruction_status=np.array([0, 0, 0, 0, 0, 3, 0], dtype="int32"),
                  particles=np.zeros(size, dtype="uint64"))
    types = {name: str(value.dtype) for name, value in values.items()}
    directory = tmp_path / "forward"
    directory.mkdir()
    path = directory / "forward.root"
    provenance_path = directory / "provenance.root"

    def write():
        with uproot.recreate(path) as root:
            root.mktree("forward_events", types).extend(values)
            for name, obj in objects.items():
                root[name] = json.dumps(obj)
        provenance["response_sha256"] = api.sha256(path)
        with uproot.recreate(provenance_path) as root:
            root["metadata"] = json.dumps(provenance)
        return path

    return response_path, path, values, types, objects, provenance, write


@pytest.mark.parametrize("mode,accepted", [("three_particle", [0, 1, 0, -1, -1, 1, -1]),
                                          ("either", [0, 1, 0, -1, 1, 1, -1]),
                                          ("none", [1, 1, 1, 1, 1, 1, 1])])
def test_measured_forward_counts_join_availability_and_reconstruction_independence(api, forward_response, tmp_path, mode, accepted):
    response_path, forward_path, _, _, _, _, write = forward_response
    write()
    result = api.diagnose_trigger(response_path, mode, "09", 1321, ARCHIVE / "data", tmp_path / "joined", forward_root=forward_path)
    with uproot.open(result) as root:
        events = root["trigger_events"].arrays(library="np")
        assert events["accepted"].tolist() == accepted
        assert events["three_particle"].tolist() == [0, 1, 0, -1, -1, 1, -1]
        assert events["itrig"].tolist() == [0, 9, 0, -1, -1, 8, -1]
        assert events["known_bits"].tolist() == [9, 9, 9, 1, 1, 9, 0]
        assert events["wall_h_accepted"].tolist() == [0, 2, 1, 0, 0, 2, 2]
        assert events["wall_reconstruction_status"][5] == 3  # complete response still enters 3PC
        metadata = json.loads(str(root["metadata"]))
        assert metadata["configuration_status"] == "mixed_legacy09_BGO_barrel_selected26_forward_diagnostic"
        assert metadata["historical_run"] == 1321
        assert metadata["forward_metadata"]["source_run"] == 4300
        assert metadata["forward_sha256"] == api.sha256(forward_path)
        assert metadata["forward_provenance_sha256"] == api.sha256(forward_path.with_name("provenance.root"))
        assert json.loads(str(root["summary"]))["full_itrig_available"] == 4


@pytest.mark.parametrize("corruption", ["different_transport", "duplicate", "reorder", "orphan", "source_entry",
                                       "event_type", "count_type", "count_capacity", "status_type", "status_bits",
                                       "availability", "placeholder", "summary_fractional", "summary_bool",
                                       "summary_events", "summary_unsupported", "summary_particles", "provenance_counter",
                                       "metadata_schema", "metadata_seed", "source_run", "provenance_config",
                                       "provenance_source", "provenance_tracking", "launcher_hash", "non_diagnostic",
                                       "applied_config_mismatch", "rf_fractional"])
def test_forward_join_rejects_corrupt_identity_ledger_and_metadata(api, forward_response, tmp_path, corruption):
    response_path, forward_path, values, types, objects, provenance, write = forward_response
    if corruption == "different_transport":
        other = tmp_path / "other_transport.root"
        other.write_bytes(b"different pilot")
        provenance.update(input_path=str(other), input_sha256=api.sha256(other))
    elif corruption == "duplicate":
        values["event"][1] = 0
    elif corruption == "reorder":
        values["event"] = values["event"][::-1]
    elif corruption == "orphan":
        values["event"][-1] = 99
    elif corruption == "source_entry":
        values["source_entry"][0] = 1
    elif corruption in ("event_type", "count_type", "status_type"):
        name = {"event_type": "event", "count_type": "wall_h_accepted", "status_type": "wall_response_status"}[corruption]
        types[name] = "float64"
        values[name] = values[name].astype("float64")
    elif corruption == "count_capacity":
        values["wall_h_accepted"][0] = 27
    elif corruption == "status_bits":
        values["wall_response_status"][3] = 8
    elif corruption == "availability":
        values["wall_response_available"][3] = 1
    elif corruption == "placeholder":
        values["wall_h_accepted"][3] = 1
    elif corruption == "summary_fractional":
        objects["summary"]["events"] = 7.0
        provenance["summary"]["events"] = 7.0
    elif corruption == "summary_bool":
        objects["summary"]["unsupported_events"] = True
        provenance["summary"]["unsupported_events"] = True
    elif corruption == "summary_events":
        objects["summary"]["events"] = 6
        provenance["summary"]["events"] = 6
    elif corruption == "summary_unsupported":
        objects["summary"]["unsupported_events"] = 2
        provenance["summary"]["unsupported_events"] = 2
    elif corruption == "summary_particles":
        objects["summary"]["particles"] = 1
        provenance["summary"]["particles"] = 1
    elif corruption == "provenance_counter":
        provenance["summary"]["events"] = 7.0
    elif corruption == "metadata_schema":
        objects["metadata"]["schema_version"] = 1.0
    elif corruption == "metadata_seed":
        objects["metadata"]["seed"] = -1
    elif corruption == "source_run":
        objects["config_metadata"]["reconstruction"]["source_run"] = 4300.0
    elif corruption == "provenance_config":
        provenance["config_sha256"] = "0" * 64
    elif corruption == "provenance_source":
        provenance["code_sha256"] = {}
    elif corruption == "provenance_tracking":
        provenance.pop("tracking_sha256")
    elif corruption == "launcher_hash":
        objects["launcher_provenance"]["input_sha256"] = "0" * 64
    elif corruption == "non_diagnostic":
        objects["metadata"]["physical_validation"] = True
    elif corruption == "applied_config_mismatch":
        objects["config_metadata"]["baseline"].append("undeclared_macro")
    elif corruption == "rf_fractional":
        objects["config_metadata"]["reconstruction"]["rf_bunch"] = 0.0
    write()
    output = tmp_path / "bad_join"
    with pytest.raises((ValueError, KeyError, OSError)):
        api.diagnose_trigger(response_path, "either", "09", 1321, ARCHIVE / "data", output, forward_root=forward_path)
    assert not output.exists()


@pytest.mark.parametrize("corruption", ["missing_provenance", "wrong_output_hash", "duplicate_root_cycle", "duplicate_json_key"])
def test_forward_provenance_requires_complete_untampered_root(api, forward_response, tmp_path, corruption):
    response_path, forward_path, _, _, _, provenance, write = forward_response
    write()
    manifest = forward_path.with_name("provenance.root")
    if corruption == "missing_provenance":
        manifest.unlink()
    elif corruption == "wrong_output_hash":
        with forward_path.open("ab") as stream:
            stream.write(b"changed")
    elif corruption == "duplicate_root_cycle":
        with uproot.update(manifest) as root:
            root["metadata"] = json.dumps(provenance)
    elif corruption == "duplicate_json_key":
        with uproot.recreate(manifest) as root:
            root["metadata"] = json.dumps(provenance)[:-1] + ', "seed": 1}'
    with pytest.raises((ValueError, OSError)):
        api.diagnose_trigger(response_path, "either", "09", 1321, ARCHIVE / "data", tmp_path / "bad_join", forward_root=forward_path)


@pytest.mark.parametrize("target", ["forward.root", "provenance.root"])
def test_forward_files_mutated_during_trigger_publication_are_rejected(api, forward_response, tmp_path, monkeypatch, target):
    response_path, forward_path, _, _, _, _, write = forward_response
    write()
    original = api._write_provenance

    def mutate(*args):
        original(*args)
        with forward_path.with_name(target).open("ab") as stream:
            stream.write(b"changed during trigger")

    monkeypatch.setattr(api, "_write_provenance", mutate)
    with pytest.raises(RuntimeError, match="changed"):
        api.diagnose_trigger(response_path, "either", "09", 1321, ARCHIVE / "data", tmp_path / "failed_join", forward_root=forward_path)
    assert not (tmp_path / "failed_join").exists()
    assert not list(tmp_path.glob(".failed_join.*"))


def test_forward_join_publication_failure_leaves_no_consumable_output(api, forward_response, tmp_path, monkeypatch):
    response_path, forward_path, _, _, _, _, write = forward_response
    write()

    def fail(*args):
        raise OSError("injected joined publication failure")

    monkeypatch.setattr(api, "_write_provenance", fail)
    with pytest.raises(OSError, match="injected joined"):
        api.diagnose_trigger(response_path, "either", "09", 1321, ARCHIVE / "data", tmp_path / "failed_join", forward_root=forward_path)
    assert not (tmp_path / "failed_join").exists()
    assert not list(tmp_path.glob(".failed_join.*"))
