"""Tests for photon_loss module."""
import numpy as np
import pytest
from analysis.ml.photon_loss import LossParams, apply_loss_events, estimate_survival, p_loss


def make_rng(seed: int = 0) -> np.random.Generator:
    return np.random.default_rng(seed)


class TestPLoss:
    def test_high_energy_low_angle_low_loss(self):
        """High-energy, central photon should have near-zero loss probability."""
        params = LossParams()
        p = p_loss(np.array([0.5]), np.array([0.2]), params)
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
        params = LossParams(E_thr=0.001, sigma_E=0.0001, theta_acc=3.0, sigma_theta=0.01)
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

    def test_stricter_n_keep_lower_survival(self):
        """Requiring all photons to survive is harder than requiring fewer."""
        rng = np.random.default_rng(1)
        Es = rng.uniform(0.1, 0.6, (2000, 4))
        thetas = rng.uniform(0.2, 1.5, (2000, 4))
        p_all4 = estimate_survival(Es, thetas, LossParams(), n_keep=4, n_trials=5)
        p_any3 = estimate_survival(Es, thetas, LossParams(), n_keep=3, n_trials=5)
        # needing all 4 survive is harder than needing exactly 3
        assert p_all4 < p_any3
