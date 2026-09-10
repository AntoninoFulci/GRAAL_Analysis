from __future__ import annotations

import pytest

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
