from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from acceptance_handoff import validate_acceptance_handoff
from contracts import PolarizationContractError


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_handoff(repo: Path, release_id: str = "acceptance-test-v1") -> Path:
    release = (
        repo
        / "results/physics/normalization/handoffs"
        / release_id
    )
    release.mkdir(parents=True)
    acceptance = release / "acceptance_v1.csv"
    response = release / "acceptance_phi_response_v1.csv"
    acceptance.write_text("channel,acceptance\neta_pi0,0.5\n", encoding="utf-8")
    response.write_text(
        "true_phi_low,true_phi_high,reco_phi_low,reco_phi_high,response\n"
        "0.0,0.5,0.0,0.5,0.9\n",
        encoding="utf-8",
    )
    qa = {
        "schema_version": 1,
        "acceptance_release_id": release_id,
        "producer_commit": "a" * 40,
        "valid": True,
        "acceptance_csv_sha256": sha256(acceptance),
        "acceptance_phi_response_csv_sha256": sha256(response),
        "phi_response_schema_approval_id": "fixture-phi-response",
        "gate0_handoff_sha256": "b" * 64,
        "n2_reconstruction_sha256": "c" * 64,
        "count_checks": {"valid": True},
        "closure": {"valid": True},
    }
    (release / "acceptance_qa.json").write_text(json.dumps(qa), encoding="utf-8")
    return release


def test_accepts_exact_immutable_triplet_with_cross_hashes(tmp_path):
    release = write_handoff(tmp_path)

    validated = validate_acceptance_handoff(
        release,
        tmp_path,
        expected_gate0_sha256="b" * 64,
    )

    assert validated.release_id == "acceptance-test-v1"
    assert validated.acceptance_csv == release / "acceptance_v1.csv"
    assert validated.phi_response_csv == release / "acceptance_phi_response_v1.csv"
    assert validated.qa_json == release / "acceptance_qa.json"
    assert validated.n2_reconstruction_sha256 == "c" * 64
    assert validated.phi_response_schema_approval_id == "fixture-phi-response"


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
def test_rejects_incomplete_extra_or_tampered_publication(tmp_path, mutate, message):
    release = write_handoff(tmp_path)
    mutate(release)

    with pytest.raises(PolarizationContractError, match=message):
        validate_acceptance_handoff(release, tmp_path)


def test_rejects_legacy_root_destination(tmp_path):
    legacy = tmp_path / "results/physics/normalization"
    legacy.mkdir(parents=True)

    with pytest.raises(PolarizationContractError, match="immutable handoff directory"):
        validate_acceptance_handoff(legacy, tmp_path)


def test_rejects_missing_phi_response_schema_approval_id(tmp_path):
    release = write_handoff(tmp_path)
    qa_path = release / "acceptance_qa.json"
    qa = json.loads(qa_path.read_text(encoding="utf-8"))
    qa.pop("phi_response_schema_approval_id")
    qa_path.write_text(json.dumps(qa), encoding="utf-8")

    with pytest.raises(PolarizationContractError, match="schema approval ID"):
        validate_acceptance_handoff(release, tmp_path)


def test_rejects_release_id_and_gate0_mismatch(tmp_path):
    release = write_handoff(tmp_path)
    qa_path = release / "acceptance_qa.json"
    qa = json.loads(qa_path.read_text(encoding="utf-8"))
    qa["acceptance_release_id"] = "different-release"
    qa_path.write_text(json.dumps(qa), encoding="utf-8")

    with pytest.raises(PolarizationContractError, match="release ID"):
        validate_acceptance_handoff(release, tmp_path)

    qa["acceptance_release_id"] = release.name
    qa_path.write_text(json.dumps(qa), encoding="utf-8")
    with pytest.raises(PolarizationContractError, match="Gate 0"):
        validate_acceptance_handoff(
            release,
            tmp_path,
            expected_gate0_sha256="d" * 64,
        )
