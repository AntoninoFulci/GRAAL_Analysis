"""Build a deterministic provenance inventory for published artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Iterable

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.s4_release_id import (
    is_owned_fit_staging_name,
    validate_fit_release_id,
)


CHUNK_BYTES = 1024 * 1024
SCHEMA_VERSION = 1
DEFAULT_ROOTS: tuple[str, ...] = ("data", "results", "graphify-out")
PORTABLE_GRAPHIFY_PATHS = frozenset(
    {
        "graphify-out/GRAPH_REPORT.md",
        "graphify-out/graph.json",
        "graphify-out/graph.html",
        "graphify-out/.graphify_labels.json",
        "graphify-out/manifest.json",
    }
)
PUBLISHED_ARTIFACT_PATHS = frozenset(
    {
        "data/flux/flux.root",
        "data/run_manifest.generated.csv",
        *PORTABLE_GRAPHIFY_PATHS,
        "results/observable_runs/flux_by_group_energy.csv",
        "results/observable_runs/flux_by_run_energy.csv",
        "results/observable_runs/observable_run_qa.json",
        "results/observable_runs/run_manifest_observables.csv",
        "results/observable_runs/run_quality.csv",
        "results/observable_runs/strip_energy_lookup.csv",
        "results/plots/dalitz_bdt_implicito.pdf",
        "results/plots/dalitz_bdt_misurato.pdf",
        "results/plots/dalitz_chi2_implicito.pdf",
        "results/plots/dalitz_chi2_misurato.pdf",
        "results/plots/dalitz_confronto.pdf",
        "results/plots/istogrammi.root",
        "results/plots/kinfit_validation.png",
        "results/plots/massa_eta.pdf",
        "results/plots/massa_eta_p.pdf",
        "results/plots/massa_eta_p_mc.pdf",
        "results/plots/massa_eta_raw_confronto.pdf",
        "results/plots/massa_pi0.pdf",
        "results/plots/massa_pi0_p.pdf",
        "results/plots/massa_pi0_p_mc.pdf",
        "results/plots/massa_pi0_raw_confronto.pdf",
        "results/plots/masse_2d_bdt.pdf",
        "results/plots/masse_2d_chi2.pdf",
        "results/plots/masse_2d_confronto.pdf",
        "results/plots/risoluzione_eta_p.pdf",
        "results/plots/risoluzione_pi0_p.pdf",
        "results/reco/reco_eta_pi0_bdt.root",
        "results/reco/reco_eta_pi0_chi2.root",
        "results/strip_energy_flux.run.log",
        "results/strip_energy_flux/flux_by_group_energy.csv",
        "results/strip_energy_flux/flux_by_run_energy.csv",
        "results/strip_energy_flux/strip_energy_flux_qa.json",
        "results/strip_energy_flux/strip_energy_lookup.csv",
    }
)
OBSERVABLE_BUNDLE_PATHS = frozenset(
    {
        "results/observable_runs/flux_by_group_energy.csv",
        "results/observable_runs/flux_by_run_energy.csv",
        "results/observable_runs/observable_run_qa.json",
        "results/observable_runs/run_manifest_observables.csv",
        "results/observable_runs/run_quality.csv",
        "results/observable_runs/strip_energy_lookup.csv",
    }
)
LFS_POINTER_HEADER = b"version https://git-lfs.github.com/spec/v1\n"
S4_FIT_PARENT = "results/physics/polarization_fits"
S4_FIT_FILENAMES = frozenset(
    {"azimuth_counts_v1.csv", "sigma_fit_v1.csv", "sigma_fit_qa.json"}
)


class ArtifactInventoryError(ValueError):
    """Raised when an inventory would include an unsafe or invalid path."""


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _repository_path(repo_root: Path, root: Path | str) -> Path:
    candidate = Path(root)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    return candidate


def _reject_symlink_components(repo_root: Path, candidate: Path) -> None:
    """Reject a link in a path below the repository before resolving it."""
    lexical = candidate.absolute()
    if not _is_within(lexical, repo_root):
        return
    current = repo_root
    for component in lexical.relative_to(repo_root).parts:
        current /= component
        if current.is_symlink():
            raise ArtifactInventoryError(f"symlink is not allowed: {current}")


def _is_excluded(relative: Path) -> bool:
    """Return whether this path is generated, local, or temporary state."""
    name = relative.name
    if name == "ARTIFACTS.json":
        return True
    if name.endswith((".tmp", ".temp", "~")):
        return True
    return relative.as_posix() not in PUBLISHED_ARTIFACT_PATHS


def _sha256_and_size(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK_BYTES):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _classification(relative: str) -> tuple[str, bool, str]:
    """Return role, validity, and approved use for a published path."""
    if relative == "data/run_manifest.generated.csv":
        return (
            "derived",
            True,
            "generated convenience manifest; verify against config/run_manifest.csv",
        )
    if relative.startswith("data/"):
        return "input", True, "published analysis input"
    if relative.startswith("results/reco/"):
        return "legacy", True, "legacy plots only; not run-flux normalization"
    if relative.startswith("results/plots/") or relative == "results/strip_energy_flux.run.log":
        return "derived", True, "diagnostic only; not normalization input"
    if relative.startswith("results/strip_energy_flux/"):
        return "derived", True, "source bundle for observable-run rebuild"
    if relative.startswith("results/observable_runs/"):
        return "derived", True, "accepted observable-run bundle when QA is valid"
    if relative.startswith(f"{S4_FIT_PARENT}/"):
        return "derived", True, "immutable replayable S4 fit evidence"
    if relative.startswith("graphify-out/"):
        return "derived", True, "portable repository knowledge-graph artifact"
    return "derived", True, "published analysis artifact"


def _artifact_paths(repo_root: Path, roots: Iterable[Path | str]) -> list[Path]:
    selected: dict[str, Path] = {}
    resolved_roots: list[Path] = []
    for root in roots:
        candidate = _repository_path(repo_root, root)
        _reject_symlink_components(repo_root, candidate)
        resolved_root = candidate.resolve(strict=False)
        if not _is_within(resolved_root, repo_root):
            raise ArtifactInventoryError(
                f"declared root is outside repository: {candidate}"
            )
        if candidate.is_symlink():
            raise ArtifactInventoryError(f"symlink is not allowed: {candidate}")
        if not candidate.exists():
            continue
        if not candidate.is_dir():
            raise ArtifactInventoryError(f"declared root is not a directory: {candidate}")
        resolved_roots.append(resolved_root)
    for relative_name in sorted(PUBLISHED_ARTIFACT_PATHS):
        path = repo_root / relative_name
        if not any(_is_within(path, root) for root in resolved_roots):
            continue
        _reject_symlink_components(repo_root, path)
        if path.is_symlink():
            raise ArtifactInventoryError(f"symlink is not allowed: {path}")
        if not path.is_file():
            continue
        resolved_path = path.resolve()
        if not _is_within(resolved_path, repo_root):
            raise ArtifactInventoryError(f"path is outside repository: {path}")
        relative = resolved_path.relative_to(repo_root)
        if _is_excluded(relative):
            continue
        selected[relative.as_posix()] = resolved_path
    s4_parent = repo_root / S4_FIT_PARENT
    if s4_parent.exists():
        _reject_symlink_components(repo_root, s4_parent)
        if s4_parent.is_symlink() or not s4_parent.is_dir():
            raise ArtifactInventoryError("S4 fit evidence parent must be a directory")
        for release in sorted(s4_parent.iterdir(), key=lambda item: item.name):
            if not any(_is_within(release, root) for root in resolved_roots):
                continue
            if (
                is_owned_fit_staging_name(release.name)
                and not release.is_symlink()
                and release.is_dir()
            ):
                continue
            try:
                validate_fit_release_id(release.name)
            except ValueError as exc:
                raise ArtifactInventoryError(
                    f"noncanonical S4 fit release entry: {release}"
                ) from exc
            if (
                release.is_symlink()
                or not release.is_dir()
            ):
                raise ArtifactInventoryError(
                    f"noncanonical S4 fit release entry: {release}"
                )
            entries = tuple(release.iterdir())
            if (
                {entry.name for entry in entries} != S4_FIT_FILENAMES
                or any(entry.is_symlink() or not entry.is_file() for entry in entries)
            ):
                raise ArtifactInventoryError(
                    f"S4 fit release must contain exact S4 triplet: {release}"
                )
            for entry in entries:
                resolved_entry = entry.resolve(strict=True)
                if not _is_within(resolved_entry, repo_root):
                    raise ArtifactInventoryError(
                        f"S4 fit evidence is outside repository: {entry}"
                    )
                relative = resolved_entry.relative_to(repo_root).as_posix()
                selected[relative] = resolved_entry
    return [selected[name] for name in sorted(selected)]


def build_inventory(
    repo_root: Path,
    commit: str,
    roots: tuple[Path | str, ...] = DEFAULT_ROOTS,
) -> dict[str, object]:
    """Return deterministic inventory for published artifact roots."""
    resolved_repo = Path(repo_root).resolve()
    if not resolved_repo.is_dir():
        raise ArtifactInventoryError(f"repository root is not a directory: {repo_root}")
    if not commit:
        raise ArtifactInventoryError("commit must not be empty")

    artifacts = []
    for path in _artifact_paths(resolved_repo, roots):
        relative = path.relative_to(resolved_repo).as_posix()
        sha256, size = _sha256_and_size(path)
        role, valid, allowed_use = _classification(relative)
        artifacts.append(
            {
                "path": relative,
                "bytes": size,
                "sha256": sha256,
                "role": role,
                "valid": valid,
                "allowed_use": allowed_use,
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_commit": commit,
        "artifacts": artifacts,
    }


def _read_json(path: Path, description: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactInventoryError(f"invalid {description}: {path}") from exc
    if not isinstance(value, dict):
        raise ArtifactInventoryError(f"invalid {description}: {path}")
    return value


def _verify_hash(path: Path, expected: object, description: str) -> None:
    if not isinstance(expected, str) or len(expected) != 64:
        raise ArtifactInventoryError(f"invalid recorded hash for {description}")
    actual, _ = _sha256_and_size(path)
    if actual != expected:
        raise ArtifactInventoryError(f"recorded hash does not match {description}")


def _reject_lfs_pointer(path: Path) -> None:
    with path.open("rb") as stream:
        if stream.read(len(LFS_POINTER_HEADER)) == LFS_POINTER_HEADER:
            raise ArtifactInventoryError(f"unhydrated Git LFS pointer: {path}")


def _verify_observable_bundle(repo_root: Path, inventory_paths: set[str]) -> None:
    if not OBSERVABLE_BUNDLE_PATHS <= inventory_paths:
        missing = sorted(OBSERVABLE_BUNDLE_PATHS - inventory_paths)
        raise ArtifactInventoryError(f"inventory misses observable bundle files: {missing}")
    qa_path = repo_root / "results/observable_runs/observable_run_qa.json"
    qa = _read_json(qa_path, "observable-run QA")
    if qa.get("valid") is not True:
        raise ArtifactInventoryError("observable-run QA must have valid=true")

    inputs = qa.get("inputs")
    input_hashes = qa.get("input_sha256")
    output_hashes = qa.get("output_sha256")
    if not isinstance(inputs, dict) or not isinstance(input_hashes, dict):
        raise ArtifactInventoryError("observable-run QA is missing input hashes")
    if not isinstance(output_hashes, dict):
        raise ArtifactInventoryError("observable-run QA is missing output hashes")
    source_files = inputs.get("source_files")
    expected_sources = {
        "manifest": "config/run_manifest.csv",
        "flux_by_run_energy": "results/strip_energy_flux/flux_by_run_energy.csv",
        "strip_energy_flux_qa": "results/strip_energy_flux/strip_energy_flux_qa.json",
        "strip_energy_lookup": "results/strip_energy_flux/strip_energy_lookup.csv",
    }
    if not isinstance(source_files, dict) or inputs.get("manifest") != expected_sources["manifest"]:
        raise ArtifactInventoryError("observable-run QA has unexpected input paths")
    if source_files != {
        "flux_by_run_energy.csv": expected_sources["flux_by_run_energy"],
        "strip_energy_flux_qa.json": expected_sources["strip_energy_flux_qa"],
        "strip_energy_lookup.csv": expected_sources["strip_energy_lookup"],
    }:
        raise ArtifactInventoryError("observable-run QA has unexpected source paths")
    for name, relative in expected_sources.items():
        _verify_hash(repo_root / relative, input_hashes.get(name), relative)
    source_qa_path = repo_root / expected_sources["strip_energy_flux_qa"]
    _verify_hash(source_qa_path, qa.get("source_qa_sha256"), str(source_qa_path))
    if _read_json(source_qa_path, "source strip-energy QA").get("valid") is not False:
        raise ArtifactInventoryError("source strip-energy QA must retain valid=false diagnostic state")

    expected_outputs = OBSERVABLE_BUNDLE_PATHS - {
        "results/observable_runs/observable_run_qa.json"
    }
    output_names = {Path(path).name for path in expected_outputs}
    if set(output_hashes) != output_names:
        raise ArtifactInventoryError("observable-run QA has incomplete output hashes")
    for name in output_names:
        _verify_hash(repo_root / "results/observable_runs" / name, output_hashes[name], name)


def verify_inventory(repo_root: Path, inventory_path: Path) -> None:
    """Verify a saved inventory and accepted observable bundle without writing files."""
    resolved_repo = Path(repo_root).resolve()
    resolved_inventory = Path(inventory_path).resolve()
    if not _is_within(resolved_inventory, resolved_repo):
        raise ArtifactInventoryError("inventory is outside repository")
    payload = _read_json(resolved_inventory, "artifact inventory")
    rows = payload.get("artifacts")
    if not isinstance(rows, list):
        raise ArtifactInventoryError("artifact inventory has no artifact list")
    expected: dict[str, dict[str, object]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            raise ArtifactInventoryError("artifact inventory contains malformed record")
        path = row["path"]
        if path in expected:
            raise ArtifactInventoryError(f"artifact inventory duplicates {path}")
        expected[path] = row

    actual_paths = {path.relative_to(resolved_repo).as_posix(): path for path in _artifact_paths(resolved_repo, DEFAULT_ROOTS)}
    if set(expected) != set(actual_paths):
        missing = sorted(set(expected) - set(actual_paths))
        extra = sorted(set(actual_paths) - set(expected))
        raise ArtifactInventoryError(f"published artifact paths differ; missing={missing}, extra={extra}")
    for relative, path in actual_paths.items():
        _reject_lfs_pointer(path)
        digest, size = _sha256_and_size(path)
        record = expected[relative]
        if record.get("bytes") != size or record.get("sha256") != digest:
            raise ArtifactInventoryError(f"inventory bytes or SHA-256 mismatch: {relative}")
    _verify_observable_bundle(resolved_repo, set(expected))


def _write_json_atomically(payload: dict[str, object], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output.parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary_name = stream.name
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, output)
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)


def _validated_output_path(repo_root: Path, output: Path) -> Path:
    candidate = output if output.is_absolute() else repo_root / output
    lexical = Path(os.path.abspath(candidate))
    if not _is_within(lexical, repo_root):
        raise ArtifactInventoryError(f"output is outside repository: {candidate}")
    _reject_symlink_components(repo_root, lexical)
    resolved = lexical.resolve(strict=False)
    if not _is_within(resolved, repo_root):
        raise ArtifactInventoryError(f"output is outside repository: {candidate}")
    if lexical.is_symlink():
        raise ArtifactInventoryError(f"output must not be a symlink: {lexical}")
    return lexical


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--commit")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--inventory", type=Path, default=Path("ARTIFACTS.json"))
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        repo_root = Path(args.repo_root).resolve()
        if args.verify:
            if args.commit is not None or args.output is not None:
                raise ArtifactInventoryError("--verify cannot be combined with --commit or --output")
            inventory = args.inventory if args.inventory.is_absolute() else repo_root / args.inventory
            verify_inventory(repo_root, inventory)
        else:
            if not args.commit or args.output is None:
                raise ArtifactInventoryError("--commit and --output are required when generating inventory")
            payload = build_inventory(repo_root, args.commit)
            _write_json_atomically(payload, _validated_output_path(repo_root, args.output))
    except ArtifactInventoryError as exc:
        raise SystemExit(f"artifact inventory error: {exc}") from None
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
