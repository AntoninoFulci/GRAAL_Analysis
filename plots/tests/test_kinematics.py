import numpy as np
import pytest

from plots.core import kinematics as kin


def test_constants_match_the_reconstruction():
    # The plots must speak the same physics as 05_reconstruction/core/reco_physics.py.
    from reconstruction.core import reco_physics as rp

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


def test_mass_squared_preserves_spacelike_values_and_empty_batches():
    assert kin.mass_squared(np.array([2., 0., 0., 1.])) == -3.
    assert kin.mass_squared(np.empty((0, 4))).shape == (0,)


@pytest.mark.parametrize("momentum", [0., 0.25])
def test_dalitz_identity_on_shell_at_threshold_and_above(momentum):
    p = np.array([momentum, 0., 0., np.hypot(kin.M_PROTON, momentum)])
    eta = np.array([-momentum, 0., 0., np.hypot(kin.M_ETA, momentum)])
    pi0 = np.array([0., 0., 0., kin.M_PI0])
    initial = p + eta + pi0
    squares = kin.dalitz_invariants(p, eta, pi0)
    assert kin.dalitz_residual(squares, initial) == pytest.approx(0., abs=2e-15)
    # Non-conservation must remain visible, never projected onto the identity.
    shifted = initial + np.array([0., 0., 0., 0.1])
    assert kin.dalitz_residual(squares, shifted) == pytest.approx(-0.2 * initial[3] - 0.01)


def test_quality_controls_use_polar_and_azimuthal_angles_independently():
    controls = kin.quality_observables(
        proton=np.array([-0.3, 0., 0.4, 0.99]),
        missing=np.array([-0.3, 0., 1.2, 1.448]),
        beam=np.array([0., 0., 1.2, 1.2]),
        target=np.array([0., 0., 0., 0.938]),
        eta=np.array([0.2, 0., 0., 0.55]),
        pi0=np.array([0.1, 0., 0., 0.14]),
    )
    assert controls['proton_theta_deg'] == pytest.approx(36.86989765)
    assert controls['theta_missing_proton_deg'] == pytest.approx(-22.83365418)
    assert controls['coplanarity_deg'] == pytest.approx(0.)
    assert controls['missing_mass_gev'] == pytest.approx(np.sqrt(1.448**2 - 1.53))


@pytest.mark.parametrize('phi_p, phi_pair, expected', [
    (179., -1., 0.), (-179., 1., 0.), (-179., -1., 2.), (179., 1., -2.),
])
def test_quality_coplanarity_wraps_across_azimuthal_boundary(phi_p, phi_pair, expected):
    def vector(phi):
        phi = np.deg2rad(phi)
        return np.array([np.cos(phi), np.sin(phi), 1., 2.])
    controls = kin.quality_observables(
        vector(phi_p), vector(phi_p), np.array([0., 0., 2., 2.]),
        np.array([0., 0., 0., 1.]), vector(phi_pair), vector(phi_pair))
    assert controls['coplanarity_deg'] == pytest.approx(expected, abs=1e-12)


def test_quality_controls_keep_signed_mass_and_undefined_directions():
    controls = kin.quality_observables(
        np.zeros(4), np.zeros(4), np.array([0., 0., 2., 2.]),
        np.array([0., 0., 0., 1.]), np.array([0., 0., 0., 1.]),
        np.array([0., 0., 0., 1.]))
    assert controls['missing_mass_gev'] == pytest.approx(-np.sqrt(3.))
    assert np.isnan(controls['proton_theta_deg'])
    assert np.isnan(controls['theta_missing_proton_deg'])
    assert np.isnan(controls['coplanarity_deg'])


def test_quality_controls_reject_nonfinite_input():
    with pytest.raises(ValueError, match='non-finite'):
        kin.quality_observables(
            np.array([np.nan, 0., 0., 1.]), *[np.ones(4) for _ in range(5)])


def test_quality_forward_proton_has_defined_theta_but_undefined_phi():
    controls = kin.quality_observables(
        np.array([0., 0., 1., 2.]), np.array([0., 0., 2., 3.]),
        np.array([0., 0., 2., 2.]), np.array([0., 0., 0., 1.]),
        np.array([1., 0., 0., 1.]), np.array([0., 0., 0., .1]))
    assert controls['proton_theta_deg'] == 0.
    assert controls['theta_missing_proton_deg'] == 0.
    assert np.isnan(controls['coplanarity_deg'])
