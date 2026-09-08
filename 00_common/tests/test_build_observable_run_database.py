"""Integration tests for the artifact-only observable-run database CLI."""

from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from graal_common.run_manifest import FIELDNAMES, validate_manifest, write_manifest
from graal_common.run_manifest import RunRecord
from graal_common.strip_energy_flux import LOOKUP_FIELDS, RUN_FLUX_FIELDS


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLI = PROJECT_ROOT / "scripts" / "build_observable_run_database.py"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _manifest_records() -> list[RunRecord]:
    return [
        RunRecord(
            run_number,
            "period_a" if run_number <= 5 else "period_b",
            "P",
            "UV",
            "P_UV",
            "manual",
            f"period/run{run_number}.root",
        )
        for run_number in range(1, 11)
    ]


def _source_qa() -> dict[str, object]:
    return {
        "schema_version": 1,
        "inputs": {},
        "thresholds": {},
        "binnings": {"ajaka_cross_section": [1.0, 1.1]},
        "manifest_run_count": 10,
        "h80_run_count": 10,
        "flux_run_count": 10,
        "lookup_strip_count": 10,
        "h80": {},
        "flux": {},
        "missing_h80_runs": [],
        "extra_h80_runs": [],
        "extra_h80_run_count": 0,
        "extra_h80_runs_truncated": False,
        "extra_flux_runs": [],
        "malformed_flux_triplets": [],
        "empty_strips": [],
        "nonzero_unmapped_strips": [],
        "monotonic_inversions": [],
        "mad_warnings": [],
        "low_stat_warnings": [],
        "underflow_overflow": [],
        "out_of_range": {},
        "negative_net_errors": [],
        "conservation": {"failures": [], "valid": True},
        "run_flux_bin_count": 10,
        "errors": [],
        "valid": True,
    }


def _build_source_bundle(tmp_path: Path) -> tuple[Path, Path]:
    manifest = tmp_path / "run_manifest.csv"
    source = tmp_path / "source"
    source.mkdir()
    records = _manifest_records()
    write_manifest(records, manifest)
    lookup_rows = []
    flux_rows = []
    for record in records:
        lookup_rows.append(
            {
                "run_number": record.run_number,
                "source_period": record.source_period,
                "target": record.target,
                "beam_type": record.beam_type,
                "group": record.group,
                "xstrip": 1,
                "event_count": 10,
                "energy_median_gev": 1.05,
                "energy_mad_gev": 0.01,
                "energy_min_gev": 1.0,
                "energy_max_gev": 1.1,
                "provenance": "observed",
            }
        )
        brem = 100.0 if record.run_number == 10 else 1.0
        pol1 = brem - 0.5 if record.run_number == 5 else brem + 3.0
        pol2 = brem + 4.0
        flux_rows.append(
            {
                "binning": "ajaka_cross_section",
                "run_number": record.run_number,
                "source_period": record.source_period,
                "target": record.target,
                "beam_type": record.beam_type,
                "group": record.group,
                "energy_low_gev": 1.0,
                "energy_high_gev": 1.1,
                "pol1": pol1,
                "brem": brem,
                "pol2": pol2,
                "pol1_net": pol1 - brem,
                "pol2_net": pol2 - brem,
                "total_net": pol1 + pol2 - 2 * brem,
                "status": "invalid" if record.run_number == 5 else "valid",
            }
        )
    _write_csv(source / "strip_energy_lookup.csv", LOOKUP_FIELDS, lookup_rows)
    _write_csv(source / "flux_by_run_energy.csv", RUN_FLUX_FIELDS, flux_rows)
    (source / "strip_energy_flux_qa.json").write_text(
        json.dumps(_source_qa(), indent=2, sort_keys=True) + "\n"
    )
    return manifest, source


def _run_cli(tmp_path: Path, manifest: Path, source: Path, output: Path) -> subprocess.CompletedProcess[str]:
    package_target = tmp_path / "package"
    shutil.copytree(
        PROJECT_ROOT / "00_common", package_target / "graal_common", dirs_exist_ok=True
    )
    environment = os.environ | {"PYTHONPATH": str(package_target)}
    return subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--manifest",
            str(manifest),
            "--strip-energy-dir",
            str(source),
            "--output-dir",
            str(output),
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def test_cli_publishes_deterministic_good_run_bundle_with_lineage(tmp_path):
    """Removing quality filtering or lineage serialization breaks this contract."""
    manifest, source = _build_source_bundle(tmp_path)
    output = tmp_path / "output"

    completed = _run_cli(tmp_path, manifest, source, output)

    assert completed.returncode == 0, completed.stderr
    assert {path.name for path in output.iterdir()} == {
        "run_quality.csv",
        "run_manifest_observables.csv",
        "strip_energy_lookup.csv",
        "flux_by_run_energy.csv",
        "flux_by_group_energy.csv",
        "observable_run_qa.json",
    }
    assert validate_manifest(output / "run_manifest_observables.csv")
    qa = json.loads((output / "observable_run_qa.json").read_text())
    assert qa["valid"] is True
    assert qa["counts_by_status"] == {"bad": 1, "good": 8, "review": 1}
    assert set(qa["input_sha256"]) == {"manifest", "strip_energy_lookup", "flux_by_run_energy", "strip_energy_flux_qa"}
    assert qa["input_sha256"]["manifest"] == _sha256(manifest)
    assert qa["input_sha256"]["strip_energy_lookup"] == _sha256(source / "strip_energy_lookup.csv")
    assert qa["input_sha256"]["flux_by_run_energy"] == _sha256(source / "flux_by_run_energy.csv")
    assert qa["input_sha256"]["strip_energy_flux_qa"] == _sha256(source / "strip_energy_flux_qa.json")
    assert all(_sha256(output / name) == digest for name, digest in qa["output_sha256"].items())

    for name in ("strip_energy_lookup.csv", "flux_by_run_energy.csv"):
        with (output / name).open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        assert {int(row["run_number"]) for row in rows} == set(range(1, 5)) | set(range(6, 10))
        assert all(row["status"] == "valid" for row in rows if "status" in row)
    with (output / "flux_by_group_energy.csv").open(newline="") as stream:
        group_rows = list(csv.DictReader(stream))
    assert len(group_rows) == 1
    assert group_rows[0]["status"] == "valid"
    assert float(group_rows[0]["brem"]) == 8.0
    assert float(group_rows[0]["pol1"]) == 32.0
    assert float(group_rows[0]["pol2"]) == 40.0

    second = tmp_path / "second-output"
    repeated = _run_cli(tmp_path, manifest, source, second)
    assert repeated.returncode == 0, repeated.stderr
    assert {
        path.name: path.read_bytes() for path in output.iterdir()
    } == {
        path.name: path.read_bytes() for path in second.iterdir()
    }


def test_cli_rejects_unclassified_source_errors_without_replacing_destination(tmp_path):
    """Accepting unknown producer errors could publish an unsafe good-run bundle."""
    manifest, source = _build_source_bundle(tmp_path)
    qa_path = source / "strip_energy_flux_qa.json"
    payload = json.loads(qa_path.read_text())
    payload["errors"] = ["unknown producer failure"]
    payload["valid"] = False
    qa_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    output = tmp_path / "output"
    output.mkdir()
    (output / "sentinel").write_text("keep")

    completed = _run_cli(tmp_path, manifest, source, output)

    assert completed.returncode == 1
    assert "unclassified source QA error" in completed.stderr
    assert (output / "sentinel").read_text() == "keep"
    assert {path.name for path in output.iterdir()} == {"sentinel"}


def test_cli_rejects_metadata_conflicts_without_replacing_destination(tmp_path):
    """Bypassing strict readers would let conflicting run metadata leak into outputs."""
    manifest, source = _build_source_bundle(tmp_path)
    lookup = source / "strip_energy_lookup.csv"
    rows = list(csv.DictReader(lookup.open(newline="")))
    rows[0]["group"] = "D_UV"
    _write_csv(lookup, LOOKUP_FIELDS, rows)
    output = tmp_path / "output"
    output.mkdir()
    (output / "sentinel").write_text("keep")

    completed = _run_cli(tmp_path, manifest, source, output)

    assert completed.returncode == 1
    assert "metadata conflicts" in completed.stderr
    assert {path.name for path in output.iterdir()} == {"sentinel"}


def test_cli_rejects_an_output_directory_inside_its_source_bundle(tmp_path):
    """Allowing output nesting would make a future build consume its own results."""
    manifest, source = _build_source_bundle(tmp_path)
    output = source / "observable-output"

    completed = _run_cli(tmp_path, manifest, source, output)

    assert completed.returncode == 1
    assert "output directory contains input path" in completed.stderr
    assert not output.exists()
