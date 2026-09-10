from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from contracts import (
    PolarizationContractError,
    load_json,
    sha256_file,
    validate_gate0_handoff,
    validate_source,
)


BUNDLE_NAMES = (
    "run_manifest_observables.csv",
    "run_quality.csv",
    "strip_energy_lookup.csv",
    "flux_by_run_energy.csv",
    "flux_by_group_energy.csv",
    "observable_run_qa.json",
)


def put(root: Path, relative: str, payload: bytes) -> Path:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return target


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def valid_source(root: Path) -> dict[str, object]:
    payload = b"signed experimental source"
    put(root, "sources/state-map.pdf", payload)
    return {
        "path": "sources/state-map.pdf",
        "sha256": digest(payload),
        "authority": "GRAAL run coordinator",
        "approval_id": "GRAAL-POL-001",
        "reviewers": ["reviewer-one", "reviewer-two"],
    }


def valid_handoff(root: Path) -> Path:
    manifest_payload = b"run_number,source_period\n7,2002_p\n"
    put(root, "config/run_manifest.csv", manifest_payload)
    file_records = []
    for name in BUNDLE_NAMES:
        if name == "observable_run_qa.json":
            payload = json.dumps({"schema_version": 1, "valid": True}).encode()
        else:
            payload = f"fixture:{name}\n".encode()
        put(root, f"results/observable_runs/{name}", payload)
        file_records.append(
            {
                "path": f"results/observable_runs/{name}",
                "sha256": digest(payload),
            }
        )
    handoff = {
        "schema_version": 1,
        "producer_commit": "a" * 40,
        "manifest_path": "config/run_manifest.csv",
        "manifest_sha256": digest(manifest_payload),
        "files": file_records,
        "observable_run_qa_path": "results/observable_runs/observable_run_qa.json",
        "observable_run_qa_sha256": file_records[-1]["sha256"],
        "observable_run_qa_valid": True,
        "energy_binning_mev": [550.0, 700.0, 900.0],
        "created_at_utc": "2026-09-10T10:00:00Z",
    }
    handoff_path = root / "results/observable_runs/HANDOFF.json"
    handoff_path.write_text(json.dumps(handoff), encoding="utf-8")
    return handoff_path


def test_sha256_file_hashes_exact_bytes(tmp_path):
    target = put(tmp_path, "source.bin", b"exact bytes\x00")
    assert sha256_file(target) == digest(b"exact bytes\x00")


def test_load_json_rejects_non_object_payload(tmp_path):
    target = put(tmp_path, "array.json", b"[]")
    with pytest.raises(PolarizationContractError, match="JSON object"):
        load_json(target)


def test_source_requires_existing_file_matching_hash_and_two_approvals(tmp_path):
    source = valid_source(tmp_path)
    assert validate_source(source, tmp_path) == (tmp_path / source["path"]).resolve()

    source["sha256"] = "0" * 64
    with pytest.raises(PolarizationContractError, match="SHA-256 mismatch"):
        validate_source(source, tmp_path)

    source = valid_source(tmp_path)
    source["reviewers"] = ["reviewer-one"]
    with pytest.raises(PolarizationContractError, match="two distinct reviewers"):
        validate_source(source, tmp_path)


def test_source_rejects_paths_outside_root_and_symlinks(tmp_path):
    outside = tmp_path.parent / "outside-polarization-source.pdf"
    outside.write_bytes(b"outside")
    source = valid_source(tmp_path)
    source["path"] = str(outside)
    source["sha256"] = sha256_file(outside)
    with pytest.raises(PolarizationContractError, match="outside repository"):
        validate_source(source, tmp_path)

    link = tmp_path / "sources/link.pdf"
    link.symlink_to(tmp_path / "sources/state-map.pdf")
    source["path"] = "sources/link.pdf"
    source["sha256"] = sha256_file(link)
    with pytest.raises(PolarizationContractError, match="symbolic link"):
        validate_source(source, tmp_path)


def test_gate0_accepts_only_complete_curated_hash_matched_bundle(tmp_path):
    handoff_path = valid_handoff(tmp_path)
    validated = validate_gate0_handoff(handoff_path, tmp_path)
    assert validated["producer_commit"] == "a" * 40
    assert validated["energy_binning_mev"] == [550.0, 700.0, 900.0]


def test_gate0_rejects_missing_handoff_invalid_qa_and_tampered_file(tmp_path):
    with pytest.raises(PolarizationContractError, match="HANDOFF does not exist"):
        validate_gate0_handoff(tmp_path / "HANDOFF.json", tmp_path)

    handoff_path = valid_handoff(tmp_path)
    handoff = json.loads(handoff_path.read_text())
    handoff["observable_run_qa_valid"] = False
    handoff_path.write_text(json.dumps(handoff), encoding="utf-8")
    with pytest.raises(PolarizationContractError, match="QA is not valid"):
        validate_gate0_handoff(handoff_path, tmp_path)

    handoff_path = valid_handoff(tmp_path)
    put(tmp_path, "results/observable_runs/run_quality.csv", b"tampered")
    with pytest.raises(PolarizationContractError, match="SHA-256 mismatch"):
        validate_gate0_handoff(handoff_path, tmp_path)


def test_gate0_rejects_noncanonical_manifest_and_bundle_inventory(tmp_path):
    handoff_path = valid_handoff(tmp_path)
    handoff = json.loads(handoff_path.read_text())
    handoff["manifest_path"] = "data/run_manifest.generated.csv"
    handoff_path.write_text(json.dumps(handoff), encoding="utf-8")
    with pytest.raises(PolarizationContractError, match="curated manifest"):
        validate_gate0_handoff(handoff_path, tmp_path)

    handoff_path = valid_handoff(tmp_path)
    handoff = json.loads(handoff_path.read_text())
    handoff["files"] = handoff["files"][:-1]
    handoff_path.write_text(json.dumps(handoff), encoding="utf-8")
    with pytest.raises(PolarizationContractError, match="exactly six"):
        validate_gate0_handoff(handoff_path, tmp_path)
