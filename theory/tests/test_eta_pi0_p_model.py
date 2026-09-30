import json
from pathlib import Path

import numpy as np
import pytest

from graal_theory.models.eta_pi0_p import (
    REQUIRED_TREE_PARAMETER_NAMES,
    EtaPi0PModel,
    load_central_parameters,
)
from graal_theory.phase_space import SobolConfig, sample_three_body
from graal_theory.sources import validate_parameter_sources
from graal_theory.spin import transverse_polarizations


REFERENCES = Path(__file__).resolve().parents[1] / "references"
PARAMETER_FILE = REFERENCES / "central_parameters.json"
SOURCE_FILE = REFERENCES / "sources.json"


def test_central_parameter_file_is_closed_and_source_complete():
    parameters = load_central_parameters(PARAMETER_FILE, SOURCE_FILE)
    assert set(parameters) == REQUIRED_TREE_PARAMETER_NAMES
    validate_parameter_sources(parameters)


def test_eta_delta_coupling_identifies_sarkar_table_10_pole():
    parameter = load_central_parameters(PARAMETER_FILE, SOURCE_FILE)["g_eta_delta"]
    assert parameter.source.citation_key == "sarkar_2005"
    assert "1827-i108" in parameter.source.locator


def test_missing_electromagnetic_coupling_is_named(tmp_path):
    raw = json.loads(PARAMETER_FILE.read_text())
    del raw["g1_prime"]
    broken = tmp_path / "central_parameters.json"
    broken.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="g1_prime"):
        load_central_parameters(broken, SOURCE_FILE)


def test_unpolarized_result_is_invariant_under_transverse_basis_rotation():
    model = EtaPi0PModel.from_files(PARAMETER_FILE, SOURCE_FILE)
    sample = sample_three_body(1.77, model.masses, SobolConfig(power=6))
    ex, ey = transverse_polarizations(np.array([0.0, 0.0, 1.0]))
    angle = 0.37
    rotated = (
        np.cos(angle) * ex + np.sin(angle) * ey,
        -np.sin(angle) * ex + np.cos(angle) * ey,
    )
    np.testing.assert_allclose(
        model.matrix_element_squared(sample, polarizations=(ex, ey)),
        model.matrix_element_squared(sample, polarizations=rotated),
        rtol=1e-12,
        atol=1e-14,
    )
