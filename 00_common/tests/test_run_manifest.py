from pathlib import Path

import pytest

from graal_common.run_manifest import (
    ManifestError,
    RunRecord,
    classify_period,
    scan_runs,
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
