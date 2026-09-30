import numpy as np
import pytest

from graal_theory.kinematics import validate_final_state
from graal_theory.phase_space import (
    BelowThresholdError,
    SobolConfig,
    phase_space_volume_quad,
    sample_three_body,
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
