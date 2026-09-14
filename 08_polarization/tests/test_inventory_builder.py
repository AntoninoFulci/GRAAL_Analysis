from __future__ import annotations

import csv
import json
import os
from pathlib import Path

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


@pytest.mark.parametrize(
    "output_path",
    (
        Path("nested/../inventory.json"),
        Path("../escaped-inventory.json"),
    ),
)
def test_builder_rejects_lexical_parent_components_before_writing(
    tmp_path, output_path
):
    arguments = _arguments(tmp_path)
    arguments["output_path"] = output_path

    with pytest.raises(PolarizationContractError, match="canonical|component"):
        build_reco_inventory(**arguments)

    assert not (tmp_path / "nested").exists()
    assert not (tmp_path.parent / "escaped-inventory.json").exists()


def test_builder_rejects_dangling_symlink_parent_before_writing(tmp_path):
    arguments = _arguments(tmp_path)
    arguments["output_path"] = Path("publish/inventory.json")
    parent = tmp_path / "publish"
    parent.symlink_to(tmp_path / "missing-parent", target_is_directory=True)

    with pytest.raises(PolarizationContractError, match="symlink|directory"):
        build_reco_inventory(**arguments)

    assert parent.is_symlink()
    assert not (tmp_path / "missing-parent").exists()


def test_builder_parent_swap_during_publish_never_writes_outside(
    tmp_path, monkeypatch
):
    import inventory_builder

    arguments = _arguments(tmp_path)
    arguments["output_path"] = Path("publish/inventory.json")
    parent = tmp_path / "publish"
    parent.mkdir()
    detached = tmp_path / "detached-owned-parent"
    outside = tmp_path / "outside"
    outside.mkdir()
    real_link = os.link

    def racing_link(source, destination, **kwargs):
        parent.rename(detached)
        parent.symlink_to(outside, target_is_directory=True)
        return real_link(source, destination, **kwargs)

    monkeypatch.setattr(inventory_builder.os, "link", racing_link)
    with pytest.raises(PolarizationContractError, match="changed|canonical"):
        build_reco_inventory(**arguments)

    assert not (outside / "inventory.json").exists()
    assert not (detached / "inventory.json").exists()
    assert not list(detached.glob(".inventory.json-*"))


def test_builder_cleanup_unlink_failure_reports_and_removes_staged_file(
    tmp_path, monkeypatch
):
    import inventory_builder

    arguments = _arguments(tmp_path)
    arguments["output_path"] = Path("publish/inventory.json")
    parent = tmp_path / "publish"
    parent.mkdir()
    detached = tmp_path / "detached-cleanup-parent"
    outside = tmp_path / "outside"
    outside.mkdir()
    real_link = os.link
    real_unlink = os.unlink

    def racing_link(source, destination, **kwargs):
        parent.rename(detached)
        parent.symlink_to(outside, target_is_directory=True)
        return real_link(source, destination, **kwargs)

    def failing_unlink(path, **kwargs):
        if path == "inventory.json":
            raise PermissionError(path)
        return real_unlink(path, **kwargs)

    monkeypatch.setattr(inventory_builder.os, "link", racing_link)
    monkeypatch.setattr(inventory_builder.os, "unlink", failing_unlink)
    with pytest.raises(PolarizationContractError, match="cannot clean owned"):
        build_reco_inventory(**arguments)

    assert (detached / "inventory.json").is_file()
    assert not list(detached.glob(".inventory.json-*"))
    assert not (outside / "inventory.json").exists()


def test_builder_cleanup_preserves_destination_replaced_after_owned_link(
    tmp_path, monkeypatch
):
    import inventory_builder

    arguments = _arguments(tmp_path)
    arguments["output_path"] = Path("publish/inventory.json")
    parent = tmp_path / "publish"
    parent.mkdir()
    detached = tmp_path / "detached-foreign-parent"
    outside = tmp_path / "outside"
    outside.mkdir()
    real_link = os.link
    real_unlink = os.unlink

    def racing_link(source, destination, **kwargs):
        parent.rename(detached)
        parent.symlink_to(outside, target_is_directory=True)
        result = real_link(source, destination, **kwargs)
        directory_fd = kwargs["dst_dir_fd"]
        real_unlink(destination, dir_fd=directory_fd)
        foreign_fd = os.open(
            destination,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
            dir_fd=directory_fd,
        )
        try:
            os.write(foreign_fd, b"foreign")
        finally:
            os.close(foreign_fd)
        return result

    monkeypatch.setattr(inventory_builder.os, "link", racing_link)
    with pytest.raises(PolarizationContractError, match="foreign"):
        build_reco_inventory(**arguments)

    assert (detached / "inventory.json").read_bytes() == b"foreign"
    assert not list(detached.glob(".inventory.json-*"))
    assert not (outside / "inventory.json").exists()


def test_builder_parent_swap_during_mkdir_fails_closed(tmp_path, monkeypatch):
    import inventory_builder

    arguments = _arguments(tmp_path)
    arguments["output_path"] = Path("publish/inventory.json")
    parent = tmp_path / "publish"
    detached = tmp_path / "detached-created-parent"
    outside = tmp_path / "outside"
    outside.mkdir()
    real_mkdir = os.mkdir

    def racing_mkdir(path, *args, **kwargs):
        result = real_mkdir(path, *args, **kwargs)
        if path == "publish" and kwargs.get("dir_fd") is not None:
            parent.rename(detached)
            parent.symlink_to(outside, target_is_directory=True)
        return result

    monkeypatch.setattr(inventory_builder.os, "mkdir", racing_mkdir)
    with pytest.raises(PolarizationContractError, match="real directory"):
        build_reco_inventory(**arguments)

    assert not (outside / "inventory.json").exists()


def test_builder_parent_swap_during_staging_cleans_only_owned_temp(
    tmp_path, monkeypatch
):
    import inventory_builder

    arguments = _arguments(tmp_path)
    arguments["output_path"] = Path("publish/inventory.json")
    parent = tmp_path / "publish"
    parent.mkdir()
    detached = tmp_path / "detached-staging-parent"
    outside = tmp_path / "outside"
    outside.mkdir()
    real_open = os.open
    swapped = False

    def racing_open(path, flags, *args, **kwargs):
        nonlocal swapped
        if (
            not swapped
            and isinstance(path, str)
            and path.startswith(".inventory.json-")
            and kwargs.get("dir_fd") is not None
        ):
            swapped = True
            parent.rename(detached)
            parent.symlink_to(outside, target_is_directory=True)
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(inventory_builder.os, "open", racing_open)
    with pytest.raises(PolarizationContractError, match="changed"):
        build_reco_inventory(**arguments)

    assert not (outside / "inventory.json").exists()
    assert not list(detached.glob(".inventory.json-*"))
