"""Source-derived spin amplitudes and independent PRC73 Eq. (25) integrals."""

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from scipy.integrate import quad

from graal_theory.amplitudes import chiral_photoproduction as chiral
from graal_theory.amplitudes import production_loops as loops
from graal_theory.amplitudes.nstar1535_reduced import load_reduced_parameters, loop_functions
from graal_theory.phase_space import SobolConfig, sample_three_body


REFERENCES = Path(__file__).resolve().parents[1] / "references"
FAMILIES = (chiral.chiral_contact_amplitude, chiral.external_pi0_amplitude,
            chiral.internal_pi0_amplitude)
X = np.array([0., np.sqrt(2), 0., .5, -1/(2*np.sqrt(3)), 0.])
Y = np.array([0., np.sqrt(2), 0., -.5, -np.sqrt(3)/2, 0.])
# Literal post-Eq.(25) values, ordered (a,a',b,b'); do not reuse production tables.
COEFFICIENTS = {1: (-1/np.sqrt(2), -1., 0., 0.),
                3: (1/np.sqrt(6), np.sqrt(2/3), 1/np.sqrt(6), -1/np.sqrt(6)),
                4: (1/np.sqrt(6), 0., 1/np.sqrt(6), -1/np.sqrt(2))}


@pytest.fixture
def production():
    return loops.load_production_parameters(REFERENCES / "eta_pi0_p_full_parameters.json",
                                            REFERENCES / "sources.json")


@pytest.fixture
def strong():
    return load_reduced_parameters(REFERENCES / "nstar1535_reduced_parameters.json",
                                   REFERENCES / "sources.json")


@pytest.fixture
def sample(strong):
    masses = (strong.meson_masses_gev[2], strong.meson_masses_gev[0],
              strong.baryon_masses_gev[0])
    full = sample_three_body(1.82, masses, SobolConfig(4))
    indices = [7, 10, 13]
    return replace(full, initial=full.initial[indices], momenta=full.momenta[indices],
                   weights_gev2=full.weights_gev2[indices], s12_gev2=full.s12_gev2[indices])


def _sigma(vector):
    # Explicit Pauli matrices catch transposition/order and cross-product errors.
    x, y, z = vector
    return np.array([[z, x-1j*y], [x+1j*y, -z]], dtype=np.complex128)


def _transition(channel, value=.7-.3j):
    t = np.zeros((6, 6), dtype=np.complex128)
    t[channel, 2] = value
    return lambda invariant: t


def _invariant(sample, event):
    pair = sample.momenta[event, 0] + sample.momenta[event, 2]
    return np.sqrt(pair[0]**2 - pair[1:] @ pair[1:])


def test_printed_coefficient_zeros_signs_and_channel_order():
    np.testing.assert_array_equal(chiral.X1, X)
    np.testing.assert_array_equal(chiral.Y1, Y)
    assert dict(chiral.INTERNAL) == COEFFICIENTS


@pytest.mark.parametrize("channel", range(6))
@pytest.mark.parametrize("b6d,b6f", [(1., 0.), (0., 1.), (2.4, 1.82)])
def test_contact_eta_column_isolates_table_iii_and_ordinary_magnetic_limit(
        production, strong, sample, channel, b6d, b6f):
    # Catches any Table III sign/zero, wrong eta column, G prescription or 2M.
    changed = replace(production, b6d=b6d, b6f=b6f)
    actual = chiral.chiral_contact_amplitude(sample, [1., 0., 0.], changed,
                                             strong, _transition(channel))
    expected = []
    for event, initial in enumerate(sample.initial):
        w = initial[0]
        k = (w*w-strong.baryon_masses_gev[0]**2)/(2*w)
        scalar = (-1j*(b6d*X[channel]+b6f*Y[channel])*production.electric_charge
                  *loop_functions(_invariant(sample, event), strong)[channel]*(.7-.3j)
                  /(8*strong.decay_constants_gev[0]*strong.decay_constants_gev[channel]
                    *strong.baryon_masses_gev[0]))
        expected.append(scalar*_sigma([0., k, 0.]))
    np.testing.assert_allclose(actual, expected, rtol=2e-13, atol=1e-13)


def test_contact_ordinary_term_equals_charge_weighted_wt_coefficient(production, strong, sample):
    # Eq.(15): Q_j C_1j = (0,sqrt2,0,-1/2,-sqrt3/2,0), independently Table I.
    ordinary = replace(production, b6d=0., b6f=1.)
    t = np.zeros((6, 6), dtype=complex)
    t[:, 2] = [0., 1+2j, 0., -3j, .2-.5j, 0.]
    expected = []
    charge_times_c = np.array([0., np.sqrt(2), 0., -.5, -np.sqrt(3)/2, 0.])
    for event, initial in enumerate(sample.initial):
        k = (initial[0]**2-strong.baryon_masses_gev[0]**2)/(2*initial[0])
        scalar = -1j*production.electric_charge*np.sum(
            charge_times_c*loop_functions(_invariant(sample, event), strong)*t[:, 2]
            /np.asarray(strong.decay_constants_gev))/(8*strong.decay_constants_gev[0]
                                                        *strong.baryon_masses_gev[0])
        expected.append(scalar*_sigma([0., k, 0.]))
    np.testing.assert_allclose(chiral.chiral_contact_amplitude(
        sample, [1., 0., 0.], ordinary, strong, lambda z: t), expected, rtol=2e-13)


def test_external_complete_eta_pair_propagator_spin_order_and_printed_i(
        production, strong, sample, monkeypatch):
    # Complex hand fixture catches omitted i, reversed spin order and using W for z.
    eta = np.array([[1+2j, 3-1j], [-2+.5j, .7-4j]])
    seen = []
    def eta_pair(z, epsilon, passed_production, passed_strong, passed_t):
        seen.append(z)
        return eta
    monkeypatch.setattr(chiral, "eta_photoproduction_amplitude", eta_pair)
    actual = chiral.external_pi0_amplitude(sample, [1., 0., 0.], production,
                                          strong, _transition(1))
    expected = []
    mass = strong.baryon_masses_gev[0]
    for event, initial in enumerate(sample.initial):
        pion = sample.momenta[event, 1]
        k = np.array([0., 0., (initial[0]**2-mass**2)/(2*initial[0])])
        energy_in, energy_out = np.sqrt(mass**2+k @ k), np.sqrt(mass**2+(k+pion[1:]) @ (k+pion[1:]))
        scalar = (1j*(production.axial_d+production.axial_f)*mass
                  /(2*strong.decay_constants_gev[0]*energy_out
                    *(energy_in-pion[0]-energy_out)))
        expected.append(scalar*eta @ _sigma(-pion[1:]))
    np.testing.assert_allclose(actual, expected, rtol=1e-13, atol=1e-13)
    np.testing.assert_allclose(seen, [_invariant(sample, i) for i in range(3)], rtol=1e-14)


def test_external_uses_real_coherent_eta_pair(production, strong, sample):
    # Catches accidentally keeping only KR or replacing the physical pair with a scalar.
    actual = chiral.external_pi0_amplitude(sample, [0., 1., 0.], production,
                                          strong, _transition(1))
    expected = []
    mass = strong.baryon_masses_gev[0]
    for event, initial in enumerate(sample.initial):
        pion = sample.momenta[event, 1]
        k = np.array([0., 0., (initial[0]**2-mass**2)/(2*initial[0])])
        en = np.sqrt(mass**2+(k+pion[1:]) @ (k+pion[1:]))
        denominator = np.sqrt(mass**2+k @ k)-pion[0]-en
        eta = loops.eta_photoproduction_amplitude(_invariant(sample, event),
            [0., 1., 0.], production, strong, _transition(1))
        expected.append(1j*(production.axial_d+production.axial_f)*mass
                        /(2*strong.decay_constants_gev[0]*en*denominator)
                        *eta @ _sigma(-pion[1:]))
    np.testing.assert_allclose(actual, expected, rtol=2e-12, atol=1e-12)


def _eq25_oracle(sample, event, production, strong, channel, angle_order,
                 *, pole_partner=True, fixed_form_energy=False, reverse_baryons=False):
    """Adaptive radial PV/cauchy plus direct GL angle integration, independently.

    Each single propagator is integrated with scipy's weighted Cauchy rule;
    its delta cut is added from the source +i0. This does not use the Task2
    subtraction or convergence helpers. The angle order is doubled in callers.
    """
    w = sample.initial[event, 0]
    pion = sample.momenta[event, 1]
    p = np.linalg.norm(pion[1:])
    meson = strong.meson_masses_gev[channel]
    left_index = {1: 1, 3: 4, 4: 3}[channel]
    left, right = strong.baryon_masses_gev[left_index], strong.baryon_masses_gev[channel]
    if reverse_baryons:
        left, right = right, left
    k = (w*w-strong.baryon_masses_gev[0]**2)/(2*w)
    q0 = (w*w+meson**2-left**2)/(2*w)
    qon2 = q0*q0-meson**2
    partner = 1-qon2/(3*q0*k) if pole_partner else 1.
    limit = production.first_loop_cutoff_gev
    nodes, weights = np.polynomial.legendre.leggauss(angle_order)
    integrals = []
    for x in nodes:
        def energies(q):
            return (np.sqrt(meson**2+q*q), np.sqrt(left**2+q*q),
                    np.sqrt(right**2+q*q+p*p+2*q*p*x))
        def d1(q):
            om, en, ep = energies(q)
            return w-om-en
        def d2(q):
            om, en, ep = energies(q)
            return w-om-pion[0]-ep
        def numerator(q):
            om, en, ep = energies(q)
            on_energy = q0 if fixed_form_energy else om
            squared = meson**2-2*on_energy*k
            form = ((production.pion_form_factor_cutoff_gev**2-strong.meson_masses_gev[0]**2)
                    /(production.pion_form_factor_cutoff_gev**2-squared))
            return q*q*left*right*form*partner/(8*np.pi**2*om*en*ep)
        first_roots = [np.sqrt(qon2)] if qon2 > 0 and q0 > 0 else []
        available = w-pion[0]
        b = (available**2+meson**2-right**2-p*p)/2
        c = available**2-(p*x)**2
        disc = (b*p*x)**2-c*(available**2*meson**2-b*b)
        second_roots = []
        if disc >= 0:
            for root in ((-b*p*x-np.sqrt(disc))/c, (-b*p*x+np.sqrt(disc))/c):
                if root > 0 and abs(d2(root)) < 1e-10:
                    second_roots.append(root)
        def one_propagator(which, roots):
            divisor = d1 if which == 1 else d2
            def smooth(q):
                return numerator(q)/(d2(q)-d1(q))
            roots = [r for r in roots if 0 < r < limit]
            assert len(roots) <= 1  # These selected physical events have simple roots.
            if not roots:
                return quad(lambda q: smooth(q)/divisor(q), 0., limit,
                            epsabs=2e-11, epsrel=2e-10)[0]
            root = roots[0]
            def slope(q):
                om, en, ep = energies(q)
                return -q/om-(q/en if which == 1 else (q+p*x)/ep)
            def regular_numerator(q):
                if abs(q-root) < 1e-8:
                    return smooth(root)/slope(root)
                return smooth(q)*(q-root)/divisor(q)
            pv = quad(regular_numerator, 0., limit, weight="cauchy", wvar=root,
                      epsabs=2e-11, epsrel=2e-10)[0]
            return pv-1j*np.pi*smooth(root)/abs(slope(root))
        integrals.append(one_propagator(1, first_roots)-one_propagator(2, second_roots))
    integral = np.dot(weights, integrals)
    a, ap, b, bp = COEFFICIENTS[channel]
    d, f = production.axial_d, production.axial_f
    coupling = -production.electric_charge*(a*(d+f)+b*(d-f))*(ap*(d+f)+bp*(d-f))
    coupling /= 2*strong.decay_constants_gev[0]*strong.decay_constants_gev[channel]
    return coupling*(.7-.3j)*integral*_sigma(pion[1:]) @ _sigma([1., 0., 0.])


@pytest.mark.parametrize("channel", [1, 3, 4])
def test_internal_eq25_isolated_channels_match_independent_doubled_order_oracle(
        production, strong, sample, channel):
    # Catches masses, signs, both propagators/cuts, angular/radial measure and pole pair.
    low = np.array([_eq25_oracle(sample, i, production, strong, channel, 96) for i in range(3)])
    high = np.array([_eq25_oracle(sample, i, production, strong, channel, 192) for i in range(3)])
    np.testing.assert_allclose(low, high, rtol=1e-8, atol=1e-10)
    actual = chiral.internal_pi0_amplitude(sample, [1., 0., 0.], production,
                                          strong, _transition(channel))
    np.testing.assert_allclose(actual, high, rtol=2e-5, atol=1e-9)
    assert np.linalg.norm(actual) > 0


@pytest.mark.parametrize("channel", [0, 2, 5])
def test_internal_printed_zero_channels_do_not_contribute(production, strong, sample, channel):
    np.testing.assert_array_equal(chiral.internal_pi0_amplitude(
        sample, [1., 0., 0.], production, strong, _transition(channel)), np.zeros((3, 2, 2)))


def test_internal_distinguishes_pole_partner_running_form_energy_and_baryon_order(
        production, strong, sample):
    # These three mutations change the physical result; oracle includes full source pair.
    baseline = _eq25_oracle(sample, 0, production, strong, 3, 192)
    for change in ({"pole_partner": False}, {"fixed_form_energy": True},
                   {"reverse_baryons": True}):
        changed = _eq25_oracle(sample, 0, production, strong, 3, 192, **change)
        assert np.linalg.norm(changed-baseline) > 1e-3*np.linalg.norm(baseline)


def test_internal_closed_channel_continues_signed_on_shell_momentum(production, strong, sample):
    # Artificial higher left/right masses close both K loops without changing external masses.
    changed_masses = list(strong.baryon_masses_gev)
    changed_masses[3], changed_masses[4] = 1.55, 1.49
    closed = replace(strong, baryon_masses_gev=tuple(changed_masses))
    def direct(order):
        # Literal tensor integration, safe because both propagators are closed.
        # No production integrator, PV helper or adaptive oracle is reused here.
        nodes, weights = np.polynomial.legendre.leggauss(order)
        limit = production.first_loop_cutoff_gev
        q, qw = (nodes+1)*limit/2, weights*limit/2
        expected = []
        m, left, right = closed.meson_masses_gev[3], closed.baryon_masses_gev[4], closed.baryon_masses_gev[3]
        for event in range(3):
            w, pion = sample.initial[event, 0], sample.momenta[event, 1]
            p = np.linalg.norm(pion[1:])
            om = np.sqrt(m*m+q[:, None]**2)
            en = np.sqrt(left*left+q[:, None]**2)
            ep = np.sqrt(right*right+q[:, None]**2+p*p+2*q[:, None]*p*nodes)
            k = (w*w-closed.baryon_masses_gev[0]**2)/(2*w)
            q0 = (w*w+m*m-left*left)/(2*w)
            assert q0*q0-m*m < 0
            pole = 1-(q0*q0-m*m)/(3*q0*k)
            cutoff2 = production.pion_form_factor_cutoff_gev**2
            form = (cutoff2-closed.meson_masses_gev[0]**2)/(cutoff2-m*m+2*om*k)
            density = (q[:, None]**2*left*right*form*pole
                       /(8*np.pi**2*om*en*ep*(w-om-en)*(w-om-pion[0]-ep)))
            integral = np.sum(qw[:, None]*weights*density)
            # Channel 4: left axial = 2D/sqrt6, right = (D+3F)/sqrt6.
            coupling = (-production.electric_charge*(2*production.axial_d)
                        *(production.axial_d+3*production.axial_f)
                        /(12*closed.decay_constants_gev[0]*closed.decay_constants_gev[3]))
            expected.append(coupling*(.7-.3j)*integral*_sigma(pion[1:]) @ _sigma([1., 0., 0.]))
        return np.asarray(expected)
    expected = direct(384)
    np.testing.assert_allclose(direct(192), expected, rtol=1e-10, atol=1e-11)
    adaptive = np.array([_eq25_oracle(sample, i, production, closed, 3, 192) for i in range(3)])
    np.testing.assert_allclose(adaptive, expected, rtol=1e-10, atol=1e-11)
    actual = chiral.internal_pi0_amplitude(sample, [1., 0., 0.], production,
                                          closed, _transition(3))
    np.testing.assert_allclose(actual, expected, rtol=2e-5, atol=1e-9)
    assert np.all(np.isfinite(actual))


@pytest.mark.parametrize("family", FAMILIES)
def test_family_finite_complex_shape_zero_t_electric_zero_and_polarization_rotation(
        production, strong, sample, family):
    tx = family(sample, [1., 0., 0.], production, strong, _transition(1))
    ty = family(sample, [0., 1., 0.], production, strong, _transition(1))
    assert tx.shape == (3, 2, 2) and tx.dtype == np.complex128
    assert np.all(np.isfinite(tx)) and np.linalg.norm(tx-ty) > 0
    for changed, callback in ((production, lambda z: np.zeros((6, 6))),
                              (replace(production, electric_charge=0.), _transition(1))):
        np.testing.assert_array_equal(family(sample, [1., 0., 0.], changed,
                                             strong, callback), np.zeros((3, 2, 2)))


@pytest.mark.parametrize("family", FAMILIES)
def test_family_rejects_wrong_particle_order_and_non_cm_sample(production, strong, sample, family):
    reordered = replace(sample, masses=(sample.masses[1], sample.masses[0], sample.masses[2]),
                        momenta=sample.momenta[:, [1, 0, 2]])
    initial = sample.initial.copy()
    initial[0, 1] = .1
    for bad in (reordered, replace(sample, initial=initial),
                replace(sample, momenta=np.zeros((3, 2, 4)))):
        with pytest.raises(ValueError, match=family.__name__.removesuffix("_amplitude")):
            family(bad, [1., 0., 0.], production, strong, _transition(1))


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("bad", [np.eye(5), np.full((6, 6), np.nan), np.ones((6, 6), dtype=bool)])
def test_family_rejects_malformed_nonfinite_or_bool_strong_t_with_context(
        production, strong, sample, family, bad):
    with pytest.raises(ValueError, match=family.__name__.removesuffix("_amplitude")+".*event=0.*z="):
        family(sample, [1., 0., 0.], production, strong, lambda z: bad)


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("bad", [[1., 0., 1.], [0., 0., 0.], [np.nan, 0., 0.]])
def test_family_rejects_invalid_polarization(production, strong, sample, family, bad):
    with pytest.raises(ValueError, match=family.__name__.removesuffix("_amplitude")):
        family(sample, bad, production, strong, _transition(1))


@pytest.mark.parametrize("family,field", [(chiral.chiral_contact_amplitude, "b6d"),
    (chiral.chiral_contact_amplitude, "b6f"), (chiral.external_pi0_amplitude, "axial_d"),
    (chiral.internal_pi0_amplitude, "axial_f")])
@pytest.mark.parametrize("bad", [None, True, 1j, np.inf])
def test_family_validates_replaced_real_couplings(production, strong, sample, family, field, bad):
    with pytest.raises(ValueError, match=family.__name__.removesuffix("_amplitude")+".*"+field):
        family(sample, [1., 0., 0.], replace(production, **{field: bad}), strong, _transition(1))


def test_internal_cutoff_endpoint_pole_is_contextual(production, strong, sample):
    w = sample.initial[0, 0]
    mass, baryon = strong.meson_masses_gev[1], strong.baryon_masses_gev[1]
    cutoff = np.sqrt((w*w-(mass+baryon)**2)*(w*w-(mass-baryon)**2))/(2*w)
    with pytest.raises(ValueError, match="internal_pi0.*event=0.*channel=1.*z=.*pole"):
        chiral.internal_pi0_amplitude(sample, [1., 0., 0.],
            replace(production, first_loop_cutoff_gev=cutoff), strong, _transition(1))


@pytest.mark.parametrize("family", FAMILIES)
def test_family_reports_genuine_strong_pole_with_event_invariant(production, strong, sample, family):
    def pole(z):
        raise ZeroDivisionError("genuine strong pole")
    with pytest.raises(ValueError, match=family.__name__.removesuffix("_amplitude")+".*event=0.*z=.*pole"):
        family(sample, [1., 0., 0.], production, strong, pole)


@pytest.mark.parametrize("family", FAMILIES)
def test_strong_t_is_evaluated_once_at_each_external_eta_proton_invariant(
        production, strong, sample, family):
    # Catches using W, a loop energy, or the wrong particle pair for strong T.
    baseline = family(sample, [1., 0., 0.], production, strong, _transition(1))
    seen = []
    def invariant_transition(z):
        seen.append(z)
        t = np.zeros((6, 6), dtype=complex)
        t[1, 2] = z*(.7-.3j)
        return t
    actual = family(sample, [1., 0., 0.], production, strong, invariant_transition)
    z = np.array([_invariant(sample, event) for event in range(3)])
    np.testing.assert_allclose(actual, z[:, None, None]*baseline, rtol=2e-12, atol=1e-12)
    np.testing.assert_allclose(seen, z, rtol=2e-14)


def test_external_near_zero_nucleon_denominator_raises(production, strong, sample):
    # Soft-pion limiting fixture isolates the 32*eps denominator guard.
    tiny_mass = 1e-16
    mesons = list(strong.meson_masses_gev)
    mesons[0] = tiny_mass
    changed = replace(strong, meson_masses_gev=tuple(mesons))
    momentum = .2
    eta_energy = np.sqrt(changed.meson_masses_gev[2]**2+momentum**2)
    proton_energy = np.sqrt(changed.baryon_masses_gev[0]**2+momentum**2)
    momenta = np.array([[[eta_energy, momentum, 0., 0.], [tiny_mass, 0., 0., 0.],
                         [proton_energy, -momentum, 0., 0.]]])
    soft = replace(sample, initial=np.array([[eta_energy+proton_energy+tiny_mass, 0., 0., 0.]]),
                   momenta=momenta, masses=(changed.meson_masses_gev[2], tiny_mass,
                                            changed.baryon_masses_gev[0]))
    with pytest.raises(ValueError, match="external_pi0.*event=0.*z=.*singular nucleon denominator"):
        chiral.external_pi0_amplitude(soft, [1., 0., 0.], production, changed, _transition(1))


def test_internal_deeply_closed_channel_does_not_misidentify_pseudothreshold_root(
        production, strong, sample):
    # Below |M-m|, Kallen q_on^2 is positive but q_on^0<0: no physical cut/pole.
    masses = list(strong.baryon_masses_gev)
    masses[4] = 2.7
    closed = replace(strong, baryon_masses_gev=tuple(masses))
    w = sample.initial[0, 0]
    meson, baryon = closed.meson_masses_gev[3], closed.baryon_masses_gev[4]
    q0 = (w*w+meson*meson-baryon*baryon)/(2*w)
    assert q0 < 0 and q0*q0-meson*meson > 0
    at_spurious_root = replace(production, first_loop_cutoff_gev=np.sqrt(q0*q0-meson*meson))
    actual = chiral.internal_pi0_amplitude(sample, [1., 0., 0.], at_spurious_root,
                                          closed, _transition(3))
    assert actual.shape == (3, 2, 2) and np.all(np.isfinite(actual))
    expected = np.array([_eq25_oracle(sample, event, at_spurious_root, closed, 3, 192)
                         for event in range(3)])
    np.testing.assert_allclose(actual, expected, rtol=2e-5, atol=1e-9)
