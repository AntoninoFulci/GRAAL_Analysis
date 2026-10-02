"""P65 vector-propagator angular average, with independent quadrature."""

from pathlib import Path

import numpy as np
import pytest

from graal_theory.amplitudes.nstar1535_reduced import load_reduced_parameters
from graal_theory.amplitudes.vmd import angular_factor


@pytest.fixture(scope="module")
def parameters():
    root = Path(__file__).resolve().parents[1] / "references"
    return load_reduced_parameters(
        root / "nstar1535_reduced_parameters.json", root / "sources.json",
    )


def test_p65_elastic_eq13_value():
    w, pion, proton, rho = 1.5, 0.13957039, 0.93827208816, 0.770
    q2 = ((w*w-(proton+pion)**2)*(w*w-(proton-pion)**2))/(4*w*w)
    expected = rho*rho/(4*q2)*np.log1p(4*q2/(rho*rho))
    assert expected == pytest.approx(0.638321728, abs=2e-8)
    assert angular_factor(w, pion, proton, pion, proton, rho) == pytest.approx(
        expected, rel=1e-12,
    )


@pytest.mark.parametrize("w,i,j,mv", [
    (1.50, 1, 1, .770),
    (1.50, 0, 4, .892),
    (1.65, 0, 4, .892),
])
def test_factor_matches_independent_angular_integral(w, i, j, mv, parameters):
    mi, mj = parameters.meson_masses_gev[i], parameters.meson_masses_gev[j]
    Mi, Mj = parameters.baryon_masses_gev[i], parameters.baryon_masses_gev[j]
    ei = (w*w + mi*mi - Mi*Mi)/(2*w)
    ej = (w*w + mj*mj - Mj*Mj)/(2*w)
    qi = np.sqrt(complex(ei*ei-mi*mi))
    qj = np.sqrt(complex(ej*ej-mj*mj))
    a = mv*mv-mi*mi-mj*mj+2*ei*ej
    nodes, weights = np.polynomial.legendre.leggauss(256)
    expected = mv*mv/2 * np.sum(weights/(a-2*qi*qj*nodes))
    assert abs(expected.imag) < 1e-12
    factor = angular_factor(w, mi, Mi, mj, Mj, mv)
    assert isinstance(factor, float)
    assert factor == pytest.approx(expected.real, rel=1e-10)


@pytest.mark.parametrize("i", [0, 1, 4])
def test_elastic_threshold_limit_is_one(i, parameters):
    m, baryon = parameters.meson_masses_gev[i], parameters.baryon_masses_gev[i]
    assert angular_factor(m+baryon, m, baryon, m, baryon, .770) == pytest.approx(
        1.0, abs=2e-15,
    )


@pytest.mark.parametrize("i,j", [(0, 0), (1, 1), (4, 4), (0, 4)])
def test_factor_continuous_at_nextafter_thresholds(i, j, parameters):
    mi, mj = parameters.meson_masses_gev[i], parameters.meson_masses_gev[j]
    Mi, Mj = parameters.baryon_masses_gev[i], parameters.baryon_masses_gev[j]
    for threshold in {mi+Mi, mj+Mj}:
        values = [angular_factor(w, mi, Mi, mj, Mj, .892) for w in (
            np.nextafter(threshold, -np.inf), threshold,
            np.nextafter(threshold, np.inf),
        )]
        assert np.all(np.isfinite(values))
        np.testing.assert_allclose(values, values[1], rtol=5e-15, atol=5e-15)
        # At q_i q_j = 0, the integrand is constant m_v^2/A.
        ei = (threshold**2 + mi**2 - Mi**2)/(2*threshold)
        ej = (threshold**2 + mj**2 - Mj**2)/(2*threshold)
        expected = .892**2/(.892**2-mi**2-mj**2+2*ei*ej)
        assert values[1] == pytest.approx(expected, rel=5e-15)


@pytest.mark.parametrize("position", range(6))
@pytest.mark.parametrize("invalid", [
    True, np.bool_(False), 1+0j, np.nan, np.inf, -np.inf, 0, -.1,
    "1.5", np.array([1.5]),
])
def test_factor_rejects_invalid_scalar_inputs(position, invalid):
    values = [1.5, .13957039, .93827208816, .13957039, .93827208816, .770]
    values[position] = invalid
    with pytest.raises(ValueError, match="finite positive real scalars"):
        angular_factor(*values)


def test_factor_accepts_numpy_real_scalars():
    result = angular_factor(
        np.float64(1.5), np.float64(.13957039), np.float64(.93827208816),
        np.float64(.13957039), np.float64(.93827208816), np.float64(.770),
    )
    assert result == pytest.approx(.638321728, abs=2e-8)


def test_factor_rejects_propagator_pole():
    with pytest.raises(ValueError, match="propagator"):
        angular_factor(1.0, .1, .4, .6, .3, .01)


@pytest.mark.parametrize("w", [np.finfo(float).max, np.nextafter(0., 1.)])
def test_factor_rejects_nonfinite_intermediate_kinematics(w):
    with pytest.raises(ValueError, match="propagator"):
        angular_factor(w, .13957039, .93827208816, .13957039, .93827208816, .770)
