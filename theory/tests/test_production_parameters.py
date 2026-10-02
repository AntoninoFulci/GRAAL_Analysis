"""Production input loading, provenance, and numerical control contracts."""

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from graal_theory.amplitudes.production_loops import (
    QuadratureSettings,
    load_production_parameters,
)


REFERENCES = Path(__file__).resolve().parents[1] / "references"
PARAMETERS = REFERENCES / "eta_pi0_p_full_parameters.json"
SOURCES = REFERENCES / "sources.json"


def test_production_parameter_record_is_closed_and_sourced():
    p = load_production_parameters(PARAMETERS, SOURCES)
    expected = {
        "electric_charge": 0.3027,
        "axial_d": 0.75,
        "axial_f": 0.51,
        "b6d": 2.40,
        "b6f": 1.82,
        "first_loop_cutoff_gev": 1.4,
        "pion_form_factor_cutoff_gev": 1.25,
        "nstar1520_mass_gev": 1.520,
        "nstar1520_npi_width_gev": 0.066,
        "f_tilde_nstar_delta_pi": -1.061,
        "g_tilde_nstar_delta_pi": 0.640,
        "g1_nstar_per_gev": 0.782 / 0.93827208816,
        "g2_nstar_per_gev2": -0.410 / 0.93827208816**2,
        "g_rho_nstar": 5.09,
        "sigma_star_mass_gev": 1.385,
        "sigma_star_width_gev": 0.036,
        "g_k_sigma_star": 3.3 + 0.7j,
        "sigma_star_su3_correction": 1.15,
    }
    for name, value in expected.items():
        assert getattr(p, name) == pytest.approx(value)
    assert p.provenance["g1_nstar"].value == pytest.approx(0.782)
    assert p.provenance["g1_nstar"].unit == "m_N^-1"
    assert p.provenance["g1_nstar"].source.citation_key == "nacher_2001"
    assert p.provenance["g_k_sigma_star"].source.persistent_id == "10.1103/PhysRevC.73.045209"
    assert p.provenance["proton_mass"].source.citation_key == "pdg_2024"
    for name in ("axial_d", "axial_f"):
        locator = p.provenance[name].source.locator
        assert "Eq. (7)" in locator
        assert "baseline reconstruction convention; value not printed" in locator
    assert "adopts isospin-symmetric 1.385 GeV" in p.provenance["sigma_star_mass_gev"].source.locator
    assert p.quadrature == QuadratureSettings(64, 48, 1e-5, 1e-10)
    assert "quadrature" not in p.provenance
    with pytest.raises(FrozenInstanceError):
        p.b6d = 1.0
    with pytest.raises(TypeError):
        p.provenance["b6d"] = p.provenance["b6f"]


def _load_changed(tmp_path, change):
    raw = json.loads(PARAMETERS.read_text())
    change(raw)
    path = tmp_path / "parameters.json"
    path.write_text(json.dumps(raw))
    return load_production_parameters(path, SOURCES)


def test_electromagnetic_units_use_sourced_proton_mass(tmp_path):
    p = _load_changed(tmp_path, lambda raw: raw["proton_mass"].update(value=1.0))
    assert p.g1_nstar_per_gev == pytest.approx(0.782)
    assert p.g2_nstar_per_gev2 == pytest.approx(-0.410)
    assert p.provenance["proton_mass"].value == pytest.approx(1.0)


@pytest.mark.parametrize("mass", [1e-200, 1e-310])
def test_rejects_nonfinite_derived_electromagnetic_couplings(tmp_path, mass):
    with pytest.raises(ValueError, match="g[12]_nstar"):
        _load_changed(tmp_path, lambda raw: raw["proton_mass"].update(value=mass))


@pytest.mark.parametrize("change, parameter", [
    (lambda raw: raw.pop("b6d"), "b6d"),
    (lambda raw: raw.update(unplanned={}), "unplanned"),
    (lambda raw: raw["b6d"].pop("locator"), "b6d"),
    (lambda raw: raw["b6d"].update(extra=1), "b6d"),
    (lambda raw: raw.update(b6d=[]), "b6d"),
    (lambda raw: raw["b6d"].update(unit="GeV"), "b6d"),
    (lambda raw: raw["b6d"].update(locator="  "), "b6d"),
    (lambda raw: raw["b6d"].update(locator="https://example.org"), "b6d"),
    (lambda raw: raw["b6d"].update(locator=None), "b6d"),
    (lambda raw: raw["b6d"].update(source_key="unknown"), "b6d"),
    (lambda raw: raw["b6d"].update(source_key="pdg_2024"), "b6d"),
    (lambda raw: raw["b6d"].update(source_key=[]), "b6d"),
    (lambda raw: raw["b6d"].update(value={"real": 2.4, "imag": 0}), "b6d"),
    (lambda raw: raw["g_k_sigma_star"].update(value=3.3), "g_k_sigma_star"),
    (lambda raw: raw["g_k_sigma_star"]["value"].pop("imag"), "g_k_sigma_star"),
    (lambda raw: raw["g_k_sigma_star"]["value"].update(extra=1), "g_k_sigma_star"),
])
def test_rejects_malformed_production_record(tmp_path, change, parameter):
    with pytest.raises(ValueError, match=parameter):
        _load_changed(tmp_path, change)


@pytest.mark.parametrize("bad", [True, "2.4", None, float("nan"), float("inf"), -float("inf")])
@pytest.mark.parametrize("name", ["b6d", "g_k_sigma_star"])
def test_rejects_nonfinite_and_nonreal_components(tmp_path, bad, name):
    def change(raw):
        if name == "g_k_sigma_star":
            raw[name]["value"]["imag"] = bad
        else:
            raw[name]["value"] = bad
    with pytest.raises(ValueError, match=name):
        _load_changed(tmp_path, change)


@pytest.mark.parametrize("name", [
    "proton_mass", "nstar1520_mass_gev", "sigma_star_mass_gev",
    "first_loop_cutoff_gev", "pion_form_factor_cutoff_gev",
])
@pytest.mark.parametrize("bad", [0, -1])
def test_rejects_nonpositive_masses_and_cutoffs(tmp_path, name, bad):
    with pytest.raises(ValueError, match=name):
        _load_changed(tmp_path, lambda raw: raw[name].update(value=bad))


@pytest.mark.parametrize("name", ["nstar1520_npi_width_gev", "sigma_star_width_gev"])
def test_widths_are_nonnegative(tmp_path, name):
    with pytest.raises(ValueError, match=name):
        _load_changed(tmp_path, lambda raw: raw[name].update(value=-0.1))
    p = _load_changed(tmp_path, lambda raw: raw[name].update(value=0))
    assert getattr(p, name) == 0


@pytest.mark.parametrize("name", ["q_order", "angle_order"])
@pytest.mark.parametrize("bad", [True, 15, 16.0, "64", None])
def test_quadrature_orders_are_integer_at_least_sixteen(name, bad):
    with pytest.raises(ValueError, match=name):
        QuadratureSettings(**{name: bad})


@pytest.mark.parametrize("name", ["relative_tolerance", "absolute_tolerance"])
@pytest.mark.parametrize("bad", [True, "0.001", 0, -1, float("nan"), float("inf"), None, 1j])
def test_quadrature_tolerances_are_finite_positive_reals(name, bad):
    with pytest.raises(ValueError, match=name):
        QuadratureSettings(**{name: bad})


def test_custom_quadrature_settings_are_immutable():
    settings = QuadratureSettings(16, 16, 1, 1e-12)
    assert settings.q_order == 16
    assert settings.absolute_tolerance == 1e-12
    with pytest.raises(FrozenInstanceError):
        settings.q_order = 32
