import numpy as np
import pytest

from plots import kinematics as kin


def test_constants_match_the_reconstruction():
    # The plots must speak the same physics as 05_reconstruction/reco_physics.py.
    from reconstruction import reco_physics as rp

    assert kin.M_PI0 == rp.M_PI0
    assert kin.M_ETA == rp.M_ETA
    assert kin.M_PROTON == rp.M_PROTON


def test_invariant_mass_of_back_to_back_photons():
    # two massless photons of energy 0.5 flying apart along z -> mass 1.0
    g1 = np.array([0.0, 0.0, 0.5, 0.5])
    g2 = np.array([0.0, 0.0, -0.5, 0.5])
    assert kin.invariant_mass(g1, g2) == pytest.approx(1.0)


def test_invariant_mass_of_a_particle_at_rest_plus_a_photon():
    # proton at rest + a 1 GeV photon along z
    proton = np.array([0.0, 0.0, 0.0, kin.M_PROTON])
    photon = np.array([0.0, 0.0, 1.0, 1.0])
    # s = E_tot^2 - p_tot^2 = (1 + m)^2 - 1
    expected = np.sqrt((1.0 + kin.M_PROTON) ** 2 - 1.0)
    assert kin.invariant_mass(proton, photon) == pytest.approx(expected)


def test_invariant_mass_is_symmetric():
    a = np.array([0.1, 0.2, 0.3, 0.9])
    b = np.array([-0.2, 0.1, 0.4, 1.1])
    assert kin.invariant_mass(a, b) == pytest.approx(kin.invariant_mass(b, a))


def test_invariant_mass_clamps_a_spacelike_sum_to_zero():
    # resolution can push m^2 marginally negative; report 0, never NaN
    a = np.array([0.0, 0.0, 1.0, 0.4])
    b = np.array([0.0, 0.0, 1.0, 0.4])
    assert kin.invariant_mass(a, b) == 0.0


def test_invariant_masses_matches_the_scalar_form_per_row():
    # the batched form must agree, row by row, with invariant_mass on each pair
    a = np.array([[0.0, 0.0, 0.5, 0.5], [0.1, 0.2, 0.3, 0.9]])
    b = np.array([[0.0, 0.0, -0.5, 0.5], [-0.2, 0.1, 0.4, 1.1]])
    got = kin.invariant_masses(a, b)
    assert got[0] == pytest.approx(kin.invariant_mass(a[0], b[0]))
    assert got[1] == pytest.approx(kin.invariant_mass(a[1], b[1]))


def test_invariant_masses_clamps_spacelike_rows_to_zero():
    # a row whose m^2 goes negative reports 0, never NaN — same as the scalar
    a = np.array([[0.0, 0.0, 1.0, 0.4]])
    b = np.array([[0.0, 0.0, 1.0, 0.4]])
    assert kin.invariant_masses(a, b)[0] == 0.0


def test_sqrt_s_of_beam_on_a_proton_at_rest():
    # W = sqrt(2 E_beam m_p + m_p^2)
    beam = np.array([0.0, 0.0, 1.5, 1.5])
    target = np.array([0.0, 0.0, 0.0, kin.M_PROTON])
    expected = np.sqrt(2 * 1.5 * kin.M_PROTON + kin.M_PROTON**2)
    assert kin.sqrt_s(beam, target) == pytest.approx(expected)


def test_dalitz_limit_subtracts_the_spectator():
    assert kin.dalitz_limit(1.9, kin.M_PI0) == pytest.approx(1.9 - 0.134977)


def test_the_limit_closes_with_sqrt_s():
    # At threshold the pi0 and the (eta p) subsystem are both at rest in the CM,
    # so their masses must add up to W exactly.
    beam = np.array([0.0, 0.0, 1.5, 1.5])
    target = np.array([0.0, 0.0, 0.0, kin.M_PROTON])
    W = kin.sqrt_s(beam, target)
    limit = kin.dalitz_limit(W, kin.M_PI0)
    assert kin.M_PI0 + limit == pytest.approx(W)
