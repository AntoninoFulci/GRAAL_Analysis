from __future__ import annotations

import json

import pytest

import closure_injected_sigma
from closure_injected_sigma import run_injected_closure
from contracts import PolarizationContractError


@pytest.mark.parametrize("injected", [-0.6, -0.2, 0.0, 0.3, 0.7])
def test_injected_closure_recovers_sigma_and_passes_sign_check(injected):
    closure = run_injected_closure(
        injected,
        seed=17,
        experiments=30,
        bias_threshold=0.025,
        pull_mean_threshold=0.35,
        pull_width_tolerance=0.35,
    )
    assert abs(closure.bias) <= closure.bias_threshold
    assert abs(closure.pull_mean) <= closure.pull_mean_threshold
    assert abs(closure.pull_width - 1.0) <= closure.pull_width_tolerance
    assert closure.sign_check_passed
    assert closure.valid


def test_closure_is_deterministic_for_fixed_seed():
    first = run_injected_closure(0.4, seed=123, experiments=12)
    second = run_injected_closure(0.4, seed=123, experiments=12)
    assert first == second


@pytest.mark.parametrize("injected", [-1.0, 1.0])
def test_closure_handles_physical_boundaries(injected):
    closure = run_injected_closure(
        injected,
        seed=17,
        experiments=30,
        bias_threshold=0.025,
        pull_mean_threshold=0.0,
        pull_width_tolerance=0.0,
    )
    assert abs(closure.bias) <= closure.bias_threshold
    assert closure.sign_check_passed
    assert closure.valid


def test_closure_design_uses_production_angle_and_state_mapping(monkeypatch):
    angle_calls = 0
    mapping_calls = 0
    real_angle = closure_injected_sigma.reaction_plane_phi
    real_mapping = closure_injected_sigma.resolve_orientation

    def tracked_angle(*args, **kwargs):
        nonlocal angle_calls
        angle_calls += 1
        return real_angle(*args, **kwargs)

    def tracked_mapping(*args, **kwargs):
        nonlocal mapping_calls
        mapping_calls += 1
        return real_mapping(*args, **kwargs)

    monkeypatch.setattr(closure_injected_sigma, "reaction_plane_phi", tracked_angle)
    monkeypatch.setattr(closure_injected_sigma, "resolve_orientation", tracked_mapping)

    design, expected = closure_injected_sigma._closure_design(0.3)

    assert angle_calls == 32
    assert mapping_calls == 32
    assert expected.shape == (32,)
    assert set(design["orientation_sign"]) == {-1, 1}


@pytest.mark.parametrize(
    "injected,experiments,match",
    [
        (1.1, 20, "injected Sigma"),
        (0.2, 1, "experiments"),
    ],
)
def test_closure_rejects_invalid_controls(injected, experiments, match):
    with pytest.raises(PolarizationContractError, match=match):
        run_injected_closure(injected, experiments=experiments)


def test_legacy_scalar_closure_cli_cannot_report_success_for_blocked_config(
    tmp_path, monkeypatch
):
    config = tmp_path / "blocked.json"
    config.write_text(
        json.dumps(
            {
                "status": "blocked",
                "blocked_reasons": ["release authorities absent"],
                "closure": {
                    "random_seed": 1701,
                    "bias_absolute_max": 1.0,
                    "pull_mean_absolute_max": 1.0,
                    "pull_width_tolerance": 1.0,
                },
            }
        ),
        encoding="utf-8",
    )
    called = False

    def diagnostic(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("blocked config must fail before scalar diagnostic")

    monkeypatch.setattr(closure_injected_sigma, "run_injected_closure", diagnostic)

    assert closure_injected_sigma.main(
        ["--config", str(config), "--injected", "0"]
    ) == 1
    assert not called
