"""Source-linked inputs for the intermediate N*(1535) pi-pi-N variant."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from graal_theory.amplitudes.nstar1535_final_fit import (
    _validated_final_values,
    load_final_fit_parameters,
)
from graal_theory.amplitudes.nstar1535_reduced import load_reduced_parameters
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
