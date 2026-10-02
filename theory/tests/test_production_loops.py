"""Independent loop checks; each test names the numerical break it catches."""

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from graal_theory.amplitudes import production_loops as loops
from graal_theory.amplitudes.nstar1535_reduced import load_reduced_parameters
from graal_theory.phase_space import SobolConfig, sample_three_body


REFERENCES = Path(__file__).resolve().parents[1] / "references"
CONTEXT = "Fig9 channel=pi_plus_n invariant=1.62GeV"


@pytest.fixture
def parameters():
    return loops.load_production_parameters(
        REFERENCES / "eta_pi0_p_full_parameters.json", REFERENCES / "sources.json",
    )


@pytest.fixture
def strong_parameters():
    return load_reduced_parameters(
        REFERENCES / "nstar1535_reduced_parameters.json", REFERENCES / "sources.json",
    )


def test_monopole_uses_minkowski_squared_momentum_and_numerator_mass():
    # Catches using |p|^2, a plus denominator, or omitting the numerator mass.
    np.testing.assert_allclose(
        loops.pion_monopole(np.array([-0.5, 0.04, 0.2]), 0.2, 1.0),
        [0.64, 1.0, 1.2], rtol=1e-14,
    )


@pytest.mark.parametrize("bad", [True, 1j, np.nan, np.inf, "0.2"])
def test_monopole_rejects_nonreal_nonfinite_momentum(bad):
    # Catches coercion that silently treats bool/string/complex as physical p^2.
    with pytest.raises(ValueError, match="monopole"):
        loops.pion_monopole(bad, 0.14, 1.25)


@pytest.mark.parametrize("mass, cutoff", [(0, 1.25), (0.14, 0), (True, 1.25), (0.14, np.inf)])
def test_monopole_rejects_nonphysical_scales(mass, cutoff):
    with pytest.raises(ValueError, match="monopole"):
        loops.pion_monopole(0.2, mass, cutoff)


def test_monopole_reports_true_cutoff_pole():
    with pytest.raises(ValueError, match="monopole.*pole"):
        loops.pion_monopole([0, 1.25**2], 0.14, 1.25)


def test_complex_1d_retains_imaginary_part_and_interval_jacobian():
    # Exact integral = sin(1) + i(1-cos(1)); catches real accumulation or 2x scale.
    value = loops._integrate_complex_1d(
        lambda q: np.exp(1j*q), 0, 1,
        settings=loops.QuadratureSettings(), context=CONTEXT,
    )
    assert value == pytest.approx(np.sin(1) + 1j*(1-np.cos(1)), abs=1e-13)


def test_complex_2d_retains_both_interval_jacobians_and_spin_shape():
    # Exact odd angular part cancels; int q^2 dq int dx = 2/3.
    matrix = np.array([[1, 2j], [3, 4]], dtype=complex)
    value = loops._integrate_complex_2d(
        lambda q, x: (x + 1j*q*q)*matrix, 0, 1, -1, 1,
        settings=loops.QuadratureSettings(), context=CONTEXT,
    )
    np.testing.assert_allclose(value, 2j/3*matrix, atol=1e-13)


@pytest.mark.parametrize("dimensions", [1, 2])
def test_quadrature_rejects_nonfinite_values_with_physics_context(dimensions):
    helper = getattr(loops, f"_integrate_complex_{dimensions}d")
    bounds = (0, 1) if dimensions == 1 else (0, 1, -1, 1)
    with pytest.raises(ValueError, match=CONTEXT):
        helper(lambda *args: np.nan + 1j, *bounds,
               settings=loops.QuadratureSettings(), context=CONTEXT)


@pytest.mark.parametrize("dimensions", [1, 2])
def test_quadrature_requires_configured_and_doubled_orders_to_agree(dimensions):
    # A rapidly oscillating unresolved function catches returning base unchecked.
    helper = getattr(loops, f"_integrate_complex_{dimensions}d")
    bounds = (0, 1) if dimensions == 1 else (0, 1, -1, 1)
    with pytest.raises(ValueError, match=CONTEXT + ".*convergen"):
        helper(lambda q, *args: np.exp(1000j*q), *bounds,
               settings=loops.QuadratureSettings(16, 16, 1e-10, 1e-12), context=CONTEXT)


@pytest.mark.parametrize("bounds", [(True, 1), (1, 0), (0, np.inf), (0, 1j)])
def test_quadrature_rejects_malformed_domains_with_context(bounds):
    with pytest.raises(ValueError, match=CONTEXT):
        loops._integrate_complex_1d(lambda q: q, *bounds,
                                    settings=loops.QuadratureSettings(), context=CONTEXT)


def _independent_eq8(w, parameters, strong_parameters, channel):
    """Separate 192x192 GL evaluation of Eq. (8), rationalized in q^2.

    This oracle does not use production quadrature, coefficients, or cut helpers.
    The delta-function term is the literal two-body cut -M p/(4 pi W).
    """
    m = strong_parameters.meson_masses_gev[channel]
    baryon = strong_parameters.baryon_masses_gev[channel]
    decay = strong_parameters.decay_constants_gev[channel]
    limit = parameters.first_loop_cutoff_gev
    nodes, weights = np.polynomial.legendre.leggauss(192)
    q, qw = (nodes+1)*limit/2, weights*limit/2
    x = nodes
    omega, energy = np.sqrt(q*q+m*m), np.sqrt(q*q+baryon*baryon)
    k = (w*w-strong_parameters.baryon_masses_gev[0]**2)/(2*w)
    kr_a = [0, -1, 0, 0, np.sqrt(2/3), 0]
    kr_b = [0, 0, 0, -1/np.sqrt(2), -1/np.sqrt(6), 0]
    bbm_a = [1/np.sqrt(2), 1, 1/np.sqrt(6), 0, -np.sqrt(2/3), 0]
    bbm_b = [0, 0, -np.sqrt(2/3), 1/np.sqrt(2), 1/np.sqrt(6), 1]
    charge = [0, -1, 0, -1, -1, 0]

    def numerator(r):
        om, en = np.sqrt(r*r+m*m), np.sqrt(r*r+baryon*baryon)
        omp = np.sqrt(r[..., None]**2+k*k-2*r[..., None]*k*x+m*m)
        bracket = k*omp + (en[..., None]-w)*(om[..., None]+omp) + (om[..., None]+omp)**2
        mp = (r[..., None]**4*(1-x*x)/en[..., None] * bracket
              / ((w-omp-k-en[..., None])*om[..., None]*omp
                 *(k-om[..., None]-omp)*(k+om[..., None]+omp)))
        return r*r*baryon/(4*np.pi**2*om*en), np.sum(mp*weights, axis=-1)

    fkr, fmp = numerator(q)
    if w > m+baryon:
        p = np.sqrt((w*w-(m+baryon)**2)*(w*w-(m-baryon)**2))/(2*w)
        omon = (w*w+m*m-baryon*baryon)/(2*w)
        transform = (omon+omega)*(w-omega+energy)/(2*w)
        fkr_on, fmp_on = numerator(np.asarray(p))
        transform_on = (2*omon)*(2*np.sqrt(p*p+baryon*baryon))/(2*w)
        cut_integral = np.log((limit+p)/(limit-p))/(2*p)-1j*np.pi/(2*p)
        kr = np.sum(qw*(fkr*transform-fkr_on*transform_on)/(p*p-q*q)) + fkr_on*transform_on*cut_integral
        mp = np.sum(qw*(fmp*transform-fmp_on*transform_on)/(p*p-q*q)) + fmp_on*transform_on*cut_integral
    else:
        kr = np.sum(qw*fkr/(w-energy-omega))
        mp = np.sum(qw*fmp/(w-energy-omega))
    axial_kr = (kr_a[channel]*(parameters.axial_d+parameters.axial_f)
                +kr_b[channel]*(parameters.axial_d-parameters.axial_f))/2
    axial_mp = (bbm_a[channel]*(parameters.axial_d+parameters.axial_f)
                +bbm_b[channel]*(parameters.axial_d-parameters.axial_f))/2
    return (-np.sqrt(2)*1j*parameters.electric_charge*axial_kr/decay*kr,
            np.sqrt(2)*1j*parameters.electric_charge*axial_mp/decay
            *charge[channel]*baryon/(8*np.pi**2)*mp)


@pytest.mark.parametrize("channel", [1, 3, 4])
def test_eta_photoproduction_preserves_both_gauge_terms_and_channel_masses(parameters, strong_parameters, channel):
    # Catches wrong Table II signs, lost MP/KR, 2pi normalization, and mass index.
    transition = 0.7+0.2j
    def t(w):
        assert w == 1.62  # source requires T at total eta-photoproduction invariant
        matrix = np.zeros((6, 6), dtype=complex)
        matrix[channel, 2] = transition
        return matrix
    kr, mp = _independent_eq8(1.62, parameters, strong_parameters, channel)
    expected = transition*(kr+mp)*np.array([[0, 1], [1, 0]])
    actual = loops.eta_photoproduction_amplitude(1.62, np.array([1., 0, 0]), parameters, strong_parameters, t)
    assert actual.shape == (2, 2)
    np.testing.assert_allclose(actual, expected, rtol=2e-5, atol=1e-9)
    assert abs(kr) > 1e-5 and abs(mp) > 1e-5
    assert not np.allclose(expected, transition*kr*np.array([[0, 1], [1, 0]]))
    assert not np.allclose(expected, transition*mp*np.array([[0, 1], [1, 0]]))


@pytest.mark.parametrize("channel", [0, 2, 5])
def test_eta_photoproduction_preserves_exact_table_ii_zero_channels(parameters, strong_parameters, channel):
    t = np.zeros((6, 6), dtype=complex)
    t[channel, 2] = 1+2j
    np.testing.assert_array_equal(
        loops.eta_photoproduction_amplitude(1.62, np.array([1., 0, 0]), parameters, strong_parameters, lambda w: t),
        np.zeros((2, 2)),
    )


def test_eta_diagonal_strong_t_is_exactly_zero(parameters, strong_parameters):
    np.testing.assert_array_equal(
        loops.eta_photoproduction_amplitude(1.62, np.array([1., 0, 0]), parameters, strong_parameters, lambda w: np.eye(6, dtype=complex)),
        np.zeros((2, 2)),
    )


@pytest.mark.parametrize("bad", [True, np.bool_(True), 1.62+0j, np.nan, np.inf, 0, 1.71])
def test_eta_energy_domain_rejects_malformed_and_unsupported_invariants(parameters, strong_parameters, bad):
    with pytest.raises(ValueError, match="eta photoproduction.*invariant"):
        loops.eta_photoproduction_amplitude(bad, np.array([1., 0, 0]), parameters, strong_parameters, lambda w: np.eye(6))


@pytest.mark.parametrize("bad", [np.zeros(3), [1, 0], [1, 0, 1], [np.nan, 0, 0], [True, False, False], ["1", "0", "0"]])
def test_eta_polarization_is_finite_nonzero_and_coulomb_transverse(parameters, strong_parameters, bad):
    with pytest.raises(ValueError, match="eta photoproduction.*polarization"):
        loops.eta_photoproduction_amplitude(1.62, bad, parameters, strong_parameters, lambda w: np.eye(6))


@pytest.mark.parametrize("bad", [np.eye(5), np.full((6, 6), np.nan), np.full((6, 6), np.inf), np.ones((6, 6), dtype=bool), np.full((6, 6), "1")])
def test_eta_strong_t_requires_finite_six_channel_matrix(parameters, strong_parameters, bad):
    with pytest.raises(ValueError, match="eta photoproduction.*T"):
        loops.eta_photoproduction_amplitude(1.62, np.array([1., 0, 0]), parameters, strong_parameters, lambda w: bad)


@pytest.mark.parametrize("w", [1.487, 1.62, 1.70])
def test_eta_direct_integrals_converge_at_threshold_peak_and_endpoint(parameters, strong_parameters, w):
    # Both closed kaon and open pion channels contribute; imaginary q is ordinary.
    if w == 1.487:
        w = strong_parameters.meson_masses_gev[2]+strong_parameters.baryon_masses_gev[2]+1e-6
    t = np.zeros((6, 6), dtype=complex)
    t[[1, 3, 4], 2] = [1+0.1j, 0.2-0.3j, -0.4+0.2j]
    value = loops.eta_photoproduction_amplitude(w, [1., 0, 0], parameters, strong_parameters, lambda z: t)
    assert np.all(np.isfinite(value))


@pytest.mark.parametrize("offset", [-1e-6, 0., 1e-6])
def test_eta_pair_converges_on_both_sides_of_pion_channel_threshold(parameters, strong_parameters, offset):
    # Catches an unresolved narrow closed-channel boundary layer or a wrong cut.
    w = strong_parameters.meson_masses_gev[1]+strong_parameters.baryon_masses_gev[1]+offset
    t = np.zeros((6, 6), dtype=complex)
    t[1, 2] = 1.
    value = loops.eta_photoproduction_amplitude(w, [1., 0, 0], parameters, strong_parameters, lambda z: t)
    assert np.all(np.isfinite(value))
    if offset < 0:
        # At a closed channel the loop is real and Eq.(8)'s vertex is imaginary.
        assert abs(value[0, 1].real) < 1e-12
    elif offset > 0:
        assert abs(value[0, 1].real) > 1e-6


@pytest.mark.parametrize("bad", [True, None, np.nan, 0, -1])
def test_eta_cutoff_validation_keeps_family_and_invariant_context(parameters, strong_parameters, bad):
    with pytest.raises(ValueError, match="eta photoproduction.*cutoff"):
        loops.eta_photoproduction_amplitude(1.62, [1., 0, 0], replace(parameters, first_loop_cutoff_gev=bad), strong_parameters, lambda z: np.eye(6))


def test_eta_true_cutoff_endpoint_pole_is_contextual(parameters, strong_parameters):
    mass, baryon = strong_parameters.meson_masses_gev[1], strong_parameters.baryon_masses_gev[1]
    cutoff = np.sqrt((1.62**2-(mass+baryon)**2)*(1.62**2-(mass-baryon)**2))/(2*1.62)
    t = np.zeros((6, 6), dtype=complex)
    t[1, 2] = 1.
    with pytest.raises(ValueError, match="eta photoproduction.*pi_plus_n.*pole"):
        loops.eta_photoproduction_amplitude(1.62, [1., 0, 0], replace(parameters, first_loop_cutoff_gev=cutoff), strong_parameters, lambda z: t)


def test_eta_circular_polarization_preserves_pauli_spin_structure(parameters, strong_parameters):
    # Catches treating sigma.epsilon as scalar or dropping complex polarization.
    t = np.zeros((6, 6), dtype=complex)
    t[1, 2] = 1.
    kr, mp = _independent_eq8(1.62, parameters, strong_parameters, 1)
    value = loops.eta_photoproduction_amplitude(1.62, np.array([1., 1j, 0])/np.sqrt(2), parameters, strong_parameters, lambda z: t)
    np.testing.assert_allclose(value, (kr+mp)*np.array([[0, np.sqrt(2)], [0, 0]]), rtol=2e-5, atol=1e-9)


@pytest.mark.parametrize("which", ["production", "strong"])
def test_eta_rejects_malformed_parameter_records_with_context(parameters, strong_parameters, which):
    if which == "production":
        parameters = None
    else:
        strong_parameters = None
    with pytest.raises(ValueError, match="eta photoproduction"):
        loops.eta_photoproduction_amplitude(1.62, [1., 0, 0], parameters, strong_parameters, lambda z: np.eye(6))


def test_eta_strong_t_pole_is_reported_with_family_and_invariant(parameters, strong_parameters):
    def pole(w):
        raise ZeroDivisionError("genuine T pole")
    with pytest.raises(ValueError, match="eta photoproduction.*T.*pole"):
        loops.eta_photoproduction_amplitude(1.62, [1., 0, 0], parameters, strong_parameters, pole)


@pytest.fixture
def sample(strong_parameters):
    masses = (strong_parameters.meson_masses_gev[2], strong_parameters.meson_masses_gev[0], strong_parameters.baryon_masses_gev[0])
    return sample_three_body(1.82, masses, SobolConfig(4))


def _independent_closed_eq26(sample, event, strong, channel, cutoff):
    # Literal Eq. (26)-(27) evaluated separately at 192x192; no subtraction/cuts
    # needed here, because selected K-Sigma channels are closed at this event.
    nodes, weights = np.polynomial.legendre.leggauss(192)
    q, qw = (nodes+1)*cutoff/2, weights*cutoff/2
    pion = sample.momenta[event, 1]
    p = np.linalg.norm(pion[1:])
    w = sample.initial[event, 0]
    mass, baryon = strong.meson_masses_gev[channel], strong.baryon_masses_gev[channel]
    omega = np.sqrt(q[:, None]**2+mass**2)
    energy = np.sqrt(baryon**2+q[:, None]**2+p*p+2*q[:, None]*p*nodes)
    value = q[:, None]**2*baryon/(8*np.pi**2*omega*energy*(w-omega-pion[0]-energy))
    return np.sum(value*qw[:, None]*weights)


@pytest.mark.parametrize("channel", [3, 5])
def test_eq26_direct_closed_integral_preserves_measure_recoil_and_requested_masses(parameters, strong_parameters, sample, channel):
    # Catches wrong channel index, q^2/(2omega E), angular Jacobian or pion recoil.
    spin = np.array([[1, 2j], [-1j, 3]], dtype=complex)
    prop, transition = 2+3j, 0.4-0.2j
    expected = _independent_closed_eq26(sample, 7, strong_parameters, channel, 1.4)*spin*prop*transition
    actual = loops.eq26_rescattering_loop(
        sample, 7, channel, lambda q, x: spin, lambda invariant: prop,
        transition, parameters, strong_parameters, CONTEXT,
    )
    np.testing.assert_allclose(actual, expected, rtol=1e-6, atol=1e-11)


def test_eq26_open_channel_has_negative_analytic_unitarity_cut(parameters, strong_parameters, sample):
    # The invariant two-body phase-space delta integral fixes the cut exactly.
    # A wrong i0 sign, missing cut, or angular measure breaks this assertion.
    value = loops.eq26_rescattering_loop(
        sample, 7, 1, lambda q, x: np.eye(2), lambda invariant: 1.,
        1., parameters, strong_parameters, CONTEXT,
    )
    pion = sample.momenta[7, 1]
    z = np.sqrt((1.82-pion[0])**2-np.dot(pion[1:], pion[1:]))
    mass, baryon = strong_parameters.meson_masses_gev[1], strong_parameters.baryon_masses_gev[1]
    pstar = np.sqrt((z*z-(mass+baryon)**2)*(z*z-(mass-baryon)**2))/(2*z)
    np.testing.assert_allclose(value.imag, -baryon*pstar/(4*np.pi*z)*np.eye(2), rtol=1e-9, atol=1e-11)


def test_eq26_uses_source_radial_angle_arguments_and_exact_intermediate_invariant(parameters, strong_parameters, sample):
    # Independent smooth 192x192 integral catches swapped source q/x arguments,
    # wrong invariant, and dropping source/propagator's complex dependence.
    nodes, weights = np.polynomial.legendre.leggauss(192)
    q, qw = (nodes+1)*1.4/2, weights*1.4/2
    mass, baryon = strong_parameters.meson_masses_gev[3], strong_parameters.baryon_masses_gev[3]
    pion = sample.momenta[7, 1]
    p = np.linalg.norm(pion[1:])
    om = np.sqrt(mass*mass+q[:, None]**2)
    en = np.sqrt(baryon*baryon+q[:, None]**2+p*p+2*q[:, None]*p*nodes)
    invariant_squared = (1.82-om)**2-q[:, None]**2
    density = (q[:, None]**2*baryon/(8*np.pi**2*om*en*(1.82-om-pion[0]-en))
               * (q[:, None]+1j*nodes**2)*(1+invariant_squared))
    expected = np.sum(density*qw[:, None]*weights)*np.array([[1, 1j], [2j, -1]])
    value = loops.eq26_rescattering_loop(
        sample, 7, 3, lambda q, x: (q+1j*x*x)*np.array([[1, 1j], [2j, -1]]),
        lambda z: 1+z*z, 1., parameters, strong_parameters, CONTEXT,
    )
    np.testing.assert_allclose(value, expected, rtol=1e-6, atol=1e-11)


def test_eq26_continues_spacelike_intermediate_invariant_on_upper_physical_sheet(parameters, strong_parameters, sample):
    seen_spacelike = []
    def propagator(invariant):
        assert isinstance(invariant, (complex, np.complexfloating))
        assert invariant.imag >= 0
        if invariant.imag > 0:
            seen_spacelike.append(invariant)
            assert invariant.real == 0
        return 1.
    value = loops.eq26_rescattering_loop(
        sample, 7, 3, lambda q, x: np.eye(2), propagator, 1.,
        parameters, strong_parameters, CONTEXT,
    )
    assert seen_spacelike and np.all(np.isfinite(value))


@pytest.mark.parametrize("event, channel", [(True, 1), (-1, 1), (16, 1), (0, True), (0, -1), (0, 6), (0, 1.0)])
def test_eq26_rejects_bad_event_or_channel_indices_with_context(parameters, strong_parameters, sample, event, channel):
    with pytest.raises(ValueError, match=CONTEXT):
        loops.eq26_rescattering_loop(sample, event, channel, lambda q, x: np.eye(2), lambda z: 1., 1., parameters, strong_parameters, CONTEXT)


@pytest.mark.parametrize("source, prop, transition", [
    (lambda q, x: np.eye(3), lambda z: 1., 1.),
    (lambda q, x: np.full((2, 2), np.nan), lambda z: 1., 1.),
    (lambda q, x: np.eye(2), lambda z: np.nan, 1.),
    (lambda q, x: np.eye(2), lambda z: np.ones(2), 1.),
    (lambda q, x: np.eye(2), lambda z: 1., np.inf),
    (lambda q, x: np.eye(2), lambda z: 1., True),
])
def test_eq26_rejects_malformed_spin_scalar_and_nonfinite_callbacks(parameters, strong_parameters, sample, source, prop, transition):
    with pytest.raises(ValueError, match=CONTEXT):
        loops.eq26_rescattering_loop(sample, 7, 3, source, prop, transition, parameters, strong_parameters, CONTEXT)


def test_eq26_propagator_pole_retains_context(parameters, strong_parameters, sample):
    def pole(z):
        raise ZeroDivisionError("genuine intermediate pole")
    with pytest.raises(ValueError, match=CONTEXT+".*pole"):
        loops.eq26_rescattering_loop(sample, 7, 3, lambda q, x: np.eye(2), pole, 1., parameters, strong_parameters, CONTEXT)


def test_eq26_unsupported_callback_branch_retains_context(parameters, strong_parameters, sample):
    def unsupported(z):
        raise ValueError("unsupported branch")
    with pytest.raises(ValueError, match=CONTEXT+".*unsupported branch"):
        loops.eq26_rescattering_loop(sample, 7, 3, lambda q, x: np.eye(2), unsupported, 1., parameters, strong_parameters, CONTEXT)


def test_eq26_rejects_malformed_or_non_cm_sample(parameters, strong_parameters, sample):
    initial = sample.initial.copy()
    initial[7, 1] = .1
    for bad in (replace(sample, momenta=np.zeros((16, 2, 4))), replace(sample, initial=initial)):
        with pytest.raises(ValueError, match=CONTEXT):
            loops.eq26_rescattering_loop(bad, 7, 3, lambda q, x: np.eye(2), lambda z: 1., 1., parameters, strong_parameters, CONTEXT)
