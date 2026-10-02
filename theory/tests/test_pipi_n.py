"""P65 Eqs. (26), (29), and (30): three-body loop and vertices."""

from __future__ import annotations

import numpy as np
import pytest
from scipy.integrate import quad

from graal_theory.amplitudes import pipi_n
from graal_theory.amplitudes.pipi_n import pipi_n_loop, pipi_n_potentials


PION = 0.13957039
NUCLEON = (0.93827208816 + 0.93956542052) / 2


def test_p65_polynomial_anchors():
    assert pipi_n_potentials(1.213, PION)[0] == pytest.approx(4 / PION**3)
    assert pipi_n_potentials(1.213 + PION, PION)[0] == pytest.approx(5 / PION**3)
    assert pipi_n_potentials(1.470, PION)[1] == pytest.approx(0, abs=1e-12)
    for x, numerator in ((-1, 3.54), (1, -4.46), (2, -0.60)):
        assert pipi_n_potentials(1.470 + x * PION, PION)[1] == pytest.approx(
            numerator / PION**3, abs=1e-10,
        )


def test_loop_threshold_and_absorptive_sign():
    threshold = NUCLEON + 2 * PION
    assert pipi_n_loop(threshold - 1e-5, PION, NUCLEON) == 0j
    assert pipi_n_loop(threshold, PION, NUCLEON) == 0j
    for w in (threshold + 1e-4, 1.45, 1.65, 1.70):
        value = pipi_n_loop(w, PION, NUCLEON)
        assert np.isfinite(value)
        assert value.real == 0
        assert value.imag < 0


@pytest.mark.parametrize(
    "bad", [True, np.bool_(False), 0, -1, np.nan, np.inf, 1 + 0j, "1.45", [1.45],
            np.array(1.45)],
)
def test_invalid_w_or_mass_rejected(bad):
    with pytest.raises(ValueError):
        pipi_n_loop(bad, PION, NUCLEON)
    with pytest.raises(ValueError):
        pipi_n_loop(1.45, bad, NUCLEON)
    with pytest.raises(ValueError):
        pipi_n_loop(1.45, PION, bad)
    with pytest.raises(ValueError):
        pipi_n_potentials(bad, PION)
    with pytest.raises(ValueError):
        pipi_n_potentials(1.45, bad)


def test_loop_validates_masses_even_below_threshold():
    with pytest.raises(ValueError, match="m_pi"):
        pipi_n_loop(0.5, np.nan, NUCLEON)
    with pytest.raises(ValueError, match="M_N"):
        pipi_n_loop(0.5, PION, -1)


def test_numpy_real_scalars_accepted():
    assert pipi_n_loop(np.float64(1.45), np.float64(PION), np.float64(NUCLEON)) == (
        pipi_n_loop(1.45, PION, NUCLEON)
    )
    assert pipi_n_potentials(np.int64(1), np.float64(PION)) == (
        pipi_n_potentials(1.0, PION)
    )


def test_loop_domain_ends_at_1p70_gev():
    with pytest.raises(ValueError, match="W"):
        pipi_n_loop(1.701, PION, NUCLEON)


def triangle_reference(w, m, nucleon):
    """Direct energy triangle with Eq. (27)'s angular mask."""
    def integrand(e2, e1):
        q1_sq, q2_sq = e1 * e1 - m * m, e2 * e2 - m * m
        if q1_sq <= 0 or q2_sq <= 0:
            return 0.0
        e_nucleon = w - e1 - e2
        if e_nucleon < nucleon:
            return 0.0
        a = (e_nucleon**2 - nucleon**2 - q1_sq - q2_sq) / (
            2 * np.sqrt(q1_sq * q2_sq)
        )
        if abs(a) > 1:
            return 0.0
        return nucleon**2 + 2 * q1_sq + 2 * q2_sq - e_nucleon**2

    def inner(e1):
        return quad(lambda e2: integrand(e2, e1), m, w - nucleon - e1,
                    epsabs=1e-12, epsrel=1e-3, limit=300)[0]

    area = quad(inner, m, w - nucleon - m,
                epsabs=1e-12, epsrel=1e-3, limit=300)[0]
    return -nucleon * area / (4 * (2 * np.pi)**3)


@pytest.mark.parametrize("w", [1.25, 1.45, 1.65])
def test_loop_agrees_with_independent_triangle(w):
    assert pipi_n_loop(w, PION, NUCLEON).imag == pytest.approx(
        triangle_reference(w, PION, NUCLEON), rel=5e-3, abs=2e-12,
    )


@pytest.mark.parametrize("w", [1.25, 1.45, 1.65])
def test_48_96_quadrature_convergence(w):
    low = pipi_n._loop_at_order(w, PION, NUCLEON, 48)
    high = pipi_n._loop_at_order(w, PION, NUCLEON, 96)
    assert abs(high - low) <= max(1e-12, 1e-3 * abs(high))
    assert pipi_n_loop(w, PION, NUCLEON).imag == high


def test_gev_mev_fifth_power_normalization():
    gev = pipi_n_loop(1.45, PION, NUCLEON).imag
    mev = pipi_n._loop_at_order(1450, PION * 1000, NUCLEON * 1000, 96)
    assert mev == pytest.approx(gev * 1e15, rel=1e-12)


def test_nonconverged_loop_is_rejected(monkeypatch):
    monkeypatch.setattr(
        pipi_n, "_loop_at_order",
        lambda w, m, nucleon, order: -1e-7 if order == 48 else -2e-7,
    )
    with pytest.raises(ValueError, match="did not converge"):
        pipi_n_loop(1.45, PION, NUCLEON)
