"""Shared meson-mass histogram and truth-marker drawing helpers."""
from __future__ import annotations

import numpy as np
import ROOT

from graal_common.physics.channels import M_ETA, M_PI0

_ETA_MASS_MIN, _ETA_MASS_MAX = 0.3, 0.8
_PI0_MASS_MIN, _PI0_MASS_MAX = 0.05, 0.25
_MASS2D_BINS = 90


def mass2d_hist(name: str, title: str, eta: np.ndarray, pi0: np.ndarray) -> ROOT.TH2F:
    """The same two masses the 1D plots show, plotted against each other.

    Deliberately on the 1D windows: this figure is those two plots crossed, and
    reading one against the other only works if the axes agree with them.
    """
    h = ROOT.TH2F(
        name,
        f"{title};M(#eta)  [GeV];M(#pi^{{0}})  [GeV]",
        _MASS2D_BINS, _ETA_MASS_MIN, _ETA_MASS_MAX,
        _MASS2D_BINS, _PI0_MASS_MIN, _PI0_MASS_MAX,
    )
    for xi, yi in zip(eta, pi0):
        h.Fill(xi, yi)
    return h


def draw_truth_cross() -> list:
    """Mark (M_ETA, M_PI0) on the current pad: where the signal must sit.

    Returns the lines so the caller can hold a reference — PyROOT collects a
    TLine nothing points at, and it disappears from the canvas silently.
    """
    v = ROOT.TLine(M_ETA, _PI0_MASS_MIN, M_ETA, _PI0_MASS_MAX)
    h = ROOT.TLine(_ETA_MASS_MIN, M_PI0, _ETA_MASS_MAX, M_PI0)
    for line in (v, h):
        line.SetLineColor(ROOT.kRed + 1)
        line.SetLineStyle(2)
        line.Draw()
    return [v, h]
