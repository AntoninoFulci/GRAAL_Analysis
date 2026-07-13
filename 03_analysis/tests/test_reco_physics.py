import numpy as np
import pytest

from analysis import reco_physics as rp

# The eta_pi0 combination table: i1 i2 i3 i4 m_target_12 m_target_34
COMBINATIONS = np.array([
    [0, 1, 2, 3, rp.M_ETA, rp.M_PI0],
    [0, 1, 2, 3, rp.M_PI0, rp.M_ETA],
    [0, 2, 1, 3, rp.M_ETA, rp.M_PI0],
    [0, 2, 1, 3, rp.M_PI0, rp.M_ETA],
    [0, 3, 1, 2, rp.M_ETA, rp.M_PI0],
    [0, 3, 1, 2, rp.M_PI0, rp.M_ETA],
])


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


def test_invariant_mass_of_back_to_back_photons():
    g = _back_to_back_pair(rp.M_ETA, axis=2)
    assert rp.invariant_mass(g[0] + g[1]) == pytest.approx(rp.M_ETA)


def test_chi2_is_zero_when_both_masses_hit_their_targets():
    assert rp.chi2_value(rp.M_ETA, rp.M_ETA, rp.M_PI0, rp.M_PI0) == pytest.approx(0.0)


def test_chi2_is_one_when_one_mass_is_one_resolution_off():
    # a mass one resolution width (8% of the target) away contributes exactly 1
    off_eta = rp.M_ETA * (1 + rp.CHI2_RESOLUTION)
    assert rp.chi2_value(off_eta, rp.M_ETA, rp.M_PI0, rp.M_PI0) == pytest.approx(1.0)


def test_best_combination_finds_the_true_pairing():
    # photons 0,1 -> eta ; photons 2,3 -> pi0. Row 0 is the truth.
    photons = np.vstack([
        _back_to_back_pair(rp.M_ETA, axis=0),
        _back_to_back_pair(rp.M_PI0, axis=1),
    ])
    idx, chi2 = rp.best_combination(photons, COMBINATIONS)
    assert idx == 0
    assert chi2 == pytest.approx(0.0, abs=1e-6)


def test_assign_pairs_sends_the_heavy_target_to_the_eta():
    # row 0: pairs (0,1) and (2,3); the first target (eta) is above 0.4 GeV
    heavy, light = rp.assign_pairs(COMBINATIONS[0], rp.ETA_PI0)
    assert heavy == (0, 1)
    assert light == (2, 3)


def test_assign_pairs_swaps_when_the_heavy_target_comes_second():
    # row 1: same photon pairs, targets (pi0, eta) — so (2,3) is the eta
    heavy, light = rp.assign_pairs(COMBINATIONS[1], rp.ETA_PI0)
    assert heavy == (2, 3)
    assert light == (0, 1)


def test_assign_pairs_keeps_the_table_order_for_two_pi0():
    # both targets are the pi0 mass: there is no heavy meson to promote,
    # so the pairs keep the order the table gives them
    row = np.array([0, 2, 1, 3, rp.M_PI0, rp.M_PI0])
    heavy, light = rp.assign_pairs(row, rp.TWO_PI0)
    assert heavy == (0, 2)
    assert light == (1, 3)
