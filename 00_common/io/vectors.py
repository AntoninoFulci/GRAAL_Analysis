"""Read a ROOT TLorentzVector branch as a plain (N, 4) [px, py, pz, E] array.

uproot-only, so it lives here rather than in trees.py (which deliberately opens
nothing and stays usable from the ROOT side too). The fP/fE unpacking is the
same in the fit validation and in the plots; keeping it in one place means one
thing to fix if the storage ever changes.
"""
from __future__ import annotations

import numpy as np


def lorentz_array(tree, name: str) -> np.ndarray:
    """An uproot TTree branch of TLorentzVector as an (N, 4) [px, py, pz, E]."""
    a = tree[name].array()
    return np.stack([np.asarray(a["fP"]["fX"]), np.asarray(a["fP"]["fY"]),
                     np.asarray(a["fP"]["fZ"]), np.asarray(a["fE"])], axis=1)
