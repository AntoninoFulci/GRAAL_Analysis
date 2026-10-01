"""P65 Table I charge-zero reduced-basis checks."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from graal_theory.amplitudes import nstar1535_charge_zero
from graal_theory.amplitudes.nstar1535_charge_zero import (
    CHANNELS_ZERO,
    CHANNEL_INDEX_ZERO,
    C_COEFFICIENTS_ZERO,
    charge_zero_loop_functions,
    charge_zero_tmatrix,
    charge_zero_wt_kernel,
    load_charge_zero_parameters,
)


ROOT = Path(__file__).resolve().parents[1]
REFERENCES = ROOT / "references"
PARAM = REFERENCES / "nstar1535_reduced_parameters.json"
SOURCES = REFERENCES / "sources.json"
EXTRA = REFERENCES / "nstar1535_charge_zero_extra.json"


def test_p65_table_i_order_coefficients_and_inputs():
    expected_c = np.array([
        [1, -np.sqrt(2), 0, 0, -1/np.sqrt(2), -np.sqrt(3/2)],
        [-np.sqrt(2), 0, 0, -1/np.sqrt(2), -1/2, np.sqrt(3)/2],
        [0, 0, 0, -np.sqrt(3/2), np.sqrt(3)/2, -3/2],
        [0, -1/np.sqrt(2), -np.sqrt(3/2), 1, -np.sqrt(2), 0],
        [-1/np.sqrt(2), -1/2, np.sqrt(3)/2, -np.sqrt(2), 0, 0],
        [-np.sqrt(3/2), np.sqrt(3)/2, -3/2, 0, 0, 0],
    ], dtype=float)
    expected_meson = (0.493677, 0.497611, 0.497611,
                      0.13957039, 0.1349768, 0.547862)
    expected_baryon = (1.197449, 1.192642, 1.115683,
                       0.93827208816, 0.93956542052, 0.93956542052)
    expected_f = (0.093*1.22, 0.093*1.22, 0.093*1.22,
                  0.093, 0.093, 0.093*1.3)
    expected_subtraction = (-2.8, -2.8, 1.6, 2.0, 2.0, 0.2)

    assert CHANNELS_ZERO == (
        "k_plus_sigma_minus", "k0_sigma0", "k0_lambda",
        "pi_minus_p", "pi0_n", "eta_n",
    )
    assert CHANNEL_INDEX_ZERO == {name: i for i, name in enumerate(CHANNELS_ZERO)}
    np.testing.assert_allclose(C_COEFFICIENTS_ZERO, expected_c, rtol=0, atol=1e-15)
    np.testing.assert_allclose(C_COEFFICIENTS_ZERO, C_COEFFICIENTS_ZERO.T, atol=0)
    assert not C_COEFFICIENTS_ZERO.flags.writeable

    p = load_charge_zero_parameters(PARAM, SOURCES, EXTRA)
    np.testing.assert_allclose(p.meson_masses_gev, expected_meson)
    np.testing.assert_allclose(p.baryon_masses_gev, expected_baryon)
    np.testing.assert_allclose(p.decay_constants_gev, expected_f)
    assert p.subtraction_constants == expected_subtraction
    assert p.mu_gev == 1.2


@pytest.mark.parametrize("field,value", [
    ("unit", "MeV"), ("source_key", "inoue_2002"),
    ("value", -1), ("value", float("nan")),
    ("value", True), ("value", "1.197449+0j"),
    ("locator", ""),
])
def test_sigma_minus_source_record_rejects_bad_fields(tmp_path, field, value):
    raw = json.loads(EXTRA.read_text(encoding="utf-8"))
    raw["sigma_minus_mass"][field] = value
    changed = tmp_path / "bad.json"
    changed.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="sigma_minus_mass"):
        load_charge_zero_parameters(PARAM, SOURCES, changed)


@pytest.mark.parametrize("shape", [
    "missing_outer", "extra_outer", "missing_inner", "extra_inner",
])
def test_sigma_minus_source_record_requires_exact_keys(tmp_path, shape):
    raw = json.loads(EXTRA.read_text(encoding="utf-8"))
    if shape == "missing_outer":
        del raw["sigma_minus_mass"]
    elif shape == "extra_outer":
        raw["proton_mass"] = raw["sigma_minus_mass"]
    elif shape == "missing_inner":
        del raw["sigma_minus_mass"]["locator"]
    else:
        raw["sigma_minus_mass"]["comment"] = "extra"
    changed = tmp_path / "bad.json"
    changed.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="sigma_minus_mass"):
        load_charge_zero_parameters(PARAM, SOURCES, changed)


@pytest.mark.parametrize("replacement", [
    lambda values: list(values),
    lambda values: (complex(values[0]),) + values[1:],
])
def test_charge_zero_record_rejects_mutable_or_complex_baryon_masses(replacement):
    p = load_charge_zero_parameters(PARAM, SOURCES, EXTRA)
    with pytest.raises(ValueError, match="baryon_masses_gev"):
        replace(p, baryon_masses_gev=replacement(p.baryon_masses_gev))


def test_charge_zero_threshold_branches_and_eq7():
    p = load_charge_zero_parameters(PARAM, SOURCES, EXTRA)
    lightest = min(np.add(p.meson_masses_gev, p.baryon_masses_gev))
    for i, (m, baryon) in enumerate(zip(p.meson_masses_gev,
                                         p.baryon_masses_gev)):
        threshold = m + baryon
        for w in (threshold-1e-6, threshold, threshold+1e-6):
            if not lightest <= w <= 1.70:
                continue
            g = charge_zero_loop_functions(w, p)
            assert np.all(np.isfinite(g))
            if w <= threshold:
                assert abs(g[i].imag) < 1e-9
            else:
                q = np.sqrt((w*w-threshold**2) *
                            (w*w-(baryon-m)**2))/(2*w)
                assert g[i].imag == pytest.approx(
                    -baryon*q/(4*np.pi*w), abs=1e-10)


def test_charge_zero_solve_and_two_body_unitarity():
    p = load_charge_zero_parameters(PARAM, SOURCES, EXTRA)
    w = 1.55
    v = charge_zero_wt_kernel(w, p)
    g = charge_zero_loop_functions(w, p)
    t = charge_zero_tmatrix(w, p)
    np.testing.assert_allclose(v, v.T, atol=1e-13)
    np.testing.assert_allclose(t, t.T, rtol=1e-10, atol=1e-10)
    np.testing.assert_allclose((np.eye(6)-v*g[None, :]) @ t, v,
                               rtol=1e-11, atol=1e-11)
    rho = np.zeros(6)
    for i, (m, baryon) in enumerate(zip(p.meson_masses_gev,
                                         p.baryon_masses_gev)):
        if w > m+baryon:
            q = np.sqrt((w*w-(m+baryon)**2)*
                        (w*w-(baryon-m)**2))/(2*w)
            rho[i] = baryon*q/(4*np.pi*w)
    np.testing.assert_allclose((t-t.conj().T)/(2j),
                               -t @ np.diag(rho) @ t.conj().T,
                               rtol=2e-9, atol=2e-9)


@pytest.mark.parametrize("w", [1+0j, True, float("nan"), 1.0, 1.701])
def test_charge_zero_invalid_energy_is_rejected(w):
    p = load_charge_zero_parameters(PARAM, SOURCES, EXTRA)
    with pytest.raises(ValueError, match="W"):
        charge_zero_tmatrix(w, p)


def test_charge_zero_below_lightest_threshold_is_rejected():
    p = load_charge_zero_parameters(PARAM, SOURCES, EXTRA)
    lightest = min(np.add(p.meson_masses_gev, p.baryon_masses_gev))
    with pytest.raises(ValueError, match="W"):
        charge_zero_tmatrix(lightest-1e-6, p)


def test_charge_zero_singular_solve_is_reported(monkeypatch):
    p = load_charge_zero_parameters(PARAM, SOURCES, EXTRA)

    def fail(*args, **kwargs):
        raise np.linalg.LinAlgError("singular")

    monkeypatch.setattr(nstar1535_charge_zero.np.linalg, "solve", fail)
    with pytest.raises(ValueError, match="singular"):
        charge_zero_tmatrix(1.55, p)


def test_charge_zero_ill_conditioned_solve_is_reported(monkeypatch):
    p = load_charge_zero_parameters(PARAM, SOURCES, EXTRA)
    monkeypatch.setattr(nstar1535_charge_zero.np.linalg, "cond", lambda _: 1e12 + 1)
    with pytest.raises(ValueError, match="ill-conditioned"):
        charge_zero_tmatrix(1.55, p)
