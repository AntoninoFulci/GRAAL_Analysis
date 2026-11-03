import json

import numpy as np
import pytest

from graal_common.physics.channels import M_ETA, M_PI0
from observable_extraction.core.candle import GaussianCandle, fit_gaussian_candle


def test_analytic_ellipse_excludes_rectangle_corners_and_nonfinite():
    candle = GaussianCandle(.55, .135, .02, .01, 0.)
    assert candle.mask([.55, .57, .57, .58, np.nan, .55],
                       [.135, .135, .145, .135, .135, np.inf]).tolist() == [
        True, True, False, False, False, False]
    # The analytic contour includes its boundary, not a sample quantile.
    radius = np.sqrt(2 * np.log(2))
    assert candle.mask([.55 + radius * .02, .55 + 1.001 * radius * .02],
                       [.135, .135]).tolist() == [True, False]
    assert candle.mask([.55] * 9 + [.7], [.135] * 10).sum() == 9


def test_correlated_gaussian_and_covariance_roundtrip():
    candle = GaussianCandle(.55, .135, .02, .01, .6)
    assert candle.mask([.57, .57, .55], [.141, .129, .145]).tolist() == [True, False, False]
    np.testing.assert_allclose(candle.covariance_gev2, [[.0004, .00012], [.00012, .0001]])
    clone = GaussianCandle.from_dict(json.loads(json.dumps(candle.to_dict(), allow_nan=False)))
    assert clone == candle
    assert clone.mask([], []).size == 0


@pytest.mark.parametrize("params", [
    (np.nan, .135, .02, .01, 0.), (.55, np.inf, .02, .01, 0.),
    (.55, .135, 0., .01, 0.), (.55, .135, -.02, .01, 0.),
    (.55, .135, .02, np.inf, 0.), (.55, .135, .02, .01, 1.),
    (.55, .135, .02, .01, -1.), (.55, .135, .02, .01, np.nan),
    (.55, .135, 1e200, .01, 0.),
])
def test_invalid_covariance_is_rejected(params):
    with pytest.raises(ValueError):
        GaussianCandle(*params)


def test_invalid_shape_or_serialized_definition_is_rejected():
    candle = GaussianCandle(.55, .135, .02, .01, .2)
    for eta, pi0 in [([.55], [.135, .135]), ([[.55]], [[.135]])]:
        with pytest.raises(ValueError, match="shape"):
            candle.mask(eta, pi0)
    for change in ({"radius_squared": 1.}, {"schema": True}, {"extra": 1},
                   {"eta_sigma_gev": "0.02"}, {"correlation": float("nan")}):
        with pytest.raises(ValueError):
            GaussianCandle.from_dict(dict(candle.to_dict(), **change))


def test_fit_recovers_correlated_gaussian_above_constant_pedestal():
    rng = np.random.default_rng(722)
    mean = [M_ETA + .003, M_PI0 - .002]
    covariance = [[.012 ** 2, .45 * .012 * .008], [.45 * .012 * .008, .008 ** 2]]
    signal = rng.multivariate_normal(mean, covariance, 16000)
    pedestal = rng.uniform([M_ETA - .05, M_PI0 - .05], [M_ETA + .05, M_PI0 + .05], (8000, 2))
    masses = np.vstack([signal, pedestal, [np.nan, .13], [.9, .3]])
    candle = fit_gaussian_candle(*masses.T)
    assert candle.eta_center_gev == pytest.approx(mean[0], abs=.0006)
    assert candle.pi0_center_gev == pytest.approx(mean[1], abs=.0004)
    assert candle.eta_sigma_gev == pytest.approx(.012, rel=.06)
    assert candle.pi0_sigma_gev == pytest.approx(.008, rel=.06)
    assert candle.correlation == pytest.approx(.45, abs=.05)
    assert .47 < candle.mask(*signal.T).mean() < .53
    assert .30 < candle.mask(*masses.T).mean() < .40
    audit = candle.to_dict()["fit"]
    assert audit["status"] == "converged"
    assert audit["input_count"] == 24002
    assert audit["finite_count"] == 24001
    assert 23990 < audit["fit_count"] <= 24000
    assert audit["fit_window_gev"] == [[M_ETA - .05, M_ETA + .05], [M_PI0 - .05, M_PI0 + .05]]
    assert np.linalg.eigvalsh(audit["parameter_covariance"]).min() > 0
    assert GaussianCandle.from_dict(json.loads(json.dumps(candle.to_dict(), allow_nan=False))) == candle


@pytest.mark.parametrize("masses", [np.empty((0, 2)), np.tile([M_ETA, M_PI0], (200, 1)),
                                     np.tile([np.nan, np.inf], (200, 1)),
                                     np.tile([M_ETA, M_PI0], (10, 1))])
def test_fit_rejects_insufficient_or_degenerate_samples(masses):
    with pytest.raises(ValueError):
        fit_gaussian_candle(*masses.T)


def test_fit_rejects_background_only_and_invalid_window():
    rng = np.random.default_rng(102)
    masses = rng.uniform([M_ETA - .05, M_PI0 - .05], [M_ETA + .05, M_PI0 + .05], (4000, 2))
    with pytest.raises(ValueError):
        fit_gaussian_candle(*masses.T)
    for width in (0., -.05, np.nan, np.inf):
        with pytest.raises(ValueError):
            fit_gaussian_candle(*masses.T, half_width_gev=width)


def test_fit_handles_resolved_pure_signal_without_requiring_background():
    rng = np.random.default_rng(0)
    masses = rng.normal([M_ETA, M_PI0], [.009, .006], (2000, 2))
    candle = fit_gaussian_candle(*masses.T)
    assert candle.eta_sigma_gev == pytest.approx(.009, rel=.06)
    assert candle.pi0_sigma_gev == pytest.approx(.006, rel=.06)
    assert .47 < candle.mask(*masses.T).mean() < .53


def test_fitted_audit_rejects_tampered_covariance_counts_and_window():
    rng = np.random.default_rng(178)
    masses = np.vstack([rng.normal([M_ETA, M_PI0], [.012, .008], (1500, 2)),
                        rng.uniform([M_ETA - .05, M_PI0 - .05], [M_ETA + .05, M_PI0 + .05], (700, 2))])
    definition = fit_gaussian_candle(*masses.T).to_dict()
    for change in ({"parameter_covariance": np.zeros((7, 7)).tolist()},
                   {"finite_count": 1}, {"status": "failed"},
                   {"fit_window_gev": [[0, 1], [0, 1]]},
                   {"parameter_errors": ["1"] * 7},
                   {"poisson_deviance": -1}, {"pedestal_at_boundary": "false"}):
        modified = dict(definition, fit=dict(definition["fit"], **change))
        with pytest.raises(ValueError):
            GaussianCandle.from_dict(modified)


def test_fit_rejects_peak_below_declared_resolution_bound():
    masses = np.random.default_rng(30).normal([M_ETA, M_PI0], [.0004, .0004], (2000, 2))
    with pytest.raises(ValueError, match="boundary"):
        fit_gaussian_candle(*masses.T)


def test_fitted_audit_enforces_fit_bounds_and_boundary_policy():
    rng = np.random.default_rng(178)
    masses = np.vstack([rng.normal([M_ETA, M_PI0], [.012, .008], (1500, 2)),
                        rng.uniform([M_ETA - .05, M_PI0 - .05], [M_ETA + .05, M_PI0 + .05], (700, 2))])
    definition = fit_gaussian_candle(*masses.T).to_dict()
    for index, name, value in (
        (0, "eta_center_gev", 100.),
        (1, "pi0_center_gev", M_PI0 - .05),
        (0, "eta_center_gev", M_ETA + .05 * (1 - 1e-5)),
        (2, "eta_sigma_gev", .002),
        (3, "pi0_sigma_gev", .051),
        (4, "correlation", .95),
        (4, "correlation", -.97),
    ):
        altered = json.loads(json.dumps(definition))
        altered[name] = altered["fit"]["parameters"][index] = value
        with pytest.raises(ValueError, match="bound"):
            GaussianCandle.from_dict(altered)

    for signal, pedestal, fit_count, at_boundary in (
        (0., 2200., 2200, False),
        (2199., 1., 2200, True),
        (2200., 0., 2200, False),
        (60., 20., 80, False),
    ):
        altered = json.loads(json.dumps(definition))
        altered["fit"]["parameters"][5:] = [signal, pedestal]
        altered["fit"]["fit_count"] = fit_count
        altered["fit"]["pedestal_at_boundary"] = at_boundary
        with pytest.raises(ValueError):
            GaussianCandle.from_dict(altered)

    # Manually specified mathematical contours have no fitted-window contract.
    manual = GaussianCandle(100., -10., .1, .2, .97)
    assert GaussianCandle.from_dict(manual.to_dict()) == manual
