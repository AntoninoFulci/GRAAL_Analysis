"""Fail-closed provenance contracts for beam-polarization analysis."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import stat
from typing import Mapping


CHUNK_BYTES = 1024 * 1024
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
CURATED_MANIFEST = "config/run_manifest.csv"
OBSERVABLE_BUNDLE_PATHS = frozenset(
    {
        "results/observable_runs/run_manifest_observables.csv",
        "results/observable_runs/run_quality.csv",
        "results/observable_runs/strip_energy_lookup.csv",
        "results/observable_runs/flux_by_run_energy.csv",
        "results/observable_runs/flux_by_group_energy.csv",
        "results/observable_runs/observable_run_qa.json",
    }
)


class PolarizationContractError(ValueError):
    """Raised when scientific input or provenance violates Person 2's contract."""


def sha256_file(path: Path) -> str:
    """Return lowercase SHA-256 of exact file bytes."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, object]:
    """Load one JSON object, translating parse and shape failures."""
    candidate = Path(path)
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PolarizationContractError(f"cannot read JSON {candidate}: {exc}") from exc
    if not isinstance(payload, dict):
        raise PolarizationContractError(f"{candidate} must contain a JSON object")
    return payload


def canonical_relative_file(root: Path, raw_path: object, label: str) -> tuple[str, Path]:
    """Return a canonical repository-relative identity and verified file path."""
    if not isinstance(raw_path, str) or not raw_path:
        raise PolarizationContractError(f"{label} path must be a non-empty string")
    if (
        "\\" in raw_path
        or Path(raw_path).is_absolute()
        or PurePosixPath(raw_path).as_posix() != raw_path
    ):
        raise PolarizationContractError(
            f"{label} path must be canonical repository-relative POSIX"
        )
    parts = PurePosixPath(raw_path).parts
    if any(component in {"", ".", ".."} for component in parts):
        raise PolarizationContractError(f"{label} path contains forbidden component")
    repository_root = Path(root).resolve()
    candidate = repository_root.joinpath(*parts)
    current = repository_root
    for component in parts:
        current /= component
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError as exc:
            raise PolarizationContractError(f"{label} does not exist: {raw_path}") from exc
        if stat.S_ISLNK(mode):
            raise PolarizationContractError(f"{label} path contains a symbolic link: {raw_path}")
    try:
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError as exc:
        raise PolarizationContractError(f"{label} does not exist: {raw_path}") from exc
    try:
        resolved.relative_to(repository_root)
    except ValueError as exc:
        raise PolarizationContractError(f"{label} path is outside repository: {raw_path}") from exc
    if not stat.S_ISREG(resolved.stat().st_mode):
        raise PolarizationContractError(f"{label} is not a regular file: {raw_path}")
    return raw_path, resolved


def _resolved_regular_file(root: Path, raw_path: object, label: str) -> Path:
    """Compatibility wrapper for readers that only need the verified path."""
    return canonical_relative_file(root, raw_path, label)[1]


def _required_text(payload: Mapping[str, object], key: str, label: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PolarizationContractError(f"{label} requires non-empty {key}")
    return value


def _required_digest(payload: Mapping[str, object], key: str, label: str) -> str:
    value = _required_text(payload, key, label)
    if SHA256_PATTERN.fullmatch(value) is None:
        raise PolarizationContractError(f"{label} {key} must be lowercase SHA-256")
    return value


def validate_source(source: Mapping[str, object], root: Path) -> Path:
    """Validate one authority-approved, content-addressed experimental source."""
    if not isinstance(source, Mapping):
        raise PolarizationContractError("source must be a JSON object")
    candidate = _resolved_regular_file(root, source.get("path"), "source")
    expected = _required_digest(source, "sha256", "source")
    actual = sha256_file(candidate)
    if actual != expected:
        raise PolarizationContractError(
            f"source SHA-256 mismatch for {source.get('path')}: expected {expected}, got {actual}"
        )
    _required_text(source, "authority", "source")
    _required_text(source, "approval_id", "source")
    reviewers = source.get("reviewers")
    if not isinstance(reviewers, list):
        raise PolarizationContractError("source requires two distinct reviewers")
    normalized = {
        reviewer.strip()
        for reviewer in reviewers
        if isinstance(reviewer, str) and reviewer.strip()
    }
    if len(normalized) < 2:
        raise PolarizationContractError("source requires two distinct reviewers")
    return candidate


def _validate_energy_binning(raw: object) -> list[float]:
    if not isinstance(raw, list) or len(raw) < 2:
        raise PolarizationContractError("HANDOFF energy_binning_mev needs at least two edges")
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in raw):
        raise PolarizationContractError("HANDOFF energy_binning_mev must be numeric")
    edges = [float(value) for value in raw]
    if any(not math.isfinite(value) for value in edges):
        raise PolarizationContractError("HANDOFF energy_binning_mev must be finite")
    if any(right <= left for left, right in zip(edges, edges[1:])):
        raise PolarizationContractError("HANDOFF energy_binning_mev must be strictly increasing")
    return edges


def validate_gate0_handoff(path: Path, repository_root: Path) -> dict[str, object]:
    """Validate Gate 0 identity, bundle completeness, QA, and exact bytes."""
    handoff_path = Path(path)
    if not handoff_path.is_file():
        raise PolarizationContractError(f"HANDOFF does not exist: {handoff_path}")
    handoff = load_json(handoff_path)
    if handoff.get("schema_version") != 1:
        raise PolarizationContractError("HANDOFF schema_version must be 1")
    producer_commit = handoff.get("producer_commit")
    if not isinstance(producer_commit, str) or COMMIT_PATTERN.fullmatch(producer_commit) is None:
        raise PolarizationContractError("HANDOFF producer_commit must be a 40-character Git hash")
    if handoff.get("manifest_path") != CURATED_MANIFEST:
        raise PolarizationContractError(
            f"HANDOFF must identify curated manifest {CURATED_MANIFEST}"
        )
    manifest = _resolved_regular_file(repository_root, CURATED_MANIFEST, "curated manifest")
    expected_manifest_hash = _required_digest(handoff, "manifest_sha256", "HANDOFF")
    actual_manifest_hash = sha256_file(manifest)
    if actual_manifest_hash != expected_manifest_hash:
        raise PolarizationContractError(
            "curated manifest SHA-256 mismatch: "
            f"expected {expected_manifest_hash}, got {actual_manifest_hash}"
        )
    records = handoff.get("files")
    if not isinstance(records, list) or len(records) != 6:
        raise PolarizationContractError("HANDOFF must declare exactly six observable bundle files")
    by_path: dict[str, Mapping[str, object]] = {}
    for record in records:
        if not isinstance(record, Mapping):
            raise PolarizationContractError("HANDOFF file records must be JSON objects")
        relative = record.get("path")
        if not isinstance(relative, str) or relative in by_path:
            raise PolarizationContractError("HANDOFF file paths must be unique strings")
        by_path[relative] = record
    if frozenset(by_path) != OBSERVABLE_BUNDLE_PATHS:
        raise PolarizationContractError("HANDOFF must declare exactly six canonical bundle paths")
    for relative, record in by_path.items():
        candidate = _resolved_regular_file(repository_root, relative, "bundle file")
        expected = _required_digest(record, "sha256", f"bundle file {relative}")
        actual = sha256_file(candidate)
        if actual != expected:
            raise PolarizationContractError(
                f"bundle file SHA-256 mismatch for {relative}: expected {expected}, got {actual}"
            )
    qa_relative = handoff.get("observable_run_qa_path")
    canonical_qa = "results/observable_runs/observable_run_qa.json"
    if qa_relative != canonical_qa:
        raise PolarizationContractError(f"HANDOFF QA path must be {canonical_qa}")
    qa_hash = _required_digest(handoff, "observable_run_qa_sha256", "HANDOFF")
    if qa_hash != by_path[canonical_qa].get("sha256"):
        raise PolarizationContractError("HANDOFF QA hash disagrees with bundle file record")
    if handoff.get("observable_run_qa_valid") is not True:
        raise PolarizationContractError("HANDOFF observable-run QA is not valid")
    qa = load_json(_resolved_regular_file(repository_root, canonical_qa, "observable-run QA"))
    if qa.get("valid") is not True:
        raise PolarizationContractError("source observable-run QA is not valid")
    handoff["energy_binning_mev"] = _validate_energy_binning(
        handoff.get("energy_binning_mev")
    )
    _required_text(handoff, "created_at_utc", "HANDOFF")
    return handoff
