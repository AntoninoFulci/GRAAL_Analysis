"""Validate Person 1's immutable N3 acceptance handoff."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from analysis_config import AnalysisConfig
from contracts import (
    COMMIT_PATTERN,
    SHA256_PATTERN,
    PolarizationContractError,
    canonical_relative_file,
    load_json,
    sha256_file,
)
from phi_response import PhiResponse, load_phi_response


HANDOFF_PARENT = Path("results/physics/normalization/handoffs")
HANDOFF_FILENAMES = frozenset(
    {
        "acceptance_v1.csv",
        "acceptance_phi_response_v1.csv",
        "acceptance_qa.json",
    }
)


@dataclass(frozen=True)
class AcceptanceHandoff:
    release_id: str
    directory: Path
    acceptance_csv: Path
    phi_response_csv: Path
    qa_json: Path
    acceptance_sha256: str
    phi_response_sha256: str
    phi_response_schema_approval_id: str
    schema_path: Path
    schema_sha256: str
    approval_id: str
    response: PhiResponse
    qa_sha256: str
    gate0_handoff_sha256: str
    n2_reconstruction_sha256: str
    qa: dict[str, object]


def _required_digest(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        raise PolarizationContractError(
            f"acceptance QA {key} must be lowercase SHA-256"
        )
    return value


def _canonical_release_directory(release_dir: Path, repository_root: Path) -> Path:
    root = Path(repository_root).resolve()
    candidate = Path(release_dir)
    if not candidate.is_absolute():
        candidate = root / candidate
    absolute = candidate.absolute()
    try:
        relative = absolute.relative_to(root)
    except ValueError as exc:
        raise PolarizationContractError(
            "acceptance must use immutable handoff directory inside repository"
        ) from exc
    parent_parts = HANDOFF_PARENT.parts
    if relative.parts[:-1] != parent_parts or len(relative.parts) != len(parent_parts) + 1:
        raise PolarizationContractError(
            "acceptance must use immutable handoff directory "
            "results/physics/normalization/handoffs/<acceptance_release_id>"
        )
    current = root
    for component in relative.parts:
        current /= component
        if current.is_symlink():
            raise PolarizationContractError("acceptance handoff cannot contain symlinks")
    try:
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError as exc:
        raise PolarizationContractError(
            f"acceptance handoff directory does not exist: {relative.as_posix()}"
        ) from exc
    if not resolved.is_dir():
        raise PolarizationContractError("acceptance handoff path must be a directory")
    return resolved


def validate_acceptance_handoff(
    release_dir: Path,
    repository_root: Path,
    *,
    config: AnalysisConfig,
    expected_gate0_sha256: str | None = None,
) -> AcceptanceHandoff:
    """Validate one externally anchored N3 triplet and parse its response."""
    directory = _canonical_release_directory(release_dir, repository_root)
    entries = {entry.name: entry for entry in directory.iterdir()}
    if frozenset(entries) != HANDOFF_FILENAMES:
        raise PolarizationContractError(
            "acceptance handoff must contain exactly three approved files"
        )
    if any(entry.is_symlink() or not entry.is_file() for entry in entries.values()):
        raise PolarizationContractError(
            "acceptance handoff files must be regular files without symlinks"
        )

    acceptance = entries["acceptance_v1.csv"].resolve()
    response = entries["acceptance_phi_response_v1.csv"].resolve()
    qa_path = entries["acceptance_qa.json"].resolve()
    qa = load_json(qa_path)
    qa_digest = sha256_file(qa_path)
    if config.status != "approved":
        raise PolarizationContractError(
            "acceptance handoff requires approved canonical config"
        )
    if config.acceptance_release_id != directory.name:
        raise PolarizationContractError(
            "acceptance handoff release ID disagrees with canonical config"
        )
    expected_directory = directory.relative_to(Path(repository_root).resolve()).as_posix()
    if config.acceptance_handoff_directory != expected_directory:
        raise PolarizationContractError(
            "acceptance handoff directory disagrees with canonical config"
        )
    if config.acceptance_qa_sha256 != qa_digest:
        raise PolarizationContractError(
            "acceptance QA SHA-256 disagrees with canonical config"
        )
    if qa.get("schema_version") != 1 or qa.get("valid") is not True:
        raise PolarizationContractError("acceptance QA is not valid schema v1")
    if qa.get("acceptance_release_id") != directory.name:
        raise PolarizationContractError(
            "acceptance QA release ID disagrees with immutable directory"
        )
    producer_commit = qa.get("producer_commit")
    if not isinstance(producer_commit, str) or COMMIT_PATTERN.fullmatch(producer_commit) is None:
        raise PolarizationContractError("acceptance QA requires producer Git hash")

    acceptance_digest = _required_digest(qa, "acceptance_csv_sha256")
    response_digest = _required_digest(qa, "acceptance_phi_response_csv_sha256")
    schema_relative = qa.get("phi_response_schema_path")
    if schema_relative != config.phi_response_schema_path:
        raise PolarizationContractError(
            "acceptance QA phi-response schema path disagrees with config"
        )
    _, schema_path = canonical_relative_file(
        repository_root, schema_relative, "acceptance QA phi-response schema"
    )
    schema_digest = _required_digest(qa, "phi_response_schema_sha256")
    if schema_digest != config.phi_response_schema_sha256:
        raise PolarizationContractError(
            "acceptance QA phi-response schema SHA-256 disagrees with config"
        )
    if sha256_file(schema_path) != schema_digest:
        raise PolarizationContractError(
            "acceptance QA phi-response schema SHA-256 mismatch"
        )
    phi_response_schema_approval_id = qa.get(
        "phi_response_schema_approval_id"
    )
    if (
        not isinstance(phi_response_schema_approval_id, str)
        or not phi_response_schema_approval_id.strip()
    ):
        raise PolarizationContractError(
            "acceptance QA requires phi-response schema approval ID"
        )
    if phi_response_schema_approval_id != config.phi_response_schema_approval_id:
        raise PolarizationContractError(
            "acceptance QA phi-response schema approval ID disagrees with config"
        )
    gate0_digest = _required_digest(qa, "gate0_handoff_sha256")
    n2_digest = _required_digest(qa, "n2_reconstruction_sha256")
    input_digest = _required_digest(qa, "input_sha256")
    config_digest = _required_digest(qa, "config_sha256")
    if sha256_file(acceptance) != acceptance_digest:
        raise PolarizationContractError("acceptance CSV SHA-256 mismatch")
    if sha256_file(response) != response_digest:
        raise PolarizationContractError("acceptance response SHA-256 mismatch")
    if expected_gate0_sha256 is not None and gate0_digest != expected_gate0_sha256:
        raise PolarizationContractError("acceptance QA Gate 0 SHA-256 mismatch")
    for check in (
        "count_checks", "matrix_checks", "weighted_covariance_checks", "closure"
    ):
        result = qa.get(check)
        if not isinstance(result, Mapping) or result.get("valid") is not True:
            raise PolarizationContractError(f"acceptance QA {check} is invalid")

    parsed_response = load_phi_response(
        response,
        repository_root=repository_root,
        config=config,
        expected_release_id=directory.name,
    )
    if parsed_response.source_sha256 != response_digest:
        raise PolarizationContractError(
            "parsed response SHA-256 disagrees with acceptance QA"
        )
    if parsed_response.input_sha256 != input_digest:
        raise PolarizationContractError(
            "response input_sha256 disagrees with acceptance QA"
        )
    if parsed_response.config_sha256 != config_digest:
        raise PolarizationContractError(
            "response config_sha256 disagrees with acceptance QA"
        )
    if any(mask != "valid" for mask in parsed_response.validity.values()):
        raise PolarizationContractError(
            "acceptance response contains an invalid true-cell block"
        )
    if sha256_file(qa_path) != qa_digest:
        raise PolarizationContractError("acceptance QA changed during validation")
    return AcceptanceHandoff(
        release_id=directory.name,
        directory=directory,
        acceptance_csv=acceptance,
        phi_response_csv=response,
        qa_json=qa_path,
        acceptance_sha256=acceptance_digest,
        phi_response_sha256=response_digest,
        phi_response_schema_approval_id=phi_response_schema_approval_id,
        schema_path=schema_path,
        schema_sha256=schema_digest,
        approval_id=phi_response_schema_approval_id,
        response=parsed_response,
        qa_sha256=qa_digest,
        gate0_handoff_sha256=gate0_digest,
        n2_reconstruction_sha256=n2_digest,
        qa=qa,
    )
