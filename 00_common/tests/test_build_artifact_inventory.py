"""Behavioral tests for the published-artifact provenance inventory."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from scripts.build_artifact_inventory import ArtifactInventoryError, build_inventory


def put(root: Path, relative: str, payload: bytes = b"payload") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def records(payload: dict) -> dict[str, dict]:
    return {row["path"]: row for row in payload["artifacts"]}


def test_inventory_is_sorted_and_hashes_file_bytes(tmp_path):
    """Changing sort order or hashing any bytes other than file contents fails."""
    put(tmp_path, "results/plots/z.pdf", b"z")
    put(tmp_path, "data/run_manifest.generated.csv", b"run_number\n1\n")
    payload = build_inventory(tmp_path, "abc123")
    paths = [row["path"] for row in payload["artifacts"]]
    assert paths == sorted(paths)
    row = records(payload)["results/plots/z.pdf"]
    assert row["sha256"] == hashlib.sha256(b"z").hexdigest()
    assert row["bytes"] == 1


def test_inventory_rejects_symlinks(tmp_path):
    """Following a symlink could inventory data not controlled by this repository."""
    target = put(tmp_path, "target.root")
    link = tmp_path / "data/flux/flux.root"
    link.parent.mkdir(parents=True)
    link.symlink_to(target)
    with pytest.raises(ArtifactInventoryError, match="symlink"):
        build_inventory(tmp_path, "abc123")


def test_inventory_rejects_paths_outside_declared_roots(tmp_path):
    """A root outside the repository must not be silently published."""
    outside = tmp_path.parent / "outside"
    outside.mkdir(exist_ok=True)
    with pytest.raises(ArtifactInventoryError, match="outside repository"):
        build_inventory(tmp_path, "abc123", roots=(outside,))


def test_inventory_marks_legacy_reco_as_not_for_normalization(tmp_path):
    """Treating old reconstruction output as a normalization source is unsafe."""
    put(tmp_path, "results/reco/reco_eta_pi0_chi2.root")
    row = records(build_inventory(tmp_path, "abc123"))[
        "results/reco/reco_eta_pi0_chi2.root"
    ]
    assert row["role"] == "legacy"
    assert row["valid"] is True
    assert "not run-flux normalization" in row["allowed_use"]


def test_inventory_excludes_itself_and_machine_graphify_files(tmp_path):
    """Including generated inventory or host-specific Graphify state breaks portability."""
    put(tmp_path, "ARTIFACTS.json")
    put(tmp_path, "graphify-out/.graphify_python")
    put(tmp_path, "graphify-out/graph.json")
    assert list(records(build_inventory(tmp_path, "abc123"))) == [
        "graphify-out/graph.json"
    ]
