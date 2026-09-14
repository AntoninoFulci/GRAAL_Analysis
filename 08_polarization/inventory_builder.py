"""Build immutable reconstruction inventory from Gate 0 and run ledger."""

from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import stat

from contracts import (
    COMMIT_PATTERN,
    SHA256_PATTERN,
    PolarizationContractError,
    sha256_file,
)
from reco_inventory import load_processed_run_ledger


def _repo_file(path: Path, root: Path, label: str) -> tuple[Path, str]:
    repository = root.resolve()
    candidate = Path(path)
    try:
        resolved = candidate.resolve(strict=True)
        relative = resolved.relative_to(repository)
    except (FileNotFoundError, ValueError) as exc:
        raise PolarizationContractError(
            f"{label} must be an existing file inside repository"
        ) from exc
    if not resolved.is_file() or candidate.is_symlink():
        raise PolarizationContractError(f"{label} must be regular and non-symlink")
    return resolved, relative.as_posix()


def _output_relative(path: Path, root: Path) -> Path:
    """Return lexical repository-relative output identity without resolving it."""
    raw = os.fspath(path)
    components = raw.split("/")
    if raw.startswith("/"):
        components = components[1:]
    if "\\" in raw or any(part in {"", ".", ".."} for part in components):
        raise PolarizationContractError(
            "reconstruction inventory output must use canonical path components"
        )
    candidate = Path(path)
    if candidate.is_absolute():
        try:
            relative = candidate.relative_to(root)
        except ValueError as exc:
            raise PolarizationContractError(
                "reconstruction inventory output must stay inside repository"
            ) from exc
    else:
        relative = candidate
    if not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
        raise PolarizationContractError(
            "reconstruction inventory output must use canonical path components"
        )
    return relative


def _directory_flags() -> int:
    """Return fail-closed flags for opening an anchored real directory."""
    if not hasattr(os, "O_DIRECTORY") or not hasattr(os, "O_NOFOLLOW"):
        raise PolarizationContractError(
            "secure reconstruction inventory publication is unsupported"
        )
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def _open_parent_directory(root: Path, relative_parent: Path) -> tuple[int, Path]:
    """Create/open each parent beneath a directory FD, rejecting link swaps."""
    flags = _directory_flags()
    current_path = root
    try:
        current_fd = os.open(root, flags)
    except OSError as exc:
        raise PolarizationContractError(
            "cannot anchor reconstruction inventory repository"
        ) from exc
    try:
        for component in relative_parent.parts:
            try:
                os.mkdir(component, dir_fd=current_fd)
            except FileExistsError:
                pass
            try:
                next_fd = os.open(component, flags, dir_fd=current_fd)
            except OSError as exc:
                raise PolarizationContractError(
                    "reconstruction inventory output parent must be a real directory"
                ) from exc
            os.close(current_fd)
            current_fd = next_fd
            current_path /= component
        return current_fd, current_path
    except BaseException:
        os.close(current_fd)
        raise


def _same_open_directory(directory_fd: int, lexical_path: Path) -> bool:
    """Confirm lexical parent still names directory held by directory_fd."""
    try:
        anchored = os.fstat(directory_fd)
        named = os.stat(lexical_path, follow_symlinks=False)
    except OSError:
        return False
    return (
        stat.S_ISDIR(named.st_mode)
        and (anchored.st_dev, anchored.st_ino) == (named.st_dev, named.st_ino)
    )


def _read_regular_at(directory_fd: int, name: str) -> bytes:
    flags = os.O_RDONLY | os.O_NOFOLLOW
    try:
        file_fd = os.open(name, flags, dir_fd=directory_fd)
    except OSError as exc:
        raise PolarizationContractError(
            "refusing overwrite of symlink or unreadable reconstruction inventory"
        ) from exc
    try:
        metadata = os.fstat(file_fd)
        if not stat.S_ISREG(metadata.st_mode):
            raise PolarizationContractError(
                "refusing overwrite of non-regular or symlink reconstruction inventory"
            )
        chunks = []
        while chunk := os.read(file_fd, 1024 * 1024):
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(file_fd)


def _publish_bytes(root: Path, relative: Path, encoded: bytes) -> None:
    """Publish immutable bytes through one inode-anchored parent directory."""
    parent_fd, parent_path = _open_parent_directory(root, relative.parent)
    temporary = f".{relative.name}-{secrets.token_hex(8)}"
    temporary_created = False
    try:
        if not _same_open_directory(parent_fd, parent_path):
            raise PolarizationContractError(
                "reconstruction inventory output parent changed before staging"
            )
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
        staged_fd = os.open(temporary, flags, 0o600, dir_fd=parent_fd)
        temporary_created = True
        try:
            view = memoryview(encoded)
            while view:
                written = os.write(staged_fd, view)
                if written <= 0:
                    raise PolarizationContractError(
                        "cannot stage reconstruction inventory bytes"
                    )
                view = view[written:]
            os.fsync(staged_fd)
        finally:
            os.close(staged_fd)
        if not _same_open_directory(parent_fd, parent_path):
            raise PolarizationContractError(
                "reconstruction inventory output parent changed before publication"
            )
        try:
            os.link(
                temporary,
                relative.name,
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
                follow_symlinks=False,
            )
        except FileExistsError as exc:
            existing = _read_regular_at(parent_fd, relative.name)
            if existing != encoded:
                raise PolarizationContractError(
                    "refusing overwrite: existing reconstruction inventory has different bytes"
                ) from exc
        if not _same_open_directory(parent_fd, parent_path):
            raise PolarizationContractError(
                "reconstruction inventory output parent changed during publication"
            )
        os.fsync(parent_fd)
    finally:
        if temporary_created:
            try:
                os.unlink(temporary, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
        os.close(parent_fd)


def build_reco_inventory(
    *,
    repository_root: Path,
    output_path: Path,
    reco_paths,
    processed_run_ledger: Path,
    gate0_handoff_sha256: str,
    gate0_run_numbers,
    observed_event_run_numbers,
    tree: str,
    vectors: str,
    producer_commit: str,
) -> dict[str, object]:
    """Write one inventory only after ledger and observed-run validation."""
    root = Path(repository_root).resolve()
    if SHA256_PATTERN.fullmatch(gate0_handoff_sha256 or "") is None:
        raise PolarizationContractError("Gate 0 handoff hash must be lowercase SHA-256")
    if COMMIT_PATTERN.fullmatch(producer_commit or "") is None:
        raise PolarizationContractError("producer_commit must be a Git hash")
    if vectors not in {"raw", "kinematic_fit"} or not isinstance(tree, str) or not tree:
        raise PolarizationContractError("tree/vector selection is invalid")
    expected_runs = frozenset(gate0_run_numbers)
    observed_runs = frozenset(observed_event_run_numbers)
    ledger_path, ledger_relative = _repo_file(
        processed_run_ledger, root, "processed-run ledger"
    )
    ledger_runs = load_processed_run_ledger(ledger_path)
    if ledger_runs != expected_runs:
        raise PolarizationContractError(
            "processed-run ledger must equal Gate 0 target run set"
        )
    unexpected = observed_runs - expected_runs
    if unexpected:
        raise PolarizationContractError(
            "reconstruction events contain runs outside Gate 0"
        )
    resolved_reco = [
        _repo_file(path, root, "reconstruction ROOT file") for path in reco_paths
    ]
    if not resolved_reco:
        raise PolarizationContractError("at least one reconstruction ROOT file is required")
    output_relative = _output_relative(output_path, root)
    payload = {
        "schema_version": 1,
        "artifact_kind": "n2_metadata_reconstruction",
        "producer_commit": producer_commit,
        "gate0_handoff_sha256": gate0_handoff_sha256,
        "complete_run_coverage": True,
        "tree": tree,
        "vectors": vectors,
        "run_numbers": sorted(expected_runs),
        "observed_event_run_numbers": sorted(observed_runs),
        "zero_selected_event_run_numbers": sorted(expected_runs - observed_runs),
        "processed_run_ledger": {
            "path": ledger_relative,
            "sha256": sha256_file(ledger_path),
        },
        "files": [
            {"path": relative, "sha256": sha256_file(path)}
            for path, relative in resolved_reco
        ],
    }
    encoded = (json.dumps(payload, indent=2) + "\n").encode("utf-8")
    _publish_bytes(root, output_relative, encoded)
    return payload
