from __future__ import annotations

import csv
import json
import os

import pytest

from contracts import PolarizationContractError, sha256_file
from inventory_builder import build_reco_inventory
from reco_inventory import load_reco_inventory


def write_ledger(path, rows):
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["run_number", "status"])
        writer.writerows(rows)


def test_builder_writes_loadable_inventory_and_records_zero_event_runs(tmp_path):
    reco = tmp_path / "reco.root"
    reco.write_bytes(b"root")
    ledger = tmp_path / "processed.csv"
    write_ledger(ledger, [(7, "complete"), (8, "complete")])
    output = tmp_path / "inventory.json"
    build_reco_inventory(
        repository_root=tmp_path,
        output_path=output,
        reco_paths=[reco],
        processed_run_ledger=ledger,
        gate0_handoff_sha256="a" * 64,
        gate0_run_numbers={7, 8},
        observed_event_run_numbers={7},
        tree="tree",
        vectors="raw",
        producer_commit="b" * 40,
    )
    payload = json.loads(output.read_text())
    assert payload["artifact_kind"] == "n2_metadata_reconstruction"
    assert payload["zero_selected_event_run_numbers"] == [8]
    assert payload["processed_run_ledger"]["sha256"] == sha256_file(ledger)
    loaded = load_reco_inventory(
        output, tmp_path, expected_handoff_sha256="a" * 64,
        expected_tree="tree", expected_vectors="raw",
        expected_run_numbers={7, 8},
    )
    assert loaded.run_numbers == {7, 8}
    assert loaded.observed_event_run_numbers == {7}
    assert loaded.zero_selected_event_run_numbers == {8}


def test_builder_rejects_incomplete_ledger_unexpected_events_and_overwrite(tmp_path):
    reco = tmp_path / "reco.root"
    reco.write_bytes(b"root")
    ledger = tmp_path / "processed.csv"
    write_ledger(ledger, [(7, "complete"), (8, "failed")])
    arguments = dict(
        repository_root=tmp_path, output_path=tmp_path / "inventory.json",
        reco_paths=[reco], processed_run_ledger=ledger,
        gate0_handoff_sha256="a" * 64, gate0_run_numbers={7, 8},
        observed_event_run_numbers={7}, tree="tree", vectors="raw",
        producer_commit="b" * 40,
    )
    with pytest.raises(PolarizationContractError, match="complete"):
        build_reco_inventory(**arguments)
    write_ledger(ledger, [(7, "complete"), (8, "complete")])
    arguments["observed_event_run_numbers"] = {9}
    with pytest.raises(PolarizationContractError, match="outside Gate 0"):
        build_reco_inventory(**arguments)
    arguments["observed_event_run_numbers"] = {7}
    arguments["output_path"].write_text("existing")
    with pytest.raises(PolarizationContractError, match="overwrite"):
        build_reco_inventory(**arguments)


def _arguments(tmp_path):
    reco = tmp_path / "reco.root"
    reco.write_bytes(b"root")
    ledger = tmp_path / "processed.csv"
    write_ledger(ledger, [(7, "complete")])
    return dict(
        repository_root=tmp_path, output_path=tmp_path / "inventory.json",
        reco_paths=[reco], processed_run_ledger=ledger,
        gate0_handoff_sha256="a" * 64, gate0_run_numbers={7},
        observed_event_run_numbers={7}, tree="tree", vectors="raw",
        producer_commit="b" * 40,
    )


def test_builder_reuses_byte_identical_inventory_without_rewriting(tmp_path):
    arguments = _arguments(tmp_path)
    build_reco_inventory(**arguments)
    output = arguments["output_path"]
    before = output.stat()
    build_reco_inventory(**arguments)
    after = output.stat()
    assert (after.st_ino, after.st_mtime_ns) == (before.st_ino, before.st_mtime_ns)


def test_builder_preserves_foreign_destination_created_during_publication(
    tmp_path, monkeypatch
):
    import inventory_builder

    arguments = _arguments(tmp_path)
    output = arguments["output_path"]
    real_link = os.link

    def racing_link(source, destination, **kwargs):
        output.write_bytes(b"foreign")
        raise FileExistsError(destination)

    monkeypatch.setattr(inventory_builder.os, "link", racing_link)
    with pytest.raises(PolarizationContractError, match="different|overwrite"):
        build_reco_inventory(**arguments)
    assert output.read_bytes() == b"foreign"
    assert not list(tmp_path.glob(".inventory.json-*"))
    monkeypatch.setattr(inventory_builder.os, "link", real_link)


def test_builder_rejects_dangling_symlink_destination_without_touching_target(tmp_path):
    arguments = _arguments(tmp_path)
    output = arguments["output_path"]
    target = tmp_path / "missing-target"
    output.symlink_to(target)
    with pytest.raises(PolarizationContractError, match="symlink|overwrite"):
        build_reco_inventory(**arguments)
    assert output.is_symlink()
    assert not target.exists()
