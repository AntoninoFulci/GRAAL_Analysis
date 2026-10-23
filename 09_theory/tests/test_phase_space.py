import numpy as np
import pytest
from scipy.integrate import quad

from graal_theory.kinematics import invariant_mass, kallen, validate_final_state
from graal_theory.phase_space import (
    BelowThresholdError,
    SobolConfig,
    phase_space_volume_quad,
    sample_three_body,
    sample_three_body_mass_window,
)


MASSES = (0.547862, 0.1349768, 0.9382721)


def test_scrambled_sobol_requires_seed():
    with pytest.raises(ValueError, match="seed"):
        SobolConfig(power=10, scramble=True, seed=None)


def test_power_must_be_supported():
    with pytest.raises(ValueError, match="power"):
        SobolConfig(power=3)


def test_three_body_sample_is_reproducible_and_conserved():
    cfg = SobolConfig(power=10, scramble=False, seed=None)
    first = sample_three_body(2.0, MASSES, cfg)
    second = sample_three_body(2.0, MASSES, cfg)
    np.testing.assert_array_equal(first.momenta, second.momenta)
    np.testing.assert_array_equal(first.weights_gev2, second.weights_gev2)
    validate_final_state(first.initial, first.momenta, first.masses, atol=1e-12)


def test_sobol_phase_space_matches_quadrature():
    sample = sample_three_body(2.0, MASSES, SobolConfig(power=16))
    expected = phase_space_volume_quad(2.0, MASSES)
    assert sample.weights_gev2.mean() == pytest.approx(expected, rel=5e-3)


def test_massless_phase_space_matches_closed_form_and_preserves_first_event():
    sample = sample_three_body(1.0, (0.0, 0.0, 0.0), SobolConfig(power=12))
    expected = 1.0 / (256.0 * np.pi**3)
    assert np.all(np.isfinite(sample.momenta))
    assert np.all(np.isfinite(sample.weights_gev2))
    validate_final_state(sample.initial, sample.momenta, sample.masses, atol=1e-12)
    assert float(np.mean(sample.weights_gev2)) == pytest.approx(expected, rel=0.005)
    assert phase_space_volume_quad(1.0, (0.0, 0.0, 0.0)) == pytest.approx(expected, rel=1e-10)


def test_nested_sobol_sample_starts_with_low_resolution_points():
    low = sample_three_body(2.0, MASSES, SobolConfig(power=8))
    high = sample_three_body(2.0, MASSES, SobolConfig(power=9))
    np.testing.assert_array_equal(low.momenta, high.momenta[:len(low.momenta)])


def test_at_threshold_sampler_fails_with_named_condition():
    with pytest.raises(BelowThresholdError):
        sample_three_body(sum(MASSES), MASSES, SobolConfig(power=8))


@pytest.mark.parametrize("pair", [(0, 1), (0, 2), (1, 2)])
def test_conditional_mass_window_preserves_canonical_state_and_integral(pair):
    sqrt_s = 2.0
    spectator = ({0, 1, 2} - set(pair)).pop()
    low = MASSES[pair[0]] + MASSES[pair[1]] + 0.03
    high = sqrt_s - MASSES[spectator] - 0.02
    sample = sample_three_body_mass_window(
        sqrt_s, MASSES, pair, (low, high), SobolConfig(16))
    assert sample is not None
    assert sample.masses == MASSES
    mass = invariant_mass(sample.momenta[:, pair[0]]+sample.momenta[:, pair[1]])
    assert np.all(mass >= low-1e-12) and np.all(mass <= high+1e-12)
    validate_final_state(sample.initial, sample.momenta, MASSES, atol=1e-12)
    np.testing.assert_allclose(sample.s12_gev2,
        invariant_mass(sample.momenta[:, 0]+sample.momenta[:, 1])**2, atol=1e-12)
    m1, m2, m3 = MASSES[pair[0]], MASSES[pair[1]], MASSES[spectator]
    def density(s_pair):
        return (np.sqrt(kallen(sqrt_s**2, s_pair, m3**2, atol=1e-12))
                *np.sqrt(kallen(s_pair, m1**2, m2**2, atol=1e-12))
                /(128*np.pi**3*sqrt_s**2*s_pair))
    expected = quad(density, low**2, high**2, epsabs=1e-12)[0]
    assert sample.weights_gev2.mean() == pytest.approx(expected, rel=0.005)


def test_conditional_mass_window_rejects_invalid_and_masks_empty():
    config = SobolConfig(5)
    assert sample_three_body_mass_window(2., MASSES, (0, 2), (2., 2.1), config) is None
    for pair, interval in (((0, 0), (1., 1.2)), ((0, 2), (1.2, 1.)),
                           ((0, 2), (float("nan"), 1.2))):
        with pytest.raises(ValueError):
            sample_three_body_mass_window(2., MASSES, pair, interval, config)


def test_reduced_global_azimuth_sampler_keeps_volume_and_nested_points():
    pair = (0, 2)
    low, high = 1.55, 1.70
    small = sample_three_body_mass_window(2., MASSES, pair, (low, high),
        SobolConfig(8), reduce_global_azimuth=True)
    large = sample_three_body_mass_window(2., MASSES, pair, (low, high),
        SobolConfig(9), reduce_global_azimuth=True)
    np.testing.assert_array_equal(small.momenta, large.momenta[:len(small.momenta)])
    validate_final_state(large.initial, large.momenta, MASSES, atol=1e-12)
    assert np.allclose(large.momenta[:,1,2], 0., atol=1e-12)
    full = sample_three_body_mass_window(2., MASSES, pair, (low, high),
        SobolConfig(12), reduce_global_azimuth=True)
    standard = sample_three_body_mass_window(2., MASSES, pair, (low, high), SobolConfig(12))
    assert full.weights_gev2.mean() == pytest.approx(standard.weights_gev2.mean(), rel=.005)
