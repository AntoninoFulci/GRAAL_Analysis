"""Source-linked inputs for the intermediate N*(1535) pi-pi-N variant."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import numpy as np
import pytest

from graal_theory.amplitudes import _reduced_t_core, nstar1535_pipi_n
from graal_theory.amplitudes.nstar1535_final_fit import (
    _validated_final_values,
    load_final_fit_parameters,
)
from graal_theory.amplitudes.nstar1535_pipi_n import (
    pipi_n_kernel_correction,
    pipi_n_tmatrix,
)
from graal_theory.amplitudes.nstar1535_reduced import (
    load_reduced_parameters,
    loop_functions,
    reduced_tmatrix,
    wt_kernel,
)
from graal_theory.amplitudes.pipi_n import pipi_n_loop, pipi_n_potentials
from graal_theory.cli import _REFERENCES
from graal_theory.sources import load_source_registry


REFERENCE_DIR = Path(__file__).resolve().parents[1] / "references"
REDUCED_JSON = REFERENCE_DIR / "nstar1535_reduced_parameters.json"
FINAL_JSON = REFERENCE_DIR / "nstar1535_final_subtractions.json"
SOURCES = REFERENCE_DIR / "sources.json"


def test_final_fit_is_distinct_and_sourced():
    base = load_reduced_parameters(REDUCED_JSON, SOURCES)
    final = load_final_fit_parameters(base, FINAL_JSON, SOURCES)
    assert final is not base
    assert base.subtraction_constants == (2, 2, .2, -2.8, 1.6, -2.8)
    assert final.subtraction_constants == (2, 2, .1, -2.8, 1.5, -2.8)
    assert final.mu_gev == base.mu_gev == 1.2
    assert final.meson_masses_gev == base.meson_masses_gev
    assert final.baryon_masses_gev == base.baryon_masses_gev
    assert final.decay_constants_gev == base.decay_constants_gev
    with pytest.raises(FrozenInstanceError):
        final.mu_gev = 1.1
    raw = json.loads(FINAL_JSON.read_text(encoding="utf-8"))
    for entry in raw.values():
        assert entry["source_key"] == "inoue_2002"
        assert entry["locator"] == "Eq. (28)"
    assert _REFERENCES.joinpath(
        "nstar1535_final_subtractions.json").is_file()


@pytest.mark.parametrize("field,value", [
    ("unit", "MeV"), ("value", True), ("value", None), ("value", "0.1"),
    ("value", float("nan")), ("value", float("inf")),
    ("value", float("-inf")), ("source_key", "missing"),
    ("source_key", "pdg_2024"), ("source_key", []),
    ("locator", ""), ("locator", "  "), ("locator", None),
    ("locator", "https://example.com"),
])
def test_final_fit_rejects_bad_entry(tmp_path, field, value):
    raw = json.loads(FINAL_JSON.read_text(encoding="utf-8"))
    raw["a_etaN"][field] = value
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="a_etaN"):
        load_final_fit_parameters(
            load_reduced_parameters(REDUCED_JSON, SOURCES), bad, SOURCES)


@pytest.mark.parametrize("entry", [None, [], 0, {}, {
    "value": .1, "unit": "1", "source_key": "inoue_2002",
    "locator": "Eq. (28)", "extra": "unexpected",
}])
def test_final_fit_rejects_malformed_entry(tmp_path, entry):
    raw = json.loads(FINAL_JSON.read_text(encoding="utf-8"))
    raw["a_etaN"] = entry
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="a_etaN"):
        load_final_fit_parameters(
            load_reduced_parameters(REDUCED_JSON, SOURCES), bad, SOURCES)


def test_final_fit_rejects_complex_value():
    raw = json.loads(FINAL_JSON.read_text(encoding="utf-8"))
    raw["a_etaN"]["value"] = .1 + 0j
    with pytest.raises(ValueError, match="a_etaN"):
        _validated_final_values(raw, load_source_registry(SOURCES))


@pytest.mark.parametrize("schema", ["missing", "extra", "list"])
def test_final_fit_rejects_wrong_names(tmp_path, schema):
    base = load_reduced_parameters(REDUCED_JSON, SOURCES)
    raw = json.loads(FINAL_JSON.read_text(encoding="utf-8"))
    if schema == "missing":
        del raw["a_KSigma"]
    elif schema == "extra":
        raw["a_other"] = raw["a_piN"]
    else:
        raw = list(raw)
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="names"):
        load_final_fit_parameters(base, bad, SOURCES)


@pytest.mark.parametrize("value", [0, -1.2, 1.1])
def test_final_fit_rejects_nonpositive_or_incompatible_mu(tmp_path, value):
    raw = json.loads(FINAL_JSON.read_text(encoding="utf-8"))
    raw["mu"]["value"] = value
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="mu"):
        load_final_fit_parameters(
            load_reduced_parameters(REDUCED_JSON, SOURCES), bad, SOURCES)


def test_final_fit_rejects_missing_source_registry_record(tmp_path):
    raw = json.loads(SOURCES.read_text(encoding="utf-8"))
    del raw["inoue_2002"]
    bad_sources = tmp_path / "sources.json"
    bad_sources.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="mu"):
        load_final_fit_parameters(
            load_reduced_parameters(REDUCED_JSON, SOURCES), FINAL_JSON, bad_sources)


@pytest.fixture
def final_parameters():
    base = load_reduced_parameters(REDUCED_JSON, SOURCES)
    return load_final_fit_parameters(base, FINAL_JSON, SOURCES)


@pytest.mark.parametrize("w", [1.25, 1.55, 1.70])
def test_p73_eq6_block_and_absorption(w):
    m, nucleon = .13957039, (.93827208816 + .93956542052)/2
    v11, v31 = pipi_n_potentials(w, m)
    a = -np.sqrt(2)*v31/3 - v11/(3*np.sqrt(2))
    b = (v31-v11)/3
    d = -v31/(3*np.sqrt(2)) - np.sqrt(2)*v11/3
    expected = pipi_n_loop(w, m, nucleon)*np.array([
        [a*a+b*b, a*b+b*d], [a*b+b*d, b*b+d*d],
    ])
    delta = pipi_n_kernel_correction(w, m, nucleon)
    assert delta.shape == (6, 6)
    assert delta.dtype == np.complex128
    np.testing.assert_allclose(delta[:2, :2], expected, rtol=1e-12)
    np.testing.assert_array_equal(delta[2:, :], 0)
    np.testing.assert_array_equal(delta[:, 2:], 0)
    np.testing.assert_array_equal(delta, delta.T)
    assert np.max(np.linalg.eigvalsh(delta.imag)) <= 1e-12


def test_p73_uses_products_not_absolute_squares(monkeypatch):
    # Complex vertices make conjugation errors observable in the real kernel.
    monkeypatch.setattr(nstar1535_pipi_n, "pipi_n_potentials",
                        lambda w, m: (1+2j, 3-1j))
    monkeypatch.setattr(nstar1535_pipi_n, "pipi_n_loop",
                        lambda w, m, nucleon: -1j)
    v11, v31 = 1+2j, 3-1j
    a = -np.sqrt(2)*v31/3 - v11/(3*np.sqrt(2))
    b = (v31-v11)/3
    d = -v31/(3*np.sqrt(2)) - np.sqrt(2)*v11/3
    delta = pipi_n_kernel_correction(1.55, .13957039, .939)
    assert delta[0, 0] == pytest.approx(-1j*(a*a+b*b))
    assert delta[0, 1] == pytest.approx(-1j*(a*b+b*d))
    assert delta[1, 1] == pytest.approx(-1j*(b*b+d*d))


@pytest.mark.parametrize("w", [1.25, 1.55, 1.70])
def test_intermediate_t_equation_and_reduced_difference(w, final_parameters):
    p = final_parameters
    delta = pipi_n_kernel_correction(
        w, p.meson_masses_gev[1],
        (p.baryon_masses_gev[0]+p.baryon_masses_gev[1])/2,
    )
    v = wt_kernel(w, p) + delta
    g, t = loop_functions(w, p), pipi_n_tmatrix(w, p)
    assert t.shape == (6, 6)
    assert t.dtype == np.complex128
    np.testing.assert_allclose(
        (np.eye(6)-v*g[None, :]) @ t, v, rtol=1e-10, atol=1e-10)
    np.testing.assert_allclose(t, t.T, rtol=1e-10, atol=1e-10)
    assert np.max(abs(t-reduced_tmatrix(w, p))) > 1e-6
    assert np.all(np.isfinite(t))


@pytest.mark.parametrize("at_threshold", [False, True])
def test_intermediate_t_reduces_when_three_body_channel_closed(
    at_threshold, final_parameters,
):
    p = final_parameters
    m = p.meson_masses_gev[1]
    nucleon = (p.baryon_masses_gev[0]+p.baryon_masses_gev[1])/2
    w = nucleon+2*m if at_threshold else 1.1
    np.testing.assert_array_equal(pipi_n_kernel_correction(w, m, nucleon), 0)
    np.testing.assert_array_equal(pipi_n_tmatrix(w, p), reduced_tmatrix(w, p))


@pytest.mark.parametrize("w", [True, 1+0j, "1.55", float("nan"),
                                    float("inf"), 1.0, np.nextafter(1.80, np.inf)])
def test_intermediate_t_rejects_invalid_energy(w, final_parameters):
    with pytest.raises(ValueError, match="W"):
        pipi_n_tmatrix(w, final_parameters)


def test_shared_solve_complex_kernel_equation():
    v = np.array([[2-1j, .3+.1j], [.3+.1j, 1-.2j]])
    g = np.array([.1-.2j, -.2-.1j])
    t = _reduced_t_core.solve_tmatrix(v, g)
    np.testing.assert_allclose((np.eye(2)-v*g[None, :]) @ t, v,
                               rtol=1e-12, atol=1e-12)
    np.testing.assert_allclose(t, t.T, rtol=1e-12, atol=1e-12)


def test_intermediate_t_preserves_condition_guard(monkeypatch, final_parameters):
    monkeypatch.setattr(np.linalg, "cond", lambda system: 1e13)
    with pytest.raises(ValueError, match="ill-conditioned"):
        pipi_n_tmatrix(1.55, final_parameters)


def test_intermediate_t_preserves_singular_guard(monkeypatch, final_parameters):
    def singular(system, kernel):
        raise np.linalg.LinAlgError("singular")

    monkeypatch.setattr(np.linalg, "solve", singular)
    with pytest.raises(ValueError, match="singular"):
        pipi_n_tmatrix(1.55, final_parameters)


def test_intermediate_t_preserves_nonfinite_guard(monkeypatch, final_parameters):
    monkeypatch.setattr(np.linalg, "solve",
                        lambda system, kernel: np.full(kernel.shape, np.nan))
    with pytest.raises(ValueError, match="nonfinite"):
        pipi_n_tmatrix(1.55, final_parameters)
