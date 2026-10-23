"""Exact phase-space map trial; no production sampler change until measured."""

import importlib.util
from pathlib import Path

import numpy as np
import pytest
from scipy.integrate import quad
from scipy.stats import qmc

from graal_theory.kinematics import invariant_mass, kallen, validate_final_state
from graal_theory import figure4_integration
from graal_theory.figure4_integration import Figure4BinMoment
from graal_theory.phase_space import SobolConfig


def _probe():
    path = Path(__file__).resolve().parents[1]/"scripts"/"figure4_endpoint_map_probe.py"
    spec = importlib.util.spec_from_file_location("figure4_endpoint_map_probe", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_endpoint_map_has_exact_jacobian_and_keeps_fourth_coordinate():
    module = _probe()
    points = np.array([[.13, .27, .42, .61], [.81, .73, .58, .39]])
    mapped, jacobian = module.endpoint_map(points)
    np.testing.assert_array_equal(mapped[:, 3], points[:, 3])
    assert np.all((mapped >= 0) & (mapped <= 1))
    for axis in range(3):
        h = 1e-6
        plus, _ = module.endpoint_map(points + np.eye(4)[axis]*h)
        minus, _ = module.endpoint_map(points - np.eye(4)[axis]*h)
        numerical = (plus[:, axis]-minus[:, axis])/(2*h)
        np.testing.assert_allclose(numerical,
            np.pi/2*np.sin(np.pi*points[:, axis]), rtol=1e-9)
    np.testing.assert_allclose(jacobian,
        np.prod(np.pi/2*np.sin(np.pi*points[:, :3]), axis=1), rtol=1e-14)


def test_endpoint_map_preserves_volume_support_nested_points_and_seeds():
    module = _probe()
    masses = (.547862, .1349768, .9382721)
    pair = (0, 2)
    interval = (1.55, 1.70)
    low = module.mapped_sample(2., masses, pair, interval, SobolConfig(8))
    high = module.mapped_sample(2., masses, pair, interval, SobolConfig(9))
    np.testing.assert_array_equal(low.momenta, high.momenta[:len(low.momenta)])
    np.testing.assert_array_equal(low.weights_gev2,
                                  high.weights_gev2[:len(low.weights_gev2)])
    mass = invariant_mass(high.momenta[:, pair[0]]+high.momenta[:, pair[1]])
    assert np.all(mass >= interval[0]-1e-12) and np.all(mass <= interval[1]+1e-12)
    validate_final_state(high.initial, high.momenta, masses, atol=1e-12)
    full = module.mapped_sample(2., masses, pair, interval, SobolConfig(14))
    spectator = masses[1]
    def density(s):
        return (np.sqrt(kallen(4., s, spectator**2, atol=1e-12))
                *np.sqrt(kallen(s, masses[0]**2, masses[2]**2, atol=1e-12))
                /(128*np.pi**3*4*s))
    expected = quad(density, interval[0]**2, interval[1]**2,
                    epsabs=1e-12)[0]
    assert full.weights_gev2.mean() == pytest.approx(expected, rel=.005)
    seed_a = module.mapped_sample(2., masses, pair, interval,
                                  SobolConfig(8, scramble=True, seed=2026))
    seed_b = module.mapped_sample(2., masses, pair, interval,
                                  SobolConfig(8, scramble=True, seed=2027))
    assert not np.array_equal(seed_a.momenta, seed_b.momenta)


def test_endpoint_map_integrates_narrow_feature_in_each_coordinate():
    module = _probe()
    points = qmc.Sobol(d=4, scramble=False).random_base2(14)
    mapped, jacobian = module.endpoint_map(points)
    assert jacobian.mean() == pytest.approx(1., rel=.005)
    for axis in range(4):
        center = .12 if axis % 2 == 0 else .83
        feature = lambda x: np.exp(-((x-center)/.035)**2)
        reference = quad(feature, 0., 1., epsabs=1e-12)[0]
        assert np.mean(feature(mapped[:, axis])*jacobian) == pytest.approx(
            reference, rel=.005)


def test_probe_restores_standard_sampler_after_diagnostic(monkeypatch):
    module = _probe()
    original = figure4_integration.sample_three_body_mass_window
    monkeypatch.setattr(module, "_figure4_model", lambda *args: object())
    def fake(model, pair, energy, mass, order, config):
        assert figure4_integration.sample_three_body_mass_window is module.mapped_sample
        return Figure4BinMoment(pair, energy, mass, energy, mass,
            np.array([energy[0]+.05]), .2, 1., .5, .5,
            sum(mass)/2, 0., "calculated")
    monkeypatch.setattr(module, "_safe_predict", fake)
    report = module.probe("lower")
    assert [row["power"] for row in report["powers"]] == [5, 6, 7, 8]
    assert figure4_integration.sample_three_body_mass_window is original
