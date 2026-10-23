"""Independent phase-space and Jacobian checks for a diagnostic-only proposal."""
import importlib.util
from functools import partial
from pathlib import Path

import numpy as np
import pytest
from scipy.integrate import quad
from scipy.stats import qmc

from graal_theory.kinematics import invariant_mass, kallen, validate_final_state
from graal_theory.phase_space import SobolConfig


def load(name):
    path = Path(__file__).resolve().parents[1]/"scripts"/(name+".py")
    assert path.exists(), "joint mass-angle proposal missing"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_truncated_cauchy_derivative_support_and_degenerate_interval():
    m = load("figure4_joint_map_probe")
    u = np.array([.13, .37, .81])
    value, jac = m.cauchy_quantile(u, 1.1, 1.8, 1.232**2, 1.232*.117)
    plus, _ = m.cauchy_quantile(u+1e-6, 1.1, 1.8, 1.232**2, 1.232*.117)
    minus, _ = m.cauchy_quantile(u-1e-6, 1.1, 1.8, 1.232**2, 1.232*.117)
    np.testing.assert_allclose((plus-minus)/(2e-6), .7*jac, rtol=1e-8)
    assert np.all((value > 1.1) & (value < 1.8))
    value, jac = m.cauchy_quantile(np.array([0., .5, 1.]), 1.4, 1.4, 1.232**2, .1)
    np.testing.assert_array_equal(value, [1.4, 1.4, 1.4])
    np.testing.assert_array_equal(jac, [1., 1., 1.])
    with pytest.raises(ValueError):
        m.cauchy_quantile(u, 1., 2., 1.5, 0.)


@pytest.mark.parametrize("pair", [(0, 1), (1, 0), (2, 0), (0, 2), (2, 1), (1, 2)])
def test_joint_map_volume_and_resonant_invariant_against_independent_quadrature(pair):
    m = load("figure4_joint_map_probe")
    masses = (.547862, .1349768, .93827208816)
    w = 1.9
    spectator = next(i for i in range(3) if i not in pair)
    m1, m2, m3 = (masses[i] for i in (*pair, spectator))
    low, high = (m1+m2)**2, (w-m3)**2
    sample = m.sample_delta_helicity(w, masses, pair, (0., 3.), SobolConfig(15),
        reduce_global_azimuth=True, resonance_mass=1.232, resonance_width=.117)
    validate_final_state(sample.initial, sample.momenta, masses, atol=1e-12)
    actual_s = invariant_mass(sample.momenta[:, 1]+sample.momenta[:, 2])**2

    def density(s):
        return np.sqrt(kallen(w*w, s, m3*m3))*np.sqrt(kallen(s, m1*m1, m2*m2))/(128*np.pi**3*w*w*s)

    def conditional_moment(s, degree):
        if set(pair) == {1, 2}:
            return s**degree
        r = masses[next(i for i in pair if i in (1, 2))]
        other = masses[next(i for i in pair if i not in (1, 2))]
        er = (s+r*r-other*other)/(2*np.sqrt(s))
        e3 = (w*w-s-m3*m3)/(2*np.sqrt(s))
        center = r*r+m3*m3+2*er*e3
        span = np.sqrt(kallen(s, r*r, other*other)*kallen(w*w, s, m3*m3))/(2*s)
        return center if degree == 1 else center**2+span**2/3

    expected = quad(density, low, high, epsabs=1e-12)[0]
    assert sample.weights_gev2.mean() == pytest.approx(expected, rel=.002)
    for degree in (1, 2):
        reference = quad(lambda s: density(s)*conditional_moment(s, degree), low, high, epsabs=1e-12)[0]
        assert np.mean(sample.weights_gev2*actual_s**degree) == pytest.approx(reference, rel=.002)
    for daughter in range(3):
        spatial = sample.momenta[:, daughter, 1:]
        length = np.linalg.norm(spatial, axis=1)
        cos_theta = np.divide(spatial[:, 2], length, out=np.zeros_like(length), where=length > 0)
        assert np.mean(sample.weights_gev2*cos_theta)/expected == pytest.approx(0., abs=.002)
        assert np.mean(sample.weights_gev2*cos_theta**2)/expected == pytest.approx(1/3, abs=.002)


def test_joint_map_preserves_conditioned_window_nesting_and_independent_seeds():
    m = load("figure4_joint_map_probe")
    sampler = partial(m.sample_delta_helicity, resonance_mass=1.232, resonance_width=.117,
                      reduce_global_azimuth=True)
    masses = (.547862, .1349768, .93827208816)
    a = sampler(1.9, masses, (0, 1), (.72, .76), SobolConfig(5))
    b = sampler(1.9, masses, (0, 1), (.72, .76), SobolConfig(6))
    np.testing.assert_array_equal(a.momenta, b.momenta[:32])
    np.testing.assert_array_equal(a.weights_gev2, b.weights_gev2[:32])
    mass = invariant_mass(b.momenta[:, 0]+b.momenta[:, 1])
    assert np.all((mass >= .72-1e-12) & (mass <= .76+1e-12))
    a = sampler(1.9, masses, (0, 1), (.72, .76), SobolConfig(6, True, 2026))
    b = sampler(1.9, masses, (0, 1), (.72, .76), SobolConfig(6, True, 2027))
    assert not np.array_equal(a.momenta, b.momenta)
    assert sampler(1.9, masses, (0, 1), (2., 3.), SobolConfig(4)) is None


def test_delta_helicity_quantile_matches_actual_secondary_mass():
    m = load("figure4_joint_map_probe")
    masses = (.547862, .1349768, .93827208816)
    sample = m.sample_delta_helicity(1.9, masses, (0, 1), (.72, .76), SobolConfig(8),
        reduce_global_azimuth=True, resonance_mass=1.232, resonance_width=.117)
    raw = qmc.Sobol(4, scramble=False).random_base2(8)
    s12 = invariant_mass(sample.momenta[:, 0]+sample.momenta[:, 1])**2
    e2 = (s12+masses[1]**2-masses[0]**2)/(2*np.sqrt(s12))
    e3 = (1.9**2-s12-masses[2]**2)/(2*np.sqrt(s12))
    center = masses[1]**2+masses[2]**2+2*e2*e3
    halfwidth = np.sqrt(kallen(s12,masses[0]**2,masses[1]**2)*kallen(1.9**2,s12,masses[2]**2))/(2*s12)
    actual = invariant_mass(sample.momenta[:, 1]+sample.momenta[:, 2])**2
    lo = np.arctan((center-halfwidth-1.232**2)/(1.232*.117))
    hi = np.arctan((center+halfwidth-1.232**2)/(1.232*.117))
    cdf = (np.arctan((actual-1.232**2)/(1.232*.117))-lo)/(hi-lo)
    np.testing.assert_allclose(cdf, raw[:, 2], atol=3e-13)


def test_near_pair_threshold_retains_finite_helicity_endpoint():
    m = load("figure4_joint_map_probe")
    masses = (.547862, .1349768, .93827208816)
    threshold = masses[2]+masses[0]
    sample = m.sample_delta_helicity(1.9, masses, (2, 0),
        (threshold+1e-12, threshold+.01), SobolConfig(4),
        reduce_global_azimuth=True, resonance_mass=1.232, resonance_width=.117)
    assert np.isfinite(sample.momenta).all()
    assert np.isfinite(sample.weights_gev2).all()
    validate_final_state(sample.initial, sample.momenta, masses, atol=1e-12)
