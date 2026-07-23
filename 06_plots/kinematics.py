"""Kinematic quantities for the plots.

No ROOT, no IO: arithmetic on (4,) [px, py, pz, E] numpy arrays, the same
convention reco_core uses when it reads a TLorentzVector. Keeping this module
pure is what lets the plots be tested without ROOT.
"""
from __future__ import annotations

import numpy as np

# From the same registry the reconstruction reads, rather than a copy kept in
# step by hand: a plot that disagrees with the reconstruction about the eta mass
# is worse than no plot.
from graal_common.channels import M_ETA, M_PI0, M_PROTON

__all__ = ["M_ETA", "M_PI0", "M_PROTON", "dalitz_limit", "invariant_mass",
           "invariant_masses", "sqrt_s"]


def invariant_mass(a: np.ndarray, b: np.ndarray) -> float:
    """Invariant mass of the a+b system. Both are [px, py, pz, E]."""
    s = a + b
    m2 = s[3] ** 2 - (s[0] ** 2 + s[1] ** 2 + s[2] ** 2)
    # Resolution can push m^2 marginally negative on a genuinely light system;
    # report 0 rather than NaN.
    return float(np.sqrt(max(m2, 0.0)))


def invariant_masses(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Invariant mass of a+b for stacks: a, b are (N, 4), result is (N,).

    The batched form of invariant_mass, same clamp to zero, so a whole tree of
    events costs one array op instead of a Python loop.
    """
    s = a + b
    m2 = s[:, 3] ** 2 - (s[:, :3] ** 2).sum(axis=1)
    return np.sqrt(np.clip(m2, 0.0, None))


def sqrt_s(beam: np.ndarray, target: np.ndarray) -> float:
    """W = sqrt(s), the total mass available to the reaction."""
    return invariant_mass(beam, target)


def dalitz_limit(W: float, m_spectator: float) -> float:
    """Largest mass a two-body subsystem can have, given the third particle.

    In gamma p -> p eta pi0, M(eta p) cannot exceed W - m_pi0: the pi0 has to be
    made too. Nothing here cuts on it — this is for drawing the boundary, and
    for whoever adds the cut later.
    """
    return W - m_spectator
