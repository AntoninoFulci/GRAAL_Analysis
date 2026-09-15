from __future__ import annotations

import numpy as np
from dataclasses import replace
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import nuisance_uncertainty
from azimuth_counts import FluxAuthorityRow
from compton import PolarizationCurve
from nuisance_uncertainty import (
    flux_net_covariance,
    propagate_compton_covariance,
    propagate_flux_exposure_covariance,
)
from state_mapping import StateInterval


def test_flux_net_covariance_uses_shared_brem_raw_poisson_model():
    covariance = flux_net_covariance(pol1=101.0, brem=7.0, pol2=83.0)

    np.testing.assert_array_equal(covariance, [[108.0, 7.0], [7.0, 90.0]])
    assert covariance.flags.writeable is False


def _linear_problem(monkeypatch, *, field):
    path = Path(__file__).with_name("test_sigma_fit.py")
    spec = importlib.util.spec_from_file_location("nuisance_sigma_tests", path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    problem = module.asimov_problem.__wrapped__()
    nominal = nuisance_uncertainty._fit_sigma_forward_folded_core(
        problem["counts"], problem["response"], config=problem["config"]
    )
    states = sorted({
        (row.source_period, row.orientation) for row in problem["counts"].rows
    })
    baseline = {
        state: next(
            getattr(row, field) for row in problem["counts"].rows
            if (row.source_period, row.orientation) == state
        )
        for state in states
    }
    jacobian = np.asarray([[0.3, -0.2, 0.5, 0.1], [-0.4, 0.6, 0.2, -0.3]])

    def linear_core(counts, response, *, config, replica_id=0):
        vector = np.asarray([
            next(
                getattr(row, field) for row in counts.rows
                if (row.source_period, row.orientation) == state
            ) - baseline[state]
            for state in states
        ])
        return replace(nominal, sigma=nominal.sigma + jacobian @ vector)

    monkeypatch.setattr(
        nuisance_uncertainty, "_fit_sigma_forward_folded_core", linear_core
    )
    return problem, nominal, states, jacobian


def test_compton_full_sigma_refits_preserve_period_and_node_correlations(monkeypatch):
    problem, _nominal, states, jacobian = _linear_problem(
        monkeypatch, field="beam_polarization"
    )
    covariance_a = np.asarray([[0.04, 0.01], [0.01, 0.09]])
    covariance_b = np.asarray([[0.02, -0.004], [-0.004, 0.03]])
    authority = SimpleNamespace(compton={
        "period-a": PolarizationCurve([700.0, 800.0], [0.7, 0.74], covariance_a),
        "period-b": PolarizationCurve([700.0, 800.0], [0.67, 0.71], covariance_b),
    })

    first = propagate_compton_covariance(
        problem["counts"], problem["response"],
        config=problem["config"], authority=authority,
    )
    second = propagate_compton_covariance(
        problem["counts"], problem["response"],
        config=problem["config"], authority=authority,
    )

    node_to_states = np.zeros((len(states), 4))
    for index, (period, _orientation) in enumerate(states):
        offset = 0 if period == "period-a" else 2
        node_to_states[index, offset:offset + 2] = 0.5
    input_covariance = np.block([
        [covariance_a, np.zeros((2, 2))],
        [np.zeros((2, 2)), covariance_b],
    ])
    expected = jacobian @ node_to_states @ input_covariance @ node_to_states.T @ jacobian.T
    np.testing.assert_allclose(first.input_covariance, input_covariance)
    np.testing.assert_allclose(first.covariance, expected, rtol=1e-9, atol=1e-12)
    assert first.covariance.tobytes() == second.covariance.tobytes()


def test_flux_full_sigma_refits_preserve_shared_brem_and_independent_rows(monkeypatch):
    problem, _nominal, states, jacobian = _linear_problem(
        monkeypatch, field="exposure"
    )
    flux_rows = []
    intervals = []
    for run, period in ((101, "period-a"), (202, "period-b")):
        parallel = next(
            row.exposure for row in problem["counts"].rows
            if row.source_period == period and row.orientation == "parallel"
        )
        perpendicular = next(
            row.exposure for row in problem["counts"].rows
            if row.source_period == period and row.orientation == "perpendicular"
        )
        flux_rows.append(FluxAuthorityRow(
            run, period, "P", "coherent", "coherent-a", 0.7, 0.8,
            parallel + 0.05, 0.05, perpendicular + 0.05,
            parallel, perpendicular,
        ))
        intervals.extend((
            StateInterval(run, run, 1, "parallel", period, "pol1_net"),
            StateInterval(run, run, 2, "perpendicular", period, "pol2_net"),
        ))
    authority = SimpleNamespace(flux_rows=tuple(flux_rows), state_map=tuple(intervals))

    result = propagate_flux_exposure_covariance(
        problem["counts"], problem["response"],
        config=problem["config"], authority=authority,
    )

    expected_input = np.zeros((4, 4))
    for index, row in enumerate(flux_rows):
        expected_input[2 * index:2 * index + 2, 2 * index:2 * index + 2] = (
            flux_net_covariance(pol1=row.pol1, brem=row.brem, pol2=row.pol2)
        )
    np.testing.assert_allclose(result.input_covariance, expected_input)
    np.testing.assert_allclose(
        result.covariance, jacobian @ expected_input @ jacobian.T,
        rtol=1e-9, atol=1e-12,
    )
