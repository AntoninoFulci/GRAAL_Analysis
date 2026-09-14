"""Build immutable reconstruction inventory from Gate 0 and run ledger."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

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
    candidate = Path(output_path)
    output = candidate if candidate.is_absolute() else root / candidate
    output = output.absolute()
    try:
        output.relative_to(root)
    except ValueError as exc:
        raise PolarizationContractError(
            "reconstruction inventory output must stay inside repository"
        ) from exc
    current = root
    for component in output.relative_to(root).parts:
        current /= component
        if current.is_symlink():
            raise PolarizationContractError(
                "reconstruction inventory output must not contain symlinks"
            )
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
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{output.name}-", dir=output.parent
    ) as temporary:
        staged = Path(temporary) / output.name
        with staged.open("wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(staged, output, follow_symlinks=False)
        except FileExistsError as exc:
            if output.is_symlink() or not output.is_file():
                raise PolarizationContractError(
                    "refusing overwrite of non-regular or symlink reconstruction inventory"
                ) from exc
            try:
                existing = output.read_bytes()
            except OSError as read_exc:
                raise PolarizationContractError(
                    "cannot authenticate existing reconstruction inventory"
                ) from read_exc
            if existing != encoded:
                raise PolarizationContractError(
                    "refusing overwrite: existing reconstruction inventory has different bytes"
                ) from exc
        else:
            directory_fd = os.open(output.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    return payload
