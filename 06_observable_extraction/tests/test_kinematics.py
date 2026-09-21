import numpy as np
import pytest

from observable_extraction.core.kinematics import (
    mass_and_phi,
    project_all_pairs,
    project_pair,
)


def test_pair_phi_is_wrapped_into_zero_two_pi():
    first = np.array([0.2, -0.3, 0.1, 0.5])
    second = np.array([0.1, 0.0, 0.2, 0.5])

    projection = project_pair("p_pi0", first, second)

    assert 0.0 <= projection.phi_rad < 2.0 * np.pi
    assert projection.phi_rad == pytest.approx(7.0 * np.pi / 4.0)


def test_longitudinal_boost_does_not_change_pair_phi():
    vectors = np.array([[0.3, 0.4, 0.2, 1.0], [0.3, 0.4, 0.7, 1.3]])

    _, phi = mass_and_phi(vectors)

    assert phi[0] == pytest.approx(phi[1])


def test_project_all_pairs_uses_correct_four_vector_sums():
    proton = np.array([[0.1, 0.0, 0.1, 1.0]])
    eta = np.array([[0.0, 0.2, 0.1, 0.7]])
    pi0 = np.array([[-0.1, 0.0, 0.1, 0.3]])

    projections = project_all_pairs(proton, eta, pi0)

    expected_p_pi0 = proton + pi0
    expected_mass = np.sqrt(
        expected_p_pi0[0, 3] ** 2 - np.dot(expected_p_pi0[0, :3], expected_p_pi0[0, :3])
    )
    assert set(projections) == {"p_pi0", "p_eta", "eta_pi0"}
    assert projections["p_pi0"][0][0] == pytest.approx(expected_mass)


def test_materially_spacelike_pair_is_rejected():
    with pytest.raises(ValueError, match="spacelike"):
        mass_and_phi(np.array([[2.0, 0.0, 0.0, 1.0]]))


def test_tiny_negative_mass_squared_is_clamped_to_zero():
    mass, _ = mass_and_phi(np.array([[1.0 + 1e-14, 0.0, 0.0, 1.0]]))

    assert mass[0] == 0.0
