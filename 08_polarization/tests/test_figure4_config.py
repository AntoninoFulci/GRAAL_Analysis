from __future__ import annotations

import json

import pytest

from contracts import PolarizationContractError
from figure4_config import load_figure4_config


def valid_payload():
    return {
        "sign_convention": {
            "status": "approved",
            "approval_id": "GRAAL-SIGN-001",
            "reviewers": ["persona-1", "persona-2"],
            "orientation_signs": {"parallel": -1, "perpendicular": 1},
        },
        "figure4_comparison": {
            "energy_edges_gev": [1.1, 1.2, 1.3, 1.4, 1.5],
            "mass_bins": 10,
            "phi_bins": 12,
            "target": "P",
            "tree": "reco_eta_pi0_chi2",
            "vectors": "kinematic_fit",
        },
    }


def test_load_figure4_config_requires_approved_sign_and_exact_layout(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(valid_payload()))
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
    path = tmp_path / "config.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(PolarizationContractError, match="sign convention"):
        load_figure4_config(path)

    payload = valid_payload()
    payload["figure4_comparison"]["energy_edges_gev"] = [1.1, 1.3, 1.5]
    path.write_text(json.dumps(payload))
    with pytest.raises(PolarizationContractError, match="four energy bins"):
        load_figure4_config(path)

    payload = valid_payload()
    payload["sign_convention"]["orientation_signs"]["perpendicular"] = True
    path.write_text(json.dumps(payload))
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
    path = tmp_path / "config.json"
    path.write_text(json.dumps(payload))

    with pytest.raises(PolarizationContractError, match="two-reviewer approval"):
        load_figure4_config(path)
