"""Read a ROOT TLorentzVector branch as a plain (N, 4) [px, py, pz, E] array."""
from __future__ import annotations

import numpy as np


def lorentz_array(tree, name: str) -> np.ndarray:
    """An uproot TTree branch of TLorentzVector as an (N, 4) [px, py, pz, E]."""
    a = tree[name].array()
    return np.stack([np.asarray(a["fP"]["fX"]), np.asarray(a["fP"]["fY"]),
                     np.asarray(a["fP"]["fZ"]), np.asarray(a["fE"])], axis=1)
