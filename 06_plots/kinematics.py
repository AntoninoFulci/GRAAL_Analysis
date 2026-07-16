"""Kinematic quantities for the plots.

No ROOT, no IO: arithmetic on (4,) [px, py, pz, E] numpy arrays, the same
convention reco_core uses when it reads a TLorentzVector. Keeping this module
pure is what lets the plots be tested without ROOT.
"""
from __future__ import annotations

import numpy as np

# Must match 03_analysis/reco_physics.py — a plot that disagrees with the
# reconstruction about the eta mass is worse than no plot.
M_PI0 = 0.134977
M_ETA = 0.547862
M_PROTON = 0.938272


def invariant_mass(a: np.ndarray, b: np.ndarray) -> float:
    """Invariant mass of the a+b system. Both are [px, py, pz, E]."""
    s = a + b
    m2 = s[3] ** 2 - (s[0] ** 2 + s[1] ** 2 + s[2] ** 2)
    # Resolution can push m^2 marginally negative on a genuinely light system;
    # report 0 rather than NaN.
    return float(np.sqrt(max(m2, 0.0)))


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
