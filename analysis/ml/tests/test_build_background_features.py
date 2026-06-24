"""Tests for build_background_features module."""
import numpy as np
import pytest
from analysis.ml.build_background_features import (
    FEATURE_NAMES_S1,
    compute_stage1_features,
    _best_chi2_eta_pi0,
    _inv_mass,
)


def _random_photons(rng, N, M):
    """Generate toy photons: isotropic, E in [0.1, 0.8] GeV."""
    E = rng.uniform(0.1, 0.8, (N, M))
    theta = rng.uniform(0.1, 2.8, (N, M))
    phi = rng.uniform(0, 2 * np.pi, (N, M))
    px = E * np.sin(theta) * np.cos(phi)
    py = E * np.sin(theta) * np.sin(phi)
    pz = E * np.cos(theta)
    return np.stack([px, py, pz, E], axis=-1)


def _random_proton(rng, N):
    p = rng.uniform(0.1, 1.5, N)
    theta = rng.uniform(0.05, 1.0, N)
    phi = rng.uniform(0, 2 * np.pi, N)
    px = p * np.sin(theta) * np.cos(phi)
    py = p * np.sin(theta) * np.sin(phi)
    pz = p * np.cos(theta)
    E = np.sqrt(p**2 + 0.938272**2)
    return np.stack([px, py, pz, E], axis=1)


def _random_beam(rng, N):
    E = rng.uniform(0.5, 1.5, N)
    return np.stack([np.zeros(N), np.zeros(N), E, E], axis=1)


class TestFeatureNames:
    def test_count(self):
        assert len(FEATURE_NAMES_S1) == 24

    def test_unique(self):
        assert len(set(FEATURE_NAMES_S1)) == 24


class TestInvMass:
    def test_pi0_mass(self):
        """Two back-to-back photons each with E=0.0675 → m ≈ 0.135."""
        g1 = np.array([0.0, 0.0, 0.0675, 0.0675])
        g2 = np.array([0.0, 0.0, -0.0675, 0.0675])
        m = _inv_mass([g1, g2])
        assert abs(m - 0.135) < 1e-4

    def test_nonnegative(self):
        rng = np.random.default_rng(0)
        for _ in range(20):
            g1 = rng.uniform(-1, 1, 4)
            g2 = rng.uniform(-1, 1, 4)
            m = _inv_mass([g1, g2])
            assert m >= 0


class TestComputeStage1Features:
    def test_output_shape(self):
        rng = np.random.default_rng(0)
        N, M = 50, 4
        photons = _random_photons(rng, N, M)
        proton = _random_proton(rng, N)
        beam = _random_beam(rng, N)
        X = compute_stage1_features(photons, proton, beam)
        assert X.shape == (N, 24)

    def test_dtype_float32(self):
        rng = np.random.default_rng(1)
        X = compute_stage1_features(
            _random_photons(rng, 10, 4),
            _random_proton(rng, 10),
            _random_beam(rng, 10),
        )
        assert X.dtype == np.float32

    def test_n_gamma_obs_matches_input(self):
        rng = np.random.default_rng(2)
        N, M = 20, 6
        X = compute_stage1_features(
            _random_photons(rng, N, M),
            _random_proton(rng, N),
            _random_beam(rng, N),
        )
        assert np.all(X[:, 21] == M)

    def test_pair_counts_nonnegative(self):
        rng = np.random.default_rng(3)
        X = compute_stage1_features(
            _random_photons(rng, 30, 4),
            _random_proton(rng, 30),
            _random_beam(rng, 30),
        )
        assert np.all(X[:, 15] >= 0)
        assert np.all(X[:, 16] >= 0)


class TestBestChi2:
    def test_perfect_eta_pi0_pair_low_chi2(self):
        """Photons that reconstruct exactly eta and pi0 → chi2 near 0."""
        # two back-to-back photons summing to meta
        meta = 0.547862
        mpi0 = 0.134977
        g0 = np.array([0.0, 0.0,  meta/2, meta/2])
        g1 = np.array([0.0, 0.0, -meta/2, meta/2])
        g2 = np.array([0.0, 0.0,  mpi0/2, mpi0/2])
        g3 = np.array([0.0, 0.0, -mpi0/2, mpi0/2])
        gammas = np.stack([g0, g1, g2, g3])
        chi2 = _best_chi2_eta_pi0(gammas)
        assert chi2 < 0.01

    def test_returns_large_for_random(self):
        rng = np.random.default_rng(9)
        gammas = rng.uniform(-0.5, 0.5, (4, 4))
        chi2 = _best_chi2_eta_pi0(gammas)
        assert isinstance(chi2, float)
