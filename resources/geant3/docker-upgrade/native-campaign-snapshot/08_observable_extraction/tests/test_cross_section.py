import numpy as np
import pytest
from mc_simulation.response import response_probabilities
from observable_extraction.core.cross_section import (
    cross_section_basis,
    design_matrix,
    design_shift,
    differential_transform,
    fit_cross_sections,
    response_uncertainty,
)


def example():
    phi = np.linspace(0, 2 * np.pi, 9)
    response = np.diag(np.linspace(0.15, 0.8, 16))
    response[8, 0] = 0.03  # real migration, not a diagonal correction
    bv = cross_section_basis([120, 70], [0.7, 0.8], phi, 1)
    bh = cross_section_basis([35, 200], [0.6, 0.9], phi, 2)
    a = np.vstack([response @ bv, response @ bh])
    truth = np.array([2.0, 5.0, 0.6, -1.0])
    return response, [bv, bh], a, truth


def test_closure_migrations_unequal_flux_and_polarization():
    response, _bases, a, truth = example()
    y = a @ truth
    result = fit_cross_sections(y, np.diag(np.maximum(y, 1)), a)
    np.testing.assert_allclose(result.coefficients, truth, atol=1e-12)
    assert result.chi2 < 1e-20
    assert result.dof == 28
    assert np.all(np.linalg.eigvalsh(result.covariance) > 0)
    np.testing.assert_allclose(
        design_matrix(response, [120, 70], [0.7, 0.8], np.linspace(0, 2 * np.pi, 9), 1),
        a[:16],
    )


def test_finite_phi_integral_and_no_energy_bin_width_factor():
    phi = np.linspace(0, 2 * np.pi, 9)
    basis = cross_section_basis([10], [0.8], phi, 1)
    assert basis[:, 0].sum() == pytest.approx(10)
    assert basis[:, 1].sum() == pytest.approx(0, abs=1e-14)
    assert basis[0, 1] == pytest.approx(10 * 0.8 / (4 * np.pi))


def test_splitting_period_with_same_response_preserves_result_and_covariance():
    _, _, a, truth = example()
    y = a @ truth
    c = np.diag(y)
    whole = fit_cross_sections(y, c, a)
    split = fit_cross_sections(
        np.r_[y / 2, y / 2], np.kron(np.eye(2), c / 2), np.vstack([a / 2, a / 2])
    )
    np.testing.assert_allclose(whole.coefficients, split.coefficients)
    np.testing.assert_allclose(whole.covariance, split.covariance)


def test_rank_deficiency_and_invalid_covariance_fail():
    with pytest.raises(ValueError, match="rank"):
        fit_cross_sections([2, 3], np.eye(2), np.ones((2, 2)))
    with pytest.raises(ValueError, match="positive definite"):
        fit_cross_sections([2, 3], np.zeros((2, 2)), np.eye(2))
    with pytest.raises(ValueError):
        cross_section_basis([10], [1.2], [0, np.pi, 2 * np.pi], 1)


def test_negative_net_yield_is_not_clipped():
    result = fit_cross_sections([-2, 3], np.eye(2), np.eye(2))
    np.testing.assert_array_equal(result.coefficients, [-2, 3])


def test_normalization_shift_matches_finite_difference():
    _, _, a, truth = example()
    y = a @ truth + np.linspace(-0.1, 0.1, len(a))
    c = np.diag(np.maximum(y, 1))
    fit = fit_cross_sections(y, c, a)
    da = a * 0.02
    delta = 1e-5
    numerical = (
        fit_cross_sections(y, c, a + delta * da).coefficients
        - fit_cross_sections(y, c, a - delta * da).coefficients
    ) / (2 * delta)
    np.testing.assert_allclose(design_shift(fit, da), numerical, rtol=1e-6, atol=1e-9)


def test_shared_mc_covariance_uses_one_draw_for_both_states():
    response, bases, a, truth = example()
    n = np.full(16, 10000)
    r, c = response_probabilities(n, np.round(response * n).astype(int))
    a = np.vstack([r @ b for b in bases])
    y = a @ truth + np.linspace(-0.1, 0.1, len(a))
    cy = np.diag(np.maximum(y, 1))
    fit = fit_cross_sections(y, cy, a)
    actual = response_uncertainty(
        fit, c, [(slice(0, 16), bases[0]), (slice(16, 32), bases[1])]
    )
    expected = np.zeros((4, 4))
    for j in range(16):
        jac = []
        for i in range(16):
            da = np.zeros_like(a)
            da[i] = bases[0][j]
            da[16 + i] = bases[1][j]
            jac.append(design_shift(fit, da))
        jac = np.array(jac).T
        expected += jac @ c[j] @ jac.T
    np.testing.assert_allclose(actual, expected, atol=1e-12)


def test_differential_units_and_covariance():
    transform = differential_transform(2, [1.0, 1.1, 1.3])
    np.testing.assert_allclose(np.diag(transform), [1 / 100, 1 / 200] * 2)
