import numpy as np
import pytest

from graal_theory.kinematics import (
    boost,
    cm_photon_momentum,
    invariant_mass,
    kallen,
    mass_squared,
    s_from_lab_photon_energy,
    two_body_momentum,
    validate_final_state,
)


def test_lab_photon_energy_maps_to_invariant_s():
    assert s_from_lab_photon_energy(1.2, 0.9382720813) == pytest.approx(
        0.9382720813**2 + 2 * 0.9382720813 * 1.2
    )


def test_roundoff_negative_kallen_clamps_but_physical_negative_fails():
    assert kallen(4.0 - 1e-15, 1.0, 1.0, atol=1e-14) == pytest.approx(0.0)
    with pytest.raises(ValueError, match="nonphysical"):
        kallen(3.0, 1.0, 1.0, atol=1e-14)


def test_two_body_momentum_at_threshold_is_zero():
    assert two_body_momentum(3.0, 1.0, 2.0) == pytest.approx(0.0)


def test_boost_preserves_mass_squared():
    p = np.array([2.0, 0.3, -0.2, 1.0])
    boosted = boost(p, np.array([0.1, -0.05, 0.2]))
    assert mass_squared(boosted) == pytest.approx(mass_squared(p), abs=1e-13)


def test_boost_rejects_superluminal_velocity():
    with pytest.raises(ValueError, match="beta"):
        boost(np.array([1.0, 0.0, 0.0, 0.0]), np.array([1.0, 0.0, 0.0]))


def test_cm_real_photon_energy_equals_momentum_norm():
    sqrt_s = np.sqrt(s_from_lab_photon_energy(1.2, 0.9382720813))
    momentum = cm_photon_momentum(sqrt_s, 0.9382720813)
    expected_energy = (sqrt_s**2 - 0.9382720813**2) / (2.0 * sqrt_s)
    assert np.linalg.norm(momentum) == pytest.approx(expected_energy)


def test_invariant_mass_rejects_spacelike_four_vector():
    with pytest.raises(ValueError, match="nonphysical"):
        invariant_mass(np.array([0.0, 1.0, 0.0, 0.0]))


def test_validate_final_state_reports_event_index():
    initial = np.array([[2.0, 0.0, 0.0, 0.0]])
    final = np.zeros((1, 3, 4))
    with pytest.raises(ValueError, match="event 0"):
        validate_final_state(initial, final, (0.5, 0.5, 0.5), atol=1e-12)
