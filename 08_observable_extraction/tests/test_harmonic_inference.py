import numpy as np
from observable_extraction.core.cross_section import (
    fit_cross_sections,
    harmonic_design,
    harmonic_mc_covariance,
    weighted_harmonic_mc_covariance,
)


def test_energy_guard_is_fitted_without_normalizing_to_reference():
    # First truth bin is below the observed energy domain. Its migrations
    # contaminate observed cells; its unknown yield is fitted as a nuisance.
    moments = np.array(
        [
            [[0.03, 0.01, 0], [0.012, -0.004, 0]],
            [[0.02, 0.08, 0.04], [0.008, -0.03, 0.01]],
        ]
    )
    lumi = np.array([[100.0, 130.0], [80.0, 110.0]])
    pol = np.array([[0.6, 0.7], [0.5, 0.65]])
    design = harmonic_design(moments, lumi, pol)
    truth = np.array([0.4, 1.2, 0.12, -0.3])
    yields = design @ truth
    fit = fit_cross_sections(yields, np.eye(6), design)
    np.testing.assert_allclose(fit.coefficients, truth, rtol=1e-12, atol=1e-12)
    missing_guard = fit_cross_sections(yields, np.eye(6), design[:, [1, 3]])
    assert abs(missing_guard.coefficients[0] - truth[1]) > 0.01


def test_shared_harmonic_mc_covariance_matches_numerical_derivatives():
    moments = np.array(
        [
            [[0.03, 0.01, 0], [0.012, -0.004, 0]],
            [[0.02, 0.08, 0.04], [0.008, -0.03, 0.01]],
        ]
    )
    lumi = np.array([[100.0, 130.0], [80.0, 110.0]])
    pol = np.array([[0.6, 0.7], [0.5, 0.65]])
    design = harmonic_design(moments, lumi, pol)
    yields = design @ np.array([0.4, 1.2, 0.12, -0.3]) + np.array(
        [0.1, -0.2, 0.15, -0.1, 0.2, -0.1]
    )
    fit = fit_cross_sections(yields, np.eye(6), design)
    # Shared stochastic mean perturbations across both beam states.
    covariance = np.tile(np.eye(6)[None] * 1e-7, (2, 1, 1))
    analytical = harmonic_mc_covariance(fit, covariance, lumi, pol)
    expected = np.zeros((4, 4))
    step = 1e-7
    # Differentiate the algebraic design directly so zero-probability cells
    # can be perturbed in both directions without asserting physical means.
    for energy in range(2):
        jac = np.zeros((4, 6))
        for column in range(6):
            moment, reco = divmod(column, 3)
            delta = np.zeros_like(design)
            for state, sign in enumerate((1, -1)):
                delta[state * 3 + reco, energy + 2 * moment] = lumi[state, energy] * (
                    sign * pol[state, energy] if moment else 1
                )
            up = fit_cross_sections(yields, np.eye(6), design + step * delta)
            down = fit_cross_sections(yields, np.eye(6), design - step * delta)
            jac[:, column] = (up.coefficients - down.coefficients) / (2 * step)
        expected += jac @ covariance[energy] @ jac.T
    np.testing.assert_allclose(analytical, expected, rtol=1e-7, atol=1e-12)


def test_weighted_moment_covariance_matches_numerical_gls_derivative():
    rng = np.random.default_rng(55)
    design = rng.normal(size=(8, 4))
    yields = design @ np.array([1.0, 2.0, 0.1, -0.2]) + rng.normal(size=8)
    fit = fit_cross_sections(yields, np.eye(8), design)
    root = rng.normal(size=(2, 16, 6)) * 1e-4
    covariance = root @ root.transpose(0, 2, 1)
    actual = weighted_harmonic_mc_covariance(fit, covariance)
    expected = np.zeros((4, 4))
    step = 1e-6
    for k in range(2):
        jac = np.zeros((4, 16))
        for j in range(16):
            moment, row = divmod(j, 8)
            delta = np.zeros_like(design)
            delta[row, k + moment * 2] = step
            up = fit_cross_sections(yields, np.eye(8), design + delta)
            down = fit_cross_sections(yields, np.eye(8), design - delta)
            jac[:, j] = (up.coefficients - down.coefficients) / (2 * step)
        expected += jac @ covariance[k] @ jac.T
    np.testing.assert_allclose(actual, expected, rtol=1e-7, atol=1e-12)


def test_strip_mask_uses_each_runs_flux_and_original_observed_domain():
    from observable_extraction.core.models import FluxExposure
    from observable_extraction.harmonic_cross_sections import exposure_weights

    exposures = {
        (1, 10): FluxExposure(1, 10, 1.05, 10, 20, 0, 0.5, 0.6),
        (1, 20): FluxExposure(1, 20, 1.2, 30, 40, 0, 0.5, 0.6),
        (2, 10): FluxExposure(2, 10, 1.05, 100, 200, 0, 0.7, 0.8),
        (2, 21): FluxExposure(2, 21, 1.2, 300, 400, 0, 0.7, 0.8),
    }
    observed = {key: val for key, val in exposures.items() if val.energy_gev >= 1.1}
    weights, photons = exposure_weights(
        exposures,
        observed,
        np.array([0.95, 1.1, 1.5]),
        np.array([0, 0, 0, 1]),
        np.array([20, 21, 10, 21]),
        1.0,
    )
    np.testing.assert_allclose(photons, [[110, 330], [220, 440]])
    np.testing.assert_allclose(
        weights[:, 0], [[10, 20], [100, 200], [0, 0], [300, 400]]
    )
    np.testing.assert_allclose(
        weights[:, 1], [[5, -12], [70, -160], [0, 0], [210, -320]]
    )
