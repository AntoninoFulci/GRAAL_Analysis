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
