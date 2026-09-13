from __future__ import annotations

import json
import hashlib
from pathlib import Path

import pytest

from contracts import PolarizationContractError
from figure4_config import load_figure4_config


def valid_payload():
    return {
        "schema_version": 1,
        "analysis_version": "polarization-v1",
        "status": "approved",
        "blocked_reasons": [],
        "gate0_handoff": "results/observable_runs/HANDOFF.json",
        "acceptance": {"status": "approved", "handoff_parent": "results/physics/normalization/handoffs", "release_id": "fixture", "handoff_directory": "results/physics/normalization/handoffs/fixture", "required_files": ["acceptance_v1.csv", "acceptance_phi_response_v1.csv", "acceptance_qa.json"], "acceptance_qa_sha256": "a" * 64, "phi_response_schema_status": "approved", "phi_response_schema_path": "config/schemas/acceptance_phi_response_v1.schema.json", "phi_response_schema_sha256": None, "phi_response_schema_approval_id": "N3-MASS-PHI-RESPONSE-V1-2026-09-13", "phi_response_schema_reviewers": ["persona-1", "persona-2"]},
        "state_mapping": {"status": "approved", "source": None, "intervals": []},
        "compton_polarization": {"status": "approved", "sources": [], "periods": []},
        "angle": {"observable": "reaction_plane_phi", "range_radians": [0.0, 3.141592653589793], "period_radians": 3.141592653589793, "degenerate_plane_policy": "invalid"},
        "sign_convention": {
            "status": "approved",
            "approval_id": "GRAAL-SIGN-001",
            "reviewers": ["persona-1", "persona-2"],
            "model": "mu = fixture",
            "orientation_signs": {"parallel": -1, "perpendicular": 1},
        },
        "figure4_comparison": {
            "energy_edges_gev": [1.1, 1.2, 1.3, 1.4, 1.5],
            "mass_bins": 10,
            "phi_bins": 12,
            "target": "P",
            "tree": "reco_eta_pi0_chi2",
            "vectors": "kinematic_fit",
            "content_policy": "framework_results_only_no_published_points_curves_or_digitization",
        },
        "closure": {"random_seed": 1701, "bias_absolute_max": 0.02, "pull_mean_absolute_max": 0.2, "pull_width_tolerance": 0.2, "require_sign_check": True},
        "response_validation": {"minimum_generated_effective_events_per_true_phi": 1.0, "probability_absolute_tolerance": 1e-12, "uncertainty_absolute_tolerance": 1e-12, "uncertainty_relative_tolerance": 1e-9, "covariance_eigenvalue_absolute_tolerance": 1e-12, "finite_difference_relative_step": 1e-4, "finite_difference_absolute_step": 1e-6, "replay_absolute_tolerance": 1e-10, "replay_relative_tolerance": 1e-8},
        "bootstrap": {"replicas": 32, "algorithm_version": "poisson1-sha256-v1", "seed": 1701, "maximum_failed_fraction": 0.05, "hessian_diagonal_ratio_min": 0.5, "hessian_diagonal_ratio_max": 2.0},
        "release_qa_thresholds": {"status": "approved", "approval_id": "fixture-release", "reviewers": ["persona-1", "persona-2"], "minimum_events_per_bin": 1, "maximum_deviance_per_ndof": 2.0, "closure_bias_absolute_max": 0.02, "closure_pull_mean_absolute_max": 0.2, "closure_pull_width_tolerance": 0.2, "minimum_systematic_sources": 1, "systematic_combination_policy": "independent_sources_quadrature"},
    }


def write_config(tmp_path: Path, payload: dict[str, object]) -> Path:
    root = tmp_path / "repo"
    schema = root / "config/schemas/acceptance_phi_response_v1.schema.json"
    schema.parent.mkdir(parents=True, exist_ok=True)
    schema.write_text('{"schema_version":1}\n')
    handoff = root / "results/observable_runs/HANDOFF.json"
    handoff.parent.mkdir(parents=True, exist_ok=True)
    handoff.write_text('{"schema_version":1}\n')
    acceptance = payload["acceptance"]
    acceptance["phi_response_schema_sha256"] = hashlib.sha256(schema.read_bytes()).hexdigest()
    path = root / "config/physics/polarization_v1.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))
    return path


def test_load_figure4_config_requires_approved_sign_and_exact_layout(tmp_path):
    path = write_config(tmp_path, valid_payload())
    config = load_figure4_config(path)
    assert config.energy_ranges == (
        (1.1, 1.2), (1.2, 1.3), (1.3, 1.4), (1.4, 1.5)
    )
    assert config.mass_bins == 10
    assert config.phi_bins == 12
    assert config.orientation_signs == {"parallel": -1, "perpendicular": 1}


def test_load_figure4_config_rejects_unapproved_sign_or_wrong_grid(tmp_path):
    payload = valid_payload()
    payload["sign_convention"]["status"] = "pending_two_reviewer_approval"
    payload["sign_convention"]["approval_id"] = None
    payload["sign_convention"]["reviewers"] = []
    payload["sign_convention"]["orientation_signs"] = {}
    path = write_config(tmp_path, payload)
    with pytest.raises(PolarizationContractError, match="sign convention"):
        load_figure4_config(path)

    payload = valid_payload()
    payload["figure4_comparison"]["energy_edges_gev"] = [1.1, 1.3, 1.5]
    path = write_config(tmp_path, payload)
    with pytest.raises(PolarizationContractError, match="four energy bins"):
        load_figure4_config(path)

    payload = valid_payload()
    payload["sign_convention"]["orientation_signs"]["perpendicular"] = True
    path = write_config(tmp_path, payload)
    with pytest.raises(PolarizationContractError, match="opposite signs"):
        load_figure4_config(path)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("approval_id", ""),
        ("reviewers", ["persona-1"]),
        ("reviewers", ["persona-1", " persona-1 "]),
    ],
)
def test_load_figure4_config_requires_documented_two_reviewer_approval(
    tmp_path, field, value
):
    payload = valid_payload()
    payload["sign_convention"][field] = value
    path = write_config(tmp_path, payload)

    with pytest.raises(PolarizationContractError, match="two-reviewer approval"):
        load_figure4_config(path)
