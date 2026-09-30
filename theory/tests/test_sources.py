import json

import pytest

from graal_theory.sources import (
    PhysicalParameter,
    SourceRef,
    load_source_registry,
    validate_parameter_sources,
)


def test_parameter_requires_nonempty_locator():
    source = SourceRef("doering_2006_prc", "10.1103/PhysRevC.73.045209", "")
    with pytest.raises(ValueError, match="locator"):
        PhysicalParameter("m_delta", 1.232, "GeV", source)


def test_parameter_rejects_nonfinite_value():
    source = SourceRef("doering_2006_prc", "10.1103/PhysRevC.73.045209", "p. 10")
    with pytest.raises(ValueError, match="finite"):
        PhysicalParameter("m_delta", float("nan"), "GeV", source)


def test_registry_rejects_missing_doi_and_arxiv(tmp_path):
    path = tmp_path / "sources.json"
    path.write_text('{"bad": {"citation": "unresolvable"}}')
    with pytest.raises(ValueError, match="identifier"):
        load_source_registry(path)


def test_registry_rejects_malformed_record(tmp_path):
    path = tmp_path / "sources.json"
    path.write_text('{"bad": null}')
    with pytest.raises(ValueError, match="object"):
        load_source_registry(path)


def test_registry_loads_source_metadata(tmp_path):
    path = tmp_path / "sources.json"
    path.write_text(json.dumps({
        "paper": {"doi": "10.1/example", "citation": "Example (2001)"}
    }))
    assert load_source_registry(path)["paper"]["doi"] == "10.1/example"


def test_parameter_set_rejects_mismatched_key():
    source = SourceRef("paper", "10.1/example", "Eq. 1")
    parameter = PhysicalParameter("mass", 1.0, "GeV", source)
    with pytest.raises(ValueError, match="mismatch"):
        validate_parameter_sources({"width": parameter})
