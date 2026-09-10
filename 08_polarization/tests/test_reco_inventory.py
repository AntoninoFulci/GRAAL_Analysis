from __future__ import annotations

import hashlib
import json

import pytest

from contracts import PolarizationContractError
from reco_inventory import load_gate0_run_numbers, load_reco_inventory


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_reco_inventory_binds_files_runs_tree_vectors_and_gate0(tmp_path):
    reco = tmp_path / "reco.root"
    reco.write_bytes(b"root")
    handoff_hash = "a" * 64
    payload = {
        "schema_version": 1,
        "producer_commit": "b" * 40,
        "gate0_handoff_sha256": handoff_hash,
        "complete_run_coverage": True,
        "tree": "reco_eta_pi0_chi2",
        "vectors": "kinematic_fit",
        "run_numbers": [7, 8],
        "files": [{"path": "reco.root", "sha256": digest(b"root")}],
    }
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps(payload))
    inventory = load_reco_inventory(
        path, tmp_path, expected_handoff_sha256=handoff_hash,
        expected_tree="reco_eta_pi0_chi2", expected_vectors="kinematic_fit",
        expected_run_numbers={7, 8},
    )
    assert inventory.paths == (reco.resolve(),)
    assert inventory.run_numbers == frozenset({7, 8})


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("complete_run_coverage", False, "complete_run_coverage"),
        ("gate0_handoff_sha256", "c" * 64, "Gate 0"),
        ("run_numbers", [7, 7], "unique"),
    ],
)
def test_reco_inventory_rejects_incomplete_or_mismatched_contract(
    tmp_path, field, value, message
):
    reco = tmp_path / "reco.root"
    reco.write_bytes(b"root")
    payload = {
        "schema_version": 1,
        "producer_commit": "b" * 40,
        "gate0_handoff_sha256": "a" * 64,
        "complete_run_coverage": True,
        "tree": "tree",
        "vectors": "raw",
        "run_numbers": [7],
        "files": [{"path": "reco.root", "sha256": digest(b"root")}],
    }
    payload[field] = value
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(PolarizationContractError, match=message):
        load_reco_inventory(
            path, tmp_path, expected_handoff_sha256="a" * 64,
            expected_tree="tree", expected_vectors="raw",
            expected_run_numbers={7},
        )


def test_reco_inventory_must_equal_gate0_target_run_set(tmp_path):
    reco = tmp_path / "reco.root"
    reco.write_bytes(b"root")
    payload = {
        "schema_version": 1, "producer_commit": "b" * 40,
        "gate0_handoff_sha256": "a" * 64, "complete_run_coverage": True,
        "tree": "tree", "vectors": "raw", "run_numbers": [7],
        "files": [{"path": "reco.root", "sha256": digest(b"root")}],
    }
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(PolarizationContractError, match="equal Gate 0"):
        load_reco_inventory(
            path, tmp_path, expected_handoff_sha256="a" * 64,
            expected_tree="tree", expected_vectors="raw",
            expected_run_numbers={7, 8},
        )


def test_load_gate0_run_numbers_filters_target_and_rejects_duplicates(tmp_path):
    path = tmp_path / "runs.csv"
    path.write_text("run_number,target\n7,P\n8,D\n9,P\n")
    assert load_gate0_run_numbers(path, target="P") == {7, 9}
    path.write_text("run_number,target\n7,P\n7,P\n")
    with pytest.raises(PolarizationContractError, match="unique"):
        load_gate0_run_numbers(path, target="P")
