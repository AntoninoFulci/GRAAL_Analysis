"""Tests for the one chi2.

This used to be two: a table-driven loop in the reconstruction and a vectorised
expression in the feature builder. Several of these tests exist to pin down that
they are now the same code — that the number the BDT is handed is the number the
reconstruction minimises, not a lookalike.
"""
import numpy as np
import pytest

from graal_common.channels import (
    CHI2_RESOLUTION,
    ETA_PI0_HYP,
    M_ETA,
    M_PI0,
    TWO_PI0_HYP,
)
from graal_common.pairing import (
    PAIR_IDX,
    PARTITIONS,
    best_chi2,
    best_pairing,
    chi2,
    chi2_per_pairing,
    pair_masses,
    pair_slot,
    pairings,
)


def _back_to_back_pair(mass, axis):
    """Two massless photons whose invariant mass is exactly `mass`.

    Each carries energy mass/2; they fly in opposite directions along `axis`.
    """
    e = mass / 2.0
    p = np.zeros((2, 4))
    p[0, axis] = e
    p[0, 3] = e
    p[1, axis] = -e
    p[1, 3] = e
    return p


def _eta_then_pi0():
    """4 photons: (0,1) make an eta, (2,3) make a pi0."""
    return np.vstack([
        _back_to_back_pair(M_ETA, axis=0),
        _back_to_back_pair(M_PI0, axis=1),
    ])


def _random_photons(rng, n):
    """n events of 4 photons each, massless by construction."""
    E = rng.uniform(0.1, 0.8, (n, 4))
    theta = rng.uniform(0.1, 2.8, (n, 4))
    phi = rng.uniform(0, 2 * np.pi, (n, 4))
    return np.stack([
        E * np.sin(theta) * np.cos(phi),
        E * np.sin(theta) * np.sin(phi),
        E * np.cos(theta),
        E,
    ], axis=-1)


class TestPairMasses:
    def test_back_to_back_photons_give_their_mass(self):
        pm = pair_masses(_eta_then_pi0())
        assert pm[pair_slot(0, 1)] == pytest.approx(M_ETA)
        assert pm[pair_slot(2, 3)] == pytest.approx(M_PI0)

    def test_it_returns_one_mass_per_pair(self):
        assert pair_masses(_eta_then_pi0()).shape == (len(PAIR_IDX),)

    def test_pair_slot_is_order_blind(self):
        assert pair_slot(3, 1) == pair_slot(1, 3)

    def test_one_event_and_a_chunk_go_through_the_same_code(self):
        # The reconstruction asks per event, the feature builder asks per chunk.
        # If those two paths disagreed, the gate and the reco would disagree.
        rng = np.random.default_rng(0)
        photons = _random_photons(rng, 7)
        chunk = pair_masses(photons)
        assert chunk.shape == (7, len(PAIR_IDX))
        for k in range(7):
            np.testing.assert_allclose(pair_masses(photons[k]), chunk[k], rtol=1e-12)

    def test_a_spacelike_pair_reports_zero_not_nan(self):
        # Resolution can push m^2 marginally negative on a genuinely light pair.
        photons = np.zeros((4, 4))
        photons[0] = [1.0, 0.0, 0.0, 0.5]  # |p| > E
        photons[1] = [1.0, 0.0, 0.0, 0.5]
        assert pair_masses(photons)[pair_slot(0, 1)] == 0.0


class TestChi2:
    def test_it_is_zero_when_both_masses_hit_their_targets(self):
        assert chi2(M_ETA, M_PI0, ETA_PI0_HYP) == pytest.approx(0.0)

    def test_one_resolution_off_contributes_exactly_one(self):
        off_eta = M_ETA * (1 + CHI2_RESOLUTION)
        assert chi2(off_eta, M_PI0, ETA_PI0_HYP) == pytest.approx(1.0)

    def test_it_broadcasts(self):
        np.testing.assert_allclose(
            chi2(np.full(5, M_ETA), np.full(5, M_PI0), ETA_PI0_HYP),
            np.zeros(5),
            atol=1e-12,
        )


class TestPairings:
    def test_two_different_mesons_give_six(self):
        # 3 ways to split the photons, times 2 ways to assign the mesons.
        assert len(pairings(ETA_PI0_HYP)) == 6

    def test_identical_mesons_give_three(self):
        # Swapping heavy and light relabels the pairs without asking a different
        # question; scoring both would be the same chi2 twice.
        assert len(pairings(TWO_PI0_HYP)) == 3

    def test_every_pairing_uses_each_photon_exactly_once(self):
        for hyp in (ETA_PI0_HYP, TWO_PI0_HYP):
            for p in pairings(hyp):
                assert sorted([*p.heavy, *p.light]) == [0, 1, 2, 3]

    def test_they_reproduce_the_combination_table_that_used_to_be_on_disk(self):
        # combinations_eta_pi0.txt, row for row: the three partitions, each with
        # the eta first and then the pi0 first. The file carried no information
        # beyond this, which is what made deriving it safe.
        assert [(p.heavy, p.light) for p in pairings(ETA_PI0_HYP)] == [
            ((0, 1), (2, 3)), ((2, 3), (0, 1)),
            ((0, 2), (1, 3)), ((1, 3), (0, 2)),
            ((0, 3), (1, 2)), ((1, 2), (0, 3)),
        ]

    def test_the_partitions_are_the_three_disjoint_splits(self):
        assert PARTITIONS == [((0, 1), (2, 3)), ((0, 2), (1, 3)), ((0, 3), (1, 2))]


class TestBestPairing:
    def test_it_finds_the_true_pairing(self):
        pairing, score = best_pairing(_eta_then_pi0(), ETA_PI0_HYP)
        assert pairing.heavy == (0, 1)
        assert pairing.light == (2, 3)
        assert score == pytest.approx(0.0, abs=1e-6)

    def test_it_sends_the_heavy_pair_to_the_heavy_meson(self):
        # Photons (2,3) make the eta this time. The pairing must follow the
        # masses, not the photon order.
        photons = np.vstack([
            _back_to_back_pair(M_PI0, axis=0),
            _back_to_back_pair(M_ETA, axis=1),
        ])
        pairing, score = best_pairing(photons, ETA_PI0_HYP)
        assert pairing.heavy == (2, 3)
        assert pairing.light == (0, 1)
        assert score == pytest.approx(0.0, abs=1e-6)

    def test_a_degenerate_hypothesis_still_picks_a_pairing(self):
        photons = np.vstack([
            _back_to_back_pair(M_PI0, axis=0),
            _back_to_back_pair(M_PI0, axis=1),
        ])
        pairing, score = best_pairing(photons, TWO_PI0_HYP)
        assert sorted([*pairing.heavy, *pairing.light]) == [0, 1, 2, 3]
        assert score == pytest.approx(0.0, abs=1e-6)


class TestOneImplementation:
    def test_the_features_chi2_is_the_reconstruction_chi2(self):
        # The regression that matters: best_chi2 (feature 8 of the BDT) and the
        # score best_pairing acts on must be the same number for the same event.
        # They were two expressions agreeing by inspection.
        rng = np.random.default_rng(42)
        photons = _random_photons(rng, 30)
        per_event = [best_pairing(photons[k], ETA_PI0_HYP)[1] for k in range(30)]
        np.testing.assert_allclose(
            best_chi2(photons, ETA_PI0_HYP), per_event, rtol=1e-10
        )

    def test_chi2_per_pairing_answers_once_per_pairing(self):
        scores = chi2_per_pairing(pair_masses(_eta_then_pi0()), ETA_PI0_HYP)
        assert scores.shape == (len(pairings(ETA_PI0_HYP)),)
