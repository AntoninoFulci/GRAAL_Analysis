"""Source-linked vector masses for the N*(1535) VMD variant."""

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import numpy as np
import pytest

from graal_theory.amplitudes.nstar1535_vmd import VectorMasses, load_vector_masses
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
