"""Strict, immutable canonical configuration for polarization analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from pathlib import Path, PurePosixPath
from typing import Mapping

from contracts import (
    SHA256_PATTERN,
    PolarizationContractError,
    canonical_relative_file,
    load_json,
    sha256_file,
)


RESPONSE_VALIDATION_KEYS = frozenset(
    {
        "minimum_generated_effective_events_per_true_phi",
        "probability_absolute_tolerance",
        "uncertainty_absolute_tolerance",
        "uncertainty_relative_tolerance",
        "covariance_eigenvalue_absolute_tolerance",
        "finite_difference_relative_step",
        "finite_difference_absolute_step",
        "replay_absolute_tolerance",
        "replay_relative_tolerance",
    }
)
BOOTSTRAP_KEYS = frozenset(
    {
        "replicas",
        "algorithm_version",
        "seed",
        "maximum_failed_fraction",
        "hessian_diagonal_ratio_min",
        "hessian_diagonal_ratio_max",
    }
)
TOP_LEVEL_KEYS = frozenset(
    {
        "schema_version", "analysis_version", "status", "blocked_reasons",
        "gate0_handoff", "acceptance", "state_mapping", "compton_polarization",
        "angle", "sign_convention", "figure4_comparison", "closure",
        "response_validation", "bootstrap", "release_qa_thresholds",
    }
)
ACCEPTANCE_KEYS = frozenset(
    {
        "status", "handoff_parent", "release_id", "handoff_directory",
        "required_files", "acceptance_qa_sha256", "phi_response_schema_status",
        "phi_response_schema_path", "phi_response_schema_sha256",
        "phi_response_schema_approval_id", "phi_response_schema_reviewers",
    }
)
SIGN_KEYS = frozenset({"status", "approval_id", "reviewers", "model", "orientation_signs"})
FIGURE4_KEYS = frozenset(
    {"energy_edges_gev", "mass_bins", "phi_bins", "target", "tree", "vectors", "content_policy"}
)
RELEASE_QA_KEYS = frozenset(
    {
        "status", "approval_id", "reviewers", "minimum_events_per_bin",
        "maximum_deviance_per_ndof", "closure_bias_absolute_max",
        "closure_pull_mean_absolute_max", "closure_pull_width_tolerance",
        "minimum_systematic_sources", "systematic_combination_policy",
    }
)
REQUIRED_ACCEPTANCE_FILES = (
    "acceptance_v1.csv", "acceptance_phi_response_v1.csv", "acceptance_qa.json",
)
BOOTSTRAP_ALGORITHM_VERSION = "poisson1-sha256-v1"
RESPONSE_SCHEMA_PATH = "config/schemas/acceptance_phi_response_v1.schema.json"
RESPONSE_SCHEMA_APPROVAL_ID = "N3-MASS-PHI-RESPONSE-V1-2026-09-15"


@dataclass(frozen=True)
class ResponseValidationConfig:
    minimum_generated_effective_events_per_true_phi: float | None
    probability_absolute_tolerance: float | None
    uncertainty_absolute_tolerance: float | None
    uncertainty_relative_tolerance: float | None
    covariance_eigenvalue_absolute_tolerance: float | None
    finite_difference_relative_step: float | None
    finite_difference_absolute_step: float | None
    replay_absolute_tolerance: float | None
    replay_relative_tolerance: float | None


@dataclass(frozen=True)
class BootstrapConfig:
    replicas: int | None
    algorithm_version: str
    seed: int | None
    maximum_failed_fraction: float | None
    hessian_diagonal_ratio_min: float | None
    hessian_diagonal_ratio_max: float | None


@dataclass(frozen=True)
class ReleaseQAConfig:
    status: str
    approval_id: str | None
    reviewers: tuple[str, ...]
    minimum_events_per_bin: int | None
    maximum_deviance_per_ndof: float | None
    closure_bias_absolute_max: float | None
    closure_pull_mean_absolute_max: float | None
    closure_pull_width_tolerance: float | None
    minimum_systematic_sources: int | None
    systematic_combination_policy: str | None


@dataclass(frozen=True)
class AnalysisConfig:
    schema_version: int
    analysis_version: str
    status: str
    blocked_reasons: tuple[str, ...]
    acceptance_release_id: str | None
    acceptance_handoff_directory: str | None
    acceptance_qa_sha256: str | None
    phi_response_schema_path: str | None
    phi_response_schema_sha256: str | None
    phi_response_schema_approval_id: str | None
    phi_response_schema_reviewers: tuple[str, ...]
    sign_status: str
    sign_approval_id: str | None
    sign_reviewers: tuple[str, ...]
    orientation_signs: tuple[tuple[str, int], ...]
    figure4_energy_edges_gev: tuple[float, ...]
    figure4_mass_bins: int
    figure4_phi_bins: int
    figure4_target: str
    figure4_tree: str
    figure4_vectors: str
    response_validation: ResponseValidationConfig
    bootstrap: BootstrapConfig
    release_qa: ReleaseQAConfig = field(
        default_factory=lambda: ReleaseQAConfig(
            "pending_owner_approval",
            None,
            (),
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        )
    )


def _mapping(payload: Mapping[str, object], key: str, keys: frozenset[str]) -> Mapping[str, object]:
    value = payload.get(key)
    if not isinstance(value, Mapping) or set(value) != keys:
        raise PolarizationContractError(f"{key} must contain exactly its required keys")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PolarizationContractError(f"{label} must be a non-empty string")
    return value


def _reviewers(value: object, label: str, *, required: bool) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise PolarizationContractError(f"{label} reviewers must be non-empty strings")
    reviewers = tuple(item.strip() for item in value)
    if len(set(reviewers)) != len(reviewers) or (required and len(reviewers) < 2):
        raise PolarizationContractError(f"{label} requires documented two-reviewer approval")
    if not required and reviewers:
        raise PolarizationContractError(f"{label} reviewers must be empty before approval")
    return reviewers


def _canonical_relative_path(value: object, label: str) -> str:
    raw = _text(value, f"{label} path")
    if "\\" in raw or Path(raw).is_absolute() or PurePosixPath(raw).as_posix() != raw:
        raise PolarizationContractError(f"{label} path must be canonical repository-relative POSIX")
    if any(part in {"", ".", ".."} for part in PurePosixPath(raw).parts):
        raise PolarizationContractError(f"{label} path contains forbidden component")
    return raw


def _digest(value: object, label: str, *, required: bool) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        raise PolarizationContractError(f"{label} must be lowercase SHA-256")
    return value


def _number(value: object, label: str, *, required: bool, positive: bool = False) -> float | None:
    if value is None and not required:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PolarizationContractError(f"{label} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise PolarizationContractError(f"{label} must be finite")
    if number < 0.0 or (positive and number <= 0.0):
        qualifier = "positive" if positive else "non-negative"
        raise PolarizationContractError(f"{label} must be {qualifier}")
    return number


def _has_null(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, Mapping):
        return any(_has_null(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_null(item) for item in value)
    return False


def _validate_response(section: Mapping[str, object], *, approved: bool) -> ResponseValidationConfig:
    if set(section) != RESPONSE_VALIDATION_KEYS:
        raise PolarizationContractError("response_validation must contain exactly its required keys")
    values = {
        key: _number(
            section[key], key, required=approved,
            positive=key in {
                "minimum_generated_effective_events_per_true_phi",
                "finite_difference_relative_step", "finite_difference_absolute_step",
            },
        )
        for key in RESPONSE_VALIDATION_KEYS
    }
    if not approved and any(value is not None for value in values.values()):
        raise PolarizationContractError("response_validation values require approval")
    return ResponseValidationConfig(**values)


def _validate_bootstrap(section: Mapping[str, object], *, approved: bool) -> BootstrapConfig:
    if set(section) != BOOTSTRAP_KEYS:
        raise PolarizationContractError("bootstrap must contain exactly its required keys")
    if section.get("algorithm_version") != BOOTSTRAP_ALGORITHM_VERSION:
        raise PolarizationContractError("bootstrap algorithm_version is not supported")
    replicas = section.get("replicas")
    seed = section.get("seed")
    if approved:
        if isinstance(replicas, bool) or not isinstance(replicas, int) or replicas <= 0:
            raise PolarizationContractError("bootstrap replicas must be a positive integer")
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
            raise PolarizationContractError("bootstrap seed must be a non-negative integer")
    elif replicas is not None or seed is not None:
        raise PolarizationContractError("bootstrap values require approval")
    minimum = _number(section.get("hessian_diagonal_ratio_min"), "hessian_diagonal_ratio_min", required=approved, positive=True)
    maximum = _number(section.get("hessian_diagonal_ratio_max"), "hessian_diagonal_ratio_max", required=approved, positive=True)
    failed_fraction = _number(section.get("maximum_failed_fraction"), "maximum_failed_fraction", required=approved)
    if not approved and any(value is not None for value in (minimum, maximum, failed_fraction)):
        raise PolarizationContractError("bootstrap values require approval")
    if failed_fraction is not None and failed_fraction > 1.0:
        raise PolarizationContractError("maximum_failed_fraction must not exceed one")
    if minimum is not None and maximum is not None and minimum > maximum:
        raise PolarizationContractError("hessian diagonal ratio bounds are reversed")
    return BootstrapConfig(replicas, BOOTSTRAP_ALGORITHM_VERSION, seed, failed_fraction, minimum, maximum)


def _validate_release_qa(
    section: Mapping[str, object], *, release_approved: bool
) -> ReleaseQAConfig:
    if set(section) != RELEASE_QA_KEYS:
        raise PolarizationContractError("release_qa_thresholds must contain exactly its required keys")
    status = section.get("status")
    if status not in {"pending_owner_approval", "approved"}:
        raise PolarizationContractError("release_qa_thresholds status is invalid")
    approved = status == "approved"
    if approved != release_approved:
        raise PolarizationContractError("release_qa_thresholds status must match release status")
    approval_id = section.get("approval_id")
    if approved:
        approval_id = _text(approval_id, "release_qa_thresholds approval_id")
    elif approval_id is not None:
        raise PolarizationContractError("pending release_qa_thresholds approval_id must be null")
    reviewers = _reviewers(
        section.get("reviewers"), "release QA", required=approved
    )
    integer_keys = {"minimum_events_per_bin", "minimum_systematic_sources"}
    numeric_keys = {
        "maximum_deviance_per_ndof", "closure_bias_absolute_max",
        "closure_pull_mean_absolute_max", "closure_pull_width_tolerance",
    }
    integers = {}
    for key in integer_keys:
        value = section.get(key)
        if approved:
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise PolarizationContractError(f"release_qa_thresholds {key} must be a positive integer")
        elif value is not None:
            raise PolarizationContractError(f"pending release_qa_thresholds {key} must be null")
        integers[key] = value
    numbers = {}
    for key in numeric_keys:
        value = _number(section.get(key), f"release_qa_thresholds {key}", required=approved)
        if not approved and value is not None:
            raise PolarizationContractError(f"pending release_qa_thresholds {key} must be null")
        numbers[key] = value
    policy = section.get("systematic_combination_policy")
    if approved:
        if policy != "independent_sources_quadrature":
            raise PolarizationContractError("release_qa_thresholds systematic_combination_policy is invalid")
    elif policy is not None:
        raise PolarizationContractError("pending release_qa_thresholds systematic_combination_policy must be null")
    return ReleaseQAConfig(
        status=status,
        approval_id=approval_id,
        reviewers=reviewers,
        minimum_events_per_bin=integers["minimum_events_per_bin"],
        maximum_deviance_per_ndof=numbers["maximum_deviance_per_ndof"],
        closure_bias_absolute_max=numbers["closure_bias_absolute_max"],
        closure_pull_mean_absolute_max=numbers["closure_pull_mean_absolute_max"],
        closure_pull_width_tolerance=numbers["closure_pull_width_tolerance"],
        minimum_systematic_sources=integers["minimum_systematic_sources"],
        systematic_combination_policy=policy,
    )


def load_analysis_config(path: Path, root: Path, *, require_approved: bool) -> AnalysisConfig:
    """Load one canonical configuration, rejecting incomplete release authorities."""
    payload = load_json(path)
    if set(payload) != TOP_LEVEL_KEYS:
        raise PolarizationContractError("analysis config must contain exactly its required keys")
    schema_version = payload.get("schema_version")
    if (
        isinstance(schema_version, bool)
        or not isinstance(schema_version, int)
        or schema_version != 1
        or payload.get("analysis_version") != "polarization-v1"
    ):
        raise PolarizationContractError(
            "analysis config schema_version must be non-boolean integer 1 and "
            "analysis_version must be polarization-v1"
        )
    status = payload.get("status")
    blockers = payload.get("blocked_reasons")
    if status not in {"blocked", "approved"} or not isinstance(blockers, list) or any(not isinstance(item, str) or not item.strip() for item in blockers):
        raise PolarizationContractError("analysis config has invalid status or blockers")
    if (status == "approved") != (not blockers):
        raise PolarizationContractError("approved config requires no blockers; blocked config requires blockers")
    if require_approved and (status != "approved" or blockers or _has_null(payload)):
        raise PolarizationContractError("release requires an approved configuration without null values")
    gate0_handoff = _canonical_relative_path(payload.get("gate0_handoff"), "gate0_handoff")
    if status == "approved":
        canonical_relative_file(root, gate0_handoff, "gate0_handoff")

    acceptance = _mapping(payload, "acceptance", ACCEPTANCE_KEYS)
    acceptance_approved = acceptance.get("status") == "approved"
    if acceptance.get("status") not in {"blocked", "approved"}:
        raise PolarizationContractError("acceptance status is invalid")
    if acceptance_approved != (status == "approved"):
        raise PolarizationContractError("acceptance status must match release status")
    _canonical_relative_path(acceptance.get("handoff_parent"), "acceptance handoff_parent")
    if acceptance.get("required_files") != list(REQUIRED_ACCEPTANCE_FILES):
        raise PolarizationContractError("acceptance required_files must be the canonical triplet")
    release_id = acceptance.get("release_id")
    handoff_directory = acceptance.get("handoff_directory")
    if acceptance_approved:
        release_id = _text(release_id, "acceptance release_id")
        handoff_directory = _canonical_relative_path(handoff_directory, "acceptance handoff_directory")
        expected_directory = f"{acceptance['handoff_parent']}/{release_id}"
        if handoff_directory != expected_directory:
            raise PolarizationContractError("acceptance handoff_directory must match release_id")
    elif release_id is not None or handoff_directory is not None:
        raise PolarizationContractError("blocked acceptance release identity must be null")
    qa_digest = _digest(acceptance.get("acceptance_qa_sha256"), "acceptance_qa_sha256", required=acceptance_approved)
    if not acceptance_approved and qa_digest is not None:
        raise PolarizationContractError("blocked acceptance QA digest must be null")
    schema_approved = acceptance.get("phi_response_schema_status") == "approved"
    if acceptance.get("phi_response_schema_status") not in {"pending_joint_approval", "approved"}:
        raise PolarizationContractError("phi-response schema status is invalid")
    if acceptance_approved and not schema_approved:
        raise PolarizationContractError(
            "acceptance release requires independent phi-response schema approval"
        )
    schema_path = acceptance.get("phi_response_schema_path")
    schema_digest = acceptance.get("phi_response_schema_sha256")
    schema_approval_id = acceptance.get("phi_response_schema_approval_id")
    schema_reviewers = _reviewers(acceptance.get("phi_response_schema_reviewers"), "phi-response schema", required=schema_approved)
    if schema_approved:
        if schema_path != RESPONSE_SCHEMA_PATH:
            raise PolarizationContractError(
                f"phi-response schema path must be {RESPONSE_SCHEMA_PATH}"
            )
        if schema_approval_id != RESPONSE_SCHEMA_APPROVAL_ID:
            raise PolarizationContractError(
                "phi-response schema approval ID does not match the canonical authority"
            )
        schema_path, resolved_schema = canonical_relative_file(root, schema_path, "phi-response schema")
        schema_digest = _digest(schema_digest, "phi_response_schema_sha256", required=True)
        if sha256_file(resolved_schema) != schema_digest:
            raise PolarizationContractError("phi-response schema SHA-256 mismatch")
        schema_approval_id = _text(schema_approval_id, "phi_response_schema_approval_id")
    elif (
        any(value is not None for value in (schema_path, schema_digest, schema_approval_id))
        or schema_reviewers
    ):
        raise PolarizationContractError("pending phi-response schema authority values must be null")

    sign = _mapping(payload, "sign_convention", SIGN_KEYS)
    sign_approved = sign.get("status") == "approved"
    if sign.get("status") not in {"pending_two_reviewer_approval", "approved"}:
        raise PolarizationContractError("sign convention status is invalid")
    if sign_approved and (not isinstance(sign.get("approval_id"), str) or not sign["approval_id"].strip()):
        raise PolarizationContractError("sign convention requires documented two-reviewer approval")
    sign_reviewers = _reviewers(sign.get("reviewers"), "sign convention", required=sign_approved)
    signs = sign.get("orientation_signs")
    if sign_approved:
        if not isinstance(sign.get("approval_id"), str) or not sign["approval_id"].strip() or not isinstance(signs, Mapping) or set(signs) != {"parallel", "perpendicular"} or any(isinstance(value, bool) or not isinstance(value, int) for value in signs.values()) or set(signs.values()) != {-1, 1}:
            raise PolarizationContractError("approved sign convention must assign opposite signs -1 and +1")
    elif sign.get("approval_id") is not None or signs != {}:
        raise PolarizationContractError("pending sign convention approval values must be null or empty")

    figure = _mapping(payload, "figure4_comparison", FIGURE4_KEYS)
    raw_edges = figure.get("energy_edges_gev")
    if not isinstance(raw_edges, list) or len(raw_edges) != 5 or any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in raw_edges):
        raise PolarizationContractError("Figure 4 comparison requires exactly four energy bins with finite edges")
    edges = tuple(float(value) for value in raw_edges)
    if any(right <= left for left, right in zip(edges, edges[1:])):
        raise PolarizationContractError("Figure 4 energy edges must be strictly increasing")
    mass_bins, phi_bins = figure.get("mass_bins"), figure.get("phi_bins")
    if isinstance(mass_bins, bool) or not isinstance(mass_bins, int) or mass_bins < 1:
        raise PolarizationContractError("mass_bins must be a positive integer")
    if isinstance(phi_bins, bool) or not isinstance(phi_bins, int) or phi_bins < 3:
        raise PolarizationContractError("phi_bins must be an integer of at least three")
    target, tree = _text(figure.get("target"), "Figure 4 target"), _text(figure.get("tree"), "Figure 4 ROOT tree")
    vectors = figure.get("vectors")
    if vectors not in {"raw", "kinematic_fit"}:
        raise PolarizationContractError("vectors must be raw or kinematic_fit")
    _text(figure.get("content_policy"), "Figure 4 content_policy")

    release_values_approved = status == "approved"
    response = _validate_response(
        _mapping(payload, "response_validation", RESPONSE_VALIDATION_KEYS),
        approved=release_values_approved,
    )
    bootstrap = _validate_bootstrap(
        _mapping(payload, "bootstrap", BOOTSTRAP_KEYS),
        approved=release_values_approved,
    )
    release_qa = _validate_release_qa(
        _mapping(payload, "release_qa_thresholds", RELEASE_QA_KEYS),
        release_approved=release_values_approved,
    )
    if require_approved:
        if sign_approved is not True or acceptance_approved is not True:
            raise PolarizationContractError("release requires approved sign and acceptance authorities")
    return AnalysisConfig(
        schema_version=1, analysis_version="polarization-v1", status=status,
        blocked_reasons=tuple(blockers), acceptance_release_id=release_id,
        acceptance_handoff_directory=handoff_directory, acceptance_qa_sha256=qa_digest,
        phi_response_schema_path=schema_path, phi_response_schema_sha256=schema_digest,
        phi_response_schema_approval_id=schema_approval_id,
        phi_response_schema_reviewers=schema_reviewers, sign_status=sign["status"],
        sign_approval_id=sign.get("approval_id"), sign_reviewers=sign_reviewers,
        orientation_signs=tuple(sorted(signs.items())) if isinstance(signs, Mapping) else (),
        figure4_energy_edges_gev=edges, figure4_mass_bins=mass_bins,
        figure4_phi_bins=phi_bins, figure4_target=target, figure4_tree=tree,
        figure4_vectors=vectors, response_validation=response, bootstrap=bootstrap,
        release_qa=release_qa,
    )
