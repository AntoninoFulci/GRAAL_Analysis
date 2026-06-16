import numpy as np
import pytest
from analysis.ml import physics


def test_invariant_mass_two_back_to_back_photons():
    # two 1-GeV photons going +z and -z -> invariant mass = 2 GeV
    g1 = np.array([1.0, 0.0, 0.0, 1.0])
    g2 = np.array([1.0, 0.0, 0.0, -1.0])
    assert physics.invariant_mass(g1, g2) == pytest.approx(2.0)


def test_invariant_mass_clips_negative():
    # numerically tiny negative m^2 must clip to 0, not NaN
    g1 = np.array([1.0, 1.0, 0.0, 0.0])
    g2 = np.array([1.0, 1.0, 0.0, 0.0])  # collinear -> m=0
    m = physics.invariant_mass(g1, g2)
    assert m == pytest.approx(0.0, abs=1e-9)
    assert not np.isnan(m)


def test_energy_asymmetry():
    g1 = np.array([3.0, 0, 0, 3.0])
    g2 = np.array([1.0, 0, 0, 1.0])
    assert physics.energy_asymmetry(g1, g2) == pytest.approx(0.5)


def test_opening_angle_orthogonal():
    g1 = np.array([1.0, 1.0, 0.0, 0.0])
    g2 = np.array([1.0, 0.0, 1.0, 0.0])
    assert physics.opening_angle(g1, g2) == pytest.approx(np.pi / 2)


def test_cos_angle_orthogonal():
    g1 = np.array([1.0, 1.0, 0.0, 0.0])
    g2 = np.array([1.0, 0.0, 1.0, 0.0])
    assert physics.cos_angle(g1, g2) == pytest.approx(0.0, abs=1e-9)


def test_pt_and_beta():
    v = np.array([5.0, 3.0, 4.0, 0.0])  # |p| = 5, E = 5 -> beta = 1, pt = 5
    assert physics.pt(v) == pytest.approx(5.0)
    assert physics.beta(v) == pytest.approx(1.0)


def test_chi2_zero_at_nominal_masses():
    assert physics.chi2_pairing(physics.MPI0, physics.META) == pytest.approx(0.0)


def test_functions_are_vectorised():
    g1 = np.array([[1.0, 0, 0, 1.0], [2.0, 0, 0, 2.0]])
    g2 = np.array([[1.0, 0, 0, -1.0], [2.0, 0, 0, -2.0]])
    m = physics.invariant_mass(g1, g2)
    assert m.shape == (2,)
    assert m == pytest.approx([2.0, 4.0])
