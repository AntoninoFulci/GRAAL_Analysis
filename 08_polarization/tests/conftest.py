from __future__ import annotations

import sys
import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest


POLARIZATION_DIR = Path(__file__).resolve().parents[1]
if str(POLARIZATION_DIR) not in sys.path:
    sys.path.insert(0, str(POLARIZATION_DIR))


RESPONSE_TEST_FIELDS = tuple("""
schema_version analysis_version acceptance_release_id channel target beam_group
Egamma_low Egamma_high cos_theta_low cos_theta_high observable selection_id
orientation true_mass_bin true_mass_low_gev true_mass_high_gev true_phi_bin
true_phi_low true_phi_high reco_mass_bin reco_mass_low_gev reco_mass_high_gev
reco_phi_bin reco_phi_low reco_phi_high n_generated_true sumw_generated_true
sumw2_generated_true n_selected_migration sumw_selected_migration
sumw2_selected_migration response_probability response_stat_uncertainty
validity_mask input_sha256 config_sha256
""".split())


@dataclass
class ResponseFixture:
    path: Path
    rows: list[dict]
    config: object
    key: object

    def write(self, rows=None, *, fields=RESPONSE_TEST_FIELDS):
        with self.path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(self.rows if rows is None else rows)

    def block(self, true_cell=0, orientation="parallel"):
        return [row for row in self.rows if row["orientation"] == orientation
                and row["true_mass_bin"] * 12 + row["true_phi_bin"] == true_cell]


@pytest.fixture
def response_fixture(tmp_path):
    from analysis_config import AnalysisConfig, BootstrapConfig, ResponseValidationConfig
    from contracts import sha256_file
    from phi_response import ResponseKey

    schema_path = "config/schemas/acceptance_phi_response_v1.schema.json"
    local_schema = tmp_path / schema_path
    local_schema.parent.mkdir(parents=True)
    local_schema.write_bytes((POLARIZATION_DIR.parent / schema_path).read_bytes())
    config = AnalysisConfig(
        schema_version=1, analysis_version="polarization-v1", status="approved",
        blocked_reasons=(), acceptance_release_id="n3-test",
        acceptance_handoff_directory="results/physics/normalization/handoffs/n3-test",
        acceptance_qa_sha256="a" * 64, phi_response_schema_path=schema_path,
        phi_response_schema_sha256=sha256_file(POLARIZATION_DIR.parent / schema_path),
        phi_response_schema_approval_id="N3-MASS-PHI-RESPONSE-V1-2026-09-13",
        phi_response_schema_reviewers=("one", "two"), sign_status="approved",
        sign_approval_id="sign-test", sign_reviewers=("one", "two"),
        orientation_signs=(("parallel", -1), ("perpendicular", 1)),
        figure4_energy_edges_gev=(1.1, 1.2, 1.3, 1.4, 1.5),
        figure4_mass_bins=2, figure4_phi_bins=12, figure4_target="P",
        figure4_tree="reco_eta_pi0_chi2", figure4_vectors="kinematic_fit",
        response_validation=ResponseValidationConfig(100., 1e-12, 1e-12, 1e-9, 1e-12, 1e-4, 1e-6, 1e-10, 1e-8),
        bootstrap=BootstrapConfig(32, "poisson1-sha256-v1", 1701, .05, .5, 2.),
    )
    key = ResponseKey("eta_pi0", "P", "group-a", 1.1, 1.2, -1., 1., "eta_pi0", "selection-v1")
    mass_edges = np.linspace(.547862 + .134977,
                             np.sqrt(.938272**2 + 2 * .938272 * 1.2) - .938272, 3)
    phi_edges = np.linspace(0, np.pi, 13)
    rows = []
    for orientation in ("parallel", "perpendicular"):
        for i in range(24):
            for j in range(24):
                count, weight, weight2, probability, variance = (0, 0., 0., 0., 0.)
                if j == i:
                    count, weight, weight2, probability, variance = (20, 40., 80., 2/15, 38/50625)
                elif j == (i + 1) % 24:
                    count, weight, weight2, probability, variance = (30, 30., 30., 1/10, 29/90000)
                rows.append(dict(zip(RESPONSE_TEST_FIELDS, (
                    1, "polarization-v1", "n3-test", *key, orientation,
                    i // 12, mass_edges[i // 12], mass_edges[i // 12 + 1],
                    i % 12, phi_edges[i % 12], phi_edges[i % 12 + 1],
                    j // 12, mass_edges[j // 12], mass_edges[j // 12 + 1],
                    j % 12, phi_edges[j % 12], phi_edges[j % 12 + 1],
                    200, 300., 500., count, weight, weight2, probability,
                    np.sqrt(variance), "valid", "b" * 64, "c" * 64,
                ))))
    result = ResponseFixture(tmp_path / "acceptance_phi_response_v1.csv", rows, config, key)
    result.write()
    return result
