"""Independent source translations for the coherent PRC73 Fig. 9 family."""

from dataclasses import replace
from importlib import import_module
from pathlib import Path

import numpy as np
import pytest
from scipy.integrate import quad

from graal_theory.amplitudes.delta1700 import Delta1700Parameters
from graal_theory.amplitudes.nstar1535_reduced import load_reduced_parameters
from graal_theory.amplitudes.production_loops import load_production_parameters
from graal_theory.amplitudes.propagators import delta1700_width
from graal_theory.phase_space import SobolConfig, sample_three_body
from graal_theory.models.eta_pi0_p import load_central_parameters


REFERENCES = Path(__file__).resolve().parents[1] / "references"


@pytest.fixture(scope="module")
def resonance():
    # Defer the missing-module assertion to test bodies for a behavioral RED.
    try:
        return import_module("graal_theory.amplitudes.resonance_photoproduction")
    except ModuleNotFoundError as exc:
        missing = str(exc)
        class UnimplementedFamily:
            def __getattr__(self, name):
                pytest.fail(f"Task 4 resonance family is not implemented: {missing}")
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


@pytest.fixture(scope="module")
def sample(strong):
    masses = (strong.meson_masses_gev[2], strong.meson_masses_gev[0],
              strong.baryon_masses_gev[0])
    full = sample_three_body(1.82, masses, SobolConfig(4))
    indices = [7, 13]
    return replace(full, initial=full.initial[indices], momenta=full.momenta[indices],
                   weights_gev2=full.weights_gev2[indices], s12_gev2=full.s12_gev2[indices])


@pytest.mark.parametrize("channel", [0, 1])
@pytest.mark.parametrize("epsilon", [[1., 0., 0.], [0., 1., 0.]])
def test_prepared_explicit_source_matches_three_printed_kernels(
        resonance, production, tree, sample, channel, epsilon):
    # Catches dropping one coherent kernel while hoisting fixed event work.
    pion = sample.momenta[0, 1]
    photon = np.array([0., 0., 0.7])
    q, x = 0.23, 0.37
    prepared = resonance._prepare_explicit_source(
        channel, pion, photon, epsilon, production, tree)
    args = (channel, q, x, pion, photon, epsilon, production, tree)
    expected = np.add.reduce((
        resonance.delta1700_pi_delta_kernel(*args),
        resonance.nstar1520_pi_delta_kernel(*args),
        resonance.delta_kr_pole_kernel(*args),
    ))
    np.testing.assert_allclose(prepared(q, x), expected, rtol=1e-10, atol=1e-10)


def _q(w, m1, m2):
    return np.sqrt((w*w-(m1+m2)**2)*(w*w-(m1-m2)**2))/(2*w)


@pytest.mark.parametrize("channel", [0, 1])
def test_explicit_family_rejects_reachable_zero_width_intermediate_delta(
        resonance, production, tree, strong, sample, channel):
    # Disable the separate Nstar spectral convolution to isolate the Eq26 pole.
    p = replace(production, f_tilde_nstar_delta_pi=0., g_tilde_nstar_delta_pi=0.)
    zero_tree = replace(tree, delta_width_gev=0.,
        width_parameters=replace(tree.width_parameters, delta_pole_width_gev=0.))
    t = np.zeros((6, 6), complex)
    t[channel, 2] = 1.
    with pytest.raises(ValueError, match=rf"explicit_resonances.*event=0.*channel={channel}.*z=.*invariant=.*zero-width Delta intermediate pole"):
        resonance.explicit_resonance_amplitude(sample, [1., 0., 0.], p, zero_tree, strong, lambda z: t)


def test_dormant_explicit_source_skips_unrelated_strong_pole(
        resonance, production, tree, strong, sample):
    dormant = replace(tree, f_delta_n_pi=0., delta_width_gev=0.,
        width_parameters=replace(tree.width_parameters, delta_pole_width_gev=0.))
    no_nstar = replace(production, f_tilde_nstar_delta_pi=0.,
                       g_tilde_nstar_delta_pi=0.)
    transition = np.zeros((6, 6), complex)
    transition[0, 2] = 1.
    transition[1, 2] = 1.
    actual = resonance.explicit_resonance_amplitude(
        sample, [1., 0., 0.], no_nstar, dormant, strong, lambda z: transition)
    np.testing.assert_array_equal(actual, np.zeros((len(sample.initial), 2, 2), complex))
    active = replace(dormant, f_delta_n_pi=tree.f_delta_n_pi)
    with pytest.raises(ValueError, match="zero-width Delta intermediate pole"):
        resonance.explicit_resonance_amplitude(
            sample, [1., 0., 0.], no_nstar, active, strong, lambda z: transition)


def test_prepared_family_matches_scalar_three_kernel_oracle(
        resonance, production, tree, strong, sample):
    from graal_theory.amplitudes.production_loops import (
        QuadratureSettings, eq26_rescattering_loop,
    )
    from graal_theory.kinematics import cm_photon_momentum, invariant_mass
    one = replace(sample, initial=sample.initial[:1], momenta=sample.momenta[:1],
                  weights_gev2=sample.weights_gev2[:1], s12_gev2=sample.s12_gev2[:1])
    p = replace(production, quadrature=QuadratureSettings(q_order=32, angle_order=32))
    transition = np.zeros((6, 6), complex)
    transition[0, 2], transition[1, 2] = .7+.2j, -.3+.5j
    epsilon = np.array([1., 0., 0.])
    actual = resonance.explicit_resonance_amplitude(
        one, epsilon, p, tree, strong, lambda z: transition)[0]
    z = float(invariant_mass(one.momenta[0, 0]+one.momenta[0, 2]))
    k = cm_photon_momentum(float(one.initial[0, 0]), tree.proton_mass_gev)
    expected = np.zeros((2, 2), complex)
    for channel in (0, 1):
        def source(q, x):
            args = (channel, q, x, one.momenta[0, 1], k, epsilon, p, tree)
            return np.add.reduce(tuple(getattr(resonance, name)(*args) for name in
                ("delta1700_pi_delta_kernel", "nstar1520_pi_delta_kernel",
                 "delta_kr_pole_kernel")))
        expected += eq26_rescattering_loop(
            one, 0, channel, source,
            lambda invariant: resonance._delta_propagator(invariant, channel, tree, strong),
            transition[channel, 2], p, strong, "scalar oracle",
            intermediate_invariant_landmarks_gev=(
                strong.baryon_masses_gev[channel]+strong.meson_masses_gev[channel],
                tree.delta_mass_gev))
    # Analytic angular integration changes reduction order; keep a bound
    # tighter than configured 1e-5 direct-loop tolerance.
    np.testing.assert_allclose(actual, expected, rtol=1e-6, atol=1e-10)


def _sigma(v):
    x, y, z = v
    return np.array([[z, x-1j*y], [x+1j*y, -z]])


def _delta_gamma(w, tree, baryon, pion):
    if w <= baryon+pion:
        return 0.
    return tree.delta_width_gev*(_q(w, baryon, pion)/_q(
        tree.delta_mass_gev, baryon, pion))**3*tree.delta_mass_gev/w


def _width_oracle(w, production, tree, strong):
    """NPA Eqs.(11),(13),(15),(16),(20),(21),(75), adaptive physical domain."""
    m, mu = strong.baryon_masses_gev[0], strong.meson_masses_gev[1]
    npi = (production.nstar1520_npi_width_gev*(_q(w, m, mu)/_q(
        production.nstar1520_mass_gev, m, mu))**5 if w > m+mu else 0.)
    if w <= m+2*mu:
        return npi, 0., 0.

    def delta_integrand(mi):
        k = _q(w, mi, mu)
        gamma = _delta_gamma(mi, tree, m, mu)
        a_s = -np.sqrt(4*np.pi)*(production.f_tilde_nstar_delta_pi
                                  +production.g_tilde_nstar_delta_pi*k*k/(3*mu*mu))
        a_d = np.sqrt(4*np.pi)*production.g_tilde_nstar_delta_pi*k*k/(3*mu*mu)
        return gamma/((mi-tree.delta_mass_gev)**2+(gamma/2)**2)*mi*k/(4*np.pi*w)*(a_s*a_s+a_d*a_d)/(2*np.pi**2)

    delta = quad(delta_integrand, m+mu, w-mu, epsabs=1e-11, epsrel=2e-10,
                 points=[tree.delta_mass_gev] if m+mu < tree.delta_mass_gev < w-mu else None)[0]
    rho_mass, f_rho = tree.width_parameters.rho_mass_gev, tree.width_parameters.f_rho
    upper = (w*w+mu*mu-(m+mu)**2)/(2*w)

    def outer(o1):
        q1 = np.sqrt(o1*o1-mu*mu)
        rem2 = w*w+mu*mu-2*w*o1
        rem = np.sqrt(rem2)
        e2 = (rem2+mu*mu-m*m)/(2*rem)
        q2star = _q(rem, m, mu)
        low, high = ((w-o1)*e2-q1*q2star)/rem, ((w-o1)*e2+q1*q2star)/rem
        def inner(o2):
            q2 = np.sqrt(o2*o2-mu*mu)
            angle = ((w-o1-o2)**2-m*m-q1*q1-q2*q2)/(2*q1*q2)
            diff2 = q1*q1+q2*q2-2*q1*q2*angle
            rho_s = (o1+o2)**2-(q1*q1+q2*q2+2*q1*q2*angle)
            gamma = 2*f_rho*f_rho*_q(np.sqrt(rho_s), mu, mu)**3/(12*np.pi*rho_s)
            cutoff = production.rho_form_factor_cutoff_gev
            form = (cutoff**2-rho_mass**2)/(cutoff**2-rho_s)
            return form*form*diff2/((rho_s-rho_mass*rho_mass)**2+(rho_mass*gamma)**2)
        return quad(inner, low, high, epsabs=1e-11, epsrel=2e-10)[0]
    integral = quad(outer, mu, upper, epsabs=1e-11, epsrel=2e-9)[0]
    rho = 3*m*production.nstar1520_mass_gev*production.g_rho_nstar**2*f_rho**2/(6*(2*np.pi)**3*w)*integral
    return npi, delta, rho


def _kernel_oracle(name, channel, q, pion, k, epsilon, production, tree, strong):
    """PRC Eqs.(30)-(35); transition contraction uses its independent identity."""
    p = pion[1:]
    k0 = np.linalg.norm(k)
    w = k0+np.sqrt(tree.proton_mass_gev**2+k0*k0)
    if name == "delta_kr_pole_kernel":
        if channel == 0:
            return np.zeros((2, 2), dtype=complex)
        mu, baryon = tree.pion_reference_mass_gev, tree.delta_mass_gev
        q0 = (w*w+mu*mu-baryon*baryon)/(2*w)
        qon2 = q0*q0-mu*mu
        cutoff = production.pion_form_factor_cutoff_gev
        form = (cutoff*cutoff-mu*mu)/(cutoff*cutoff-mu*mu+2*q0*k0)
        return (production.electric_charge*np.sqrt(2)/9*(tree.f_delta_n_pi/mu)**2
                *form*(1-qon2/(3*q0*k0))
                *(2*(p @ epsilon)*np.eye(2)-1j*_sigma(np.cross(p, epsilon))))
    if name == "delta1700_pi_delta_kernel":
        coefficient = 2/np.sqrt(3)*(1/(2*np.sqrt(2)) if channel == 0 else 1.)
        ft, gt = tree.width_parameters.f_tilde_delta_pi, tree.width_parameters.g_tilde_delta_pi
        g1, g2 = tree.g1_prime, tree.g2_prime
        mass, gamma = tree.delta1700_mass_gev, delta1700_width(w, tree.width_parameters)
    else:
        coefficient = np.sqrt(2)/3*(np.sqrt(2) if channel == 0 else 1.)
        ft, gt = production.f_tilde_nstar_delta_pi, production.g_tilde_nstar_delta_pi
        g1, g2 = production.g1_nstar_per_gev, production.g2_nstar_per_gev2
        mass, gamma = production.nstar1520_mass_gev, sum(_width_oracle(w, production, tree, strong))
    def contraction(a, b):
        return 2/3*(a @ b)*np.eye(2)-1j/3*_sigma(np.cross(a, b))
    bracket = (g1/(2*tree.proton_mass_gev)*contraction(p, k) @ _sigma(np.cross(k, epsilon))
               -1j*contraction(p, epsilon)*(g1*(k0+k0*k0/(2*tree.proton_mass_gev))+g2*w*k0))
    return (-1j*coefficient*tree.f_delta_n_pi/tree.pion_reference_mass_gev
            *(ft+gt*q*q/(3*tree.pion_reference_mass_gev**2))
            /(w-mass+.5j*gamma)*bracket)


@pytest.mark.parametrize("name", ["delta1700_pi_delta_kernel", "nstar1520_pi_delta_kernel", "delta_kr_pole_kernel"])
@pytest.mark.parametrize("channel", [0, 1])
def test_printed_kernel_phases_spin_order_channel_factors_and_pole_partner(
        resonance, production, tree, strong, name, channel):
    # Catches a wrong overall i, charge coefficient, cross product, q^2 or partner.
    assert (tree.width_parameters.f_tilde_delta_pi, tree.width_parameters.g_tilde_delta_pi) == (-1.325, .146)
    assert (production.f_tilde_nstar_delta_pi, production.g_tilde_nstar_delta_pi) == (-1.061, .640)
    p = np.array([.11, -.17, .23])
    pion = np.r_[np.sqrt(tree.pi0_mass_gev**2+p @ p), p]
    k, epsilon = np.array([0., 0., .51]), np.array([.6, .8, 0.])
    actual = getattr(resonance, name)(channel, .33, -.2, pion, k, epsilon, production, tree)
    expected = _kernel_oracle(name, channel, .33, pion, k, epsilon, production, tree, strong)
    assert actual.shape == (2, 2) and actual.dtype == np.complex128
    np.testing.assert_allclose(actual, expected, rtol=2e-5, atol=1e-11)
    if name == "delta_kr_pole_kernel" and channel == 0:
        np.testing.assert_array_equal(actual, np.zeros((2, 2), complex))


def test_nstar_width_at_pole_matches_all_three_independent_source_integrals(resonance, production, tree, strong):
    # Catches missing N-rho isospin 3/F_rho, wrong Delta spectral coefficient, q^3.
    expected = _width_oracle(production.nstar1520_mass_gev, production, tree, strong)
    assert expected[0] == .066
    assert all(v > 0 for v in expected)
    assert resonance.nstar1520_width(production.nstar1520_mass_gev, production, tree, strong) == pytest.approx(sum(expected), rel=2e-5, abs=1e-10)


def test_nstar_width_rejects_accessible_interior_zero_width_delta_spectral_pole(
        resonance, production, tree, strong):
    # quad(points=[pole]) avoids sampling the pole and otherwise returns false zero.
    delta_only = replace(production, nstar1520_npi_width_gev=0., g_rho_nstar=0.)
    zero_width = replace(tree, delta_width_gev=0.)
    with pytest.raises(ValueError, match="nstar1520 width.*zero-width Delta spectral pole"):
        resonance.nstar1520_width(1.52, delta_only, zero_width, strong)


@pytest.mark.parametrize("offset", [-1e-8, 0.])
def test_zero_width_delta_spectral_pole_at_or_above_upper_endpoint_contributes_zero(
        resonance, production, tree, strong, offset):
    # The phase-space endpoint is zero; no stable-Delta distribution is invented.
    delta_only = replace(production, nstar1520_npi_width_gev=0., g_rho_nstar=0.)
    zero_width = replace(tree, delta_width_gev=0.)
    endpoint_energy = tree.delta_mass_gev+strong.meson_masses_gev[1]+offset
    assert resonance.nstar1520_width(endpoint_energy, delta_only, zero_width, strong) == 0.


def test_inactive_delta_pi_couplings_do_not_trigger_zero_width_spectral_pole(
        resonance, production, tree, strong):
    zero = replace(production, nstar1520_npi_width_gev=0., g_rho_nstar=0.,
                   f_tilde_nstar_delta_pi=0., g_tilde_nstar_delta_pi=0.)
    assert resonance.nstar1520_width(1.52, zero, replace(tree, delta_width_gev=0.), strong) == 0.


def test_kr_pole_uses_pi_delta_on_shell_kinematics_with_signed_closed_channel(resonance, production, tree, strong):
    # W=1.30 is below pi-Delta threshold; the signed q_on^2 must stay negative.
    w = 1.30
    k = np.array([0., 0., (w*w-tree.proton_mass_gev**2)/(2*w)])
    p = np.array([.12, -.07, .09])
    pion = np.r_[np.sqrt(tree.pi0_mass_gev**2+p @ p), p]
    q0 = (w*w+tree.pion_reference_mass_gev**2-tree.delta_mass_gev**2)/(2*w)
    assert q0*q0-tree.pion_reference_mass_gev**2 < 0
    actual = resonance.delta_kr_pole_kernel(1, .3, .1, pion, k, [1., 0., 0.], production, tree)
    expected = _kernel_oracle("delta_kr_pole_kernel", 1, .3, pion, k, np.array([1., 0., 0.]), production, tree, strong)
    np.testing.assert_allclose(actual, expected, rtol=2e-13, atol=1e-12)


@pytest.mark.parametrize("component", ["npi", "delta", "rho"])
def test_partial_widths_vanish_exactly_at_and_below_physical_thresholds(resonance, production, tree, strong, component):
    # Finite Delta/rho thresholds are N+2pi, not stable Delta+pi or N+rho.
    p = replace(production,
        nstar1520_npi_width_gev=production.nstar1520_npi_width_gev if component == "npi" else 0.,
        f_tilde_nstar_delta_pi=production.f_tilde_nstar_delta_pi if component == "delta" else 0.,
        g_tilde_nstar_delta_pi=production.g_tilde_nstar_delta_pi if component == "delta" else 0.,
        g_rho_nstar=production.g_rho_nstar if component == "rho" else 0.)
    threshold = strong.baryon_masses_gev[0]+(1 if component == "npi" else 2)*strong.meson_masses_gev[1]
    for w in (.3, threshold-1e-8, threshold):
        assert resonance.nstar1520_width(w, p, tree, strong) == 0.
    assert resonance.nstar1520_width(threshold+.05, p, tree, strong) > 0.


@pytest.mark.parametrize("bad", [True, 0., -1., np.nan, np.inf, 1j])
def test_width_rejects_nonphysical_energy_with_context(resonance, production, tree, strong, bad):
    with pytest.raises(ValueError, match="nstar1520.*width"):
        resonance.nstar1520_width(bad, production, tree, strong)


def test_nrho_form_cutoff_changes_width_independently_of_loop_cutoff(resonance, production, tree, strong):
    # Catches coupling 5.09 without Eq75 and accidentally aliasing physical cutoffs.
    p = replace(production, nstar1520_npi_width_gev=0., f_tilde_nstar_delta_pi=0., g_tilde_nstar_delta_pi=0.)
    first = resonance.nstar1520_width(1.52, p, tree, strong)
    loop_changed = resonance.nstar1520_width(1.52, replace(p, first_loop_cutoff_gev=1.8), tree, strong)
    rho_changed = replace(p, rho_form_factor_cutoff_gev=1.8)
    second = resonance.nstar1520_width(1.52, rho_changed, tree, strong)
    assert loop_changed == first
    assert second == pytest.approx(_width_oracle(1.52, rho_changed, tree, strong)[2], rel=2e-5)
    assert not np.isclose(first, second, rtol=1e-3)


@pytest.mark.parametrize("bad", [True, 0., -1., np.nan, 1j])
def test_replacement_rho_cutoff_is_validated_before_zero_transition(resonance, production, tree, strong, sample, bad):
    p = replace(production, rho_form_factor_cutoff_gev=bad)
    with pytest.raises(ValueError, match="nstar1520.*width.*rho_form_factor_cutoff_gev"):
        resonance.nstar1520_width(1.52, p, tree, strong)
    with pytest.raises(ValueError, match="explicit_resonances.*rho_form_factor_cutoff_gev"):
        resonance.explicit_resonance_amplitude(sample, [1., 0., 0.], p, tree, strong, lambda z: np.zeros((6, 6)))


@pytest.mark.parametrize("bad_width", [None, {"rho_mass_gev": .77526}])
def test_nested_width_record_is_validated_before_zero_transition(
        resonance, production, tree, strong, sample, bad_width):
    # A zero strong transition must not hide a malformed consumed tree record.
    bad_tree = replace(tree, width_parameters=bad_width)
    with pytest.raises(ValueError, match="explicit_resonances.*width_parameters.*Delta1700WidthParameters"):
        resonance.explicit_resonance_amplitude(sample, [1., 0., 0.], production,
            bad_tree, strong, lambda z: np.zeros((6, 6)))
    with pytest.raises(ValueError, match="nstar1520 width.*width_parameters.*Delta1700WidthParameters"):
        resonance.nstar1520_width(1.52, production, bad_tree, strong)


@pytest.mark.parametrize("invariant", [1.3+0j, 1.+0j, .4j, 0j])
def test_delta_propagator_physical_subthreshold_and_spacelike_branches(resonance, tree, strong, invariant):
    # Catches clamping sqrt(sDelta) or extending the real open-channel width off-sheet.
    m, mu = strong.baryon_masses_gev[1], strong.meson_masses_gev[1]
    gamma = _delta_gamma(invariant.real, tree, m, mu) if invariant.imag == 0 else 0.
    expected = 1/(invariant-tree.delta_mass_gev+.5j*gamma)
    assert resonance._delta_propagator(invariant, 1, tree, strong) == pytest.approx(expected, rel=1e-13)


@pytest.mark.parametrize("channel", [False, -1, 2, "pi_plus_n"])
def test_kernels_reject_wrong_charge_channel(resonance, production, tree, channel):
    with pytest.raises(ValueError, match="channel"):
        resonance.delta_kr_pole_kernel(channel, .3, 0., [.3, .1, .1, .1], [0., 0., .5], [1., 0., 0.], production, tree)


def _eq26_oracle(sample, event, channel, production, tree, strong, kernel, squared_propagator=False):
    """Independent adaptive complex Cauchy PV and physical-cut term."""
    w, pion = sample.initial[event, 0], sample.momenta[event, 1]
    p = np.linalg.norm(pion[1:])
    mu, m = strong.meson_masses_gev[channel], strong.baryon_masses_gev[channel]
    limit = production.first_loop_cutoff_gev
    nodes, weights = np.polynomial.legendre.leggauss(80)
    result = 0j
    for x, weight in zip(nodes, weights):
        def den(q):
            return w-np.sqrt(mu*mu+q*q)-pion[0]-np.sqrt(m*m+q*q+p*p+2*q*p*x)
        def slope(q):
            return -q/np.sqrt(mu*mu+q*q)-(q+p*x)/np.sqrt(m*m+q*q+p*p+2*q*p*x)
        def num(q):
            omega = np.sqrt(mu*mu+q*q)
            en = np.sqrt(m*m+q*q+p*p+2*q*p*x)
            invariant = np.sqrt(complex((w-omega)**2-q*q))
            gamma = _delta_gamma(invariant.real, tree, m, mu) if invariant.imag == 0 else 0.
            prop = 1/(invariant-tree.delta_mass_gev+.5j*gamma)
            return q*q*m/(8*np.pi**2*omega*en)*prop**(2 if squared_propagator else 1)
        from scipy.optimize import brentq
        root = brentq(den, 0., limit)
        residue = num(root)/slope(root)
        def smooth(q):
            return residue if abs(q-root) < 1e-8 else num(q)*(q-root)/den(q)
        scalar = (quad(lambda q: smooth(q).real, 0., limit, weight="cauchy", wvar=root, epsabs=2e-9, epsrel=1e-8, limit=200)[0]
                  +1j*quad(lambda q: smooth(q).imag, 0., limit, weight="cauchy", wvar=root, epsabs=2e-9, epsrel=1e-8, limit=200)[0]
                  -1j*np.pi*num(root)/abs(slope(root)))
        result += weight*scalar
    return result*kernel


@pytest.mark.parametrize("channel", range(6))
def test_wrapper_selects_only_pi_channels_coherently_and_delta_propagator_once(
        resonance, production, tree, strong, sample, monkeypatch, channel):
    # Control diagnostic sources but exercise the real Eq26 loop and real propagator.
    matrices = (np.array([[1+2j, .4j], [.3, -.2j]]),
                np.array([[-.2j, .7], [1j, 2.]]), np.eye(2)*(1-.5j))
    monkeypatch.setattr(resonance, "_prepare_explicit_source",
        lambda c, pion, k, e, p, t: (
            lambda q, x: sum(matrices)*(c+1)*pion[1]))
    seen = []
    def transition(z):
        seen.append(z)
        t = np.zeros((6, 6), dtype=complex)
        t[channel, 2] = .7-.3j
        t[channel, 0] = 99+3j
        return t
    actual = resonance.explicit_resonance_amplitude(sample, [1., 0., 0.], production, tree, strong, transition)
    expected = np.zeros_like(actual)
    if channel < 2:
        for event in range(len(sample.initial)):
            kernel = sum(matrices)*(channel+1)*sample.momenta[event, 1, 1]
            expected[event] = (.7-.3j)*_eq26_oracle(sample, event, channel, production, tree, strong, kernel)
    assert actual.shape == (2, 2, 2) and actual.dtype == np.complex128
    np.testing.assert_allclose(actual, expected, rtol=4e-5, atol=2e-7)
    pair = sample.momenta[:, 0]+sample.momenta[:, 2]
    np.testing.assert_allclose(seen, np.sqrt(pair[:, 0]**2-np.sum(pair[:, 1:]**2, axis=1)), rtol=1e-13)


def test_phase_flip_changes_coherent_wrapper_without_changing_kernel_norm(
        resonance, production, tree, strong, sample):
    # Reject incoherent sum of norms: the same isolated magnitude interferes differently.
    one = replace(sample, initial=sample.initial[:1], momenta=sample.momenta[:1],
                  weights_gev2=sample.weights_gev2[:1], s12_gev2=sample.s12_gev2[:1])
    def t(z):
        matrix = np.zeros((6, 6), complex)
        matrix[1, 2] = 1+1j
        return matrix
    pion = one.momenta[0, 1]
    w = one.initial[0, 0]
    k = [0., 0., (w*w-tree.proton_mass_gev**2)/(2*w)]
    kernel = resonance.nstar1520_pi_delta_kernel(
        1, .3, .2, pion, k, [1., 0., 0.], production, tree)
    first = resonance.explicit_resonance_amplitude(one, [1., 0., 0.], production, tree, strong, t)
    flipped_production = replace(production,
        g1_nstar_per_gev=-production.g1_nstar_per_gev,
        g2_nstar_per_gev2=-production.g2_nstar_per_gev2)
    flipped = resonance.nstar1520_pi_delta_kernel(
        1, .3, .2, pion, k, [1., 0., 0.], flipped_production, tree)
    second = resonance.explicit_resonance_amplitude(
        one, [1., 0., 0.], flipped_production, tree, strong, t)
    assert np.sum(abs(kernel)**2) == np.sum(abs(flipped)**2)
    assert not np.isclose(np.sum(abs(first)**2), np.sum(abs(second)**2), rtol=1e-3)


@pytest.mark.parametrize("bad_t", [lambda z: np.ones((2, 2)), lambda z: np.full((6, 6), np.nan)])
def test_wrapper_reports_event_channel_invariant_for_bad_strong_matrix(resonance, production, tree, strong, sample, bad_t):
    with pytest.raises(ValueError, match="explicit_resonances.*event=0.*channel=.*z="):
        resonance.explicit_resonance_amplitude(sample, [1., 0., 0.], production, tree, strong, bad_t)
