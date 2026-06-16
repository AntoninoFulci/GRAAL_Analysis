"""Build the feature matrix + truth labels for the photon-pairing BDT study.

Reads the labelled MC (tree `mc` of eta_pi0_mc.root), shuffles the four
photons per event, builds the three disjoint pairings ordered by chi2, and
emits a 54-dim feature row plus a class label (which chi2-ordered slot holds
the truth pairing) per event.
"""
import numpy as np
import uproot

from analysis.ml import physics

SEED = 42
PAIRINGS = [((0, 1), (2, 3)), ((0, 2), (1, 3)), ((0, 3), (1, 2))]
PHOTON_BRANCHES = ["eta_gamma1", "eta_gamma2", "pi0_gamma1", "pi0_gamma2"]


def load_photons(root_path, tree="mc", n_max=None):
    """Return photons as a (N, 4, 4) array; last axis is [E, px, py, pz].

    Photon order matches truth: index 0,1 -> eta decay; 2,3 -> pi0 decay.
    """
    t = uproot.open(f"{root_path}:{tree}")
    arrays = t.arrays(PHOTON_BRANCHES, entry_stop=n_max, library="ak")
    n = len(arrays)
    out = np.empty((n, 4, 4), dtype=np.float64)
    for i, name in enumerate(PHOTON_BRANCHES):
        v = arrays[name]
        out[:, i, 0] = np.asarray(v["fE"])
        out[:, i, 1] = np.asarray(v["fP"]["fX"])
        out[:, i, 2] = np.asarray(v["fP"]["fY"])
        out[:, i, 3] = np.asarray(v["fP"]["fZ"])
    return out


# --- per-block feature names (18 each) -------------------------------------
_BLOCK_FEATURES = [
    "m_low", "m_high", "dm_pi0", "dm_eta",
    "asym_low", "asym_high", "theta_low", "theta_high",
    "E1", "E2", "E3", "E4", "cos_mesons",
    "pt_low", "pt_high", "beta_low", "beta_high", "chi2",
]


def _feature_names():
    names = []
    for b in range(3):
        for f in _BLOCK_FEATURES:
            names.append("chi2_block{}".format(b) if f == "chi2" else "{}_block{}".format(f, b))
    return names


FEATURE_NAMES = _feature_names()


def shuffle_photons(photons, seed=SEED):
    """Randomly permute the 4 photons per event. Returns (P, perm).

    P[n, j] = photons[n, perm[n, j]]; perm[n] is a permutation of {0,1,2,3}.
    """
    rng = np.random.default_rng(seed)
    n = photons.shape[0]
    perm = np.argsort(rng.random((n, 4)), axis=1)
    P = np.take_along_axis(photons, perm[:, :, None], axis=1)
    return P, perm


def truth_pairing_index(perm):
    """Index in PAIRINGS whose one pair contains exactly the two eta photons."""
    n = perm.shape[0]
    is_eta = perm < 2  # eta photons had original index 0,1
    truth = np.full(n, -1, dtype=np.int64)
    for k, ((i, j), _) in enumerate(PAIRINGS):
        in_pair = is_eta[:, i].astype(int) + is_eta[:, j].astype(int)
        grouped = (in_pair == 2) | (in_pair == 0)
        truth = np.where(grouped & (truth < 0), k, truth)
    return truth


def _feature_block(P, pairing):
    """Return (block (N,18), chi2 (N,), m_low (N,), m_high (N,)) for one pairing."""
    (i, j), (k, l) = pairing
    mA = physics.invariant_mass(P[:, i], P[:, j])
    mB = physics.invariant_mass(P[:, k], P[:, l])
    a_low = mA <= mB

    def sel(a, b):
        return np.where(a_low, a, b)

    asymA = physics.energy_asymmetry(P[:, i], P[:, j])
    asymB = physics.energy_asymmetry(P[:, k], P[:, l])
    thA = physics.opening_angle(P[:, i], P[:, j])
    thB = physics.opening_angle(P[:, k], P[:, l])
    mesonA = P[:, i] + P[:, j]
    mesonB = P[:, k] + P[:, l]
    ptA, ptB = physics.pt(mesonA), physics.pt(mesonB)
    beA, beB = physics.beta(mesonA), physics.beta(mesonB)

    m_low, m_high = np.minimum(mA, mB), np.maximum(mA, mB)
    asym_low, asym_high = sel(asymA, asymB), sel(asymB, asymA)
    th_low, th_high = sel(thA, thB), sel(thB, thA)
    pt_low, pt_high = sel(ptA, ptB), sel(ptB, ptA)
    be_low, be_high = sel(beA, beB), sel(beB, beA)
    cos_mes = physics.cos_angle(mesonA, mesonB)
    chi2 = physics.chi2_pairing(m_low, m_high)
    e_sorted = np.sort(P[:, :, 0], axis=1)[:, ::-1]  # (N,4) energies desc

    block = np.column_stack([
        m_low, m_high, np.abs(m_low - physics.MPI0), np.abs(m_high - physics.META),
        asym_low, asym_high, th_low, th_high,
        e_sorted[:, 0], e_sorted[:, 1], e_sorted[:, 2], e_sorted[:, 3], cos_mes,
        pt_low, pt_high, be_low, be_high, chi2,
    ])
    return block, chi2, m_low, m_high


def build(photons, seed=SEED):
    """Return (X (N,54), y (N,), masses (N,3,2), feature_names list)."""
    P, perm = shuffle_photons(photons, seed=seed)
    n = P.shape[0]
    blocks, chi2s, masses = [], [], []
    for pairing in PAIRINGS:
        blk, c, ml, mh = _feature_block(P, pairing)
        blocks.append(blk)
        chi2s.append(c)
        masses.append(np.column_stack([ml, mh]))  # (N,2): [pi0-ish, eta-ish]
    blocks = np.stack(blocks, axis=1)   # (N,3,18)
    chi2s = np.stack(chi2s, axis=1)     # (N,3)
    masses = np.stack(masses, axis=1)   # (N,3,2)

    order = np.argsort(chi2s, axis=1)   # (N,3) ascending chi2
    rows = np.arange(n)[:, None]
    blocks_ord = blocks[rows, order]    # (N,3,18)
    masses_ord = masses[rows, order]    # (N,3,2)
    X = blocks_ord.reshape(n, -1)       # (N,54)

    truth = truth_pairing_index(perm)
    y = np.argmax(order == truth[:, None], axis=1).astype(np.int64)  # slot of truth
    return X, y, masses_ord, FEATURE_NAMES
