"""Behavioral tests for the published-artifact provenance inventory."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.build_artifact_inventory import (
    ArtifactInventoryError,
    build_inventory,
    verify_inventory,
)


def test_inventory_cli_help_runs_without_pythonpath_from_any_working_directory(
    tmp_path,
):
    script = Path(__file__).resolve().parents[2] / "scripts/build_artifact_inventory.py"
    environment = {
        key: value for key, value in os.environ.items() if key != "PYTHONPATH"
    }

    for working_directory in (script.parents[1], tmp_path):
        completed = subprocess.run(
            [sys.executable, str(script), "--help"],
            cwd=working_directory,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr


def put(root: Path, relative: str, payload: bytes = b"payload") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def records(payload: dict) -> dict[str, dict]:
    return {row["path"]: row for row in payload["artifacts"]}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put_n3_bundle(root: Path, release_id="n3-v1", *, valid=True) -> Path:
    release = root / f"results/physics/normalization/handoffs/{release_id}"
    acceptance = put(root, f"{release.relative_to(root)}/acceptance_v1.csv", b"acceptance\n")
    response = put(root, f"{release.relative_to(root)}/acceptance_phi_response_v1.csv", b"response\n")
    put(
        root,
        f"{release.relative_to(root)}/acceptance_qa.json",
        json.dumps(
            {
                "schema_version": 1,
                "acceptance_release_id": release_id,
                "valid": valid,
                "acceptance_csv_sha256": digest(acceptance),
                "acceptance_phi_response_csv_sha256": digest(response),
            }
        ).encode(),
    )
    return release


def put_s4_bundle(root: Path, release_id="fit-v1", *, approved=True) -> Path:
    release = root / f"results/physics/polarization_fits/{release_id}"
    counts = put(root, f"{release.relative_to(root)}/azimuth_counts_v1.csv", b"counts\n")
    fit = put(root, f"{release.relative_to(root)}/sigma_fit_v1.csv", b"fit\n")
    put(
        root,
        f"{release.relative_to(root)}/sigma_fit_qa.json",
        json.dumps(
            {
                "schema_version": 1,
                "fit_release_id": release_id,
                "status": "approved" if approved else "blocked",
                "valid": approved,
                "blocked_reasons": [] if approved else ["pending review"],
                "counts": {"path": counts.relative_to(root).as_posix(), "sha256": digest(counts)},
                "fit": {"path": fit.relative_to(root).as_posix(), "sha256": digest(fit)},
            }
        ).encode(),
    )
    return release


def put_s6_bundle(root: Path, *, approved=True) -> Path:
    release = root / "results/physics/polarization"
    csv_path = put(root, f"{release.relative_to(root)}/sigma_v1.csv", b"sigma\n")
    npz_path = put(root, f"{release.relative_to(root)}/sigma_covariance.npz", b"npz\n")
    put(
        root,
        f"{release.relative_to(root)}/polarization_qa.json",
        json.dumps(
            {
                "schema_version": 1,
                "status": "approved" if approved else "blocked",
                "valid": approved,
                "blocked_reasons": [] if approved else ["pending review"],
                "files": {
                    "sigma_v1.csv": digest(csv_path),
                    "sigma_covariance.npz": digest(npz_path),
                },
            }
        ).encode(),
    )
    return release


def test_inventory_is_sorted_and_hashes_file_bytes(tmp_path):
    """Changing sort order or hashing any bytes other than file contents fails."""
    put(tmp_path, "results/plots/massa_eta.pdf", b"z")
    put(tmp_path, "data/run_manifest.generated.csv", b"run_number\n1\n")
    payload = build_inventory(tmp_path, "abc123")
    paths = [row["path"] for row in payload["artifacts"]]
    assert paths == sorted(paths)
    row = records(payload)["results/plots/massa_eta.pdf"]
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


def test_inventory_allows_only_portable_graphify_artifacts(tmp_path):
    """New host/run-state Graphify files must not become published by default."""
    portable = (
        "GRAPH_REPORT.md",
        "graph.json",
        "graph.html",
        ".graphify_labels.json",
        "manifest.json",
    )
    for name in portable:
        put(tmp_path, f"graphify-out/{name}")
    for name in (
        ".graphify_detect.json",
        ".graphify_ast.json",
        ".graphify_semantic.json",
        ".graphify_cached.json",
        ".graphify_uncached.txt",
        "cache/extraction.json",
    ):
        put(tmp_path, f"graphify-out/{name}")

    assert list(records(build_inventory(tmp_path, "abc123"))) == [
        f"graphify-out/{name}" for name in sorted(portable)
    ]


def test_inventory_selects_only_explicitly_published_paths(tmp_path):
    """Adding raw or scratch bytes must not alter the published inventory."""
    published = (
        "data/flux/flux.root",
        "data/run_manifest.generated.csv",
        "results/reco/reco_eta_pi0_chi2.root",
        "results/plots/massa_eta.pdf",
        "results/strip_energy_flux/strip_energy_lookup.csv",
        "results/strip_energy_flux.run.log",
        "results/observable_runs/observable_run_qa.json",
    )
    for path in published:
        put(tmp_path, path)
    baseline = build_inventory(tmp_path, "abc123")
    for path in (
        "data/graal_data/raw.root",
        "data/pre_analyzed/h80.root",
        "data/selected/selected.root",
        "data/cache/local.csv",
        "results/observable_runs.clone-check/flux.csv",
        "results/strip_energy_flux.failed/input.json",
        "results/cache/partial.csv",
        "results/scratch/not-for-publication.txt",
    ):
        put(tmp_path, path, b"must not be selected")
    assert build_inventory(tmp_path, "abc123") == baseline


def test_inventory_recognizes_only_complete_canonical_s4_triplets(tmp_path):
    release = put_s4_bundle(tmp_path)
    assert set(records(build_inventory(tmp_path, "abc123"))) == {
        f"results/physics/polarization_fits/fit-v1/{name}"
        for name in (
            "azimuth_counts_v1.csv",
            "sigma_fit_v1.csv",
            "sigma_fit_qa.json",
        )
    }

    (release / "sigma_fit_v1.csv").unlink()
    with pytest.raises(ArtifactInventoryError, match="exact S4 triplet"):
        build_inventory(tmp_path, "abc123")
    put(tmp_path, "results/physics/polarization_fits/fit-v1/sigma_fit_v1.csv", b"fit\n")
    put(tmp_path, "results/physics/polarization_fits/fit-v1/legacy_sigma.csv")
    with pytest.raises(ArtifactInventoryError, match="exact S4 triplet"):
        build_inventory(tmp_path, "abc123")


def test_inventory_discovers_exact_n3_s4_s6_and_propagates_qa_state(tmp_path):
    put_n3_bundle(tmp_path)
    put_s4_bundle(tmp_path, approved=False)
    put_s6_bundle(tmp_path)
    indexed = records(build_inventory(tmp_path, "abc123"))
    assert len(indexed) == 9
    assert indexed["results/physics/normalization/handoffs/n3-v1/acceptance_v1.csv"]["valid"] is True
    assert indexed["results/physics/polarization_fits/fit-v1/sigma_fit_v1.csv"]["valid"] is False
    assert indexed["results/physics/polarization/sigma_v1.csv"]["valid"] is True


@pytest.mark.parametrize("bundle", ["n3", "s4", "s6"])
def test_inventory_rejects_internal_hash_tampering_and_garbage_qa(tmp_path, bundle):
    release = {
        "n3": put_n3_bundle,
        "s4": put_s4_bundle,
        "s6": put_s6_bundle,
    }[bundle](tmp_path)
    qa_name = {
        "n3": "acceptance_qa.json",
        "s4": "sigma_fit_qa.json",
        "s6": "polarization_qa.json",
    }[bundle]
    qa_path = release / qa_name
    qa = json.loads(qa_path.read_text())
    if bundle == "n3":
        qa["acceptance_csv_sha256"] = "0" * 64
    elif bundle == "s4":
        qa["counts"]["sha256"] = "0" * 64
    else:
        qa["files"]["sigma_v1.csv"] = "0" * 64
    qa_path.write_text(json.dumps(qa))
    with pytest.raises(ArtifactInventoryError, match="hash|SHA"):
        build_inventory(tmp_path, "abc123")

    qa_path.write_text("{}")
    with pytest.raises(ArtifactInventoryError):
        build_inventory(tmp_path, "abc123")


@pytest.mark.parametrize("bundle", ["s4", "s6"])
def test_inventory_rejects_incoherent_release_state(tmp_path, bundle):
    release = (put_s4_bundle if bundle == "s4" else put_s6_bundle)(tmp_path)
    qa_name = "sigma_fit_qa.json" if bundle == "s4" else "polarization_qa.json"
    qa_path = release / qa_name
    qa = json.loads(qa_path.read_text())
    qa["valid"] = False
    qa_path.write_text(json.dumps(qa))
    with pytest.raises(ArtifactInventoryError, match="state"):
        build_inventory(tmp_path, "abc123")


def test_inventory_rejects_dangling_dynamic_bundle_parent_symlink(tmp_path):
    parent = tmp_path / "results/physics/normalization/handoffs"
    parent.parent.mkdir(parents=True)
    parent.symlink_to(tmp_path / "missing", target_is_directory=True)
    with pytest.raises(ArtifactInventoryError, match="symlink"):
        build_inventory(tmp_path, "abc123")


@pytest.mark.parametrize(
    "release_id",
    (
        ".fit-v1",
        "fit v1",
        "fit\\v1",
    ),
)
def test_inventory_rejects_same_noncanonical_s4_release_ids_as_publisher(
    tmp_path, release_id
):
    for name in (
        "azimuth_counts_v1.csv",
        "sigma_fit_v1.csv",
        "sigma_fit_qa.json",
    ):
        put(
            tmp_path,
            f"results/physics/polarization_fits/{release_id}/{name}",
        )

    with pytest.raises(ArtifactInventoryError, match="noncanonical S4 fit release"):
        build_inventory(tmp_path, "abc123")


def test_inventory_ignores_only_owned_s4_staging_pattern(tmp_path):
    owned = tmp_path / "results/physics/polarization_fits/.fit-v1.staging-abcdefgh"
    owned.mkdir(parents=True)

    assert build_inventory(tmp_path, "abc123")["artifacts"] == []

    (owned.parent / ".scratch").mkdir()
    with pytest.raises(ArtifactInventoryError, match="noncanonical S4 fit release"):
        build_inventory(tmp_path, "abc123")


def _inventory_fixture(tmp_path: Path) -> Path:
    """Create a minimal valid published bundle and return its inventory path."""
    inputs = {
        "config/run_manifest.csv": b"run\n1\n",
        "results/strip_energy_flux/flux_by_run_energy.csv": b"source flux\n",
        "results/strip_energy_flux/strip_energy_lookup.csv": b"source lookup\n",
        "results/strip_energy_flux/strip_energy_flux_qa.json": b'{"valid": false}\n',
    }
    outputs = {
        "flux_by_group_energy.csv": b"groups\n",
        "flux_by_run_energy.csv": b"runs\n",
        "run_manifest_observables.csv": b"manifest\n",
        "run_quality.csv": b"quality\n",
        "strip_energy_lookup.csv": b"lookup\n",
    }
    for path, payload in inputs.items():
        put(tmp_path, path, payload)
    for name, payload in outputs.items():
        put(tmp_path, f"results/observable_runs/{name}", payload)
    digest = lambda path: hashlib.sha256((tmp_path / path).read_bytes()).hexdigest()
    qa = {
        "valid": True,
        "inputs": {
            "manifest": "config/run_manifest.csv",
            "source_files": {
                "flux_by_run_energy.csv": "results/strip_energy_flux/flux_by_run_energy.csv",
                "strip_energy_flux_qa.json": "results/strip_energy_flux/strip_energy_flux_qa.json",
                "strip_energy_lookup.csv": "results/strip_energy_flux/strip_energy_lookup.csv",
            },
        },
        "input_sha256": {
            "manifest": digest("config/run_manifest.csv"),
            "flux_by_run_energy": digest("results/strip_energy_flux/flux_by_run_energy.csv"),
            "strip_energy_flux_qa": digest("results/strip_energy_flux/strip_energy_flux_qa.json"),
            "strip_energy_lookup": digest("results/strip_energy_flux/strip_energy_lookup.csv"),
        },
        "source_qa_sha256": digest("results/strip_energy_flux/strip_energy_flux_qa.json"),
        "output_sha256": {
            name: hashlib.sha256(payload).hexdigest() for name, payload in outputs.items()
        },
    }
    put(tmp_path, "results/observable_runs/observable_run_qa.json", json.dumps(qa).encode())
    inventory = build_inventory(tmp_path, "abc123")
    path = tmp_path / "ARTIFACTS.json"
    path.write_text(json.dumps(inventory), encoding="utf-8")
    return path


def test_verifier_accepts_complete_observable_bundle_and_false_source_diagnostic(tmp_path):
    """Rejecting the intentionally false source QA would block the published snapshot."""
    verify_inventory(tmp_path, _inventory_fixture(tmp_path))


@pytest.mark.parametrize(
    "mutation",
    (
        "missing",
        "changed",
        "extra",
        "invalid_observable_qa",
        "bad_recorded_hash",
        "lfs_pointer",
        "record_role",
        "record_valid",
        "record_allowed_use",
    ),
)
def test_verifier_rejects_snapshot_mutations_without_rewriting_inventory(tmp_path, mutation):
    """A bad publication must fail verification while its reference inventory stays intact."""
    inventory_path = _inventory_fixture(tmp_path)
    target = tmp_path / "results/observable_runs/run_quality.csv"
    if mutation == "missing":
        target.unlink()
    elif mutation == "changed":
        target.write_bytes(b"changed\n")
    elif mutation == "extra":
        put(tmp_path, "results/plots/massa_eta.pdf")
    elif mutation == "invalid_observable_qa":
        qa_path = tmp_path / "results/observable_runs/observable_run_qa.json"
        qa = json.loads(qa_path.read_text())
        qa["valid"] = False
        qa_path.write_text(json.dumps(qa), encoding="utf-8")
    elif mutation == "bad_recorded_hash":
        qa_path = tmp_path / "results/observable_runs/observable_run_qa.json"
        qa = json.loads(qa_path.read_text())
        qa["output_sha256"]["run_quality.csv"] = "0" * 64
        qa_path.write_text(json.dumps(qa), encoding="utf-8")
    elif mutation.startswith("record_"):
        inventory = json.loads(inventory_path.read_text())
        field = mutation.removeprefix("record_")
        inventory["artifacts"][0][field] = (
            False if field == "valid" else "forged"
        )
        inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
    else:
        put(
            tmp_path,
            "data/flux/flux.root",
            b"version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 1\n",
        )
    expected_inventory_bytes = inventory_path.read_bytes()
    with pytest.raises(ArtifactInventoryError):
        verify_inventory(tmp_path, inventory_path)
    assert inventory_path.read_bytes() == expected_inventory_bytes


def test_inventory_cli_rejects_output_outside_repo_and_symlinked_parent(tmp_path):
    """Writing through an escaped output path could overwrite unrelated user data."""
    put(tmp_path, "data/flux/flux.root")
    script = Path(__file__).resolve().parents[2] / "scripts/build_artifact_inventory.py"
    outside = tmp_path.parent / "outside.json"
    command = [
        sys.executable,
        str(script),
        "--repo-root", str(tmp_path), "--commit", "abc123", "--output", str(outside),
    ]
    assert subprocess.run(command, capture_output=True, text=True).returncode != 0
    assert not outside.exists()
    linked_parent = tmp_path / "linked"
    linked_parent.symlink_to(tmp_path.parent, target_is_directory=True)
    command[-1] = str(linked_parent / "inventory.json")
    assert subprocess.run(command, capture_output=True, text=True).returncode != 0
    assert not (tmp_path.parent / "inventory.json").exists()
