"""Validate Person 1's immutable N3 acceptance handoff."""

from __future__ import annotations

from dataclasses import InitVar, dataclass
import hashlib
import json
from pathlib import Path
from typing import Mapping

from analysis_config import AnalysisConfig
from contracts import (
    COMMIT_PATTERN,
    SHA256_PATTERN,
    PolarizationContractError,
    canonical_relative_file,
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
_RESPONSE_COVARIANCE_SCOPE_TOKEN = object()
_RESPONSE_PERIOD_COVERAGE_TOKEN = object()
_RESPONSE_PERIOD_COVERAGE_KEYS = (
    "beam_group",
    "covered_source_periods",
    "coverage_valid",
    "detector_conditions_sha256",
    "mc_config_sha256",
    "selection_sha256",
)


@dataclass(frozen=True)
class ResponseCovarianceScope:
    """Loader-sealed N3 declaration that v1 covariance blocks are independent."""

    qa_sha256: str
    shared_mc_across_blocks: bool
    cross_block_covariance: bool
    _loader_token: InitVar[object] = None

    def __post_init__(self, _loader_token: object) -> None:
        if _loader_token is not _RESPONSE_COVARIANCE_SCOPE_TOKEN:
            raise PolarizationContractError(
                "ResponseCovarianceScope must come from validate_acceptance_handoff"
            )


@dataclass(frozen=True)
class ResponsePeriodCoverage:
    """Loader-sealed N3 detector/MC/selection coverage for one beam group."""

    beam_group: str
    covered_source_periods: tuple[str, ...]
    coverage_valid: bool
    detector_conditions_sha256: str
    mc_config_sha256: str
    selection_sha256: str
    qa_sha256: str
    _loader_token: InitVar[object] = None

    def __post_init__(self, _loader_token: object) -> None:
        if _loader_token is not _RESPONSE_PERIOD_COVERAGE_TOKEN:
            raise PolarizationContractError(
                "ResponsePeriodCoverage must come from validate_acceptance_handoff"
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
    response_covariance_scope: ResponseCovarianceScope
    response_period_coverage: tuple[ResponsePeriodCoverage, ...]
    qa: dict[str, object]


def _response_covariance_scope(
    qa: Mapping[str, object], qa_sha256: str
) -> ResponseCovarianceScope:
    """Parse v1 covariance scope from an already byte-authenticated QA object."""
    covariance_checks = qa.get("weighted_covariance_checks")
    if not isinstance(covariance_checks, Mapping):
        raise PolarizationContractError(
            "acceptance QA covariance scope requires weighted covariance checks"
        )
    shared_mc = covariance_checks.get("shared_mc_across_blocks")
    cross_block = covariance_checks.get("cross_block_covariance")
    if type(shared_mc) is not bool or type(cross_block) is not bool:
        raise PolarizationContractError(
            "acceptance QA covariance scope requires exact boolean claims"
        )
    if shared_mc or cross_block:
        raise PolarizationContractError(
            "acceptance QA covariance scope is unsupported by response schema v1"
        )
    return ResponseCovarianceScope(
        qa_sha256,
        shared_mc,
        cross_block,
        _loader_token=_RESPONSE_COVARIANCE_SCOPE_TOKEN,
    )


def _required_digest(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        raise PolarizationContractError(
            f"acceptance QA {key} must be lowercase SHA-256"
        )
    return value


def _response_period_coverage(
    raw: object,
    qa_sha256: str,
    expected_beam_groups: frozenset[str],
) -> tuple[ResponsePeriodCoverage, ...]:
    if not isinstance(raw, list) or not raw:
        raise PolarizationContractError(
            "acceptance QA response period coverage must be a non-empty list"
        )
    parsed = []
    for record in raw:
        if (
            not isinstance(record, Mapping)
            or tuple(record) != _RESPONSE_PERIOD_COVERAGE_KEYS
        ):
            raise PolarizationContractError(
                "acceptance QA response period coverage record has invalid keys"
            )
        beam_group = record.get("beam_group")
        periods = record.get("covered_source_periods")
        if (
            not isinstance(beam_group, str)
            or not beam_group.strip()
            or beam_group != beam_group.strip()
            or not isinstance(periods, list)
            or not periods
            or any(
                not isinstance(period, str)
                or not period.strip()
                or period != period.strip()
                for period in periods
            )
            or periods != sorted(periods)
            or len(set(periods)) != len(periods)
        ):
            raise PolarizationContractError(
                "acceptance QA response period coverage names must be canonical"
            )
        if record.get("coverage_valid") is not True:
            raise PolarizationContractError(
                "acceptance QA response period coverage must be valid"
            )
        for digest_key in (
            "detector_conditions_sha256", "mc_config_sha256", "selection_sha256"
        ):
            digest = record.get(digest_key)
            if not isinstance(digest, str) or SHA256_PATTERN.fullmatch(digest) is None:
                raise PolarizationContractError(
                    "acceptance QA response period coverage hashes must be lowercase SHA-256"
                )
        parsed.append(
            ResponsePeriodCoverage(
                beam_group=beam_group,
                covered_source_periods=tuple(periods),
                coverage_valid=True,
                detector_conditions_sha256=_required_digest(
                    record, "detector_conditions_sha256"
                ),
                mc_config_sha256=_required_digest(record, "mc_config_sha256"),
                selection_sha256=_required_digest(record, "selection_sha256"),
                qa_sha256=qa_sha256,
                _loader_token=_RESPONSE_PERIOD_COVERAGE_TOKEN,
            )
        )
    groups = [record.beam_group for record in parsed]
    if (
        groups != sorted(groups)
        or len(set(groups)) != len(groups)
        or frozenset(groups) != expected_beam_groups
    ):
        raise PolarizationContractError(
            "acceptance QA response period coverage must contain exactly one record per response beam group"
        )
    return tuple(parsed)


def _load_qa_snapshot(path: Path) -> tuple[dict[str, object], str]:
    """Parse QA and hash the exact same byte snapshot."""
    candidate = Path(path)
    try:
        raw = candidate.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PolarizationContractError(
            f"cannot read JSON {candidate}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise PolarizationContractError(
            f"{candidate} must contain a JSON object"
        )
    return payload, hashlib.sha256(raw).hexdigest()


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
    qa, qa_digest = _load_qa_snapshot(qa_path)
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
    covariance_scope = _response_covariance_scope(qa, qa_digest)

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
    period_coverage = _response_period_coverage(
        qa.get("response_period_coverage"),
        qa_digest,
        frozenset(key.beam_group for key in parsed_response.keys),
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
        response_covariance_scope=covariance_scope,
        response_period_coverage=period_coverage,
        qa=qa,
    )
