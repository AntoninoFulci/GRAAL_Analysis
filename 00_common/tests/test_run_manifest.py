from pathlib import Path

import pytest

from graal_common.run_manifest import (
    ManifestError,
    RunRecord,
    classify_period,
    scan_runs,
    validate_manifest,
    write_manifest,
)


@pytest.mark.parametrize(
    ("period", "expected"),
    [
        ("1998_uv", ("P", "UV", "P_UV", "automatic")),
        ("2000_fuv", ("P", "UV", "P_UV", "automatic")),
        ("1999_vis", ("P", "VIS", "P_VIS", "automatic")),
        ("2002_d1", ("D", "UNKNOWN", "UNASSIGNED", "unresolved")),
        ("2005_d2", ("D", "UNKNOWN", "UNASSIGNED", "unresolved")),
        ("mystery", ("UNKNOWN", "UNKNOWN", "UNASSIGNED", "unresolved")),
    ],
)
def test_classify_period(period, expected):
    assert classify_period(period) == expected


def _touch_run(root: Path, period: str, run: int) -> Path:
    path = root / period / f"run{run}.root"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    return path


def test_scan_runs_sorts_numerically_and_keeps_relative_provenance(tmp_path):
    _touch_run(tmp_path, "1999_vis", 20)
    _touch_run(tmp_path, "1998_uv", 3)

    records = scan_runs(tmp_path)

    assert [record.run_number for record in records] == [3, 20]
    assert records[0].source_file == "1998_uv/run3.root"
    assert records[1].group == "P_VIS"


def test_scan_runs_rejects_duplicate_run_numbers(tmp_path):
    _touch_run(tmp_path, "1998_uv", 7)
    _touch_run(tmp_path, "1999_vis", 7)

    with pytest.raises(ManifestError, match="duplicate run 7"):
        scan_runs(tmp_path)


def test_scan_runs_rejects_malformed_run_root_name(tmp_path):
    bad = tmp_path / "1998_uv" / "runABC.root"
    bad.parent.mkdir(parents=True)
    bad.touch()

    with pytest.raises(ManifestError, match="malformed run filename"):
        scan_runs(tmp_path)


def test_scan_runs_rejects_empty_scan(tmp_path):
    with pytest.raises(ManifestError, match="no run files"):
        scan_runs(tmp_path)


def test_write_manifest_uses_fixed_schema_and_stable_order(tmp_path):
    records = [
        RunRecord(3, "1998_uv", "P", "UV", "P_UV", "automatic",
                  "1998_uv/run3.root")
    ]
    output = tmp_path / "manifest.csv"

    write_manifest(records, output)

    assert output.read_text() == (
        "run_number,source_period,target,beam_type,group,"
        "classification_source,source_file\n"
        "3,1998_uv,P,UV,P_UV,automatic,1998_uv/run3.root\n"
    )


def test_validate_manifest_accepts_complete_consistent_rows(tmp_path):
    path = tmp_path / "manifest.csv"
    path.write_text(
        "run_number,source_period,target,beam_type,group,"
        "classification_source,source_file\n"
        "3,1998_uv,P,UV,P_UV,automatic,1998_uv/run3.root\n"
        "20,2002_d1,D,VIS,D_VIS,manual,2002_d1/run20.root\n"
    )

    records = validate_manifest(path)

    assert [record.group for record in records] == ["P_UV", "D_VIS"]


@pytest.mark.parametrize(
    ("row", "message"),
    [
        ("3,2002_d1,D,UNKNOWN,UNASSIGNED,unresolved,2002_d1/run3.root",
         "classification is unresolved"),
        ("3,1998_uv,P,UV,P_VIS,manual,1998_uv/run3.root",
         "conflicts with target/beam"),
        ("0,1998_uv,P,UV,P_UV,automatic,1998_uv/run0.root",
         "positive integer"),
        ("3,1998_uv,P,BLUE,P_UV,manual,1998_uv/run3.root",
         "invalid beam_type"),
        ("3,1998_uv,P,UV,P_UV,automatic,/farm/1998_uv/run3.root",
         "must be relative"),
        ("3,1998_uv,P,UV,P_UV,automatic,1998_uv/run4.root",
         "does not match run_number"),
    ],
)
def test_validate_manifest_rejects_invalid_rows(tmp_path, row, message):
    path = tmp_path / "manifest.csv"
    path.write_text(
        "run_number,source_period,target,beam_type,group,"
        "classification_source,source_file\n" + row + "\n"
    )
    with pytest.raises(ManifestError, match=message):
        validate_manifest(path)


def test_validate_manifest_rejects_duplicate_and_unsorted_rows(tmp_path):
    path = tmp_path / "manifest.csv"
    path.write_text(
        "run_number,source_period,target,beam_type,group,"
        "classification_source,source_file\n"
        "20,1999_vis,P,VIS,P_VIS,automatic,1999_vis/run20.root\n"
        "3,1998_uv,P,UV,P_UV,automatic,1998_uv/run3.root\n"
    )
    with pytest.raises(ManifestError, match="ordered by run_number"):
        validate_manifest(path)


def test_validate_manifest_rejects_wrong_schema(tmp_path):
    path = tmp_path / "manifest.csv"
    path.write_text("run_number,target\n3,P\n")
    with pytest.raises(ManifestError, match="invalid columns"):
        validate_manifest(path)
