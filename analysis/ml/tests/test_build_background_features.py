"""Tests for build_background_features module."""
import numpy as np
import pytest
from analysis.ml.build_background_features import (
    FEATURE_NAMES_S1,
    compute_stage1_features,
    _PAIR_IDX,
)


def _make_photons(rng, N, M=4):
    """Toy photon array (N, M, 4) = [px, py, pz, E] with E > |p|."""
    E = rng.uniform(0.1, 0.8, (N, M))
    theta = rng.uniform(0.1, 2.8, (N, M))
    phi = rng.uniform(0, 2 * np.pi, (N, M))
    px = E * np.sin(theta) * np.cos(phi)
    py = E * np.sin(theta) * np.sin(phi)
    pz = E * np.cos(theta)
    return np.stack([px, py, pz, E], axis=-1)


def _make_proton(rng, N):
    p = rng.uniform(0.1, 1.5, N)
    theta = rng.uniform(0.05, 1.0, N)
    phi = rng.uniform(0, 2 * np.pi, N)
    px = p * np.sin(theta) * np.cos(phi)
    py = p * np.sin(theta) * np.sin(phi)
    pz = p * np.cos(theta)
    E = np.sqrt(p**2 + 0.938272**2)
    return np.stack([px, py, pz, E], axis=1)


def _make_beam(rng, N):
    E = rng.uniform(0.5, 1.5, N)
    return np.stack([np.zeros(N), np.zeros(N), E, E], axis=1)


class TestFeatureNames:
    def test_count(self):
        assert len(FEATURE_NAMES_S1) == 24

    def test_unique(self):
        assert len(set(FEATURE_NAMES_S1)) == 24

    def test_six_pair_masses(self):
        mass_names = [n for n in FEATURE_NAMES_S1 if n.startswith("m_gg_")]
        assert len(mass_names) == 6


class TestComputeStage1Features:
    def test_output_shape(self):
        rng = np.random.default_rng(0)
        X = compute_stage1_features(
            _make_photons(rng, 50), _make_proton(rng, 50), _make_beam(rng, 50)
        )
        assert X.shape == (50, 24)

    def test_dtype_float32(self):
        rng = np.random.default_rng(1)
        X = compute_stage1_features(
            _make_photons(rng, 10), _make_proton(rng, 10), _make_beam(rng, 10)
        )
        assert X.dtype == np.float32

    def test_pair_masses_nonnegative(self):
        rng = np.random.default_rng(2)
        X = compute_stage1_features(
            _make_photons(rng, 30), _make_proton(rng, 30), _make_beam(rng, 30)
        )
        assert np.all(X[:, :6] >= 0)

    def test_pair_counts_nonnegative(self):
        rng = np.random.default_rng(3)
        X = compute_stage1_features(
            _make_photons(rng, 30), _make_proton(rng, 30), _make_beam(rng, 30)
        )
        assert np.all(X[:, 6] >= 0) and np.all(X[:, 7] >= 0)

    def test_best_chi2_nonnegative(self):
        rng = np.random.default_rng(4)
        X = compute_stage1_features(
            _make_photons(rng, 20), _make_proton(rng, 20), _make_beam(rng, 20)
        )
        assert np.all(X[:, 8] >= 0)

    def test_proton_p_nonnegative(self):
        rng = np.random.default_rng(5)
        X = compute_stage1_features(
            _make_photons(rng, 20), _make_proton(rng, 20), _make_beam(rng, 20)
        )
        assert np.all(X[:, 22] >= 0)

    def test_proton_costheta_range(self):
        rng = np.random.default_rng(6)
        X = compute_stage1_features(
            _make_photons(rng, 50), _make_proton(rng, 50), _make_beam(rng, 50)
        )
        assert np.all(X[:, 23] >= -1) and np.all(X[:, 23] <= 1)

    def test_min_max_pair_mass_consistent(self):
        rng = np.random.default_rng(7)
        X = compute_stage1_features(
            _make_photons(rng, 50), _make_proton(rng, 50), _make_beam(rng, 50)
        )
        # min_pair_mass (col 19) <= max_pair_mass (col 20)
        assert np.all(X[:, 19] <= X[:, 20])

    def test_perfect_eta_pi0_low_chi2(self):
        """4 photons that reconstruct exactly eta+pi0 → best_chi2 ≈ 0."""
        meta = 0.547862
        mpi0 = 0.134977
        g0 = np.array([0.0, 0.0,  meta/2, meta/2])
        g1 = np.array([0.0, 0.0, -meta/2, meta/2])
        g2 = np.array([0.0, 0.0,  mpi0/2, mpi0/2])
        g3 = np.array([0.0, 0.0, -mpi0/2, mpi0/2])
        photons = np.stack([g0, g1, g2, g3])[None]  # (1,4,4)
        proton = np.array([[0, 0, 0.5, np.sqrt(0.5**2 + 0.938272**2)]])
        beam   = np.array([[0, 0, 1.2, 1.2]])
        X = compute_stage1_features(photons, proton, beam)
        assert X[0, 8] < 0.01   # best_chi2
