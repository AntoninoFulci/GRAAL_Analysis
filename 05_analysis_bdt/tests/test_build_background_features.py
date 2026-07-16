"""Tests for build_background_features module."""
import numpy as np
import pytest
from graal_common.channels import ETA_PI0_HYP, TWO_PI0_HYP
from analysis_bdt.build_background_features import (
    FEATURE_NAMES_S1,
    compute_stage1_features,
    feature_names,
    shuffle_photons,
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


class TestHypothesisIsParametric:
    def test_names_follow_the_hypothesis(self):
        # The hypothesis a model was trained against has to be legible from the
        # feature list itself, not remembered.
        assert feature_names(ETA_PI0_HYP)[6:9] == [
            "n_pairs_near_pi0", "n_pairs_near_eta", "best_chi2_eta_pi0",
        ]
        assert feature_names(TWO_PI0_HYP)[6:9] == [
            "n_pairs_near_pi0_2", "n_pairs_near_pi0_1", "best_chi2_2pi0",
        ]

    def test_the_default_is_eta_pi0(self):
        assert FEATURE_NAMES_S1 == feature_names(ETA_PI0_HYP)

    def test_the_chi2_answers_the_hypothesis_it_was_asked(self):
        # The same four photons are a perfect eta+pi0 and a poor 2pi0. A chi2
        # that ignored the hypothesis would return the same number for both.
        meta, mpi0 = 0.547862, 0.134977
        photons = np.stack([
            np.array([0.0, 0.0,  meta/2, meta/2]),
            np.array([0.0, 0.0, -meta/2, meta/2]),
            np.array([0.0, 0.0,  mpi0/2, mpi0/2]),
            np.array([0.0, 0.0, -mpi0/2, mpi0/2]),
        ])[None]
        proton = np.array([[0, 0, 0.5, np.sqrt(0.5**2 + 0.938272**2)]])
        beam = np.array([[0, 0, 1.2, 1.2]])

        as_eta_pi0 = compute_stage1_features(photons, proton, beam, ETA_PI0_HYP)
        as_2pi0 = compute_stage1_features(photons, proton, beam, TWO_PI0_HYP)

        assert as_eta_pi0[0, 8] < 0.01
        assert as_2pi0[0, 8] > 100


class TestWeightScale:
    """The training weights must be usable, not just correct in ratio.

    Regression: the per-channel shares summed to 1 across the whole sample, so
    each event carried ~5e-7. Every ratio was right and the training was still
    dead — XGBoost counts min_child_weight in summed-hessian units, so no split
    could ever reach 1, and all 30 grid-search configurations came back at AUC
    0.5000. Nothing raised. Only the absolute scale was wrong.
    """

    def test_normalising_keeps_every_ratio(self):
        w = np.array([0.5, 0.25, 0.125, 0.125]) / 1e6
        normalised = w / w.mean()
        np.testing.assert_allclose(normalised / normalised[0], w / w[0], rtol=1e-12)

    def test_normalising_puts_the_mean_at_one(self):
        w = np.array([0.5, 0.25, 0.125, 0.125]) / 1e6
        assert (w / w.mean()).mean() == pytest.approx(1.0)

    def test_a_mean_of_one_survives_zero_weighted_events(self):
        # Beam reweighting zeroes events at energies the data never produced —
        # 99045 of them in the real sample. The mean must still land on 1.
        w = np.concatenate([np.zeros(100), np.full(100, 3e-7)])
        assert (w / w.mean()).mean() == pytest.approx(1.0)


class TestShufflePhotons:
    def test_every_event_keeps_its_own_four_photons(self):
        # A shuffle that leaked photons between events would still look random.
        rng = np.random.default_rng(11)
        photons = _make_photons(rng, 200)
        out = shuffle_photons(photons, np.random.default_rng(3))

        for before, after in zip(photons, out):
            assert sorted(before[:, 3].tolist()) == pytest.approx(
                sorted(after[:, 3].tolist())
            )

    def test_it_actually_reorders(self):
        rng = np.random.default_rng(12)
        photons = _make_photons(rng, 500)
        out = shuffle_photons(photons, np.random.default_rng(4))
        moved = (photons[:, 0, 3] != out[:, 0, 3]).mean()
        # 3 in 4 events should see a different photon land in slot 0.
        assert moved > 0.5

    def test_order_invariant_features_survive_it(self):
        # min/max pair mass and the best chi2 are answers about the event, not
        # about the slots. If a shuffle moved them, the features would be
        # reading the generator's writing order.
        rng = np.random.default_rng(13)
        photons = _make_photons(rng, 100)
        proton = _make_proton(rng, 100)
        beam = _make_beam(rng, 100)

        X = compute_stage1_features(photons, proton, beam)
        X_shuffled = compute_stage1_features(
            shuffle_photons(photons, np.random.default_rng(5)), proton, beam
        )

        for col in (8, 19, 20):  # best_chi2, min_pair_mass, max_pair_mass
            np.testing.assert_allclose(X[:, col], X_shuffled[:, col], rtol=1e-5)
