"""Build a deterministic provenance inventory for published artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Iterable


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
    if relative.parts and relative.parts[0] == "graphify-out":
        return relative.as_posix() not in PORTABLE_GRAPHIFY_PATHS
    return False


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
    if relative.startswith("graphify-out/"):
        return "derived", True, "portable repository knowledge-graph artifact"
    return "derived", True, "published analysis artifact"


def _artifact_paths(repo_root: Path, roots: Iterable[Path | str]) -> list[Path]:
    selected: dict[str, Path] = {}
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
        for path in candidate.rglob("*"):
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


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        payload = build_inventory(args.repo_root, args.commit)
        output = args.output
        if not output.is_absolute():
            output = args.repo_root / output
        if output.is_symlink():
            raise ArtifactInventoryError(f"output must not be a symlink: {output}")
        _write_json_atomically(payload, output)
    except ArtifactInventoryError as exc:
        raise SystemExit(f"artifact inventory error: {exc}") from None
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
