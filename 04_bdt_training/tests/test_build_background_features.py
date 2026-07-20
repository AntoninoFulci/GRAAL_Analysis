"""Tests for build_background_features module."""
import numpy as np
import pytest
from graal_common.channels import ETA_PI0_HYP, M_ETA, M_PI0, M_PROTON, MCChannel, TWO_PI0_HYP
from bdt_training.build_background_features import (
    ChannelYield,
    FEATURE_NAMES_S1,
    channel_yield,
    compute_shares,
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


def _bkg(name, sigma=1.0, e_ref=1.2):
    return MCChannel(
        name=name,
        sigma_ref_ub=sigma,
        e_ref_gev=e_ref,
        production_masses=(M_PROTON, M_PI0, M_PI0),
    )


def _signal():
    return MCChannel(
        name="eta_pi0",
        sigma_ref_ub=None,
        e_ref_gev=None,
        production_masses=(M_PROTON, M_ETA, M_PI0),
    )


def _slaved(br=0.830):
    return MCChannel(
        name="eta_pi0_via_3pi0",
        sigma_ref_ub=None,
        e_ref_gev=None,
        production_masses=(M_PROTON, M_ETA, M_PI0),
        signal_br_ratio=br,
    )


class TestChannelYield:
    def test_divides_by_the_generated_count_not_the_survivor_count(self):
        # Generated count is bookkeeping — an arbitrary choice of how many
        # events to simulate — and must be erased.
        c = _bkg("probe")
        beam_E = np.full(100, 1.3)
        w = np.ones(100)
        y_small = channel_yield(c, beam_E, w, n_gen=1000)
        y_big = channel_yield(c, beam_E, w, n_gen=2000)
        assert y_big.y_sigma == pytest.approx(y_small.y_sigma / 2.0)

    def test_acceptance_is_not_erased(self):
        # THE REGRESSION TEST. Fails on the pre-plan code, where every channel
        # was rescaled to its share regardless of how many events survived.
        #
        # Two identical channels, one with half the survivors, same N_gen:
        # half the yield. Without this, an 8-photon channel that must lose 4 of
        # its photons is weighted as though it reconstructed as efficiently as
        # a 4-photon one.
        c = _bkg("probe")
        n_gen = 1000
        full = channel_yield(c, np.full(400, 1.3), np.ones(400), n_gen)
        half = channel_yield(c, np.full(200, 1.3), np.ones(200), n_gen)
        assert half.y_sigma == pytest.approx(full.y_sigma / 2.0)

    def test_y_unit_ignores_the_cross_section(self):
        # y_unit is the sigma=1 yield: flux x acceptance alone. It is what lets
        # the slaved channel be weighted without naming sigma(signal).
        c = _bkg("probe", sigma=5.0)
        y = channel_yield(c, np.full(100, 1.3), np.full(100, 2.0), n_gen=500)
        assert y.y_unit == pytest.approx(100 * 2.0 / 500)

    def test_y_sigma_is_none_for_a_channel_without_one(self):
        y = channel_yield(_signal(), np.full(10, 1.3), np.ones(10), n_gen=100)
        assert y.y_sigma is None
        assert y.y_unit == pytest.approx(10 / 100)

    def test_zero_weighted_events_do_not_contribute(self):
        # beam_spectrum.reweight zeroes events the data never produced, and
        # events in bins where the MC is too thin to give a density. Those must
        # not buy the channel any weight.
        c = _bkg("probe")
        w = np.concatenate([np.ones(50), np.zeros(50)])
        y_half = channel_yield(c, np.full(100, 1.3), w, n_gen=1000)
        y_full = channel_yield(c, np.full(50, 1.3), np.ones(50), n_gen=1000)
        assert y_half.y_sigma == pytest.approx(y_full.y_sigma)

    def test_refuses_a_non_positive_generated_count(self):
        with pytest.raises(ValueError, match="n_gen must be positive"):
            channel_yield(_bkg("probe"), np.full(10, 1.3), np.ones(10), n_gen=0)


class TestComputeShares:
    def _yields(self):
        sig = ChannelYield(_signal(), y_sigma=None, y_unit=1.0, is_signal=True)
        a = ChannelYield(_bkg("pi0pi0"), y_sigma=3.0, y_unit=1.0, is_signal=False)
        b = ChannelYield(_bkg("3pi0"), y_sigma=1.0, y_unit=1.0, is_signal=False)
        return [sig, a, b]

    def test_the_signal_gets_exactly_its_prior(self):
        assert compute_shares(self._yields(), 0.5)["eta_pi0"] == pytest.approx(0.5)

    def test_everything_sums_to_one(self):
        assert sum(compute_shares(self._yields(), 0.5).values()) == pytest.approx(1.0)

    def test_backgrounds_split_by_their_yields(self):
        # 3:1 in yield is 3:1 in share. This is the real physics the BDT should
        # know: how much of the contamination is pi0pi0 rather than 3pi0.
        shares = compute_shares(self._yields(), 0.5)
        assert shares["pi0pi0"] == pytest.approx(0.5 * 0.75)
        assert shares["3pi0"] == pytest.approx(0.5 * 0.25)

    def test_a_slaved_channel_is_weighted_by_br_times_acceptance(self):
        sig = ChannelYield(_signal(), y_sigma=None, y_unit=2.0, is_signal=True)
        slaved = ChannelYield(_slaved(0.830), y_sigma=None, y_unit=0.2, is_signal=False)
        bkg = ChannelYield(_bkg("pi0pi0"), y_sigma=1.0, y_unit=1.0, is_signal=False)
        shares = compute_shares([sig, slaved, bkg], 0.5)
        # 0.5 * 0.830 * (0.2 / 2.0)
        assert shares["eta_pi0_via_3pi0"] == pytest.approx(0.5 * 0.830 * 0.1)

    def test_the_slaved_share_depends_only_on_the_acceptance_ratio(self):
        # The point of slaving. sigma(gamma p -> p eta pi0) is the measurement;
        # it appears identically in numerator and denominator and cancels. No
        # absolute cross-section may enter this share by any path — so scaling
        # both yields together (which is what an assumed sigma would do) must
        # leave the share untouched.
        base = compute_shares(
            [
                ChannelYield(_signal(), y_sigma=None, y_unit=2.0, is_signal=True),
                ChannelYield(_slaved(), y_sigma=None, y_unit=0.2, is_signal=False),
                ChannelYield(_bkg("pi0pi0"), y_sigma=1.0, y_unit=1.0, is_signal=False),
            ],
            0.5,
        )
        doubled = compute_shares(
            [
                ChannelYield(_signal(), y_sigma=None, y_unit=4.0, is_signal=True),
                ChannelYield(_slaved(), y_sigma=None, y_unit=0.4, is_signal=False),
                ChannelYield(_bkg("pi0pi0"), y_sigma=1.0, y_unit=1.0, is_signal=False),
            ],
            0.5,
        )
        assert doubled["eta_pi0_via_3pi0"] == pytest.approx(base["eta_pi0_via_3pi0"])

    def test_acceptance_keeps_the_slaved_share_usable(self):
        # Slaving to the BR alone would hand it 0.5 * 0.830 = 0.415, crushing
        # every real background into the remaining 8.5%. The acceptance ratio
        # is not a refinement; it is what makes the slaving usable at all.
        sig = ChannelYield(_signal(), y_sigma=None, y_unit=1.0, is_signal=True)
        slaved = ChannelYield(_slaved(), y_sigma=None, y_unit=0.1, is_signal=False)
        bkg = ChannelYield(_bkg("pi0pi0"), y_sigma=1.0, y_unit=1.0, is_signal=False)
        shares = compute_shares([sig, slaved, bkg], 0.5)
        assert shares["eta_pi0_via_3pi0"] < 0.1
        assert shares["pi0pi0"] > 0.4

    def test_refuses_a_prior_that_leaves_no_room_for_backgrounds(self):
        sig = ChannelYield(_signal(), y_sigma=None, y_unit=1.0, is_signal=True)
        slaved = ChannelYield(_slaved(0.830), y_sigma=None, y_unit=1.0, is_signal=False)
        bkg = ChannelYield(_bkg("pi0pi0"), y_sigma=1.0, y_unit=1.0, is_signal=False)
        # 0.9 + 0.9*0.830 > 1: the ordinary backgrounds would need negative weight.
        with pytest.raises(ValueError, match="no weight left"):
            compute_shares([sig, slaved, bkg], 0.9)

    def test_refuses_a_prior_outside_zero_to_one(self):
        with pytest.raises(ValueError, match="strictly between 0 and 1"):
            compute_shares(self._yields(), 1.0)

    def test_refuses_more_than_one_signal(self):
        sig = ChannelYield(_signal(), y_sigma=None, y_unit=1.0, is_signal=True)
        bkg = ChannelYield(_bkg("pi0pi0"), y_sigma=1.0, y_unit=1.0, is_signal=False)
        with pytest.raises(ValueError, match="exactly one signal"):
            compute_shares([sig, sig, bkg], 0.5)

    def test_refuses_a_signal_with_no_surviving_weight(self):
        sig = ChannelYield(_signal(), y_sigma=None, y_unit=0.0, is_signal=True)
        bkg = ChannelYield(_bkg("pi0pi0"), y_sigma=1.0, y_unit=1.0, is_signal=False)
        with pytest.raises(ValueError, match="no weight left"):
            compute_shares([sig, bkg], 0.5)

    def test_refuses_backgrounds_with_no_yield_between_them(self):
        sig = ChannelYield(_signal(), y_sigma=None, y_unit=1.0, is_signal=True)
        bkg = ChannelYield(_bkg("pi0pi0"), y_sigma=0.0, y_unit=1.0, is_signal=False)
        with pytest.raises(ValueError, match="no weight left"):
            compute_shares([sig, bkg], 0.5)

    def test_refuses_a_weightless_ordinary_background_with_a_clear_error(self):
        # eta_pi0 carries no cross-section by design. When something other than
        # eta_pi0 is the signal, eta_pi0 becomes an ordinary background with
        # y_sigma=None. That must raise a legible error naming the channel, not
        # a bare TypeError when None reaches the yield sum. (Regression: an
        # earlier version summed the None and crashed with
        # "unsupported operand type(s) for +: 'int' and 'NoneType'".)
        signal = ChannelYield(_bkg("pi0pi0"), y_sigma=1.0, y_unit=1.0, is_signal=True)
        weightless = ChannelYield(_signal(), y_sigma=None, y_unit=1.0, is_signal=False)
        with pytest.raises(ValueError, match="no cross-section to be weighted by"):
            compute_shares([signal, weightless], 0.5)
