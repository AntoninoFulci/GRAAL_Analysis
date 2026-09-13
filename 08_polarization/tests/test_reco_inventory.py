from __future__ import annotations

import hashlib
import json

import pytest

from contracts import PolarizationContractError
from reco_inventory import load_gate0_run_numbers, load_reco_inventory


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_ledger(path, runs=(7, 8)):
    content = "run_number,status\n" + "".join(
        f"{run},complete\n" for run in runs
    )
    path.write_text(content)
    return {"path": path.name, "sha256": digest(content.encode())}


def test_reco_inventory_binds_files_runs_tree_vectors_and_gate0(tmp_path):
    reco = tmp_path / "reco.root"
    reco.write_bytes(b"root")
    ledger = write_ledger(tmp_path / "processed_runs.csv")
    handoff_hash = "a" * 64
    payload = {
        "schema_version": 1,
        "producer_commit": "b" * 40,
        "gate0_handoff_sha256": handoff_hash,
        "complete_run_coverage": True,
        "tree": "reco_eta_pi0_chi2",
        "vectors": "kinematic_fit",
        "run_numbers": [7, 8],
        "observed_event_run_numbers": [7],
        "zero_selected_event_run_numbers": [8],
        "processed_run_ledger": ledger,
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
    assert inventory.observed_event_run_numbers == frozenset({7})
    assert inventory.zero_selected_event_run_numbers == frozenset({8})


@pytest.mark.parametrize("raw_path", ["./reco.root", "a/../reco.root", "reco\\.root"])
def test_reco_inventory_rejects_noncanonical_serialized_paths(tmp_path, raw_path):
    reco = tmp_path / "reco.root"
    reco.write_bytes(b"root")
    (tmp_path / "a").mkdir()
    ledger = write_ledger(tmp_path / "processed_runs.csv", runs=(7,))
    payload = {
        "schema_version": 1, "producer_commit": "b" * 40,
        "gate0_handoff_sha256": "a" * 64, "complete_run_coverage": True,
        "tree": "tree", "vectors": "raw", "run_numbers": [7],
        "observed_event_run_numbers": [7], "zero_selected_event_run_numbers": [],
        "processed_run_ledger": ledger,
        "files": [{"path": raw_path, "sha256": digest(b"root")}],
    }
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(PolarizationContractError, match="canonical repository-relative POSIX|forbidden component"):
        load_reco_inventory(
            path, tmp_path, expected_handoff_sha256="a" * 64,
            expected_tree="tree", expected_vectors="raw", expected_run_numbers={7},
        )


def test_reco_inventory_rejects_absolute_and_intermediate_symlink_paths(tmp_path):
    reco = tmp_path / "reco.root"
    reco.write_bytes(b"root")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "reco.root").write_bytes(b"root")
    (tmp_path / "linked").symlink_to(nested, target_is_directory=True)
    ledger = write_ledger(tmp_path / "processed_runs.csv", runs=(7,))
    base = {
        "schema_version": 1, "producer_commit": "b" * 40,
        "gate0_handoff_sha256": "a" * 64, "complete_run_coverage": True,
        "tree": "tree", "vectors": "raw", "run_numbers": [7],
        "observed_event_run_numbers": [7], "zero_selected_event_run_numbers": [],
        "processed_run_ledger": ledger,
    }
    for raw_path in (str(reco), "linked/reco.root"):
        payload = {
            **base,
            "files": [{"path": raw_path, "sha256": digest(b"root")}],
        }
        path = tmp_path / "inventory.json"
        path.write_text(json.dumps(payload))
        with pytest.raises(PolarizationContractError):
            load_reco_inventory(
                path, tmp_path, expected_handoff_sha256="a" * 64,
                expected_tree="tree", expected_vectors="raw", expected_run_numbers={7},
            )


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
    ledger = write_ledger(tmp_path / "processed_runs.csv", runs=(7,))
    payload = {
        "schema_version": 1,
        "producer_commit": "b" * 40,
        "gate0_handoff_sha256": "a" * 64,
        "complete_run_coverage": True,
        "tree": "tree",
        "vectors": "raw",
        "run_numbers": [7],
        "observed_event_run_numbers": [7],
        "zero_selected_event_run_numbers": [],
        "processed_run_ledger": ledger,
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
    ledger = write_ledger(tmp_path / "processed_runs.csv", runs=(7,))
    payload = {
        "schema_version": 1, "producer_commit": "b" * 40,
        "gate0_handoff_sha256": "a" * 64, "complete_run_coverage": True,
        "tree": "tree", "vectors": "raw", "run_numbers": [7],
        "observed_event_run_numbers": [7], "zero_selected_event_run_numbers": [],
        "processed_run_ledger": ledger,
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


def test_reco_inventory_rejects_inconsistent_observed_zero_event_partition(tmp_path):
    reco = tmp_path / "reco.root"
    reco.write_bytes(b"root")
    ledger = write_ledger(tmp_path / "processed_runs.csv")
    payload = {
        "schema_version": 1, "producer_commit": "b" * 40,
        "gate0_handoff_sha256": "a" * 64, "complete_run_coverage": True,
        "tree": "tree", "vectors": "raw", "run_numbers": [7, 8],
        "observed_event_run_numbers": [7],
        "zero_selected_event_run_numbers": [7, 8],
        "processed_run_ledger": ledger,
        "files": [{"path": "reco.root", "sha256": digest(b"root")}],
    }
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(PolarizationContractError, match="partition"):
        load_reco_inventory(
            path, tmp_path, expected_handoff_sha256="a" * 64,
            expected_tree="tree", expected_vectors="raw",
            expected_run_numbers={7, 8},
        )
