"""Independent Fig. 10 source and physical-loop checks, PRC73 Eqs. (39)--(42)."""

from dataclasses import replace
from importlib import import_module
from pathlib import Path

import numpy as np
import pytest
from scipy.integrate import quad
from scipy.optimize import brentq

from graal_theory.amplitudes.delta1700 import Delta1700Parameters
from graal_theory.amplitudes.nstar1535_reduced import load_reduced_parameters
from graal_theory.amplitudes.production_loops import QuadratureSettings, load_production_parameters
from graal_theory.amplitudes.propagators import delta1700_width
from graal_theory.models.eta_pi0_p import load_central_parameters
from graal_theory.phase_space import SobolConfig, sample_three_body


REFERENCES = Path(__file__).resolve().parents[1] / "references"
EPSILON = np.array([.6, .8, 0.])
FAMILIES = ("eta_delta_rescattering_amplitude", "k_sigma_star_rescattering_amplitude")


@pytest.fixture(scope="module")
def decuplet():
    try:
        return import_module("graal_theory.amplitudes.decuplet_rescattering")
    except ModuleNotFoundError as exc:
        missing = str(exc)
        class UnimplementedFamily:
            def __getattr__(self, name):
                pytest.fail(f"Task 5 decuplet families are not implemented: {missing}")
        return UnimplementedFamily()


@pytest.fixture(scope="module")
def production():
    return load_production_parameters(REFERENCES / "eta_pi0_p_full_parameters.json",
                                      REFERENCES / "sources.json")


@pytest.fixture(scope="module")
def strong():
    return load_reduced_parameters(REFERENCES / "nstar1535_reduced_parameters.json",
                                   REFERENCES / "sources.json")


@pytest.fixture(scope="module")
def tree():
    return Delta1700Parameters.from_parameters(load_central_parameters(
        REFERENCES / "central_parameters.json", REFERENCES / "sources.json"))


def _sample(w, strong, indices):
    masses = (strong.meson_masses_gev[2], strong.meson_masses_gev[0],
              strong.baryon_masses_gev[0])
    full = sample_three_body(w, masses, SobolConfig(4))
    return replace(full, initial=full.initial[indices], momenta=full.momenta[indices],
                   weights_gev2=full.weights_gev2[indices], s12_gev2=full.s12_gev2[indices])


@pytest.fixture(scope="module")
def sample(strong):
    return _sample(1.82, strong, [7, 13])


def _q(w, m, mu):
    return np.sqrt((w*w-(m+mu)**2)*(w*w-(m-mu)**2))/(2*w)


def _sigma(v):
    x, y, z = v
    return np.array([[z, x-1j*y], [x+1j*y, -z]])


def _source_oracle(channel, pion, k, epsilon, production, tree, strong, *, kr=True):
    """Printed coefficients; independent S_a S_b^dagger transition identity."""
    p, k0 = pion[1:], np.linalg.norm(k)
    w = k0+np.sqrt(tree.proton_mass_gev**2+k0*k0)
    f_pi = strong.decay_constants_gev[0]
    d, f = production.axial_d, production.axial_f
    if channel == 2:
        scalar = -np.sqrt(2/3)*tree.g_eta_delta*tree.f_delta_n_pi/tree.pion_reference_mass_gev
    elif channel == 4:
        scalar = production.sigma_star_su3_correction*np.sqrt(24/25)*(d+f)/(2*f_pi)*production.g_k_sigma_star
    elif channel == 5:
        # The close-up prints (2D+F)/(5*2*f_pi), not the brief's sqrt(2).
        scalar = (2*d+f)/(10*f_pi)*production.g_k_sigma_star
    else:
        return np.zeros((2, 2), dtype=complex)
    def contraction(a, b):
        return 2/3*(a @ b)*np.eye(2)-1j/3*_sigma(np.cross(a, b))
    electromagnetic = (-1j*tree.g1_prime/(2*tree.proton_mass_gev)
        *contraction(p, k) @ _sigma(np.cross(k, epsilon))
        -contraction(p, epsilon)*(tree.g1_prime*(k0+k0*k0/(2*tree.proton_mass_gev))
                                  +tree.g2_prime*w*k0))
    result = scalar/(w-tree.delta1700_mass_gev+.5j*delta1700_width(w, tree.width_parameters))*electromagnetic
    if kr and channel == 4:
        result += _kr_oracle(pion, epsilon, production, strong)
    return result


def _kr_oracle(pion, epsilon, production, strong):
    p = pion[1:]
    coefficient = (-production.sigma_star_su3_correction*production.electric_charge
                   *4*np.sqrt(3)/25*((production.axial_d+production.axial_f)
                                      /(2*strong.decay_constants_gev[0]))**2)
    return coefficient*(2*(p @ epsilon)*np.eye(2)-1j*_sigma(np.cross(p, epsilon)))


def _propagator(invariant, pole, rest_width, daughters):
    """Independent real-cut q^3 M/E width and principal spacelike denominator."""
    gamma = 0.
    if invariant.imag == 0 and invariant.real > sum(daughters):
        gamma = rest_width*(_q(invariant.real, *daughters)/_q(pole, *daughters))**3*pole/invariant.real
    return 1/(invariant-pole+.5j*gamma)


def _loop_oracle(sample, event, channel, production, strong, pole, width, daughters, *, power=1):
    """Separate adaptive PV subtraction with explicit -i*pi cut, no Eq26 helper."""
    w, pion = sample.initial[event, 0], sample.momenta[event, 1]
    p, limit = np.linalg.norm(pion[1:]), production.first_loop_cutoff_gev
    mu, m = strong.meson_masses_gev[channel], strong.baryon_masses_gev[channel]
    angular_nodes, angular_weights = np.polynomial.legendre.leggauss(48)
    landmarks = [0., sum(daughters), pole]
    points = []
    for value in landmarks:
        omega = (w*w+mu*mu-value*value)/(2*w)
        if omega > mu:
            radial = np.sqrt(omega*omega-mu*mu)
            if 0 < radial < limit:
                points.append(radial)
    result = 0j
    for x, weight in zip(angular_nodes, angular_weights):
        def denominator(q):
            return w-pion[0]-np.sqrt(mu*mu+q*q)-np.sqrt(m*m+q*q+p*p+2*q*p*x)
        def derivative(q):
            return -q/np.sqrt(mu*mu+q*q)-(q+p*x)/np.sqrt(m*m+q*q+p*p+2*q*p*x)
        def numerator(q):
            omega, energy = np.sqrt(mu*mu+q*q), np.sqrt(m*m+q*q+p*p+2*q*p*x)
            invariant = np.sqrt(complex((w-omega)**2-q*q))
            return q*q*m/(8*np.pi**2*omega*energy)*_propagator(invariant, pole, width, daughters)**power
        root = brentq(denominator, 0., limit) if denominator(0)*denominator(limit) < 0 else None
        if root is None:
            def density(q):
                return numerator(q)/denominator(q)
            cut = 0j
            splits = points
        else:
            residue = numerator(root)/derivative(root)
            # Independent symmetric limit at the removable subtraction point.
            def density(q):
                if abs(q-root) < 1e-7:
                    step = 2e-6
                    return .5*(numerator(root-step)/denominator(root-step)+residue/step
                               +numerator(root+step)/denominator(root+step)-residue/step)
                return numerator(q)/denominator(q)-residue/(q-root)
            cut = residue*np.log((limit-root)/root)-1j*np.pi*numerator(root)/abs(derivative(root))
            splits = points+[root]
        scalar = (quad(lambda q: density(q).real, 0., limit, points=splits,
                       epsabs=1e-9, epsrel=3e-8, limit=200)[0]
                  +1j*quad(lambda q: density(q).imag, 0., limit, points=splits,
                            epsabs=1e-9, epsrel=3e-8, limit=200)[0]+cut)
        result += weight*scalar
    return result


@pytest.mark.parametrize("name,channel", [("eq40_k_sigma_star", 4), ("eq41_k_sigma_star", 5)])
@pytest.mark.parametrize("epsilon", [EPSILON, np.array([1., 1j, 0.])/np.sqrt(2)])
def test_printed_k_coefficients_complex_gk_and_electromagnetic_phase(
        decuplet, production, tree, strong, name, channel, epsilon):
    # Catches wrong Eq41 sqrt(2), a conjugated gK, wrong i, spin order or f_K.
    p = np.array([.11, -.17, .23])
    pion = np.r_[np.sqrt(tree.pi0_mass_gev**2+p @ p), p]
    k = np.array([0., 0., .51])
    actual = getattr(decuplet, name)(pion, k, epsilon, production, tree, strong)
    expected = _source_oracle(channel, pion, k, epsilon, production, tree, strong, kr=False)
    assert actual.shape == (2, 2) and actual.dtype == np.complex128
    np.testing.assert_allclose(actual, expected, rtol=2e-13, atol=1e-12)
    if channel == 5:
        assert not np.allclose(actual, expected*np.sqrt(2))


def test_eq42_printed_4sqrt3_coefficient_and_cross_product_phase(decuplet, production, tree, strong):
    # Catches the brief's six-times-smaller coefficient and reversed spin phase.
    pion, epsilon = np.array([.4, .11, -.17, .23]), np.array([1., 1j, 0.])/np.sqrt(2)
    actual = decuplet.eq42_sigma_star_kr(pion, epsilon, production, strong)
    expected = _kr_oracle(pion, epsilon, production, strong)
    np.testing.assert_allclose(actual, expected, rtol=1e-14, atol=1e-12)
    assert not np.allclose(actual, expected/6)


@pytest.mark.parametrize("name", ["eq40_k_sigma_star", "eq41_k_sigma_star"])
def test_k_sources_are_independent_of_eta_coupling_delta_decay_and_kaon_decay_constant(
        decuplet, production, tree, strong, name):
    # Catches normalizing by original g_eta or f_Delta, including divisions by zero.
    args = (np.array([.4, .11, -.17, .23]), np.array([0., 0., .51]), EPSILON, production)
    expected = getattr(decuplet, name)(*args, tree, strong)
    zeroed = replace(tree, g_eta_delta=0j, f_delta_n_pi=0.)
    altered = replace(strong, decay_constants_gev=strong.decay_constants_gev[:3]+(.4, .5, .6))
    np.testing.assert_allclose(getattr(decuplet, name)(*args, zeroed, altered), expected, rtol=1e-14)


@pytest.mark.parametrize("invariant", [0j, 1.2+0j, 1.25065997686+0j, 1.385+0j, 1.52+0j, .4j])
def test_sigma_star_pole_threshold_q3_scaling_and_spacelike_convention(
        decuplet, production, strong, invariant):
    daughters = (strong.baryon_masses_gev[4], strong.meson_masses_gev[0])
    expected = _propagator(invariant, 1.385, .036, daughters)
    actual = decuplet._sigma_star_propagator(invariant, production, daughters)
    assert actual == pytest.approx(expected, rel=1e-13)
    if invariant == 1.385:
        assert actual == pytest.approx(1/(.018j), rel=1e-14)
    elif invariant == .4j:
        assert actual == pytest.approx(1/(.4j-1.385), rel=1e-14)


def test_sigma_star_width_vanishes_exactly_at_threshold(decuplet, production, strong):
    daughters = (strong.baryon_masses_gev[4], strong.meson_masses_gev[0])
    value = decuplet._sigma_star_propagator(complex(sum(daughters)), production, daughters)
    assert value.imag == 0.
    assert value == pytest.approx(1/(sum(daughters)-production.sigma_star_mass_gev))


@pytest.mark.parametrize("bad", [True, np.nan, -1., -.4j, 1.+.2j, "1.385"])
def test_sigma_star_rejects_unsupported_invariant_with_context(decuplet, production, strong, bad):
    with pytest.raises(ValueError, match="Sigma.*propagator"):
        decuplet._sigma_star_propagator(bad, production, (strong.baryon_masses_gev[4], strong.meson_masses_gev[0]))


@pytest.mark.parametrize("daughters", [(0., .14), (True, .14), (1.2,), (1.4, .14), (1.1, np.nan)])
def test_sigma_star_rejects_invalid_daughter_thresholds(decuplet, production, daughters):
    with pytest.raises(ValueError, match="Sigma.*propagator"):
        decuplet._sigma_star_propagator(1.385, production, daughters)


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("channel", range(6))
def test_single_entry_t_preserves_physical_channels_and_one_intermediate_propagator(
        decuplet, production, tree, strong, sample, family, channel):
    # Catches a wrong row/column, an external Delta, squared propagator or lost KR.
    seen = []
    transition = .7-.3j
    def strong_t(z):
        seen.append(z)
        value = np.zeros((6, 6), complex)
        value[channel, 2], value[channel, 0] = transition, 99+3j
        return value
    actual = getattr(decuplet, family)(sample, EPSILON, production, tree, strong, strong_t)
    expected = np.zeros((len(sample.initial), 2, 2), complex)
    active = channel == 2 if family == FAMILIES[0] else channel in (4, 5)
    if active:
        pole, width, daughters = ((tree.delta_mass_gev, tree.delta_width_gev,
            (strong.baryon_masses_gev[0], strong.meson_masses_gev[0])) if channel == 2 else
            (production.sigma_star_mass_gev, production.sigma_star_width_gev,
             (strong.baryon_masses_gev[4], strong.meson_masses_gev[0])))
        for event, w in enumerate(sample.initial[:, 0]):
            k = np.array([0., 0., (w*w-tree.proton_mass_gev**2)/(2*w)])
            source = _source_oracle(channel, sample.momenta[event, 1], k, EPSILON, production, tree, strong)
            expected[event] = transition*source*_loop_oracle(sample, event, channel, production, strong,
                                                            pole, width, daughters)
    assert actual.shape == (2, 2, 2) and actual.dtype == np.complex128
    assert np.all(np.isfinite(actual))
    np.testing.assert_allclose(actual, expected, rtol=4e-5, atol=2e-7)
    if not active:
        np.testing.assert_array_equal(actual, expected)
    pair = sample.momenta[:, 0]+sample.momenta[:, 2]
    np.testing.assert_allclose(seen, np.sqrt(pair[:, 0]**2-np.sum(pair[:, 1:]**2, axis=1)), rtol=1e-13)


def test_eta_family_uses_the_shared_eq39_with_original_tree_and_complex_polarization(
        decuplet, production, tree, strong, sample, monkeypatch):
    # A shared-vertex correction must reach this family; duplicated Eq39 would fail.
    one = replace(sample, initial=sample.initial[:1], momenta=sample.momenta[:1],
                  weights_gev2=sample.weights_gev2[:1], s12_gev2=sample.s12_gev2[:1])
    epsilon = np.array([1., 1j, 0.])/np.sqrt(2)
    t = np.zeros((6, 6), complex)
    t[2, 2] = 1j
    original = decuplet.delta1700_eta_delta_vertex
    baseline = decuplet.eta_delta_rescattering_amplitude(one, epsilon, production, tree, strong, lambda z: t)
    def corrected(w, k, p, e, parameters):
        assert parameters is tree
        return -original(w, k, p, e, parameters)
    monkeypatch.setattr(decuplet, "delta1700_eta_delta_vertex", corrected)
    corrected_result = decuplet.eta_delta_rescattering_amplitude(one, epsilon, production, tree, strong, lambda z: t)
    np.testing.assert_allclose(corrected_result, -baseline, rtol=1e-13, atol=1e-12)
    w = one.initial[0, 0]
    k = np.array([0., 0., (w*w-tree.proton_mass_gev**2)/(2*w)])
    daughters = (strong.baryon_masses_gev[0], strong.meson_masses_gev[0])
    expected = 1j*_source_oracle(2, one.momenta[0, 1], k, epsilon, production, tree, strong)
    expected *= _loop_oracle(one, 0, 2, production, strong, tree.delta_mass_gev, tree.delta_width_gev, daughters)
    np.testing.assert_allclose(baseline[0], expected, rtol=4e-5, atol=2e-7)


def test_families_supply_physical_landmarks_and_common_lambda_pi_sigma_width(
        decuplet, production, tree, strong, sample, monkeypatch):
    # Contract pins threshold/pole splits, Delta in Eq39, Lambda-pi for both K rows.
    def checked_loop(event_sample, event, channel_index, *, source_kernel,
                     intermediate_propagator, transition, production, strong_parameters,
                     context, intermediate_invariant_landmarks_gev):
        pole, threshold, width = ((tree.delta_mass_gev, strong.baryon_masses_gev[0]
            +strong.meson_masses_gev[0], tree.delta_width_gev) if channel_index == 2 else
            (production.sigma_star_mass_gev, strong.baryon_masses_gev[4]
             +strong.meson_masses_gev[0], production.sigma_star_width_gev))
        assert intermediate_invariant_landmarks_gev == (threshold, pole)
        assert f"event={event}" in context and f"channel={channel_index}" in context and "z=" in context
        assert channel_index in (2, 4, 5)
        assert intermediate_propagator(complex(pole)) == pytest.approx(1/(.5j*width))
        return transition*source_kernel(.33, -.2)*intermediate_propagator(complex(pole))
    monkeypatch.setattr(decuplet, "eq26_rescattering_loop", checked_loop)
    t = np.zeros((6, 6), complex)
    t[[2, 3, 4, 5], 2] = [1+2j, 123, .3-.4j, -.7+1j]
    for family, channels in zip(FAMILIES, ((2,), (4, 5))):
        actual = getattr(decuplet, family)(sample, EPSILON, production, tree, strong, lambda z: t)
        expected = np.zeros_like(actual)
        for event, w in enumerate(sample.initial[:, 0]):
            k = np.array([0., 0., (w*w-tree.proton_mass_gev**2)/(2*w)])
            for channel in channels:
                width = tree.delta_width_gev if channel == 2 else production.sigma_star_width_gev
                expected[event] += t[channel, 2]*_source_oracle(channel, sample.momenta[event, 1], k,
                    EPSILON, production, tree, strong)/(width*.5j)
        np.testing.assert_allclose(actual, expected, rtol=2e-13, atol=1e-12)


def test_k_family_includes_kr_even_with_zero_gk_and_sums_before_observables(
        decuplet, production, tree, strong, sample):
    # No gK shortcut/switch may omit Eq42; linear T proves coherent matrix addition.
    one = replace(sample, initial=sample.initial[:1], momenta=sample.momenta[:1],
                  weights_gev2=sample.weights_gev2[:1], s12_gev2=sample.s12_gev2[:1])
    def evaluate(channels, p=production):
        t = np.zeros((6, 6), complex)
        t[list(channels), 2] = 1+1j
        return decuplet.k_sigma_star_rescattering_amplitude(one, EPSILON, p, tree, strong, lambda z: t)
    a, b = evaluate((4,)), evaluate((5,))
    np.testing.assert_allclose(evaluate((4, 5)), a+b, rtol=1e-13, atol=1e-12)
    kr_only = evaluate((4,), replace(production, g_k_sigma_star=0j))
    daughters = (strong.baryon_masses_gev[4], strong.meson_masses_gev[0])
    expected = (1+1j)*_kr_oracle(one.momenta[0, 1], EPSILON, production, strong)*_loop_oracle(
        one, 0, 4, production, strong, production.sigma_star_mass_gev, production.sigma_star_width_gev, daughters)
    np.testing.assert_allclose(kr_only[0], expected, rtol=4e-5, atol=2e-7)
    assert np.linalg.norm(kr_only) > 1e-5


@pytest.mark.parametrize("family,channel,w", [(FAMILIES[0], 2, 1.82), (FAMILIES[1], 4, 2.05), (FAMILIES[1], 5, 2.05)])
def test_physical_default_and_doubled_loops_agree_through_threshold_and_pole(
        decuplet, production, tree, strong, family, channel, w):
    sample = _sample(w, strong, [7])
    t = np.zeros((6, 6), complex)
    t[channel, 2] = .7+.2j
    evaluate = getattr(decuplet, family)
    actual = evaluate(sample, EPSILON, production, tree, strong, lambda z: t)
    doubled = replace(production, quadrature=replace(production.quadrature,
        q_order=2*production.quadrature.q_order, angle_order=2*production.quadrature.angle_order))
    expected = evaluate(sample, EPSILON, doubled, tree, strong, lambda z: t)
    assert np.all(np.isfinite(actual))
    np.testing.assert_allclose(actual, expected, rtol=1e-5, atol=1e-10)


@pytest.mark.parametrize("family,channel", [(FAMILIES[0], 2), (FAMILIES[1], 4)])
def test_forced_nonconvergence_keeps_family_event_channel_and_invariant_context(
        decuplet, production, tree, strong, sample, family, channel):
    low_order = replace(production, quadrature=QuadratureSettings(16, 16, 1e-16, 1e-18))
    t = np.zeros((6, 6), complex)
    t[channel, 2] = 1+1j
    label = "eta_delta" if channel == 2 else "k_sigma_star"
    with pytest.raises(ValueError, match=label+f".*event=0.*channel={channel}.*z=.*convergen"):
        getattr(decuplet, family)(sample, EPSILON, low_order, tree, strong, lambda z: t)


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("bad_t", [np.eye(5), np.full((6, 6), np.nan), np.ones((6, 6), bool)])
def test_malformed_t_has_event_and_invariant_context(decuplet, production, tree, strong, sample, family, bad_t):
    with pytest.raises(ValueError, match="event=0.*channel=.*z=.*T"):
        getattr(decuplet, family)(sample, EPSILON, production, tree, strong, lambda z: bad_t)


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("epsilon", [np.zeros(3), [1., 0., 1.], [True, False, False], [np.nan, 0., 0.]])
def test_invalid_polarization_is_rejected_before_zero_transition(decuplet, production, tree, strong, sample, family, epsilon):
    with pytest.raises(ValueError, match="polarization"):
        getattr(decuplet, family)(sample, epsilon, production, tree, strong, lambda z: np.zeros((6, 6)))


@pytest.mark.parametrize("family", FAMILIES)
def test_wrong_sample_mass_order_and_recoil_are_contextual(decuplet, production, tree, strong, sample, family):
    wrong_order = replace(sample, masses=(sample.masses[1], sample.masses[0], sample.masses[2]))
    recoil = sample.initial.copy()
    recoil[:, 3] = .1
    for bad in (wrong_order, replace(sample, initial=recoil)):
        with pytest.raises(ValueError, match="eta_delta|k_sigma_star"):
            getattr(decuplet, family)(bad, EPSILON, production, tree, strong, lambda z: np.zeros((6, 6)))


@pytest.mark.parametrize("field,bad", [("sigma_star_mass_gev", 0.), ("sigma_star_width_gev", -.036),
                                     ("g_k_sigma_star", complex(np.nan)), ("sigma_star_su3_correction", True),
                                     ("axial_d", np.nan), ("first_loop_cutoff_gev", 0.)])
def test_k_replacement_parameters_are_validated_before_zero_transition(
        decuplet, production, tree, strong, sample, field, bad):
    with pytest.raises(ValueError, match="k_sigma_star.*"+field):
        decuplet.k_sigma_star_rescattering_amplitude(sample, EPSILON, replace(production, **{field: bad}),
            tree, strong, lambda z: np.zeros((6, 6)))


@pytest.mark.parametrize("offset", [0., -.05])
@pytest.mark.parametrize("different_tree_masses", [False, True])
def test_eta_delta_daughter_threshold_is_validated_before_zero_transition(
        decuplet, production, tree, strong, sample, offset, different_tree_masses):
    # Catches the zero-T bypass, equality acceptance, and using tree daughters.
    threshold = strong.baryon_masses_gev[0]+strong.meson_masses_gev[0]
    invalid_tree = replace(tree, delta_mass_gev=threshold+offset)
    if different_tree_masses:
        invalid_tree = replace(invalid_tree, proton_mass_gev=.8, pi0_mass_gev=.1)
    calls = []
    def zero_t(z):
        calls.append(z)
        return np.zeros((6, 6), complex)
    with pytest.raises(ValueError, match="eta_delta.*delta_mass_gev.*proton-pi0 threshold"):
        decuplet.eta_delta_rescattering_amplitude(sample, EPSILON, production,
            invalid_tree, strong, zero_t)
    assert calls == []


def test_k_zero_channel_coefficient_map_is_immutable(decuplet):
    # An exposed mapping must not let a caller turn physical channel 4 on.
    coefficients = decuplet.K_SIGMA_STAR_COEFFICIENTS
    assert coefficients[3] == 0.
    with pytest.raises(TypeError):
        coefficients[3] = 1.
