"""Independent contractions of coherent spin matrices and global azimuth."""

import numpy as np
import pytest

from graal_theory.figure4_integration import project_azimuth_averaged_moments
from graal_theory.quadratic_moments import azimuth_state_moments, quadratic_moments


@pytest.fixture
def toy():
    rng = np.random.default_rng(31)
    vertical = rng.normal(size=(3, 5, 2, 2)) + 1j*rng.normal(size=(3, 5, 2, 2))
    horizontal = rng.normal(size=(3, 5, 2, 2)) + 1j*rng.normal(size=(3, 5, 2, 2))
    return vertical, horizontal, np.array([-2.1, -0.7, 0.2, 1.4, 2.6]), np.array([.2, 1., .4, 2., .7])


def test_quadratic_moments_match_direct_coherent_oracle(toy):
    vertical, horizontal, phi, weights = toy
    moments = quadratic_moments(vertical, horizontal, phi, weights)
    for matrix in (moments.numerator, moments.denominator):
        assert matrix.shape == (3, 3)
        assert not matrix.flags.writeable
        np.testing.assert_allclose(matrix, matrix.conj().T, atol=1e-13)
    for coefficients in ([1., 0., 0.], [1., .08, -.04], [1., -.11, .14]):
        v = np.einsum("a,anij->nij", coefficients, vertical)
        h = np.einsum("a,anij->nij", coefficients, horizontal)
        expected_n, expected_d = project_azimuth_averaged_moments(phi, v, h, weights)
        actual_n, actual_d, sigma = moments.evaluate(coefficients)
        assert (actual_n, actual_d) == pytest.approx((expected_n, expected_d), rel=1e-13)
        assert sigma == pytest.approx(expected_n/expected_d)


def test_polarized_norm_matrices_recover_each_state_independently(toy):
    vertical, horizontal, phi, weights = toy
    moments = quadratic_moments(vertical, horizontal, phi, weights)
    coefficients = np.array([1., .08, -.04])
    v = np.einsum("a,anij->nij", coefficients, vertical)
    h = np.einsum("a,anij->nij", coefficients, horizontal)
    expected_v = float(np.sum(weights*np.sum(abs(v)**2, axis=(1, 2))/2))
    expected_h = float(np.sum(weights*np.sum(abs(h)**2, axis=(1, 2))/2))
    assert np.real(coefficients @ moments.vertical @ coefficients) == pytest.approx(expected_v)
    assert np.real(coefficients @ moments.horizontal @ coefficients) == pytest.approx(expected_h)
    np.testing.assert_allclose(moments.vertical+moments.horizontal, moments.denominator)


def test_moments_reject_bad_measure_or_contraction(toy):
    v, h, phi, weights = toy
    with pytest.raises(ValueError):
        quadratic_moments(v, h, phi, -weights)
    with pytest.raises(ValueError):
        quadratic_moments(v[:, :-1], h, phi, weights)
    moments = quadratic_moments(v, h, phi, weights)
    with pytest.raises(ValueError):
        moments.evaluate([1., np.nan, 0.])
    with pytest.raises(ValueError):
        quadratic_moments(np.zeros_like(v), np.zeros_like(h), phi, weights).evaluate([1., 0., 0.])


def test_finite_phi_states_match_explicit_azimuth_quadrature(toy):
    vertical, horizontal, phi, weights = toy
    pv, ph = .68, .42
    states = azimuth_state_moments(vertical, horizontal, phi, weights, pv, ph)
    assert states.shape == (2, 12, 3, 3)
    assert not states.flags.writeable
    coefficients = np.array([1., .08, -.04])
    v = np.einsum("a,anij->nij", coefficients, vertical)
    h = np.einsum("a,anij->nij", coefficients, horizontal)
    v2 = np.sum(abs(v)**2, axis=(1, 2))/2
    h2 = np.sum(abs(h)**2, axis=(1, 2))/2
    interference = np.real(np.sum(np.conj(h)*v, axis=(1, 2)))/2
    direct_total = float(np.sum((v2+h2)*weights)/2)
    for state, polarization in enumerate((pv, ph)):
        measured = np.real(np.einsum("a,pab,b->p", coefficients, states[state], coefficients))
        assert measured.sum() == pytest.approx(direct_total, rel=1e-13)
        direct = []
        for lower, upper in zip(np.linspace(0., 2*np.pi, 13)[:-1], np.linspace(0., 2*np.pi, 13)[1:]):
            beta = lower + (np.arange(48)+.5)*(upper-lower)/48
            alpha = beta[:, None] - phi[None, :]
            polarized = (v2-h2)[None, :]*np.cos(2*alpha) - 2*interference[None, :]*np.sin(2*alpha)
            density = (v2+h2)[None, :]/2 + (1 if state == 0 else -1)*polarization*polarized/2
            direct.append(np.sum(np.mean(density, axis=0)*weights)*(upper-lower)/(2*np.pi))
        np.testing.assert_allclose(measured, direct, rtol=2e-4, atol=1e-10)


@pytest.mark.parametrize('bins', [8, 12, 16])
def test_cone_averaged_harmonics_match_symmetric_explicit_azimuth(toy, bins):
    from graal_theory.quadratic_moments import cone_averaged_moments, harmonic_state_moments
    v, h, phi, weights = toy
    # Equal +/- azimuths: sine mean vanishes, H/V interference need not.
    q, sine = cone_averaged_moments(v, h, np.cos(2*phi), weights)
    expected = quadratic_moments(np.repeat(v, 2, axis=1), np.repeat(h, 2, axis=1),
                                np.column_stack((phi, -phi)).ravel(), np.repeat(weights/2, 2))
    np.testing.assert_allclose(q.numerator, expected.numerator, atol=1e-13)
    np.testing.assert_allclose(q.denominator, expected.denominator, atol=1e-13)
    assert np.linalg.norm(sine) > .1
    state = harmonic_state_moments(q.numerator, sine, q.denominator, .68, .42, phi_bins=bins)
    explicit = azimuth_state_moments(np.repeat(v, 2, axis=1), np.repeat(h, 2, axis=1),
        np.column_stack((phi, -phi)).ravel(), np.repeat(weights/2, 2), .68, .42, phi_bins=bins)
    np.testing.assert_allclose(state, explicit, atol=1e-13)
