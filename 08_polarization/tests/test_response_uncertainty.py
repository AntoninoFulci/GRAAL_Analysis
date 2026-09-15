from __future__ import annotations

from dataclasses import replace
import importlib.util
from pathlib import Path
from types import MappingProxyType

import numpy as np
import pytest

from contracts import PolarizationContractError
from azimuth_counts import AzimuthCountTable
from acceptance_handoff import (
    ResponseCovarianceScope,
    _response_covariance_scope,
)
from phi_response import TrueCellKey
import response_uncertainty
from response_uncertainty import (
    _covariance_eigenmodes,
    _perturbed_response,
    _physical_step_limits,
    propagate_response_covariance,
)


def _task5_problem():
    path = Path(__file__).with_name("test_sigma_fit.py")
    spec = importlib.util.spec_from_file_location("task5_sigma_fit_tests", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    problem = module.asimov_problem.__wrapped__()
    problem["covariance_scope"] = _response_covariance_scope(
        {
            "weighted_covariance_checks": {
                "valid": True,
                "shared_mc_across_blocks": False,
                "cross_block_covariance": False,
            }
        },
        problem["config"].acceptance_qa_sha256,
    )
    return problem


def _nominal_fit(problem):
    return response_uncertainty._fit_sigma_forward_folded_core(
        problem["counts"], problem["response"], config=problem["config"]
    )


def _constant_refit_inputs(problem, monkeypatch):
    nominal = _nominal_fit(problem)
    response = problem["response"]
    key = response.keys[0]
    cell = TrueCellKey(key, "parallel", 0)
    direction = np.zeros(16)
    direction[0] = 1.0
    monkeypatch.setattr(
        response_uncertainty,
        "_fit_sigma_forward_folded_core",
        lambda *args, **kwargs: nominal,
    )
    return nominal, response, cell, direction


def test_covariance_eigenmodes_reconstruct_linear_reference():
    covariance = np.array([[0.04, 0.012], [0.012, 0.01]])
    jacobian = np.array([[2.0, -0.5], [0.3, 1.2]])

    modes = _covariance_eigenmodes(covariance, tolerance=1e-14)
    assert [value for value, _ in modes] == sorted(
        (value for value, _ in modes), reverse=True
    )
    assert all(
        vector[np.argmax(np.abs(vector))] > 0.0 for _, vector in modes
    )
    propagated = sum(
        np.outer(jacobian @ vector, jacobian @ vector) * eigenvalue
        for eigenvalue, vector in modes
    )

    np.testing.assert_allclose(
        propagated,
        jacobian @ covariance @ jacobian.T,
        rtol=1e-13,
        atol=1e-15,
    )


def test_covariance_eigenmode_at_cutoff_is_retained():
    tolerance = 1e-6

    modes = _covariance_eigenmodes(
        np.diag([2.0 * tolerance, tolerance, 0.5 * tolerance]),
        tolerance=tolerance,
    )

    assert [value for value, _ in modes] == [2.0 * tolerance, tolerance]


def test_eigenvalue_tolerance_does_not_relax_covariance_symmetry():
    covariance = np.array([[1.0, 1e-3], [0.0, 1.0]])

    with pytest.raises(PolarizationContractError, match="symmetric"):
        _covariance_eigenmodes(covariance, tolerance=0.1)


def test_covariance_symmetry_tolerance_scales_with_tiny_matrix():
    covariance = np.array([[1e-30, 1e-30], [0.0, 1e-30]])

    with pytest.raises(PolarizationContractError, match="symmetric"):
        _covariance_eigenmodes(covariance, tolerance=0.0)


def test_covariance_symmetry_rejects_smallest_subnormal_asymmetry():
    subnormal = np.nextafter(0.0, 1.0)
    covariance = np.array([[subnormal, subnormal], [0.0, subnormal]])

    with pytest.raises(PolarizationContractError, match="symmetric"):
        _covariance_eigenmodes(covariance, tolerance=0.0)


def test_zero_eigenvalues_are_discarded_when_cutoff_is_zero():
    modes = _covariance_eigenmodes(np.diag([1e-8, 0.0]), tolerance=0.0)

    assert len(modes) == 1
    assert modes[0][0] == pytest.approx(1e-8)


@pytest.fixture
def response_problem():
    problem = _task5_problem()
    response = problem["response"]
    key = response.keys[0]
    cell = TrueCellKey(key, "parallel", 0)
    direction = np.zeros(16)
    direction[0] = 1.0 / np.sqrt(2.0)
    direction[1] = -1.0 / np.sqrt(2.0)
    covariance = dict(response.covariance_by_true_cell)
    covariance[cell] = 1e-4 * np.outer(direction, direction)
    problem["response"] = replace(
        response,
        covariance_by_true_cell=MappingProxyType(covariance),
    )
    return problem


def test_propagation_refits_full_sigma_and_is_byte_deterministic(response_problem):
    first = propagate_response_covariance(**response_problem)
    second = propagate_response_covariance(**response_problem)

    assert first.valid
    assert len(first.retained_modes) == 1
    assert len(first.refits) == 1
    assert first.covariance.shape == (2, 2)
    assert first.covariance[0, 1] != 0.0
    assert np.linalg.eigvalsh(first.covariance)[0] >= -1e-18
    assert first.covariance.tobytes() == second.covariance.tobytes()
    assert first.retained_modes == second.retained_modes
    assert first.refits[0].derivative.tobytes() == second.refits[0].derivative.tobytes()
    with pytest.raises(ValueError):
        first.covariance[0, 0] = 1.0


def test_propagation_matches_exact_linear_jacobian_reference(
    response_problem, monkeypatch
):
    nominal = _nominal_fit(response_problem)
    response = response_problem["response"]
    key = response.keys[0]
    base = response.matrix(key, "parallel")[:, 0].copy()
    jacobian = np.vstack(
        (
            np.linspace(-0.4, 0.7, 16),
            np.linspace(0.8, -0.2, 16),
        )
    )
    block = response.covariance_by_true_cell[
        TrueCellKey(key, "parallel", 0)
    ]

    def linear_core(counts, varied, *, config, replica_id=0):
        delta = varied.matrix(key, "parallel")[:, 0] - base
        return replace(nominal, sigma=nominal.sigma + jacobian @ delta)

    monkeypatch.setattr(
        response_uncertainty, "_fit_sigma_forward_folded_core", linear_core
    )

    result = propagate_response_covariance(**response_problem)

    assert result.refits[0].scheme == "central"
    direction = _covariance_eigenmodes(block, tolerance=1e-12)[0][1]
    np.testing.assert_allclose(result.refits[0].derivative, jacobian @ direction)
    np.testing.assert_allclose(
        result.covariance,
        jacobian @ block @ jacobian.T,
        rtol=2e-12,
        atol=1e-16,
    )


def test_physical_boundary_uses_one_sided_refit(response_problem, monkeypatch):
    response = response_problem["response"]
    key = response.keys[0]
    cell = TrueCellKey(key, "parallel", 0)
    direction = np.zeros(16)
    direction[2] = 1.0
    covariance = dict(response.covariance_by_true_cell)
    covariance[cell] = 1e-4 * np.outer(direction, direction)
    response_problem["response"] = replace(
        response,
        covariance_by_true_cell=MappingProxyType(covariance),
    )
    nominal = _nominal_fit(response_problem)
    base = response.matrix(key, "parallel")[:, 0].copy()
    jacobian = np.vstack((np.arange(16), -np.arange(16))) / 100.0

    def linear_core(counts, varied, *, config, replica_id=0):
        delta = varied.matrix(key, "parallel")[:, 0] - base
        return replace(nominal, sigma=nominal.sigma + jacobian @ delta)

    monkeypatch.setattr(
        response_uncertainty, "_fit_sigma_forward_folded_core", linear_core
    )

    result = propagate_response_covariance(**response_problem)

    assert result.refits[0].scheme == "forward"
    assert result.refits[0].lower_sigma is None
    assert result.refits[0].upper_sigma is not None
    np.testing.assert_allclose(result.refits[0].derivative, jacobian @ direction)
    np.testing.assert_allclose(
        result.covariance,
        1e-4 * np.outer(jacobian @ direction, jacobian @ direction),
    )


def test_probability_tolerance_applies_only_to_column_normalization(response_problem):
    response = response_problem["response"]
    key = response.keys[0]
    cell = TrueCellKey(key, "parallel", 0)
    probabilities = response.matrix(key, "parallel")[:, 0]
    direction = np.zeros_like(probabilities)
    direction[0] = 1.0
    tolerance = 2.5e-4
    upper_expected = 1.0 + tolerance - float(np.sum(probabilities))

    lower, upper = _physical_step_limits(
        probabilities, direction, tolerance=tolerance
    )

    assert lower == pytest.approx(-probabilities[0])
    assert upper == pytest.approx(upper_expected)
    endpoint = _perturbed_response(
        response, cell, direction, upper, tolerance=tolerance
    )
    assert np.all(endpoint.matrix(key, "parallel")[:, 0] <= 1.0)
    assert endpoint.matrix(key, "parallel")[:, 0].sum() == pytest.approx(
        1.0 + tolerance
    )
    with pytest.raises(PolarizationContractError, match="physical probability"):
        _perturbed_response(
            response,
            cell,
            direction,
            upper + tolerance,
            tolerance=tolerance,
        )


def test_physical_step_and_perturbation_enforce_individual_probability_bounds(
    response_problem,
):
    response = response_problem["response"]
    key = response.keys[0]
    cell = TrueCellKey(key, "parallel", 0)
    matrices = dict(response.matrices)
    target = response.matrix(key, "parallel").copy()
    target[:, 0] = 0.0
    target[0, 0] = 0.9
    target[1, 0] = 0.1
    matrices[key, "parallel"] = target
    response = replace(response, matrices=MappingProxyType(matrices))
    direction = np.zeros(16)
    direction[0] = 2.0
    direction[1] = -1.0

    lower, upper = _physical_step_limits(
        target[:, 0], direction, tolerance=0.2
    )

    assert upper == pytest.approx(0.05)
    with pytest.raises(PolarizationContractError, match="physical probability"):
        _perturbed_response(
            response, cell, direction, 0.075, tolerance=0.2
        )


def test_propagation_uses_probability_tolerance_for_column_sum_only(
    response_problem, monkeypatch
):
    response = response_problem["response"]
    nominal = _nominal_fit(response_problem)
    key = response.keys[0]
    cell = TrueCellKey(key, "parallel", 0)
    matrices = dict(response.matrices)
    target = response.matrix(key, "parallel").copy()
    target[:, 0] /= target[:, 0].sum()
    matrices[key, "parallel"] = target
    direction = np.zeros(16)
    direction[0] = 1.0
    covariance = dict(response.covariance_by_true_cell)
    covariance[cell] = 1e-4 * np.outer(direction, direction)
    response_problem["response"] = replace(
        response,
        matrices=MappingProxyType(matrices),
        covariance_by_true_cell=MappingProxyType(covariance),
    )
    config = response_problem["config"]
    response_problem["config"] = replace(
        config,
        response_validation=replace(
            config.response_validation,
            probability_absolute_tolerance=1e-3,
            covariance_eigenvalue_absolute_tolerance=1e-12,
        ),
    )

    def stable_core(counts, varied, *, config, replica_id=0):
        return nominal

    monkeypatch.setattr(
        response_uncertainty, "_fit_sigma_forward_folded_core", stable_core
    )

    result = propagate_response_covariance(**response_problem)

    assert result.refits[0].scheme == "central"


def test_physical_upper_boundary_uses_backward_refit(response_problem, monkeypatch):
    response = response_problem["response"]
    nominal = _nominal_fit(response_problem)
    key = response.keys[0]
    cell = TrueCellKey(key, "parallel", 0)
    matrices = dict(response.matrices)
    target = response.matrix(key, "parallel").copy()
    target[:, 0] /= target[:, 0].sum()
    matrices[key, "parallel"] = target
    direction = np.zeros(16)
    direction[0] = 1.0
    covariance = dict(response.covariance_by_true_cell)
    covariance[cell] = 1e-4 * np.outer(direction, direction)
    response = replace(
        response,
        matrices=MappingProxyType(matrices),
        covariance_by_true_cell=MappingProxyType(covariance),
    )
    response_problem["response"] = response
    base = response.matrix(key, "parallel")[:, 0].copy()
    jacobian = np.vstack((np.arange(16), -np.arange(16))) / 100.0

    def linear_core(counts, varied, *, config, replica_id=0):
        delta = varied.matrix(key, "parallel")[:, 0] - base
        return replace(nominal, sigma=nominal.sigma + jacobian @ delta)

    monkeypatch.setattr(
        response_uncertainty, "_fit_sigma_forward_folded_core", linear_core
    )

    result = propagate_response_covariance(**response_problem)

    assert result.refits[0].scheme == "backward"
    assert result.refits[0].lower_sigma is not None
    assert result.refits[0].upper_sigma is None
    np.testing.assert_allclose(result.refits[0].derivative, jacobian @ direction)


def test_machine_rounded_feasible_endpoint_keeps_central_refit(
    response_problem, monkeypatch
):
    nominal, response, cell, direction = _constant_refit_inputs(
        response_problem, monkeypatch
    )
    step = 1e-4

    refit = response_uncertainty._refit_response_mode(
        response_problem["counts"],
        response,
        config=response_problem["config"],
        nominal=nominal,
        cell=cell,
        direction=direction,
        eigenvalue=1e-8,
        step=step,
        lower_limit=-step,
        upper_limit=np.nextafter(step, 0.0),
        tolerance=1e-10,
        identifier="rounded-endpoint",
    )

    assert refit.scheme == "central"


def test_machine_slack_does_not_accept_materially_infeasible_endpoint(
    response_problem, monkeypatch
):
    nominal, response, cell, direction = _constant_refit_inputs(
        response_problem, monkeypatch
    )
    step = 1e-4

    refit = response_uncertainty._refit_response_mode(
        response_problem["counts"],
        response,
        config=response_problem["config"],
        nominal=nominal,
        cell=cell,
        direction=direction,
        eigenvalue=1e-8,
        step=step,
        lower_limit=-step,
        upper_limit=step - 1e-10,
        tolerance=1e-10,
        identifier="infeasible-endpoint",
    )

    assert refit.scheme == "backward"


def test_zero_modes_are_skipped_and_negative_mode_is_rejected(response_problem):
    zero = _task5_problem()
    result = propagate_response_covariance(**zero)
    assert result.retained_modes == ()
    np.testing.assert_array_equal(result.covariance, np.zeros((2, 2)))

    response = response_problem["response"]
    key = response.keys[0]
    cell = TrueCellKey(key, "parallel", 0)
    covariance = dict(response.covariance_by_true_cell)
    covariance[cell] = np.diag([-1e-4] + [0.0] * 15)
    response_problem["response"] = replace(
        response,
        covariance_by_true_cell=MappingProxyType(covariance),
    )
    with pytest.raises(PolarizationContractError, match="negative eigenvalue"):
        propagate_response_covariance(**response_problem)


@pytest.mark.parametrize(
    "field,value",
    [
        ("shared_mc_across_blocks", True),
        ("shared_mc_across_blocks", 1),
        ("shared_mc_across_blocks", "false"),
        ("cross_block_covariance", True),
        ("cross_block_covariance", np.eye(2)),
        ("cross_block_covariance", []),
    ],
)
def test_v1_rejects_malformed_or_cross_block_covariance_claims(
    response_problem, field, value
):
    claims = {
        "valid": True,
        "shared_mc_across_blocks": False,
        "cross_block_covariance": False,
    }
    claims[field] = value
    with pytest.raises(PolarizationContractError, match="covariance scope"):
        _response_covariance_scope(
            {"weighted_covariance_checks": claims},
            response_problem["config"].acceptance_qa_sha256,
        )


def test_propagation_requires_loader_sealed_scope_bound_to_config(response_problem):
    with pytest.raises(PolarizationContractError, match="validate_acceptance_handoff"):
        ResponseCovarianceScope(
            response_problem["config"].acceptance_qa_sha256, False, False
        )

    response_problem["covariance_scope"] = _response_covariance_scope(
        {
            "weighted_covariance_checks": {
                "valid": True,
                "shared_mc_across_blocks": False,
                "cross_block_covariance": False,
            }
        },
        "f" * 64,
    )
    with pytest.raises(PolarizationContractError, match="QA SHA-256"):
        propagate_response_covariance(**response_problem)


@pytest.mark.parametrize("mutation", ["missing", "shape", "nonnumeric", "step"])
def test_propagation_rejects_malformed_authorities(response_problem, mutation):
    response = response_problem["response"]
    if mutation == "missing":
        covariance = dict(response.covariance_by_true_cell)
        covariance.pop(next(iter(covariance)))
        response_problem["response"] = replace(
            response,
            covariance_by_true_cell=MappingProxyType(covariance),
        )
        match = "exactly cover"
    elif mutation == "shape":
        covariance = dict(response.covariance_by_true_cell)
        covariance[next(iter(covariance))] = np.zeros((2, 2))
        response_problem["response"] = replace(
            response,
            covariance_by_true_cell=MappingProxyType(covariance),
        )
        match = "shape"
    elif mutation == "nonnumeric":
        covariance = dict(response.covariance_by_true_cell)
        covariance[next(iter(covariance))] = [["bad"]]
        response_problem["response"] = replace(
            response,
            covariance_by_true_cell=MappingProxyType(covariance),
        )
        match = "numeric"
    else:
        config = response_problem["config"]
        response_problem["config"] = replace(
            config,
            response_validation=replace(
                config.response_validation,
                finite_difference_absolute_step=None,
            ),
        )
        match = "finite tolerances"

    with pytest.raises(PolarizationContractError, match=match):
        propagate_response_covariance(**response_problem)


def test_propagation_fails_closed_when_mode_refit_fails(
    response_problem, monkeypatch
):
    real_core = response_uncertainty._fit_sigma_forward_folded_core
    calls = 0

    def failing_core(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise PolarizationContractError("synthetic refit failure")
        return real_core(*args, **kwargs)

    monkeypatch.setattr(
        response_uncertainty, "_fit_sigma_forward_folded_core", failing_core
    )

    with pytest.raises(PolarizationContractError, match="synthetic refit failure"):
        propagate_response_covariance(**response_problem)


def test_propagation_rejects_stateful_count_subtype(response_problem):
    class StatefulCounts(AzimuthCountTable):
        pass

    counts = response_problem["counts"]
    response_problem["counts"] = StatefulCounts(
        counts.rows, counts.expected_universe, counts.expected_replica_ids
    )

    with pytest.raises(PolarizationContractError, match="exact count table"):
        propagate_response_covariance(**response_problem)
