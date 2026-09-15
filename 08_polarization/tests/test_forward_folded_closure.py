from __future__ import annotations

from dataclasses import replace
import importlib.util
from pathlib import Path

import numpy as np
import pytest

from contracts import PolarizationContractError


def _sigma_fit_test_module():
    path = Path(__file__).with_name("test_sigma_fit.py")
    spec = importlib.util.spec_from_file_location("closure_sigma_fit_tests", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def closure_problem():
    return _sigma_fit_test_module().asimov_problem.__wrapped__()


def test_forward_folded_closure_uses_full_s4_layout_and_is_deterministic(
    closure_problem,
):
    from forward_folded_closure import run_forward_folded_closure

    kwargs = {
        **closure_problem,
        "seed": 1701,
        "experiments": 8,
        "bias_threshold": 1.0,
        "pull_mean_threshold": 2.0,
        "pull_width_tolerance": 2.0,
    }
    first = run_forward_folded_closure(**kwargs)
    second = run_forward_folded_closure(**kwargs)

    assert first.bin_keys == second.bin_keys
    assert len(first.bin_keys) == 2
    assert first.experiments == 8
    assert first.seed == 1701
    assert first.fitted_sigma_vectors.shape == (8, 2)
    for name in (
        "injected_sigma",
        "fitted_mean",
        "bias",
        "pull_mean",
        "pull_width",
        "sign_swapped_sigma",
    ):
        actual = getattr(first, name)
        assert actual.shape == (2,)
        np.testing.assert_array_equal(actual, getattr(second, name))
        with pytest.raises(ValueError):
            actual[0] = 9.0
    np.testing.assert_array_equal(
        first.fitted_sigma_vectors, second.fitted_sigma_vectors
    )
    np.testing.assert_allclose(
        first.sign_swapped_sigma, -first.injected_sigma, atol=5e-5
    )
    assert first.sign_check_passed
    assert first.valid


def test_forward_folded_closure_changes_when_authenticated_response_changes(
    closure_problem,
):
    from forward_folded_closure import run_forward_folded_closure

    nominal = run_forward_folded_closure(
        **closure_problem,
        seed=7,
        experiments=3,
        bias_threshold=1.0,
        pull_mean_threshold=5.0,
        pull_width_tolerance=5.0,
    )
    response = closure_problem["response"]
    matrices = dict(response.matrices)
    key = response.keys[0]
    matrices[key, "parallel"] = matrices[key, "parallel"] * 0.97
    changed = replace(response, matrices=type(response.matrices)(matrices))
    changed_problem = dict(closure_problem)
    changed_problem["response"] = changed
    _sigma_fit_test_module()._replace_injected_sigma(
        changed_problem, [-0.35, 0.20]
    )

    altered = run_forward_folded_closure(
        counts=changed_problem["counts"],
        response=changed,
        config=closure_problem["config"],
        seed=7,
        experiments=3,
        bias_threshold=1.0,
        pull_mean_threshold=5.0,
        pull_width_tolerance=5.0,
    )

    assert not np.array_equal(
        nominal.fitted_sigma_vectors, altered.fitted_sigma_vectors
    )


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("experiments", 1, "experiments"),
        ("seed", -1, "seed"),
        ("bias_threshold", -1.0, "threshold"),
    ],
)
def test_forward_folded_closure_rejects_invalid_controls(
    closure_problem, field, value, match
):
    from forward_folded_closure import run_forward_folded_closure

    kwargs = {
        **closure_problem,
        "seed": 1,
        "experiments": 2,
        "bias_threshold": 1.0,
        "pull_mean_threshold": 1.0,
        "pull_width_tolerance": 1.0,
    }
    kwargs[field] = value
    with pytest.raises(PolarizationContractError, match=match):
        run_forward_folded_closure(**kwargs)
