"""Strong reduced N*(1535) input and kernel checks."""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from graal_theory.amplitudes import nstar1535_reduced
from graal_theory.amplitudes.nstar1535_reduced import (
    CHANNELS,
    C_COEFFICIENTS,
    load_reduced_parameters,
    loop_functions,
    reduced_tmatrix,
    wt_kernel,
)


REFERENCE_DIR = Path(__file__).resolve().parents[1] / "references"
PARAM = REFERENCE_DIR / "nstar1535_reduced_parameters.json"
SOURCES = REFERENCE_DIR / "sources.json"


def test_reduced_inputs_and_channel_order():
    p = load_reduced_parameters(PARAM, SOURCES)
    assert CHANNELS == (
        "pi0_p", "pi_plus_n", "eta_p",
        "k_plus_sigma0", "k_plus_lambda", "k0_sigma_plus",
    )
    assert p.mu_gev == 1.2
    assert p.subtraction_constants == (2.0, 2.0, 0.2, -2.8, 1.6, -2.8)
    np.testing.assert_allclose(
        p.decay_constants_gev,
        (0.093, 0.093, 0.093 * 1.3, 0.093 * 1.22, 0.093 * 1.22, 0.093 * 1.22),
    )


def test_wt_charge_coefficients_and_symmetry():
    p = load_reduced_parameters(PARAM, SOURCES)
    v = wt_kernel(1.5, p)
    np.testing.assert_allclose(v, v.T, atol=1e-13)
    assert C_COEFFICIENTS[0, 1] == pytest.approx(np.sqrt(2))
    assert C_COEFFICIENTS[0, 2] == C_COEFFICIENTS[1, 2] == 0
    e = (
        1.5**2 + p.baryon_masses_gev[0] ** 2 - p.meson_masses_gev[0] ** 2
    ) / (2 * 1.5)
    ej = (
        1.5**2 + p.baryon_masses_gev[1] ** 2 - p.meson_masses_gev[1] ** 2
    ) / (2 * 1.5)
    expected = (
        -np.sqrt(2)
        * (3.0 - p.baryon_masses_gev[0] - p.baryon_masses_gev[1])
        / (4 * 0.093**2)
        * np.sqrt((p.baryon_masses_gev[0] + e) / (2 * p.baryon_masses_gev[0]))
        * np.sqrt((p.baryon_masses_gev[1] + ej) / (2 * p.baryon_masses_gev[1]))
    )
    assert v[0, 1] == pytest.approx(expected)


def test_reduced_inputs_reject_bad_mass_unit_and_value(tmp_path):
    raw = json.loads(PARAM.read_text(encoding="utf-8"))
    raw["neutron_mass"]["unit"] = "MeV"
    changed = tmp_path / "wrong-unit.json"
    changed.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="neutron_mass"):
        load_reduced_parameters(changed, SOURCES)
    raw["neutron_mass"]["unit"] = "GeV"
    raw["neutron_mass"]["value"] = -1
    changed.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="neutron_mass"):
        load_reduced_parameters(changed, SOURCES)


def test_reduced_inputs_reject_nonfinite_unknown_source_and_missing_key(tmp_path):
    original = json.loads(PARAM.read_text(encoding="utf-8"))
    changed = tmp_path / "bad.json"
    for field, replacement in (("value", float("nan")), ("source_key", "not_a_source")):
        raw = copy.deepcopy(original)
        raw["a_piN"][field] = replacement
        changed.write_text(json.dumps(raw), encoding="utf-8")
        with pytest.raises(ValueError, match="a_piN"):
            load_reduced_parameters(changed, SOURCES)
    raw = copy.deepcopy(original)
    del raw["a_piN"]
    changed.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="names"):
        load_reduced_parameters(changed, SOURCES)


def test_loop_imaginary_part_eq7_and_closed_channels():
    p = load_reduced_parameters(PARAM, SOURCES)
    w = 1.50
    g = loop_functions(w, p)
    for i in range(6):
        m, baryon = p.meson_masses_gev[i], p.baryon_masses_gev[i]
        if w > m + baryon:
            q = np.sqrt((w*w-(m+baryon)**2)*(w*w-(m-baryon)**2))/(2*w)
            assert g[i].imag == pytest.approx(-baryon*q/(4*np.pi*w), abs=1e-11)
        else:
            assert abs(g[i].imag) < 1e-11


def test_loop_finite_across_thresholds():
    p = load_reduced_parameters(PARAM, SOURCES)
    thresholds = sorted(set(np.add(p.meson_masses_gev, p.baryon_masses_gev)))
    for threshold in thresholds[1:]:
        if threshold < 1.70:
            for w in (threshold-1e-6, threshold, threshold+1e-6):
                assert np.all(np.isfinite(loop_functions(w, p)))


def test_t_symmetry_coupled_transition_and_unitarity():
    p = load_reduced_parameters(PARAM, SOURCES)
    w = 1.55
    t = reduced_tmatrix(w, p)
    assert t.shape == (6, 6)
    np.testing.assert_allclose(t, t.T, rtol=1e-10, atol=1e-10)
    assert abs(t[0, 2]) > 1e-8
    rho = np.zeros(6)
    for i, (m, baryon) in enumerate(zip(p.meson_masses_gev, p.baryon_masses_gev)):
        if w > m + baryon:
            q = np.sqrt((w*w-(m+baryon)**2)*(w*w-(m-baryon)**2))/(2*w)
            rho[i] = baryon*q/(4*np.pi*w)
    np.testing.assert_allclose((t-t.conj().T)/(2j),
                               -t @ np.diag(rho) @ t.conj().T,
                               rtol=2e-9, atol=2e-9)


def test_t_satisfies_both_linear_equations():
    p = load_reduced_parameters(PARAM, SOURCES)
    w = 1.55
    v, g, t = wt_kernel(w, p), loop_functions(w, p), reduced_tmatrix(w, p)
    np.testing.assert_allclose((np.eye(6)-v*g[None, :]) @ t, v,
                               rtol=1e-11, atol=1e-11)
    np.testing.assert_allclose(t @ (np.eye(6)-g[:, None]*v), v,
                               rtol=1e-11, atol=1e-11)


@pytest.mark.parametrize("w", [0.5, 1.701, float("nan"), float("inf"), True])
def test_invalid_real_axis_energy_is_rejected(w):
    p = load_reduced_parameters(PARAM, SOURCES)
    with pytest.raises(ValueError, match="W"):
        reduced_tmatrix(w, p)


def test_singular_matrix_is_reported(monkeypatch):
    p = load_reduced_parameters(PARAM, SOURCES)

    def fail(*args, **kwargs):
        raise np.linalg.LinAlgError("singular")

    monkeypatch.setattr(nstar1535_reduced.np.linalg, "solve", fail)
    with pytest.raises(ValueError, match="singular"):
        reduced_tmatrix(1.55, p)


@pytest.mark.parametrize("field,replacement", [
    ("subtraction_constants", (2.0, 2.0, 0.2, -2.8+1j, 1.6, -2.8)),
    ("meson_masses_gev", (0.1349768+0j, 0.13957039, 0.547862,
                           0.493677, 0.493677, 0.497611)),
    ("mu_gev", True),
    ("meson_masses_gev", [0.1349768, 0.13957039, 0.547862,
                          0.493677, 0.493677, 0.497611]),
])
def test_direct_parameters_reject_nonreal_or_mutable_inputs(field, replacement):
    p = load_reduced_parameters(PARAM, SOURCES)
    with pytest.raises(ValueError, match=field):
        replace(p, **{field: replacement})


def test_nearly_singular_reduced_t_is_reported():
    p = load_reduced_parameters(PARAM, SOURCES)
    subtraction = (*p.subtraction_constants[:4], 416.75627803738945,
                   p.subtraction_constants[5])
    p = replace(p, subtraction_constants=subtraction)
    w = min(np.add(p.meson_masses_gev, p.baryon_masses_gev))
    with pytest.raises(ValueError, match="ill-conditioned"):
        reduced_tmatrix(w, p)


def test_each_channel_loop_branch_across_its_threshold():
    p = load_reduced_parameters(PARAM, SOURCES)
    lightest = min(np.add(p.meson_masses_gev, p.baryon_masses_gev))
    for i, (meson, baryon) in enumerate(zip(p.meson_masses_gev,
                                             p.baryon_masses_gev)):
        threshold = meson + baryon
        if threshold - 1e-6 >= lightest:
            assert abs(loop_functions(threshold - 1e-6, p)[i].imag) < 1e-11
        assert abs(loop_functions(threshold, p)[i].imag) < 1e-9
        w = threshold + 1e-6
        q = np.sqrt((w*w-threshold**2)*(w*w-(baryon-meson)**2))/(2*w)
        assert loop_functions(w, p)[i].imag == pytest.approx(
            -baryon*q/(4*np.pi*w), abs=1e-11)


def test_charge_plus_one_grid_is_frozen():
    from graal_theory.reduced_t_reference import isospin_half_s11_eta
    p = load_reduced_parameters(PARAM, SOURCES)
    energies = (1.50, 1.52, 1.54, 1.56, 1.58, 1.60, 1.62, 1.64)
    expected = np.array([
        [ 0.208470845706157, 0.240612778280716],
        [ 0.137447699010282, 0.422724541038566],
        [-0.0899104594703734, 0.432547480238677],
        [-0.190358055793633, 0.266178397794420],
        [-0.167720733393300, 0.141591721442651],
        [-0.127123075987937, 0.0768778655603441],
        [-0.0989879586984333, 0.0374499912385641],
        [-0.0816296402031595, 0.00666205708376796],
    ])
    actual = np.array([[z.real, z.imag] for w in energies
                       for z in (isospin_half_s11_eta(w, p),)])
    np.testing.assert_allclose(actual, expected, rtol=2e-11, atol=2e-11)


def test_public_charge_plus_one_calls_shared_core_exactly():
    from graal_theory.amplitudes import _reduced_t_core as core
    p = load_reduced_parameters(PARAM, SOURCES)
    w = 1.55
    for public, shared in (
        (wt_kernel(w, p), core.wt_kernel(w, p, C_COEFFICIENTS)),
        (loop_functions(w, p), core.loop_functions(w, p)),
        (reduced_tmatrix(w, p), core.reduced_tmatrix(w, p, C_COEFFICIENTS)),
    ):
        np.testing.assert_allclose(public, shared, rtol=0, atol=0)
