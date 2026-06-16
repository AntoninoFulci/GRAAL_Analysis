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
