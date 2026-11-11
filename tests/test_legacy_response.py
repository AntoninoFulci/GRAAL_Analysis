"""Source-backed diagnostic response constants and an explicit ROOT boundary."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

import numpy as np
import pytest
import uproot

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs/reference/fortran/prog/data"


@pytest.fixture
def api():
    path = ROOT / "03_mc_simulation/geant4/legacy_response.py"
    spec = importlib.util.spec_from_file_location("legacy_response", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def data(tmp_path):
    """Copy consumed files only; historical inputs remain immutable."""
    destination = tmp_path / "data"
    for family, pattern in (("base", "data09.base"), ("calib_bgo", "run1321.*"),
                            ("calib_tag", "calib_1321.dat"),
                            ("calib_strip", "calstrip_1321.dat"),
                            ("calib_barrel", "calib_1321.dat"),
                            ("calib_wall", "calib_1321.cal")):
        (destination / family).mkdir(parents=True, exist_ok=True)
        for source in (DATA / family).glob(pattern):
            shutil.copyfile(source, destination / family / source.name)
    return destination


def replace_line(data, number, text):
    source = data / "base/data09.base"
    lines = source.read_text().splitlines()
    lines[number-1] = text
    source.write_text("\n".join(lines)+"\n")


def test_actual_constants_and_read_only_provenance(api):
    response = api.read_legacy09_response(DATA, 1321)
    expected = dict(scbgo=2048., vscbgo_GeV=1.2901, thres_GeV=.0022,
                    scdeb=2048., vscdeb_GeV=.02294, debdis=.1458,
                    dthres_GeV=.0000392, dedxat=1, zc3_cm=21.7,
                    sdetof=2048., vdetof_s=116.3e-9, ddetof_s=.47e-9,
                    dlight_cm_s=3e10/1.58)
    for key, value in expected.items():
        assert response[key] == pytest.approx(value)
    assert response["schema"] == 1
    assert response["mode"] == "legacy09_diagnostic"
    assert response["period"] == "1998_uv"
    assert response["physics_validation"] is False
    assert response["detector_geometry_status"] == "unqualified_for_1998"
    assert len(response["attenuation"]) == 32
    assert response["attenuation"][0] == [.19043666, 0., 0., 0.]
    assert response["attenuation"][-1] == [.23117222, 0., 0., 0.]
    assert len(response["sources"]) == 7
    for row in response["sources"]:
        assert not Path(row["path"]).is_absolute()
        assert row["sha256"] == hashlib.sha256((DATA/row["path"]).read_bytes()).hexdigest()
    assert response["masks"]["status"] == "unqualified"
    assert response["masks"]["zero_pedestal_bgo_channels"] == [262, 308]
    assert response["control_role"] == "tuning_candidate"
    assert len(response["applied_sources"]) == 1
    assert len(response["inspected_sources"]) == 6


def test_runs_are_separate_controls_not_transport_run_numbers(api):
    a, b = [api.read_legacy09_response(DATA, run) for run in (1321, 1324)]
    assert a["historical_run"] == 1321 and b["historical_run"] == 1324
    assert b["control_role"] == "validation_candidate_prior_use_unqualified"
    assert b["prior_beam_target_use"]
    assert a["sources"] != b["sources"]
    assert a["control_barrel_tdc_windows"][13] == [1111., 1335.]
    assert b["control_barrel_tdc_windows"][13] == [1106., 1330.]


@pytest.mark.parametrize("run", [1320, 1322, 1325, True, 1321., "1321"])
def test_reject_undeclared_historical_run(api, run):
    with pytest.raises(ValueError, match="1321.*1324"):
        api.read_legacy09_response(DATA, run)


def test_electronics_mapping_identities(api):
    assert api.bgo_electronics(1) == dict(theta_index=1, phi_index=1, fera_vsn=0, fera_sub=0)
    assert api.bgo_electronics(262) == dict(theta_index=9, phi_index=6, fera_vsn=16, fera_sub=5)
    assert api.bgo_electronics(480) == dict(theta_index=15, phi_index=32, fera_vsn=29, fera_sub=15)
    assert api.barrel_electronics(1) == dict(physical_copy=101, tdc_vsn=31, adc_vsn=34, fera_sub=0)
    assert api.barrel_electronics(32) == dict(physical_copy=132, tdc_vsn=32, adc_vsn=35, fera_sub=15)
    for channel in range(1, 481):
        row = api.bgo_electronics(channel)
        assert row["fera_vsn"]*16+row["fera_sub"] == channel-1
        assert (row["theta_index"]-1)*32+row["phi_index"] == channel
    assert len({tuple(api.barrel_electronics(channel).values()) for channel in range(1, 33)}) == 32


@pytest.mark.parametrize("channel", [0, -1, 481, True, 1., "1"])
def test_bgo_mapping_rejects_invalid_channel(api, channel):
    with pytest.raises(ValueError):
        api.bgo_electronics(channel)


@pytest.mark.parametrize("channel", [0, -1, 33, True, 1., "1"])
def test_barrel_mapping_rejects_invalid_channel(api, channel):
    with pytest.raises(ValueError):
        api.barrel_electronics(channel)


@pytest.mark.parametrize("line, value", [
    (2, "2048000"), (3, "1290.1D-3"), (4, "2.2E-3"), (45, "00001"),
])
def test_fortran_fixed_width_formats(api, data, line, value):
    original = api.read_legacy09_response(data, 1321)
    replace_line(data, line, value.rjust(5 if line == 45 else 15)+" ! preserved format")
    changed = api.read_legacy09_response(data, 1321)
    for key in ("scbgo", "vscbgo_GeV", "thres_GeV", "dedxat"):
        assert original[key] == pytest.approx(changed[key])
    assert original["sources"][0]["sha256"] != changed["sources"][0]["sha256"]


@pytest.mark.parametrize("token, expected", [("100E-3", .0001), ("1E3", 1.),
                                            ("100D-3", .0001), ("1.E3", 1000.)])
def test_fortran_exponent_implied_decimal_oracle(api, token, expected):
    # Verified against a native Fortran READ(...,'(F15.3)') by the integrator.
    assert api._f15_3(token.rjust(15)) == pytest.approx(expected)


@pytest.mark.parametrize("line, value", [
    (2, "2048."),  # short fixed-width record, even though float() accepts it
    (3, "NaN".rjust(15)), (3, "1e999".rjust(15)),
    (3, "0.".rjust(15)), (4, "2.".rjust(15)),
    (40, "2048.5".rjust(15)), (42, "-.1".rjust(15)),
    (45, "00000"), (45, "1.000"),
    (46, ".1 0 0"), (46, ".1 0 NaN 0"), (46, "0 0 0 0"),
    (46, ".1 1e99 0 0"), (46, ".1 0 -1 0"), (46, ".1 -20 0 0"),
    (46, "1.1 0 0 0"),
    (83, "0.".rjust(15)), (155, "0.".rjust(15)),
])
def test_malformed_and_unsafe_constants_are_rejected(api, data, line, value):
    replace_line(data, line, value)
    with pytest.raises(ValueError):
        api.read_legacy09_response(data, 1321)


def test_truncated_database_and_bad_six_family_identity_rejected(api, data):
    source = data/"base/data09.base"
    original = source.read_text()
    source.write_text("\n".join(original.splitlines()[:76]))
    with pytest.raises(ValueError, match="Truncated"):
        api.read_legacy09_response(data, 1321)
    source.write_text(original)
    source = data/"calib_bgo/run1321.cal"
    source.write_text(source.read_text().replace("BGO Source =", "Wrong label =", 1))
    with pytest.raises(ValueError, match="identity"):
        api.read_legacy09_response(data, 1321)


def test_explicit_root_ttrees_metadata_compression_and_no_overwrite(api, tmp_path):
    output = tmp_path/"config.root"
    metadata = api.write_response_config(DATA, 1321, output)
    with uproot.open(output) as root:
        assert root.file.compression == uproot.ZSTD(5)
        assert root["scalars"].classname == "TTree"
        assert root["attenuation"].classname == "TTree"
        assert root["metadata"].classname == "TObjString"
        assert root["scalars"].num_entries == 1
        assert root["attenuation"].num_entries == 32
        assert root["scalars"]["historical_run"].typename == "int32_t"
        assert root["scalars"]["dedxat"].typename == "int32_t"
        assert root["scalars"]["vscbgo_GeV"].typename == "double"
        assert root["attenuation"]["channel"].typename == "int32_t"
        np.testing.assert_array_equal(root["attenuation"]["channel"].array(library="np"), np.arange(1,33))
        assert json.loads(str(root["metadata"])) == metadata
    original = output.read_bytes()
    with pytest.raises(FileExistsError):
        api.write_response_config(DATA, 1324, output)
    assert output.read_bytes() == original
    assert sorted(p.name for p in tmp_path.iterdir()) == ["config.root"]
    second = tmp_path/"1324.root"
    api.write_response_config(DATA, 1324, second)
    with uproot.open(second) as root:
        assert root["scalars"]["historical_run"].array(library="np")[0] == 1324


def test_publication_race_does_not_clobber_or_leave_partial(api, tmp_path, monkeypatch):
    output = tmp_path/"config.root"
    link = api.os.link

    def competitor(source, destination):
        Path(destination).write_bytes(b"other writer")
        return link(source, destination)

    monkeypatch.setattr(api.os, "link", competitor)
    with pytest.raises(FileExistsError):
        api.write_response_config(DATA, 1321, output)
    assert output.read_bytes() == b"other writer"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["config.root"]


def test_failed_write_removes_partial(api, tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("injected ROOT failure")

    monkeypatch.setattr(uproot.WritableDirectory, "mktree", fail)
    output = tmp_path/"config.root"
    with pytest.raises(RuntimeError, match="injected ROOT failure"):
        api.write_response_config(DATA, 1321, output)
    assert not list(tmp_path.iterdir())
