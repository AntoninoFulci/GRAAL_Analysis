import numpy as np
import pytest

from analysis.ml import build_features as bf
from analysis.ml import physics

MC_PATH = "simulation/eta_pi0_mc.root"


def test_load_photons_shape_and_masses():
    p = bf.load_photons(MC_PATH, n_max=2000)
    assert p.shape == (2000, 4, 4)          # [event, photon, (E,px,py,pz)]
    # photons 0,1 are the eta decay -> reconstruct ~eta mass (smeared)
    m_eta = physics.invariant_mass(p[:, 0], p[:, 1])
    m_pi0 = physics.invariant_mass(p[:, 2], p[:, 3])
    assert 0.45 < np.median(m_eta) < 0.65
    assert 0.10 < np.median(m_pi0) < 0.18


def test_shuffle_is_permutation():
    photons = bf.load_photons(MC_PATH, n_max=1000)
    P, perm = bf.shuffle_photons(photons, seed=1)
    # every row of perm is a permutation of {0,1,2,3}
    assert np.all(np.sort(perm, axis=1) == np.arange(4))
    # P[n, j] == photons[n, perm[n, j]]
    assert np.allclose(P[np.arange(1000)[:, None], np.arange(4)],
                       photons[np.arange(1000)[:, None], perm])


def test_truth_label_matches_eta_grouping():
    photons = bf.load_photons(MC_PATH, n_max=5000)
    P, perm = bf.shuffle_photons(photons, seed=1)
    truth = bf.truth_pairing_index(perm)
    # the truth pairing groups the two eta photons (orig idx <2) together
    for k in range(3):
        (i, j), (a, b) = bf.PAIRINGS[k]
        sel = truth == k
        is_eta = perm[sel] < 2
        same_pair = is_eta[:, i].astype(int) + is_eta[:, j].astype(int)
        assert np.all((same_pair == 0) | (same_pair == 2))


def test_no_positional_leakage_before_chi2_ordering():
    # The shuffle must make the truth pairing equally likely to be any of the
    # three pairings; otherwise the model could exploit photon input position.
    # This is checked on the RAW truth index (before chi2 ordering): it must be
    # ~uniform (1/3 each). NB: after chi2 ordering the label distribution is
    # deliberately skewed toward slot 0 (the chi2 pick is usually correct on
    # this clean MC) -- that skew is real physics, not leakage.
    photons = bf.load_photons(MC_PATH, n_max=50000)
    P, perm = bf.shuffle_photons(photons, seed=1)
    truth = bf.truth_pairing_index(perm)
    frac = np.bincount(truth, minlength=3) / len(truth)
    assert np.all(np.abs(frac - 1 / 3) < 0.02)


def test_feature_matrix_shape_and_names():
    photons = bf.load_photons(MC_PATH, n_max=1000)
    X, y, masses, names = bf.build(photons, seed=1)
    assert X.shape == (1000, 54)
    assert len(names) == 54
    assert masses.shape == (1000, 3, 2)
    assert set(np.unique(y)).issubset({0, 1, 2})


def test_chi2_baseline_is_block_zero():
    # block 0 is the minimum-chi2 pairing by construction; its chi2 feature
    # must be <= the chi2 feature of blocks 1 and 2.
    photons = bf.load_photons(MC_PATH, n_max=2000)
    X, y, masses, names = bf.build(photons, seed=1)
    chi2_cols = [names.index(f"chi2_block{b}") for b in range(3)]
    c0, c1, c2 = X[:, chi2_cols[0]], X[:, chi2_cols[1]], X[:, chi2_cols[2]]
    assert np.all(c0 <= c1 + 1e-9)
    assert np.all(c0 <= c2 + 1e-9)
