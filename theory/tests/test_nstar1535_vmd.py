"""Source-linked masses and six-channel switching for the N*(1535) VMD variant."""

import json
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import numpy as np
import pytest

from graal_theory.amplitudes.nstar1535_reduced import (
    C_COEFFICIENTS, load_reduced_parameters, wt_kernel,
)
from graal_theory.amplitudes.nstar1535_vmd import (
    VECTOR_SPECIES, VectorMasses, corrected_coefficients, load_vector_masses,
    switching_energies, vmd_kernel,
)
from graal_theory.amplitudes.vmd import angular_factor
from graal_theory.cli import _REFERENCES


REFERENCE_DIR = Path(__file__).resolve().parents[1] / "references"
MASSES_JSON = REFERENCE_DIR / "nstar1535_vmd_masses.json"
SOURCES = REFERENCE_DIR / "sources.json"


def test_p65_vector_masses_are_sourced():
    masses = load_vector_masses(MASSES_JSON, SOURCES)
    assert masses == VectorMasses(0.770, 0.892)
    assert _REFERENCES.joinpath("nstar1535_vmd_masses.json").is_file()


@pytest.mark.parametrize("name", ["rho_gev", "kstar_gev"])
def test_vector_masses_are_immutable(name):
    masses = load_vector_masses(MASSES_JSON, SOURCES)
    with pytest.raises(FrozenInstanceError):
        setattr(masses, name, 1.0)


@pytest.mark.parametrize("name", ["m_rho", "m_kstar"])
@pytest.mark.parametrize("field,value", [
    ("unit", "MeV"), ("value", True), ("value", False),
    ("value", "0.770"), ("value", None),
    ("value", float("nan")), ("value", float("inf")),
    ("value", float("-inf")), ("value", 0), ("value", -0.770),
    ("source_key", "missing"), ("source_key", "pdg_2024"),
    ("locator", ""), ("locator", "  "), ("locator", None),
    ("locator", "https://example.com"),
])
def test_vector_masses_reject_bad_entry(tmp_path, name, field, value):
    raw = json.loads(MASSES_JSON.read_text(encoding="utf-8"))
    raw[name][field] = value
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match=name):
        load_vector_masses(bad, SOURCES)


@pytest.mark.parametrize("name", ["m_rho", "m_kstar"])
@pytest.mark.parametrize("schema", ["missing-source", "extra-field", "list"])
def test_vector_masses_reject_malformed_entry(tmp_path, name, schema):
    raw = json.loads(MASSES_JSON.read_text(encoding="utf-8"))
    if schema == "missing-source":
        del raw[name]["source_key"]
    elif schema == "extra-field":
        raw[name]["extra"] = "unexpected"
    else:
        raw[name] = []
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match=name):
        load_vector_masses(bad, SOURCES)


@pytest.mark.parametrize("schema", ["missing", "extra", "list"])
def test_vector_masses_reject_wrong_names(tmp_path, schema):
    raw = json.loads(MASSES_JSON.read_text(encoding="utf-8"))
    if schema == "missing":
        del raw["m_kstar"]
    elif schema == "extra":
        raw["m_other"] = raw["m_rho"]
    else:
        raw = list(raw)
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="names"):
        load_vector_masses(bad, SOURCES)


def test_vector_masses_reject_missing_source_registry_record(tmp_path):
    raw = json.loads(SOURCES.read_text(encoding="utf-8"))
    del raw["inoue_2002"]
    bad_sources = tmp_path / "sources.json"
    bad_sources.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="m_rho"):
        load_vector_masses(MASSES_JSON, bad_sources)


@pytest.mark.parametrize("name", ["rho_gev", "kstar_gev"])
@pytest.mark.parametrize("value", [
    True, np.bool_(True), "0.770", None, 0.770+0j,
    float("nan"), float("inf"), float("-inf"), 0, -0.770,
])
def test_vector_masses_reject_invalid_direct_value(name, value):
    values = {"rho_gev": 0.770, "kstar_gev": 0.892}
    values[name] = value
    with pytest.raises(ValueError, match=name):
        VectorMasses(**values)


@pytest.fixture
def parameters():
    return load_reduced_parameters(
        REFERENCE_DIR / "nstar1535_reduced_parameters.json", SOURCES)


@pytest.fixture
def vector_masses():
    return load_vector_masses(MASSES_JSON, SOURCES)


def test_vector_species_follows_meson_strangeness():
    strangeness = (0, 0, 0, 1, 1, 1)
    assert isinstance(VECTOR_SPECIES, tuple)
    assert len(VECTOR_SPECIES) == 6
    for i, row in enumerate(VECTOR_SPECIES):
        assert isinstance(row, tuple)
        assert len(row) == 6
        for j, species in enumerate(row):
            if C_COEFFICIENTS[i, j] == 0:
                assert species is None
            else:
                expected = "rho" if strangeness[i] == strangeness[j] else "kstar"
                assert species == expected
                assert species == VECTOR_SPECIES[j][i]


def test_switches_are_bracketed_and_continuous(parameters, vector_masses):
    roots = switching_energies(parameters, vector_masses)
    assert roots.shape == (6, 6)
    assert roots.dtype == np.float64
    for i in range(6):
        for j in range(i, 6):
            if C_COEFFICIENTS[i, j] == 0:
                assert np.isnan(roots[i, j])
                assert np.isnan(roots[j, i])
                continue
            mi, mj = parameters.meson_masses_gev[i], parameters.meson_masses_gev[j]
            bi, bj = parameters.baryon_masses_gev[i], parameters.baryon_masses_gev[j]
            lo, hi = sorted((mi + bi, mj + bj))
            root = roots[i, j]
            assert lo <= root <= hi
            assert root == roots[j, i]
            if i == j:
                assert root == lo
            mass = (vector_masses.rho_gev if (i < 3) == (j < 3)
                    else vector_masses.kstar_gev)
            assert angular_factor(root, mi, bi, mj, bj, mass) == pytest.approx(
                1.0, rel=0, abs=1e-10)
            for w in (np.nextafter(root, -np.inf), root):
                result = corrected_coefficients(w, parameters, vector_masses)
                assert result[i, j] == C_COEFFICIENTS[i, j]
            above = corrected_coefficients(
                np.nextafter(root, np.inf), parameters, vector_masses)
            assert above[i, j] == pytest.approx(C_COEFFICIENTS[i, j], rel=0, abs=1e-10)


def test_switches_are_read_only_and_cache_is_preserved(parameters, vector_masses):
    roots = switching_energies(parameters, vector_masses)
    original = roots.copy()
    with pytest.raises(ValueError, match="read-only"):
        roots[0, 1] = 0.0
    np.testing.assert_array_equal(
        switching_energies(parameters, vector_masses), original)
    # Equal immutable values must reuse the cache; changed values must not.
    assert switching_energies(replace(parameters), replace(vector_masses)) is roots
    changed = switching_energies(parameters, replace(vector_masses, rho_gev=0.8))
    assert changed is not roots


def test_cached_switches_cannot_be_made_writeable(parameters, vector_masses):
    roots = switching_energies(parameters, vector_masses)
    original = roots.copy()
    with pytest.raises(ValueError):
        roots.setflags(write=True)
    np.testing.assert_array_equal(
        switching_energies(parameters, vector_masses), original)


@pytest.mark.parametrize("threshold_gap", [0.0, 0.001])
def test_missing_switch_is_rejected(parameters, vector_masses, threshold_gap):
    mesons = list(parameters.meson_masses_gev)
    baryons = list(parameters.baryon_masses_gev)
    threshold = mesons[0] + baryons[0]
    mesons[1] = 0.2
    baryons[1] = threshold + threshold_gap - mesons[1]
    synthetic = replace(parameters, meson_masses_gev=tuple(mesons),
                        baryon_masses_gev=tuple(baryons))
    with pytest.raises(ValueError, match="switch not bracketed"):
        switching_energies(synthetic, vector_masses)


def test_equal_threshold_pair_accepts_unit_factor(parameters, vector_masses):
    mesons = list(parameters.meson_masses_gev)
    baryons = list(parameters.baryon_masses_gev)
    mesons[1], baryons[1] = mesons[0], baryons[0]
    synthetic = replace(parameters, meson_masses_gev=tuple(mesons),
                        baryon_masses_gev=tuple(baryons))
    assert switching_energies(synthetic, vector_masses)[0, 1] == mesons[0] + baryons[0]


@pytest.mark.parametrize("w", [1.08, 1.30, 1.50, 1.70])
def test_corrected_coefficients_preserve_symmetry_and_zero_support(
    parameters, vector_masses, w,
):
    result = corrected_coefficients(w, parameters, vector_masses)
    assert result.shape == (6, 6)
    assert result.dtype == np.float64
    assert np.all(np.isfinite(result))
    np.testing.assert_array_equal(result, result.T)
    np.testing.assert_array_equal(result[C_COEFFICIENTS == 0], 0.0)
    assert not result.flags.writeable
    roots = switching_energies(parameters, vector_masses)
    for i in range(6):
        for j in range(i, 6):
            coefficient = C_COEFFICIENTS[i, j]
            if coefficient == 0:
                continue
            if w <= roots[i, j]:
                assert result[i, j] == coefficient
            else:
                mass = (vector_masses.rho_gev if (i < 3) == (j < 3)
                        else vector_masses.kstar_gev)
                factor = angular_factor(
                    w, parameters.meson_masses_gev[i], parameters.baryon_masses_gev[i],
                    parameters.meson_masses_gev[j], parameters.baryon_masses_gev[j], mass)
                assert result[i, j] == pytest.approx(coefficient * factor, rel=1e-14)


def test_vmd_replaces_coefficients_inside_wt_kernel(parameters, vector_masses):
    w = 1.50
    result = vmd_kernel(w, parameters, vector_masses)
    assert result.shape == (6, 6)
    assert result.dtype == np.float64
    assert np.all(np.isfinite(result))
    np.testing.assert_allclose(result, result.T, rtol=1e-14, atol=1e-14)
    np.testing.assert_array_equal(result[C_COEFFICIENTS == 0], 0.0)
    # Independently evaluate the pion elastic Eq. (5) normalization in GeV^-1.
    meson = parameters.meson_masses_gev[1]
    baryon = parameters.baryon_masses_gev[1]
    decay = parameters.decay_constants_gev[1]
    energy = (w*w + baryon*baryon - meson*meson)/(2*w)
    correction = angular_factor(w, meson, baryon, meson, baryon, vector_masses.rho_gev)
    expected = -correction * (2*w - 2*baryon) * (baryon + energy)/(2*baryon)/(4*decay**2)
    assert result[1, 1] == pytest.approx(expected, rel=1e-14)
    assert result[1, 1] != wt_kernel(w, parameters)[1, 1]
    threshold = min(np.add(parameters.meson_masses_gev, parameters.baryon_masses_gev))
    np.testing.assert_array_equal(
        corrected_coefficients(threshold, parameters, vector_masses), C_COEFFICIENTS)
    np.testing.assert_array_equal(
        vmd_kernel(threshold, parameters, vector_masses), wt_kernel(threshold, parameters))


@pytest.mark.parametrize("function", [corrected_coefficients, vmd_kernel])
@pytest.mark.parametrize("w", [True, np.bool_(True), "1.5", np.nan, np.inf, 1.0, 1.71])
def test_vmd_matrix_functions_validate_energy(parameters, vector_masses, function, w):
    with pytest.raises(ValueError, match="W"):
        function(w, parameters, vector_masses)
