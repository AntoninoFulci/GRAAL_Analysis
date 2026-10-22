import numpy as np
import pytest
from mc_simulation.response import harmonic_response


def test_lost_events_and_guard_energy_stay_in_harmonic_denominator():
    # Only two of four guard photons survive: both have cos(2phi)=+1.
    n, moment, cov = harmonic_response(
        np.arange(8),
        np.repeat([0, 1], 4),
        np.tile([0, np.pi / 2, np.pi, 3 * np.pi / 2], 2),
        np.array([0, 2, 4, 5]),
        np.array([0, 0, 1, 1]),
        2,
        3,
    )
    np.testing.assert_array_equal(n, [4, 4])
    np.testing.assert_allclose(moment[0], [[0.5, 0, 0], [0.5, 0, 0]])
    np.testing.assert_allclose(moment[1], [[0, 0.5, 0], [0, 0, 0]], atol=1e-15)
    assert cov[0, 0, 3] == pytest.approx(0.0625)
    assert cov[1, 4, 4] == pytest.approx(0.125)
    # A guard can have no reconstructed support; inference, not this counter,
    # must decide whether its cross section is identifiable.
    assert moment.shape == (2, 2, 3)


def test_duplicate_and_unknown_harmonic_identities_rejected():
    for selected in (np.array([0, 0]), np.array([0, 10])):
        with pytest.raises(ValueError, match="duplicate|absent"):
            harmonic_response(
                np.arange(4),
                np.zeros(4, dtype=int),
                np.zeros(4),
                selected,
                np.array([0, 1]),
                1,
                2,
            )


def test_exposure_weighted_states_share_same_mc_losses_and_covariance():
    # Two selected, two lost. One selected event has no exposure in state H.
    weights = np.array([[[10, 20], [5, -10]], [[20, 0], [6, 0]]])
    n, means, cov = harmonic_response(
        np.arange(4),
        np.zeros(4, dtype=int),
        np.array([0, np.pi / 2, 0, 0]),
        np.array([0, 1]),
        np.array([0, 0]),
        1,
        1,
        selected_weights=weights,
    )
    contributions = np.array(
        [[10, 20, 5, -10], [20, 0, -6, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
    )
    np.testing.assert_allclose(means.ravel(), contributions.mean(axis=0))
    np.testing.assert_allclose(cov[0], np.cov(contributions.T, ddof=0) / n[0])
    assert cov[0, 0, 1] != 0
