"""Tests for photon_loss module."""
import numpy as np
import pytest
from analysis.ml.photon_loss import LossParams, apply_loss_events, estimate_survival, p_loss


def make_rng(seed: int = 0) -> np.random.Generator:
    return np.random.default_rng(seed)


class TestPLoss:
    def test_high_energy_central_angle_low_loss(self):
        """High-energy, central photon (theta=1.0 rad, 57 deg) should have near-zero loss."""
        params = LossParams()
        p = p_loss(np.array([0.5]), np.array([1.0]), params)
        assert p[0] < 0.10

    def test_low_energy_high_loss(self):
        """Below-threshold photon should have high loss probability."""
        params = LossParams()
        p = p_loss(np.array([0.01]), np.array([0.2]), params)
        assert p[0] > 0.85

    def test_large_angle_high_loss(self):
        """Photon far outside acceptance angle should have high loss probability."""
        params = LossParams()
        p = p_loss(np.array([0.3]), np.array([2.8]), params)
        assert p[0] > 0.85

    def test_output_range(self):
        """p_loss must be in [0, 1]."""
        rng = make_rng()
        Es = rng.uniform(0.01, 1.0, 1000)
        thetas = rng.uniform(0.0, np.pi, 1000)
        p = p_loss(Es, thetas, LossParams())
        assert np.all(p >= 0) and np.all(p <= 1)

    def test_vectorised_shape(self):
        """Output shape matches input shape."""
        Es = np.ones((10, 6)) * 0.3
        thetas = np.ones((10, 6)) * 0.5
        p = p_loss(Es, thetas, LossParams())
        assert p.shape == (10, 6)


class TestApplyLossEvents:
    def test_all_survive_high_energy(self):
        """With very high energy photons at small angles, most events survive if n_photons == n_keep."""
        params = LossParams(E_thr=0.001, sigma_E=0.0001, theta_min_acc=0.01, theta_max_acc=6.0, sigma_theta=0.01)
        N = 500
        Es = np.ones((N, 4)) * 0.8
        thetas = np.ones((N, 4)) * 0.2
        rng = make_rng()
        mask = apply_loss_events(Es, thetas, rng, params, n_keep=4)
        assert mask.sum() > 480

    def test_return_shape(self):
        Es = np.ones((100, 6)) * 0.3
        thetas = np.ones((100, 6)) * 0.5
        mask = apply_loss_events(Es, thetas, make_rng(), LossParams())
        assert mask.shape == (100,)
        assert mask.dtype == bool


class TestEstimateSurvival:
    def test_returns_float_in_range(self):
        rng = np.random.default_rng(0)
        Es = rng.uniform(0.1, 0.8, (1000, 6))
        thetas = rng.uniform(0.2, 2.5, (1000, 6))
        p = estimate_survival(Es, thetas, LossParams(), n_keep=4)
        assert 0.0 <= p <= 1.0

    def test_more_photons_lower_all_survive(self):
        """P(all 4 of 4 survive) > P(all 6 of 6 survive): always true for p < 1."""
        rng = np.random.default_rng(1)
        params = LossParams()
        Es4 = rng.uniform(0.1, 0.6, (2000, 4))
        Es6 = rng.uniform(0.1, 0.6, (2000, 6))
        thetas4 = rng.uniform(0.5, 1.5, (2000, 4))
        thetas6 = rng.uniform(0.5, 1.5, (2000, 6))
        p_4of4 = estimate_survival(Es4, thetas4, params, n_keep=4, n_trials=5)
        p_6of6 = estimate_survival(Es6, thetas6, params, n_keep=6, n_trials=5)
        assert p_4of4 > p_6of6
