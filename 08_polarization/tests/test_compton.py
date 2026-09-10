from __future__ import annotations

import numpy as np
import pytest

from compton import PolarizationCurve
from contracts import PolarizationContractError


def test_curve_interpolates_value_and_covariance_without_extrapolation():
    curve = PolarizationCurve(
        [600.0, 800.0],
        [0.4, 0.8],
        [[0.01, 0.002], [0.002, 0.04]],
    )
    value, variance = curve.evaluate(700.0)
    assert value == pytest.approx(0.6)
    assert variance == pytest.approx(0.0135)
    with pytest.raises(PolarizationContractError, match="extrapolation"):
        curve.evaluate(500.0)


def test_curve_returns_endpoint_values_and_variances():
    curve = PolarizationCurve(
        [600.0, 800.0],
        [0.4, 0.8],
        [[0.01, 0.002], [0.002, 0.04]],
    )
    assert curve.evaluate(600.0) == pytest.approx((0.4, 0.01))
    assert curve.evaluate(800.0) == pytest.approx((0.8, 0.04))


def test_curve_bin_average_uses_piecewise_linear_weights_and_covariance():
    curve = PolarizationCurve(
        [600.0, 700.0, 800.0],
        [0.2, 0.6, 0.8],
        np.diag([0.01, 0.04, 0.09]),
    )
    value, variance = curve.bin_average(600.0, 800.0)
    # Trapezoids give normalized nodal weights [0.25, 0.5, 0.25].
    assert value == pytest.approx(0.55)
    assert variance == pytest.approx(0.25**2 * 0.01 + 0.5**2 * 0.04 + 0.25**2 * 0.09)


@pytest.mark.parametrize(
    "energies,values,covariance,match",
    [
        ([600.0], [0.5], [[0.01]], "at least two"),
        ([600.0, 600.0], [0.4, 0.5], [[0.01, 0.0], [0.0, 0.01]], "increasing"),
        ([600.0, 800.0], [-0.1, 0.5], [[0.01, 0.0], [0.0, 0.01]], "physical"),
        ([600.0, 800.0], [0.4, 0.5], [[0.01, 0.2], [0.0, 0.01]], "symmetric"),
        ([600.0, 800.0], [0.4, 0.5], [[1.0, 2.0], [2.0, 1.0]], "semidefinite"),
    ],
)
def test_curve_rejects_invalid_physics_and_covariance(energies, values, covariance, match):
    with pytest.raises(PolarizationContractError, match=match):
        PolarizationCurve(energies, values, covariance)


def test_curve_rejects_bin_average_outside_support_or_empty_width():
    curve = PolarizationCurve([600.0, 800.0], [0.4, 0.8], np.eye(2) * 0.01)
    with pytest.raises(PolarizationContractError, match="positive width"):
        curve.bin_average(700.0, 700.0)
    with pytest.raises(PolarizationContractError, match="extrapolation"):
        curve.bin_average(500.0, 700.0)
