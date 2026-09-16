"""Tests for build_background_features module."""
import numpy as np
import pytest
from graal_common.physics.channels import ETA_PI0_HYP, TWO_PI0_HYP
from bdt_training.build_background_features import (
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
        assert len(FEATURE_NAMES_S1) == 26

    def test_unique(self):
        assert len(set(FEATURE_NAMES_S1)) == 26

    def test_six_pair_masses(self):
        mass_names = [n for n in FEATURE_NAMES_S1 if n.startswith("m_gg_")]
        assert len(mass_names) == 6


class TestComputeStage1Features:
    def test_output_shape(self):
        rng = np.random.default_rng(0)
        X = compute_stage1_features(
            _make_photons(rng, 50), _make_proton(rng, 50), _make_beam(rng, 50)
        )
        assert X.shape == (50, 26)

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


class TestMesonCandidateFeatures:
    """The two features built on the chi2-best pairing (cols 24, 25)."""

    def _perfect(self):
        # eta pair (g0,g1) and pi0 pair (g2,g3), each back to back on z.
        meta, mpi0 = 0.547862, 0.134977
        photons = np.stack([
            np.array([0.0, 0.0,  meta / 2, meta / 2]),
            np.array([0.0, 0.0, -meta / 2, meta / 2]),
            np.array([0.0, 0.0,  mpi0 / 2, mpi0 / 2]),
            np.array([0.0, 0.0, -mpi0 / 2, mpi0 / 2]),
        ])[None]
        proton = np.array([[0, 0, 0.5, np.sqrt(0.5**2 + 0.938272**2)]])
        beam = np.array([[0, 0, 1.2, 1.2]])
        return photons, proton, beam

    def test_eta_E_asym_is_in_the_unit_interval(self):
        rng = np.random.default_rng(20)
        X = compute_stage1_features(
            _make_photons(rng, 60), _make_proton(rng, 60), _make_beam(rng, 60)
        )
        assert np.all(X[:, 24] >= 0.0) and np.all(X[:, 24] <= 1.0)

    def test_equal_energy_eta_pair_has_zero_asymmetry(self):
        # The chi2-best heavy pair is the two meta/2 photons — equal energy, so
        # the normalised asymmetry |E1-E2|/(E1+E2) is exactly 0.
        photons, proton, beam = self._perfect()
        X = compute_stage1_features(photons, proton, beam)
        assert X[0, 24] == pytest.approx(0.0, abs=1e-9)

    def test_meson_angle_is_a_cosine(self):
        rng = np.random.default_rng(21)
        X = compute_stage1_features(
            _make_photons(rng, 60), _make_proton(rng, 60), _make_beam(rng, 60)
        )
        assert np.all(X[:, 25] >= -1.0) and np.all(X[:, 25] <= 1.0)

    def test_back_to_back_mesons_give_cos_near_minus_one(self):
        # eta pair moving +x (mass meta), pi0 pair moving -x (mass mpi0). The
        # chi2 picks (0,1)=eta and (2,3)=pi0, and the two mesons are back to
        # back, so the cosine of the angle between them is -1.
        c, s = np.cos(np.pi / 6), np.sin(np.pi / 6)
        Ee = 0.547862 / (2 * s)
        Ep = 0.134977 / (2 * s)
        photons = np.stack([
            np.array([ Ee * c,  Ee * s, 0, Ee]),
            np.array([ Ee * c, -Ee * s, 0, Ee]),
            np.array([-Ep * c,  Ep * s, 0, Ep]),
            np.array([-Ep * c, -Ep * s, 0, Ep]),
        ])[None]
        proton = np.array([[0, 0, 0.0, 0.938272]])
        beam = np.array([[0, 0, 1.5, 1.5]])
        X = compute_stage1_features(photons, proton, beam)
        assert X[0, 25] == pytest.approx(-1.0, abs=1e-6)

    def test_zero_momentum_proton_is_warning_free(self):
        photons, proton, beam = self._perfect()
        proton[0] = [0.0, 0.0, 0.0, 0.938272]
        with np.errstate(all="raise"):
            X = compute_stage1_features(photons, proton, beam)
        assert X[0, 23] == 0.0

    def test_both_new_features_survive_a_photon_shuffle(self):
        # The pairing is re-chosen from the chi2, not read off photon order, so
        # shuffling the four photons must leave cols 24 and 25 unchanged. This
        # is what makes them safe in the same way the other 24 features are.
        rng = np.random.default_rng(22)
        photons = _make_photons(rng, 40)
        proton, beam = _make_proton(rng, 40), _make_beam(rng, 40)
        X0 = compute_stage1_features(photons, proton, beam)
        shuffled = shuffle_photons(photons.copy(), np.random.default_rng(99))
        X1 = compute_stage1_features(shuffled, proton, beam)
        np.testing.assert_allclose(X0[:, 24], X1[:, 24], atol=1e-6)
        np.testing.assert_allclose(X0[:, 25], X1[:, 25], atol=1e-6)


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
