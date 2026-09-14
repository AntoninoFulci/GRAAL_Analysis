from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from analysis_config import load_analysis_config
from contracts import PolarizationContractError


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _payload(schema_digest: str, *, status: str = "blocked") -> dict[str, object]:
    approved = status == "approved"
    return {
        "schema_version": 1,
        "analysis_version": "polarization-v1",
        "status": status,
        "blocked_reasons": [] if approved else ["fixture release authorities are pending"],
        "gate0_handoff": "results/observable_runs/HANDOFF.json",
        "acceptance": {
            "status": "approved" if approved else "blocked",
            "handoff_parent": "results/physics/normalization/handoffs",
            "release_id": "acceptance-fixture-v1" if approved else None,
            "handoff_directory": "results/physics/normalization/handoffs/acceptance-fixture-v1" if approved else None,
            "required_files": ["acceptance_v1.csv", "acceptance_phi_response_v1.csv", "acceptance_qa.json"],
            "acceptance_qa_sha256": "a" * 64 if approved else None,
            "phi_response_schema_status": "approved",
            "phi_response_schema_path": "config/schemas/acceptance_phi_response_v1.schema.json",
            "phi_response_schema_sha256": schema_digest,
            "phi_response_schema_approval_id": "N3-MASS-PHI-RESPONSE-V1-2026-09-15",
            "phi_response_schema_reviewers": ["reviewer-one", "reviewer-two"],
        },
        "state_mapping": {"status": "approved" if approved else "blocked", "source": {"fixture": "state"} if approved else None, "intervals": []},
        "compton_polarization": {"status": "approved" if approved else "blocked", "sources": [], "periods": []},
        "angle": {"observable": "reaction_plane_phi", "range_radians": [0.0, 3.141592653589793], "period_radians": 3.141592653589793, "degenerate_plane_policy": "invalid"},
        "sign_convention": {
            "status": "approved" if approved else "pending_two_reviewer_approval",
            "approval_id": "fixture-sign" if approved else None,
            "reviewers": ["reviewer-one", "reviewer-two"] if approved else [],
            "model": "mu = fixture",
            "orientation_signs": {"parallel": -1, "perpendicular": 1} if approved else {},
        },
        "figure4_comparison": {"energy_edges_gev": [1.1, 1.2, 1.3, 1.4, 1.5], "mass_bins": 10, "phi_bins": 12, "target": "P", "tree": "reco_eta_pi0_chi2", "vectors": "kinematic_fit", "content_policy": "framework_results_only_no_published_points_curves_or_digitization"},
        "closure": {"random_seed": 1701, "bias_absolute_max": 0.02, "pull_mean_absolute_max": 0.2, "pull_width_tolerance": 0.2, "require_sign_check": True},
        "response_validation": {
            "minimum_generated_effective_events_per_true_phi": 100.0 if approved else None,
            "probability_absolute_tolerance": 1e-12 if approved else None,
            "uncertainty_absolute_tolerance": 1e-12 if approved else None,
            "uncertainty_relative_tolerance": 1e-9 if approved else None,
            "covariance_eigenvalue_absolute_tolerance": 1e-12 if approved else None,
            "finite_difference_relative_step": 1e-4 if approved else None,
            "finite_difference_absolute_step": 1e-6 if approved else None,
            "replay_absolute_tolerance": 1e-10 if approved else None,
            "replay_relative_tolerance": 1e-8 if approved else None,
        },
        "bootstrap": {
            "replicas": 32 if approved else None,
            "algorithm_version": "poisson1-sha256-v1",
            "seed": 1701 if approved else None,
            "maximum_failed_fraction": 0.05 if approved else None,
            "hessian_diagonal_ratio_min": 0.5 if approved else None,
            "hessian_diagonal_ratio_max": 2.0 if approved else None,
        },
        "release_qa_thresholds": {
            "status": "approved" if approved else "pending_owner_approval",
            "approval_id": "fixture-release" if approved else None,
            "reviewers": ["reviewer-one", "reviewer-two"] if approved else [],
            "minimum_events_per_bin": 10 if approved else None,
            "maximum_deviance_per_ndof": 2.0 if approved else None,
            "closure_bias_absolute_max": 0.02 if approved else None,
            "closure_pull_mean_absolute_max": 0.2 if approved else None,
            "closure_pull_width_tolerance": 0.2 if approved else None,
            "minimum_systematic_sources": 1 if approved else None,
            "systematic_combination_policy": "independent_sources_quadrature" if approved else None,
        },
    }


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    schema = root / "config/schemas/acceptance_phi_response_v1.schema.json"
    schema.parent.mkdir(parents=True)
    schema.write_text('{"schema_version":1}\n', encoding="utf-8")
    handoff = root / "results/observable_runs/HANDOFF.json"
    handoff.parent.mkdir(parents=True)
    handoff.write_text('{"schema_version":1}\n', encoding="utf-8")
    return root


@pytest.fixture
def valid_config(repo):
    path = repo / "config/physics/polarization_v1.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(_payload(_digest(repo / "config/schemas/acceptance_phi_response_v1.schema.json"))), encoding="utf-8")
    return path


def test_blocked_config_validates_complete_release_sections(valid_config, repo):
    loaded = load_analysis_config(valid_config, repo, require_approved=False)
    assert loaded.status == "blocked"
    assert loaded.bootstrap.algorithm_version == "poisson1-sha256-v1"
    assert loaded.bootstrap.replicas is None
    assert loaded.response_validation.replay_relative_tolerance is None
    assert loaded.phi_response_schema_approval_id == (
        "N3-MASS-PHI-RESPONSE-V1-2026-09-15"
    )
    assert loaded.phi_response_schema_reviewers == ("reviewer-one", "reviewer-two")


def test_blocked_config_cannot_be_used_as_release(valid_config, repo):
    with pytest.raises(PolarizationContractError, match="approved"):
        load_analysis_config(valid_config, repo, require_approved=True)


def test_approved_acceptance_requires_independently_approved_schema(valid_config, repo):
    payload = _payload(
        _digest(repo / "config/schemas/acceptance_phi_response_v1.schema.json"),
        status="approved",
    )
    payload["acceptance"].update(
        phi_response_schema_status="pending_joint_approval",
        phi_response_schema_path=None,
        phi_response_schema_sha256=None,
        phi_response_schema_approval_id=None,
        phi_response_schema_reviewers=[],
    )
    valid_config.write_text(json.dumps(payload))
    with pytest.raises(PolarizationContractError, match="schema approval"):
        load_analysis_config(valid_config, repo, require_approved=False)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("phi_response_schema_sha256", "0" * 64),
        ("phi_response_schema_approval_id", "other"),
        ("phi_response_schema_reviewers", ["only-one"]),
    ],
)
def test_blocked_release_still_authenticates_approved_schema(
    valid_config, repo, field, value
):
    payload = json.loads(valid_config.read_text())
    payload["acceptance"][field] = value
    valid_config.write_text(json.dumps(payload))
    with pytest.raises(PolarizationContractError, match="schema|reviewer"):
        load_analysis_config(valid_config, repo, require_approved=False)


def test_release_config_requires_exact_approved_identity(valid_config, repo):
    payload = json.loads(valid_config.read_text())
    payload = _payload(_digest(repo / "config/schemas/acceptance_phi_response_v1.schema.json"), status="approved")
    payload["acceptance"]["acceptance_qa_sha256"] = "a" * 64
    valid_config.write_text(json.dumps(payload))
    loaded = load_analysis_config(valid_config, repo, require_approved=True)
    assert loaded.acceptance_qa_sha256 == "a" * 64


def test_release_config_retains_validated_qa_policy(valid_config, repo):
    payload = _payload(
        _digest(repo / "config/schemas/acceptance_phi_response_v1.schema.json"),
        status="approved",
    )
    valid_config.write_text(json.dumps(payload))

    loaded = load_analysis_config(valid_config, repo, require_approved=True)

    assert loaded.release_qa.status == "approved"
    assert loaded.release_qa.reviewers == ("reviewer-one", "reviewer-two")
    assert loaded.release_qa.minimum_events_per_bin == 10
    assert loaded.release_qa.maximum_deviance_per_ndof == 2.0
    assert loaded.release_qa.systematic_combination_policy == (
        "independent_sources_quadrature"
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("phi_response_schema_path", "config/schemas/substituted.schema.json"),
        ("phi_response_schema_approval_id", "other-approval"),
    ],
)
def test_release_config_rejects_substituted_schema_authority(valid_config, repo, field, value):
    schema = repo / "config/schemas/acceptance_phi_response_v1.schema.json"
    substituted = repo / "config/schemas/substituted.schema.json"
    substituted.write_bytes(schema.read_bytes())
    payload = _payload(_digest(schema), status="approved")
    payload["acceptance"][field] = value
    valid_config.write_text(json.dumps(payload))
    with pytest.raises(PolarizationContractError, match="phi-response schema (path|approval ID)"):
        load_analysis_config(valid_config, repo, require_approved=True)


@pytest.mark.parametrize("mutation", ["missing", "symlink", "non_regular"])
@pytest.mark.parametrize("require_approved", [False, True])
def test_approved_config_requires_regular_gate0_handoff(
    valid_config, repo, mutation, require_approved
):
    handoff = repo / "results/observable_runs/HANDOFF.json"
    payload = _payload(
        _digest(repo / "config/schemas/acceptance_phi_response_v1.schema.json"),
        status="approved",
    )
    if mutation == "missing":
        handoff.unlink()
    elif mutation == "symlink":
        target = repo / "results/observable_runs/HANDOFF-target.json"
        target.write_text('{"schema_version":1}\n', encoding="utf-8")
        handoff.unlink()
        handoff.symlink_to(target)
    else:
        handoff.unlink()
        handoff.mkdir()
    valid_config.write_text(json.dumps(payload))
    with pytest.raises(PolarizationContractError):
        load_analysis_config(valid_config, repo, require_approved=require_approved)


@pytest.mark.parametrize("field,value", [("schema_version", 2), ("analysis_version", "other"), ("status", "blocked"), ("blocked_reasons", ["x"])])
def test_release_config_rejects_wrong_identity(valid_config, repo, field, value):
    payload = _payload(_digest(repo / "config/schemas/acceptance_phi_response_v1.schema.json"), status="approved")
    payload[field] = value
    valid_config.write_text(json.dumps(payload))
    with pytest.raises(PolarizationContractError):
        load_analysis_config(valid_config, repo, require_approved=True)


def test_release_config_rejects_boolean_schema_version(valid_config, repo):
    payload = _payload(
        _digest(repo / "config/schemas/acceptance_phi_response_v1.schema.json"),
        status="approved",
    )
    payload["schema_version"] = True
    valid_config.write_text(json.dumps(payload))
    with pytest.raises(PolarizationContractError, match="schema_version"):
        load_analysis_config(valid_config, repo, require_approved=True)


@pytest.mark.parametrize("section", ["response_validation", "bootstrap"])
def test_config_requires_exact_release_section_keys(valid_config, repo, section):
    payload = json.loads(valid_config.read_text())
    payload[section].pop(next(iter(payload[section])))
    valid_config.write_text(json.dumps(payload))
    with pytest.raises(PolarizationContractError, match="exactly"):
        load_analysis_config(valid_config, repo, require_approved=False)


def test_config_rejects_nonfinite_approved_threshold(valid_config, repo):
    payload = _payload(_digest(repo / "config/schemas/acceptance_phi_response_v1.schema.json"), status="approved")
    payload["response_validation"]["replay_relative_tolerance"] = float("inf")
    valid_config.write_text(json.dumps(payload))
    with pytest.raises(PolarizationContractError, match="finite"):
        load_analysis_config(valid_config, repo, require_approved=True)


def test_config_rejects_unapproved_release_threshold_status(valid_config, repo):
    payload = _payload(_digest(repo / "config/schemas/acceptance_phi_response_v1.schema.json"), status="approved")
    payload["release_qa_thresholds"]["status"] = "other"
    valid_config.write_text(json.dumps(payload))
    with pytest.raises(PolarizationContractError, match="release_qa_thresholds status"):
        load_analysis_config(valid_config, repo, require_approved=False)


def test_config_rejects_schema_hash_mismatch(valid_config, repo):
    payload = _payload("0" * 64, status="approved")
    valid_config.write_text(json.dumps(payload))
    with pytest.raises(PolarizationContractError, match="schema SHA-256 mismatch"):
        load_analysis_config(valid_config, repo, require_approved=True)
