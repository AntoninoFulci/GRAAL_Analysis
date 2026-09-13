from __future__ import annotations

import csv
import dataclasses
import hashlib
import json
from pathlib import Path

import pytest

from acceptance_handoff import validate_acceptance_handoff
from contracts import PolarizationContractError


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def repo(response_fixture) -> Path:
    return response_fixture.path.parent


@pytest.fixture
def valid_handoff(response_fixture, repo: Path) -> Path:
    release = (
        repo
        / "results/physics/normalization/handoffs"
        / response_fixture.config.acceptance_release_id
    )
    release.mkdir(parents=True)
    acceptance = release / "acceptance_v1.csv"
    response = release / "acceptance_phi_response_v1.csv"
    acceptance.write_text("channel,acceptance\neta_pi0,0.5\n", encoding="utf-8")
    response.write_bytes(response_fixture.path.read_bytes())
    qa = {
        "schema_version": 1,
        "acceptance_release_id": release.name,
        "producer_commit": "a" * 40,
        "valid": True,
        "acceptance_csv_sha256": sha256(acceptance),
        "acceptance_phi_response_csv_sha256": sha256(response),
        "phi_response_schema_path": response_fixture.config.phi_response_schema_path,
        "phi_response_schema_sha256": response_fixture.config.phi_response_schema_sha256,
        "phi_response_schema_approval_id": response_fixture.config.phi_response_schema_approval_id,
        "gate0_handoff_sha256": "d" * 64,
        "n2_reconstruction_sha256": "e" * 64,
        "input_sha256": "b" * 64,
        "config_sha256": "c" * 64,
        "count_checks": {"valid": True},
        "matrix_checks": {"valid": True},
        "weighted_covariance_checks": {"valid": True},
        "closure": {"valid": True},
    }
    (release / "acceptance_qa.json").write_text(json.dumps(qa), encoding="utf-8")
    return release


@pytest.fixture
def approved_config(response_fixture, valid_handoff):
    return dataclasses.replace(
        response_fixture.config,
        acceptance_qa_sha256=sha256(valid_handoff / "acceptance_qa.json"),
    )


def config_for_current_qa(config, release: Path):
    return dataclasses.replace(
        config,
        acceptance_qa_sha256=sha256(release / "acceptance_qa.json"),
    )


def rewrite_qa(release: Path, mutate) -> None:
    qa_path = release / "acceptance_qa.json"
    qa = json.loads(qa_path.read_text(encoding="utf-8"))
    mutate(qa)
    qa_path.write_text(json.dumps(qa), encoding="utf-8")


def rewrite_triplet_and_internal_hashes(release: Path) -> None:
    acceptance = release / "acceptance_v1.csv"
    response = release / "acceptance_phi_response_v1.csv"
    acceptance.write_text(
        "channel,acceptance\neta_pi0,0.625\n", encoding="utf-8"
    )
    response.write_bytes(response.read_bytes() + b"\n")

    def refresh(qa):
        qa["acceptance_csv_sha256"] = sha256(acceptance)
        qa["acceptance_phi_response_csv_sha256"] = sha256(response)

    rewrite_qa(release, refresh)


def test_accepts_exact_immutable_triplet_with_transitive_authorities(
    valid_handoff, approved_config, repo
):
    validated = validate_acceptance_handoff(
        valid_handoff,
        repo,
        config=approved_config,
        expected_gate0_sha256="d" * 64,
    )

    assert validated.release_id == "n3-test"
    assert validated.acceptance_csv == valid_handoff / "acceptance_v1.csv"
    assert validated.phi_response_csv == valid_handoff / "acceptance_phi_response_v1.csv"
    assert validated.qa_json == valid_handoff / "acceptance_qa.json"
    assert validated.n2_reconstruction_sha256 == "e" * 64
    assert validated.schema_path == repo / approved_config.phi_response_schema_path
    assert validated.schema_sha256 == approved_config.phi_response_schema_sha256
    assert validated.approval_id == approved_config.phi_response_schema_approval_id
    assert validated.response.source_sha256 == validated.phi_response_sha256
    assert validated.response.input_sha256 == "b" * 64
    assert validated.response.config_sha256 == "c" * 64


def test_handoff_requires_config_pinned_qa_digest(
    valid_handoff, approved_config, repo
):
    unpinned = dataclasses.replace(
        approved_config, acceptance_qa_sha256="f" * 64
    )
    with pytest.raises(PolarizationContractError, match="QA SHA-256"):
        validate_acceptance_handoff(valid_handoff, repo, config=unpinned)


def test_handoff_rejects_wholesale_self_consistent_replacement(
    valid_handoff, approved_config, repo
):
    rewrite_triplet_and_internal_hashes(valid_handoff)
    with pytest.raises(PolarizationContractError, match="QA SHA-256"):
        validate_acceptance_handoff(valid_handoff, repo, config=approved_config)


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda release: (release / "acceptance_phi_response_v1.csv").unlink(), "exactly three"),
        (lambda release: (release / "legacy.csv").write_text("legacy"), "exactly three"),
        (
            lambda release: (release / "acceptance_phi_response_v1.csv").write_text("tampered"),
            "response.*SHA-256",
        ),
    ],
)
def test_rejects_incomplete_extra_or_tampered_publication(
    valid_handoff, approved_config, repo, mutate, message
):
    mutate(valid_handoff)
    with pytest.raises(PolarizationContractError, match=message):
        validate_acceptance_handoff(valid_handoff, repo, config=approved_config)


def test_rejects_legacy_root_destination(repo, approved_config):
    legacy = repo / "results/physics/normalization"
    with pytest.raises(PolarizationContractError, match="immutable handoff directory"):
        validate_acceptance_handoff(legacy, repo, config=approved_config)


@pytest.mark.parametrize(
    "field,value,message",
    [
        ("phi_response_schema_path", "config/schemas/substituted.json", "schema path"),
        ("phi_response_schema_sha256", "f" * 64, "schema SHA-256"),
        ("phi_response_schema_approval_id", "other-approval", "schema approval ID"),
    ],
)
def test_rejects_qa_schema_authority_not_equal_to_config(
    valid_handoff, approved_config, repo, field, value, message
):
    rewrite_qa(valid_handoff, lambda qa: qa.__setitem__(field, value))
    anchored = config_for_current_qa(approved_config, valid_handoff)
    with pytest.raises(PolarizationContractError, match=message):
        validate_acceptance_handoff(valid_handoff, repo, config=anchored)


@pytest.mark.parametrize(
    "check",
    ["count_checks", "matrix_checks", "weighted_covariance_checks", "closure"],
)
def test_rejects_any_invalid_or_missing_required_qa_check(
    valid_handoff, approved_config, repo, check
):
    rewrite_qa(valid_handoff, lambda qa: qa.__setitem__(check, {"valid": False}))
    anchored = config_for_current_qa(approved_config, valid_handoff)
    with pytest.raises(PolarizationContractError, match=check):
        validate_acceptance_handoff(valid_handoff, repo, config=anchored)


@pytest.mark.parametrize("field", ["input_sha256", "config_sha256"])
def test_rejects_response_producer_hash_not_bound_to_qa(
    valid_handoff, approved_config, repo, field
):
    rewrite_qa(valid_handoff, lambda qa: qa.__setitem__(field, "f" * 64))
    anchored = config_for_current_qa(approved_config, valid_handoff)
    with pytest.raises(PolarizationContractError, match=f"response {field}"):
        validate_acceptance_handoff(valid_handoff, repo, config=anchored)


def test_rejects_diagnostic_response_with_any_invalid_true_cell(
    valid_handoff, approved_config, repo
):
    response = valid_handoff / "acceptance_phi_response_v1.csv"
    with response.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
        fields = tuple(rows[0])
    first = rows[0]
    for row in rows:
        if (
            row["orientation"] == first["orientation"]
            and row["true_mass_bin"] == first["true_mass_bin"]
            and row["true_phi_bin"] == first["true_phi_bin"]
        ):
            row["validity_mask"] = "invalid_nonphysical_weights"
    with response.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    rewrite_qa(
        valid_handoff,
        lambda qa: qa.__setitem__(
            "acceptance_phi_response_csv_sha256", sha256(response)
        ),
    )
    anchored = config_for_current_qa(approved_config, valid_handoff)
    with pytest.raises(PolarizationContractError, match="invalid true-cell"):
        validate_acceptance_handoff(valid_handoff, repo, config=anchored)


def test_rejects_release_id_and_gate0_mismatch(
    valid_handoff, approved_config, repo
):
    mismatched_release = dataclasses.replace(
        approved_config, acceptance_release_id="different-release"
    )
    with pytest.raises(PolarizationContractError, match="release ID"):
        validate_acceptance_handoff(
            valid_handoff, repo, config=mismatched_release
        )

    mismatched_directory = dataclasses.replace(
        approved_config,
        acceptance_handoff_directory=(
            "results/physics/normalization/handoffs/different-release"
        ),
    )
    with pytest.raises(PolarizationContractError, match="directory"):
        validate_acceptance_handoff(
            valid_handoff, repo, config=mismatched_directory
        )

    with pytest.raises(PolarizationContractError, match="Gate 0"):
        validate_acceptance_handoff(
            valid_handoff,
            repo,
            config=approved_config,
            expected_gate0_sha256="a" * 64,
        )
