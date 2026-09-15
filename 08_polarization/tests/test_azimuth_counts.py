from __future__ import annotations

import csv
from dataclasses import replace
import json

import numpy as np
import pytest

import azimuth_counts
import sigma_fit
from azimuth_counts import (
    AZIMUTH_COUNT_FIELDS,
    build_azimuth_counts,
    event_bootstrap_weight,
    write_azimuth_counts,
)
from contracts import PolarizationContractError, sha256_file
from figure4_analysis import PAIR_NAMES, PairObservables, physical_mass_edges
from root_events import EventSample


FILE_HASH = "0123456789abcdef" * 4
CANONICAL_BUNDLE = (
    "run_manifest_observables.csv",
    "run_quality.csv",
    "strip_energy_lookup.csv",
    "flux_by_run_energy.csv",
    "flux_by_group_energy.csv",
    "observable_run_qa.json",
)
EXPECTED_COUNT_FIELDS = tuple(
    """
schema_version analysis_version fit_release_id bin_set_id channel target beam_group
source_period Egamma_low Egamma_high cos_theta_low cos_theta_high observable
selection_id orientation replica_id reco_mass_bin reco_mass_low_gev
reco_mass_high_gev reco_phi_bin reco_phi_low reco_phi_high observed_count exposure
beam_polarization beam_polarization_variance gate0_handoff_sha256
n2_reconstruction_sha256 state_mapping_sha256 compton_source_sha256 config_sha256
input_sha256
""".split()
)


def _event_sample(paths):
    proton = np.tile([0.10, 0.05, 0.00, 1.00], (4, 1))
    eta = np.tile([0.10, 0.10, 0.00, 0.65], (4, 1))
    pi0 = np.tile([0.10, -0.05, 0.00, 0.20], (4, 1))
    return EventSample(
        beam_energy=np.full(4, 1.15),
        beam=np.tile([0.0, 0.0, 1.15, 1.15], (4, 1)),
        run_number=np.array([101, 101, 101, 101]),
        state_code=np.array([1, 1, 2, 2]),
        xstrip=np.array([40.0, 41.0, 42.0, 43.0]),
        proton=proton,
        eta=eta,
        pi0=pi0,
        file_sha256=np.array([sha256_file(paths["reco"])] * 4),
        tree_entry=np.arange(4),
    )


@pytest.fixture
def event_sample(count_authority_repo):
    return _event_sample(count_authority_repo)


def _authority_source(path, repository_root):
    return {
        "path": path.relative_to(repository_root).as_posix(),
        "sha256": sha256_file(path),
        "authority": "synthetic-test-authority",
        "approval_id": "TEST-ONLY",
        "reviewers": ["test-owner-1", "test-owner-2"],
    }


def _authority_file(path, repository_root):
    return {
        "path": path.relative_to(repository_root).as_posix(),
        "sha256": sha256_file(path),
    }


@pytest.fixture
def count_authority_repo(response_fixture):
    repository_root = response_fixture.path.parent
    bundle_dir = repository_root / "results/observable_runs"
    bundle_dir.mkdir(parents=True)
    manifest = repository_root / "config/run_manifest.csv"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        "run_number,target\n101,P\n102,P\n103,P\n", encoding="utf-8"
    )
    (bundle_dir / "run_manifest_observables.csv").write_text(
        "run_number,source_period,target,beam_type,group,classification_source,source_file\n"
        "101,period-a,P,UV,group-a,synthetic,reco.root\n"
        "102,period-b,P,UV,group-a,synthetic,reco.root\n"
        "103,period-a,P,UV,group-a,synthetic,reco.root\n",
        encoding="utf-8",
    )
    (bundle_dir / "run_quality.csv").write_text(
        "run_number,status\n101,good\n102,good\n103,good\n", encoding="utf-8"
    )
    (bundle_dir / "strip_energy_lookup.csv").write_text(
        "run_number,source_period,target,beam_type,group,xstrip,event_count,"
        "energy_median_gev,energy_mad_gev,energy_min_gev,energy_max_gev,provenance\n"
        + "".join(
            f"101,period-a,P,UV,group-a,{strip},10,1.15,0.01,1.14,1.16,observed\n"
            for strip in range(40, 44)
        )
        + "102,period-b,P,UV,group-a,42,10,1.15,0.01,1.14,1.16,observed\n"
        + "103,period-a,P,UV,group-a,42,10,1.15,0.01,1.14,1.16,observed\n",
        encoding="utf-8",
    )
    flux_path = bundle_dir / "flux_by_run_energy.csv"
    flux_fields = (
        "binning", "run_number", "source_period", "target", "beam_type",
        "group", "energy_low_gev", "energy_high_gev", "pol1", "brem",
        "pol2", "pol1_net", "pol2_net", "total_net", "status",
    )
    with flux_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=flux_fields)
        writer.writeheader()
        for run, period, pol1_net, pol2_net in (
            (101, "period-a", 100.0, 80.0),
            (102, "period-b", 30.0, 40.0),
            (103, "period-a", 50.0, 60.0),
        ):
            for low, high in ((1.1, 1.2), (1.2, 1.3), (1.3, 1.4), (1.4, 1.5)):
                writer.writerow(
                    {
                        "binning": "ajaka_sigma",
                        "run_number": run,
                        "source_period": period,
                        "target": "P",
                        "beam_type": "UV",
                        "group": "group-a",
                        "energy_low_gev": low,
                        "energy_high_gev": high,
                        "pol1": pol1_net + 1.0,
                        "brem": 1.0,
                        "pol2": pol2_net + 1.0,
                        "pol1_net": pol1_net,
                        "pol2_net": pol2_net,
                        "total_net": pol1_net + pol2_net,
                        "status": "valid",
                    }
                )
    (bundle_dir / "flux_by_group_energy.csv").write_text(
        "status\nvalid\n", encoding="utf-8"
    )
    (bundle_dir / "observable_run_qa.json").write_text(
        json.dumps({"schema_version": 1, "valid": True}), encoding="utf-8"
    )
    gate0_path = bundle_dir / "HANDOFF.json"
    gate0_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "producer_commit": "a" * 40,
                "manifest_path": "config/run_manifest.csv",
                "manifest_sha256": sha256_file(manifest),
                "files": [
                    _authority_file(bundle_dir / name, repository_root)
                    for name in CANONICAL_BUNDLE
                ],
                "observable_run_qa_path": (
                    "results/observable_runs/observable_run_qa.json"
                ),
                "observable_run_qa_sha256": sha256_file(
                    bundle_dir / "observable_run_qa.json"
                ),
                "observable_run_qa_valid": True,
                "energy_binning_mev": [1100, 1200, 1300, 1400, 1500],
                "created_at_utc": "2026-09-13T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    reconstruction_dir = repository_root / "results/reconstruction"
    reconstruction_dir.mkdir(parents=True)
    reco_path = reconstruction_dir / "reco.root"
    reco_path.write_bytes(b"synthetic N2 ROOT bytes")
    ledger_path = reconstruction_dir / "processed_runs.csv"
    ledger_path.write_text(
        "run_number,status\n101,complete\n102,complete\n103,complete\n",
        encoding="utf-8",
    )
    inventory_path = reconstruction_dir / "inventory.json"
    inventory_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "artifact_kind": "n2_metadata_reconstruction",
                "producer_commit": "b" * 40,
                "gate0_handoff_sha256": sha256_file(gate0_path),
                "complete_run_coverage": True,
                "tree": "reco_eta_pi0_chi2",
                "vectors": "kinematic_fit",
                "run_numbers": [101, 102, 103],
                "observed_event_run_numbers": [101],
                "zero_selected_event_run_numbers": [102, 103],
                "processed_run_ledger": _authority_file(
                    ledger_path, repository_root
                ),
                "files": [_authority_file(reco_path, repository_root)],
            }
        ),
        encoding="utf-8",
    )

    authority_dir = repository_root / "data/authorities"
    authority_dir.mkdir(parents=True)
    state_source = authority_dir / "state.csv"
    state_source.write_text(
        "run,state\n101,1\n102,1\n103,1\n", encoding="utf-8"
    )
    compton_source = authority_dir / "compton.csv"
    compton_source.write_text(
        "energy_mev,polarization\n1100,0.8\n1500,0.8\n", encoding="utf-8"
    )
    compton_source_b = authority_dir / "compton-b.csv"
    compton_source_b.write_text(
        "energy_mev,polarization\n1100,0.7\n1500,0.7\n", encoding="utf-8"
    )

    release_dir = (
        repository_root
        / "results/physics/normalization/handoffs/n3-test"
    )
    release_dir.mkdir(parents=True)
    acceptance_path = release_dir / "acceptance_v1.csv"
    acceptance_path.write_text(
        "analysis_version,channel,target,beam_group,Egamma_low,Egamma_high,"
        "cos_theta_low,cos_theta_high,observable,selection_id,n_generated,"
        "n_thrown_in_bin,n_reconstructed_selected,acceptance,"
        "acceptance_stat_uncertainty,validity_mask,input_sha256,config_sha256\n"
        + "".join(
            "polarization-v1,eta_pi0,P,group-a,1.1,1.2,-1.0,1.0,"
            f"{observable},selection-v1,1000,500,250,0.5,0.02,valid,"
            f"{'b' * 64},{'c' * 64}\n"
            for observable in PAIR_NAMES
        ),
        encoding="utf-8",
    )
    response_path = release_dir / "acceptance_phi_response_v1.csv"
    response_rows = []
    mass_edges = physical_mass_edges(
        1.2,
        bins=2,
        masses_gev={"proton": 0.938272, "eta": 0.547862, "pi0": 0.134977},
    )
    for observable in PAIR_NAMES:
        for original in response_fixture.rows:
            row = dict(original)
            row["observable"] = observable
            true_bin = row["true_mass_bin"]
            reco_bin = row["reco_mass_bin"]
            row["true_mass_low_gev"] = mass_edges[observable][true_bin]
            row["true_mass_high_gev"] = mass_edges[observable][true_bin + 1]
            row["reco_mass_low_gev"] = mass_edges[observable][reco_bin]
            row["reco_mass_high_gev"] = mass_edges[observable][reco_bin + 1]
            response_rows.append(row)
    response_rows.sort(
        key=lambda row: (
            *(row[name] for name in (
                "channel", "target", "beam_group", "Egamma_low", "Egamma_high",
                "cos_theta_low", "cos_theta_high", "observable", "selection_id",
            )),
            row["orientation"],
            row["true_mass_bin"],
            row["true_phi_bin"],
            row["reco_mass_bin"],
            row["reco_phi_bin"],
        )
    )
    with response_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=tuple(response_rows[0]))
        writer.writeheader()
        writer.writerows(response_rows)
    acceptance_qa_path = release_dir / "acceptance_qa.json"
    acceptance_qa_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "acceptance_release_id": "n3-test",
                "producer_commit": "c" * 40,
                "valid": True,
                "acceptance_csv_sha256": sha256_file(acceptance_path),
                "acceptance_phi_response_csv_sha256": sha256_file(response_path),
                "phi_response_schema_path": (
                    "config/schemas/acceptance_phi_response_v1.schema.json"
                ),
                "phi_response_schema_sha256": response_fixture.config.phi_response_schema_sha256,
                "phi_response_schema_approval_id": (
                    "N3-MASS-PHI-RESPONSE-V1-2026-09-15"
                ),
                "gate0_handoff_sha256": sha256_file(gate0_path),
                "n2_reconstruction_sha256": sha256_file(inventory_path),
                "input_sha256": "b" * 64,
                "config_sha256": "c" * 64,
                "count_checks": {"valid": True},
                "matrix_checks": {"valid": True},
                "weighted_covariance_checks": {
                    "valid": True,
                    "shared_mc_across_blocks": False,
                    "cross_block_covariance": False,
                },
                "response_period_coverage": [
                    {
                        "beam_group": "group-a",
                        "covered_source_periods": ["period-a", "period-b"],
                        "coverage_valid": True,
                        "detector_conditions_sha256": "1" * 64,
                        "mc_config_sha256": "2" * 64,
                        "selection_sha256": "3" * 64,
                    }
                ],
                "closure": {"valid": True},
            }
        ),
        encoding="utf-8",
    )

    config_path = repository_root / "config/physics/polarization_v1.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "analysis_version": "polarization-v1",
                "status": "approved",
                "blocked_reasons": [],
                "gate0_handoff": "results/observable_runs/HANDOFF.json",
                "acceptance": {
                    "status": "approved",
                    "handoff_parent": "results/physics/normalization/handoffs",
                    "release_id": "n3-test",
                    "handoff_directory": (
                        "results/physics/normalization/handoffs/n3-test"
                    ),
                    "required_files": [
                        "acceptance_v1.csv",
                        "acceptance_phi_response_v1.csv",
                        "acceptance_qa.json",
                    ],
                    "acceptance_qa_sha256": sha256_file(acceptance_qa_path),
                    "phi_response_schema_status": "approved",
                    "phi_response_schema_path": (
                        "config/schemas/acceptance_phi_response_v1.schema.json"
                    ),
                    "phi_response_schema_sha256": response_fixture.config.phi_response_schema_sha256,
                    "phi_response_schema_approval_id": (
                        "N3-MASS-PHI-RESPONSE-V1-2026-09-15"
                    ),
                    "phi_response_schema_reviewers": ["test-a", "test-b"],
                },
                "state_mapping": {
                    "status": "ready",
                    "source": _authority_source(state_source, repository_root),
                    "intervals": [
                        {
                            "run_start": 101,
                            "run_end": 101,
                            "state_code": 1,
                            "orientation": "parallel",
                            "source_period": "period-a",
                            "flux_component": "pol1_net",
                        },
                        {
                            "run_start": 101,
                            "run_end": 101,
                            "state_code": 2,
                            "orientation": "perpendicular",
                            "source_period": "period-a",
                            "flux_component": "pol2_net",
                        },
                        {
                            "run_start": 102,
                            "run_end": 102,
                            "state_code": 1,
                            "orientation": "parallel",
                            "source_period": "period-b",
                            "flux_component": "pol1_net",
                        },
                        {
                            "run_start": 102,
                            "run_end": 102,
                            "state_code": 2,
                            "orientation": "perpendicular",
                            "source_period": "period-b",
                            "flux_component": "pol2_net",
                        },
                        {
                            "run_start": 103,
                            "run_end": 103,
                            "state_code": 1,
                            "orientation": "parallel",
                            "source_period": "period-a",
                            "flux_component": "pol1_net",
                        },
                        {
                            "run_start": 103,
                            "run_end": 103,
                            "state_code": 2,
                            "orientation": "perpendicular",
                            "source_period": "period-a",
                            "flux_component": "pol2_net",
                        },
                    ],
                },
                "compton_polarization": {
                    "status": "ready",
                    "periods": [
                        {
                            "source_period": "period-a",
                            "source": _authority_source(
                                compton_source, repository_root
                            ),
                            "energies_mev": [1100.0, 1500.0],
                            "polarization": [0.8, 0.8],
                            "covariance": [[0.0001, 0.0], [0.0, 0.0001]],
                        },
                        {
                            "source_period": "period-b",
                            "source": _authority_source(
                                compton_source_b, repository_root
                            ),
                            "energies_mev": [1100.0, 1500.0],
                            "polarization": [0.7, 0.7],
                            "covariance": [[0.0004, 0.0], [0.0, 0.0004]],
                        },
                    ],
                },
                "angle": {
                    "observable": "reaction_plane_phi",
                    "period_radians": np.pi,
                    "range_radians": [0.0, np.pi],
                    "reference_axis_lab": [1.0, 0.0, 0.0],
                    "reaction_momentum": "proton",
                    "degenerate_plane_policy": "invalid",
                    "tolerance": 1e-12,
                },
                "sign_convention": {
                    "status": "approved",
                    "approval_id": "fixture-sign",
                    "reviewers": ["test-a", "test-b"],
                    "model": "mu = fixture",
                    "orientation_signs": {"parallel": -1, "perpendicular": 1},
                },
                "figure4_comparison": {
                    "energy_edges_gev": [1.1, 1.2, 1.3, 1.4, 1.5],
                    "mass_bins": 2,
                    "phi_bins": 12,
                    "target": "P",
                    "tree": "reco_eta_pi0_chi2",
                    "vectors": "kinematic_fit",
                    "content_policy": (
                        "framework_results_only_no_published_points_curves_or_digitization"
                    ),
                },
                "closure": {
                    "random_seed": 1701,
                    "bias_absolute_max": 0.02,
                    "pull_mean_absolute_max": 0.2,
                    "pull_width_tolerance": 0.2,
                    "require_sign_check": True,
                },
                "response_validation": {
                    "minimum_generated_effective_events_per_true_phi": 100.0,
                    "probability_absolute_tolerance": 1e-12,
                    "uncertainty_absolute_tolerance": 1e-12,
                    "uncertainty_relative_tolerance": 1e-9,
                    "covariance_eigenvalue_absolute_tolerance": 1e-12,
                    "finite_difference_relative_step": 1e-4,
                    "finite_difference_absolute_step": 1e-6,
                    "replay_absolute_tolerance": 1e-10,
                    "replay_relative_tolerance": 1e-8,
                },
                "bootstrap": {
                    "replicas": 32,
                    "algorithm_version": "poisson1-sha256-v1",
                    "seed": 1701,
                    "maximum_failed_fraction": 0.05,
                    "hessian_diagonal_ratio_min": 0.5,
                    "hessian_diagonal_ratio_max": 2.0,
                },
                "release_qa_thresholds": {
                    "status": "approved",
                    "approval_id": "fixture-release",
                    "reviewers": ["test-a", "test-b"],
                    "minimum_events_per_bin": 10,
                    "maximum_deviance_per_ndof": 2.0,
                    "closure_bias_absolute_max": 0.02,
                    "closure_pull_mean_absolute_max": 0.2,
                    "closure_pull_width_tolerance": 0.2,
                    "minimum_systematic_sources": 1,
                    "systematic_combination_policy": (
                        "independent_sources_quadrature"
                    ),
                },
            }
        ),
        encoding="utf-8",
    )
    return {
        "root": repository_root,
        "config": config_path,
        "gate0": gate0_path,
        "manifest": manifest,
        "flux": flux_path,
        "lookup": bundle_dir / "strip_energy_lookup.csv",
        "inventory": inventory_path,
        "reco": reco_path,
        "ledger": ledger_path,
        "schema": repository_root / "config/schemas/acceptance_phi_response_v1.schema.json",
        "state": state_source,
        "compton": compton_source,
        "compton_b": compton_source_b,
        "acceptance_qa": acceptance_qa_path,
        "response": response_path,
    }


def _load_count_authority(paths):
    root = paths["root"]
    return azimuth_counts.load_count_authority(
        repository_root=root,
        config_path=paths["config"].relative_to(root).as_posix(),
        gate0_handoff_path=paths["gate0"].relative_to(root).as_posix(),
        n2_inventory_path=paths["inventory"].relative_to(root).as_posix(),
        acceptance_handoff_path=paths["acceptance_qa"].relative_to(root).as_posix(),
        fit_release_id="fit-test",
        bin_set_id="figure4-v1",
    )


def _project(sample, authority):
    """Exercise the non-release array projector without supplying public input."""
    return azimuth_counts._project_azimuth_counts(sample, authority=authority)


@pytest.fixture
def count_authority(count_authority_repo):
    return _load_count_authority(count_authority_repo)


def _reanchor_response(paths):
    qa = json.loads(paths["acceptance_qa"].read_text(encoding="utf-8"))
    qa["acceptance_phi_response_csv_sha256"] = sha256_file(paths["response"])
    paths["acceptance_qa"].write_text(json.dumps(qa), encoding="utf-8")
    config = json.loads(paths["config"].read_text(encoding="utf-8"))
    config["acceptance"]["acceptance_qa_sha256"] = sha256_file(
        paths["acceptance_qa"]
    )
    paths["config"].write_text(json.dumps(config), encoding="utf-8")


def _reanchor_gate0_flux(paths):
    handoff = json.loads(paths["gate0"].read_text(encoding="utf-8"))
    for record in handoff["files"]:
        if record["path"].endswith("/flux_by_run_energy.csv"):
            record["sha256"] = sha256_file(paths["flux"])
    paths["gate0"].write_text(json.dumps(handoff), encoding="utf-8")
    inventory = json.loads(paths["inventory"].read_text(encoding="utf-8"))
    inventory["gate0_handoff_sha256"] = sha256_file(paths["gate0"])
    paths["inventory"].write_text(json.dumps(inventory), encoding="utf-8")
    qa = json.loads(paths["acceptance_qa"].read_text(encoding="utf-8"))
    qa["gate0_handoff_sha256"] = sha256_file(paths["gate0"])
    qa["n2_reconstruction_sha256"] = sha256_file(paths["inventory"])
    paths["acceptance_qa"].write_text(json.dumps(qa), encoding="utf-8")
    config = json.loads(paths["config"].read_text(encoding="utf-8"))
    config["acceptance"]["acceptance_qa_sha256"] = sha256_file(
        paths["acceptance_qa"]
    )
    paths["config"].write_text(json.dumps(config), encoding="utf-8")


def test_count_authority_loader_retains_only_actual_authenticated_bytes(
    count_authority_repo,
):
    authority = _load_count_authority(count_authority_repo)

    assert authority.config_file.sha256 == sha256_file(count_authority_repo["config"])
    assert authority.gate0_handoff_file.sha256 == sha256_file(
        count_authority_repo["gate0"]
    )
    assert authority.gate0_manifest_file.sha256 == sha256_file(
        count_authority_repo["manifest"]
    )
    assert authority.flux_file.sha256 == sha256_file(count_authority_repo["flux"])
    assert authority.strip_energy_lookup_file.sha256 == sha256_file(
        count_authority_repo["lookup"]
    )
    assert authority.n2_inventory_file.sha256 == sha256_file(
        count_authority_repo["inventory"]
    )
    assert authority.n2_processed_run_ledger_file.sha256 == sha256_file(
        count_authority_repo["ledger"]
    )
    assert authority.n3_schema_file.sha256 == sha256_file(
        count_authority_repo["schema"]
    )
    assert tuple(
        (record.relative_path, record.sha256) for record in authority.n2_files
    ) == (
        (
            "results/reconstruction/reco.root",
            sha256_file(count_authority_repo["reco"]),
        ),
    )
    retained = (
        authority.config_file,
        authority.gate0_handoff_file,
        authority.gate0_manifest_file,
        *authority.gate0_bundle_files,
        authority.n2_inventory_file,
        authority.n2_processed_run_ledger_file,
        *authority.n2_files,
        authority.state_mapping_file,
        *[item.file for item in authority.compton_files],
        *authority.acceptance_files,
        authority.n3_schema_file,
    )
    assert all(record.sha256 == sha256_file(record.path) for record in retained)
    assert authority.response.source_sha256 == sha256_file(
        count_authority_repo["response"]
    )
    assert authority.response_covariance_scope.qa_sha256 == (
        authority.config.acceptance_qa_sha256
    )
    assert authority.response_covariance_scope.shared_mc_across_blocks is False
    assert authority.response_covariance_scope.cross_block_covariance is False
    assert authority.response_period_coverage[0].covered_source_periods == (
        "period-a",
        "period-b",
    )
    assert len(authority.flux_rows) == 3
    assert {
        (row.beam_group, row.energy_low_gev, row.energy_high_gev)
        for row in authority.flux_rows
    } == {("group-a", 1.1, 1.2)}


def test_count_authority_ignores_valid_gate0_flux_outside_response_universe(
    count_authority_repo,
):
    with count_authority_repo["flux"].open("a", encoding="utf-8") as stream:
        stream.write(
            "ajaka_sigma,101,period-without-authority,P,UV,irrelevant-group,"
            "1.1,1.2,11,1,13,10,12,22,valid\n"
        )
    _reanchor_gate0_flux(count_authority_repo)

    authority = _load_count_authority(count_authority_repo)

    assert len(authority.flux_rows) == 3
    assert {row.source_period for row in authority.flux_rows} == {
        "period-a", "period-b"
    }
    assert {key.observable for key in authority.response.keys} == set(PAIR_NAMES)


def _break_authority_file(path, mutation):
    if mutation == "tampered":
        if path.name == "polarization_v1.json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["status"] = "blocked"
            path.write_text(json.dumps(payload), encoding="utf-8")
        else:
            path.write_bytes(path.read_bytes() + b"\n")
    elif mutation == "missing":
        path.unlink()
    else:
        target = path.with_name(f"{path.name}.target")
        path.rename(target)
        path.symlink_to(target)


@pytest.mark.parametrize(
    "authority_name",
    (
        "config",
        "gate0",
        "flux",
        "inventory",
        "reco",
        "state",
        "compton",
        "acceptance_qa",
        "response",
    ),
)
@pytest.mark.parametrize("mutation", ("tampered", "missing", "symlink"))
def test_count_authority_loader_rejects_changed_missing_or_linked_inputs(
    count_authority_repo, authority_name, mutation
):
    _break_authority_file(count_authority_repo[authority_name], mutation)

    with pytest.raises(PolarizationContractError):
        _load_count_authority(count_authority_repo)


def test_count_authority_cannot_be_rebuilt_with_forged_hash_strings(
    count_authority_repo,
):
    authority = _load_count_authority(count_authority_repo)
    forged = replace(authority.config_file, sha256="f" * 64)

    with pytest.raises(PolarizationContractError, match="load_count_authority"):
        replace(authority, config_file=forged)


def test_public_builder_reloads_authority_and_reads_authenticated_inventory(
    monkeypatch, count_authority, count_authority_repo
):
    sample = _event_sample(count_authority_repo)
    calls = []

    def read_authenticated(paths, *, tree_name, vectors):
        calls.append((tuple(paths), tree_name, vectors))
        return sample

    monkeypatch.setattr(
        azimuth_counts, "read_reco_root", read_authenticated, raising=False
    )

    table = build_azimuth_counts(authority=count_authority)

    assert calls == [(
        count_authority.n2_inventory.paths,
        count_authority.config.figure4_tree,
        count_authority.config.figure4_vectors,
    )]
    assert table.has_every_reco_cell()


def test_public_builder_rejects_caller_supplied_event_sample(
    event_sample, count_authority
):
    with pytest.raises(TypeError):
        build_azimuth_counts(event_sample, authority=count_authority)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ({"xstrip": np.array([99.0, 41.0, 42.0, 43.0])}, "strip-energy lookup"),
        ({"beam_energy": np.array([1.17, 1.15, 1.15, 1.15])}, "strip-energy interval"),
    ],
)
def test_selected_event_requires_exact_authenticated_strip_energy_mapping(
    event_sample, count_authority, mutation, message
):
    if "beam_energy" in mutation:
        beam = event_sample.beam.copy()
        beam[:, 3] = mutation["beam_energy"]
        mutation = {**mutation, "beam": beam}
    sample = replace(event_sample, **mutation)
    with pytest.raises(PolarizationContractError, match=message):
        _project(sample, count_authority)


def test_selected_event_degenerate_reaction_plane_rejects_count_publication(
    event_sample, count_authority
):
    proton = event_sample.proton.copy()
    proton[0, :3] = event_sample.beam[0, :3]
    with pytest.raises(PolarizationContractError, match="degenerate reaction plane"):
        _project(replace(event_sample, proton=proton), count_authority)


def test_selected_event_outside_any_required_reco_axis_rejects_whole_publication(
    event_sample, count_authority
):
    eta = event_sample.eta.copy()
    eta[0] = [0.0, 0.0, 0.0, 10.0]

    with pytest.raises(
        PolarizationContractError,
        match=r"selected N2 event .*run=101.*tree_entry=0.*observable=eta_pi0.*reco mass",
    ):
        _project(replace(event_sample, eta=eta), count_authority)


def test_selected_event_without_required_reco_phi_cell_rejects_whole_publication(
    monkeypatch, event_sample, count_authority
):
    real_projection = azimuth_counts.event_pair_observables

    def project_outside_phi(*args, **kwargs):
        projected = real_projection(*args, **kwargs)
        original = projected["eta_pi0"]
        phi = original.phi.copy()
        phi[0] = 4.0
        projected["eta_pi0"] = PairObservables(
            mass=original.mass, phi=phi, valid_phi=original.valid_phi
        )
        return projected

    monkeypatch.setattr(
        azimuth_counts, "event_pair_observables", project_outside_phi
    )

    with pytest.raises(
        PolarizationContractError,
        match=r"selected N2 event .*tree_entry=0.*observable=eta_pi0.*reco phi",
    ):
        _project(event_sample, count_authority)


def test_selected_event_xstrip_uses_shared_half_up_normalization(
    event_sample, count_authority
):
    xstrip = event_sample.xstrip.copy()
    xstrip[0] = 40.5

    table = _project(replace(event_sample, xstrip=xstrip), count_authority)

    assert table.sum_for("p_pi0", replica_id=0) == 4


def test_count_authority_rejects_n3_declared_period_mismatch(count_authority_repo):
    qa = json.loads(count_authority_repo["acceptance_qa"].read_text())
    qa["response_period_coverage"][0]["covered_source_periods"] = ["period-a"]
    count_authority_repo["acceptance_qa"].write_text(json.dumps(qa))
    config = json.loads(count_authority_repo["config"].read_text())
    config["acceptance"]["acceptance_qa_sha256"] = sha256_file(
        count_authority_repo["acceptance_qa"]
    )
    count_authority_repo["config"].write_text(json.dumps(config))

    with pytest.raises(PolarizationContractError, match="declared periods"):
        _load_count_authority(count_authority_repo)


def test_public_fit_cannot_accept_caller_forged_observed_counts(
    monkeypatch, event_sample, count_authority
):
    """Removing the public ``counts`` argument must make forged data unusable."""
    table = _project(event_sample, count_authority)
    forged = replace(
        table,
        rows=(
            replace(table.rows[0], observed_count=table.rows[0].observed_count + 10_000),
            *table.rows[1:],
        ),
    )
    monkeypatch.setattr(
        azimuth_counts,
        "read_reco_root",
        lambda *_args, **_kwargs: event_sample,
    )

    with pytest.raises(TypeError):
        sigma_fit.fit_sigma_forward_folded(
            counts=forged,
            authority=count_authority,
        )


def test_public_fit_rejects_stateful_count_table_subclass(
    monkeypatch, event_sample, count_authority
):
    """An alternating ``rows`` property must not cross the fit trust boundary."""
    table = _project(event_sample, count_authority)
    forged_rows = (
        replace(table.rows[0], observed_count=table.rows[0].observed_count + 10_000),
        *table.rows[1:],
    )

    class StatefulCountTable(azimuth_counts.AzimuthCountTable):
        def __getattribute__(self, name):
            if name == "rows" and getattr(self, "_armed", False):
                current = object.__getattribute__(self, "_return_forged")
                object.__setattr__(self, "_return_forged", not current)
                if current:
                    return object.__getattribute__(self, "_forged_rows")
            return super().__getattribute__(name)

    stateful = StatefulCountTable(
        table.rows,
        table.expected_universe,
        table.expected_replica_ids,
    )
    object.__setattr__(stateful, "_armed", False)
    object.__setattr__(stateful, "_return_forged", False)
    object.__setattr__(stateful, "_forged_rows", forged_rows)
    object.__setattr__(stateful, "_armed", True)
    monkeypatch.setattr(
        sigma_fit,
        "build_azimuth_counts",
        lambda *, authority: stateful,
        raising=False,
    )

    with pytest.raises(PolarizationContractError, match="exact immutable"):
        sigma_fit.fit_sigma_forward_folded(authority=count_authority)


def test_public_fit_rejects_reanchored_authority_change_after_count_build(
    monkeypatch, event_sample, count_authority, count_authority_repo
):
    """Post-build reload must catch a coherent authority swap after ROOT read."""
    real_builder = sigma_fit.build_azimuth_counts
    monkeypatch.setattr(
        azimuth_counts,
        "read_reco_root",
        lambda *_args, **_kwargs: event_sample,
    )

    def build_then_replace(*, authority):
        table = real_builder(authority=authority)
        _replace_file(count_authority_repo["manifest"])
        _reanchor_transitive_replacement(count_authority_repo, "manifest")
        return table

    monkeypatch.setattr(sigma_fit, "build_azimuth_counts", build_then_replace)

    with pytest.raises(PolarizationContractError, match="changed while counts"):
        sigma_fit.fit_sigma_forward_folded(authority=count_authority)


def test_writer_requires_fresh_authority(
    event_sample, count_authority, tmp_path
):
    table = _project(event_sample, count_authority)
    output = tmp_path / "azimuth_counts_v1.csv"

    digest = write_azimuth_counts(table, output, authority=count_authority)

    assert digest == sha256_file(output)


def _replace_file(path):
    replacement = path.with_name(f"{path.name}.replacement")
    replacement.write_bytes(path.read_bytes() + b"\n")
    replacement.replace(path)


def _reanchor_transitive_replacement(paths, authority_name):
    if authority_name == "manifest":
        gate0 = json.loads(paths["gate0"].read_text(encoding="utf-8"))
        gate0["manifest_sha256"] = sha256_file(paths["manifest"])
        paths["gate0"].write_text(json.dumps(gate0), encoding="utf-8")
    if authority_name in {"manifest", "ledger"}:
        inventory = json.loads(paths["inventory"].read_text(encoding="utf-8"))
        if authority_name == "manifest":
            inventory["gate0_handoff_sha256"] = sha256_file(paths["gate0"])
        else:
            inventory["processed_run_ledger"]["sha256"] = sha256_file(
                paths["ledger"]
            )
        paths["inventory"].write_text(json.dumps(inventory), encoding="utf-8")
    qa = json.loads(paths["acceptance_qa"].read_text(encoding="utf-8"))
    if authority_name == "manifest":
        qa["gate0_handoff_sha256"] = sha256_file(paths["gate0"])
        qa["n2_reconstruction_sha256"] = sha256_file(paths["inventory"])
    elif authority_name == "ledger":
        qa["n2_reconstruction_sha256"] = sha256_file(paths["inventory"])
    else:
        qa["phi_response_schema_sha256"] = sha256_file(paths["schema"])
    paths["acceptance_qa"].write_text(json.dumps(qa), encoding="utf-8")
    config = json.loads(paths["config"].read_text(encoding="utf-8"))
    config["acceptance"]["acceptance_qa_sha256"] = sha256_file(
        paths["acceptance_qa"]
    )
    if authority_name == "schema":
        config["acceptance"]["phi_response_schema_sha256"] = sha256_file(
            paths["schema"]
        )
    paths["config"].write_text(json.dumps(config), encoding="utf-8")


@pytest.mark.parametrize("authority_name", ("manifest", "ledger", "schema"))
def test_public_builder_rejects_transitive_authority_replaced_during_root_read(
    monkeypatch, count_authority, count_authority_repo, authority_name
):
    sample = _event_sample(count_authority_repo)

    def read_then_replace(*_args, **_kwargs):
        _replace_file(count_authority_repo[authority_name])
        return sample

    monkeypatch.setattr(azimuth_counts, "read_reco_root", read_then_replace)

    with pytest.raises(PolarizationContractError, match="SHA-256"):
        build_azimuth_counts(authority=count_authority)


@pytest.mark.parametrize("authority_name", ("manifest", "ledger", "schema"))
def test_public_builder_rejects_reanchored_transitive_change_by_fingerprint(
    monkeypatch, count_authority, count_authority_repo, authority_name
):
    sample = _event_sample(count_authority_repo)

    def read_then_reanchor(*_args, **_kwargs):
        _replace_file(count_authority_repo[authority_name])
        _reanchor_transitive_replacement(count_authority_repo, authority_name)
        return sample

    monkeypatch.setattr(azimuth_counts, "read_reco_root", read_then_reanchor)

    with pytest.raises(PolarizationContractError, match="changed while"):
        build_azimuth_counts(authority=count_authority)


def test_public_builder_uses_fresh_compton_values_not_mutable_caller_bundle(
    monkeypatch, count_authority, count_authority_repo
):
    curve = count_authority.compton["period-a"]
    curve.values.setflags(write=True)
    curve.values[:] = 0.1
    sample = _event_sample(count_authority_repo)
    monkeypatch.setattr(azimuth_counts, "read_reco_root", lambda *_args, **_kwargs: sample)

    table = build_azimuth_counts(authority=count_authority)

    assert all(
        row.beam_polarization == pytest.approx(0.8)
        for row in table.rows
        if row.source_period == "period-a"
    )


def test_writer_rejects_coforged_missing_authority_period(
    event_sample, count_authority, tmp_path
):
    table = _project(event_sample, count_authority)
    forged = replace(
        table,
        rows=tuple(row for row in table.rows if row.source_period != "period-b"),
        expected_universe=tuple(
            expected
            for expected in table.expected_universe
            if expected.source_period != "period-b"
        ),
    )
    assert forged.has_every_reco_cell()

    with pytest.raises(PolarizationContractError, match="expected universe"):
        write_azimuth_counts(
            forged,
            tmp_path / "azimuth_counts_v1.csv",
            authority=count_authority,
        )


def test_writer_rejects_coforged_shrunken_replica_ids(
    event_sample, count_authority, tmp_path
):
    table = _project(event_sample, count_authority)
    forged = replace(
        table,
        rows=tuple(row for row in table.rows if row.replica_id <= 1),
        expected_replica_ids=(0, 1),
    )
    assert forged.has_every_reco_cell()

    with pytest.raises(PolarizationContractError, match="replica IDs"):
        write_azimuth_counts(
            forged,
            tmp_path / "azimuth_counts_v1.csv",
            authority=count_authority,
        )


def test_writer_reloads_and_rejects_changed_authority_bytes(
    event_sample, count_authority, count_authority_repo, tmp_path
):
    table = _project(event_sample, count_authority)
    _replace_file(count_authority_repo["manifest"])

    with pytest.raises(PolarizationContractError, match="SHA-256"):
        write_azimuth_counts(
            table,
            tmp_path / "azimuth_counts_v1.csv",
            authority=count_authority,
        )


def test_count_authority_binds_n2_file_to_inventory_recorded_digest(
    count_authority_repo, monkeypatch
):
    original = azimuth_counts.load_reco_inventory

    def mutate_after_inventory_validation(*args, **kwargs):
        inventory = original(*args, **kwargs)
        count_authority_repo["reco"].write_bytes(b"substituted after inventory read")
        return inventory

    monkeypatch.setattr(
        azimuth_counts,
        "load_reco_inventory",
        mutate_after_inventory_validation,
    )

    with pytest.raises(PolarizationContractError, match="N2 reconstruction file SHA-256"):
        _load_count_authority(count_authority_repo)


def test_poisson_multiplier_has_frozen_versioned_vectors():
    assert event_bootstrap_weight(
        FILE_HASH,
        "reco_eta_pi0_chi2",
        0,
        0,
        algorithm="poisson1-sha256-v1",
        seed=1701,
    ) == 1
    expected = {(0, 1): 0, (0, 2): 1, (2, 7): 2, (4, 32): 4}
    for (entry, replica_id), wanted in expected.items():
        assert event_bootstrap_weight(
            FILE_HASH,
            "reco_eta_pi0_chi2",
            entry,
            replica_id,
            algorithm="poisson1-sha256-v1",
            seed=1701,
        ) == wanted


@pytest.mark.parametrize(
    "change",
    [
        {"algorithm": "other"},
        {"file_sha256": "A" * 64},
        {"tree": ""},
        {"entry": -1},
        {"replica_id": -1},
        {"seed": -1},
    ],
)
def test_poisson_multiplier_rejects_noncanonical_identity_or_config(change):
    arguments = dict(
        file_sha256=FILE_HASH,
        tree="reco_eta_pi0_chi2",
        entry=0,
        replica_id=1,
        algorithm="poisson1-sha256-v1",
        seed=1701,
    )
    arguments.update(change)
    with pytest.raises(PolarizationContractError):
        event_bootstrap_weight(**arguments)


def test_bootstrap_multiplier_is_shared_across_observables(
    event_sample, count_authority
):
    table = _project(event_sample, count_authority)
    totals = [
        table.sum_for(name, replica_id=7)
        for name in ("p_pi0", "p_eta", "eta_pi0")
    ]
    assert len(set(totals)) == 1
    assert [table.sum_for(name, replica_id=0) for name in PAIR_NAMES] == [4, 4, 4]


def test_shared_replicas_retain_nonzero_cross_observable_covariance(
    event_sample, count_authority
):
    table = _project(event_sample, count_authority)
    replica_totals = np.array(
        [
            [table.sum_for(name, replica_id=replica_id) for name in PAIR_NAMES]
            for replica_id in table.replica_ids[1:]
        ]
    )
    covariance = np.cov(replica_totals, rowvar=False)
    assert covariance[0, 1] > 0.0
    assert covariance[0, 2] > 0.0


def test_counts_publish_complete_nominal_and_replica_grids(
    event_sample, count_authority
):
    table = _project(event_sample, count_authority)
    assert table.replica_ids == tuple(
        range(count_authority.config.bootstrap.replicas + 1)
    )
    assert table.has_every_reco_cell()
    assert len(table.rows) == 3 * 2 * 2 * 33 * 2 * 12
    assert any(row.observed_count == 0 for row in table.rows)
    assert all(
        row.observed_count == 0
        for row in table.rows
        if row.source_period == "period-b"
    )


def test_counts_require_more_replicas_than_the_published_sigma_dimension(
    event_sample, count_authority_repo
):
    payload = json.loads(count_authority_repo["config"].read_text(encoding="utf-8"))
    payload["bootstrap"]["replicas"] = 6
    count_authority_repo["config"].write_text(json.dumps(payload), encoding="utf-8")
    authority = _load_count_authority(count_authority_repo)
    sample = _event_sample(count_authority_repo)

    with pytest.raises(PolarizationContractError, match="Sigma-vector dimension"):
        _project(sample, authority)


def test_expected_universe_rejects_wholly_missing_orientation(
    event_sample, count_authority
):
    table = _project(event_sample, count_authority)
    with pytest.raises(PolarizationContractError, match="complete reconstructed grid"):
        replace(
            table,
            rows=tuple(row for row in table.rows if row.orientation != "parallel"),
        )


def test_count_grid_rejects_noncontiguous_azimuth_partition(
    event_sample, count_authority, tmp_path
):
    table = _project(event_sample, count_authority)
    with pytest.raises(PolarizationContractError, match="complete reconstructed grid"):
        replace(
            table,
            rows=tuple(
                replace(row, reco_phi_high=0.7) if row.reco_phi_bin == 0 else row
                for row in table.rows
            ),
        )


def test_counts_serialize_exact_ordered_schema_and_hash(
    event_sample, count_authority, tmp_path
):
    table = _project(event_sample, count_authority)
    output = tmp_path / "azimuth_counts_v1.csv"

    digest = write_azimuth_counts(table, output, authority=count_authority)

    assert digest == sha256_file(output)
    with output.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
    assert AZIMUTH_COUNT_FIELDS == EXPECTED_COUNT_FIELDS
    assert tuple(reader.fieldnames or ()) == EXPECTED_COUNT_FIELDS
    assert len(rows) == len(table.rows)
    assert rows[0]["replica_id"] == "0"
    assert rows[0]["reco_mass_bin"] == "0"
    assert rows[0]["reco_phi_bin"] == "0"
    assert rows[0]["n2_reconstruction_sha256"] == (
        count_authority.n2_inventory_file.sha256
    )
    assert rows[0]["input_sha256"] == count_authority.flux_file.sha256


@pytest.mark.parametrize(
    "mutation,match",
    [
        ({"input_sha256": "bad"}, "SHA-256"),
        ({"reco_phi_high": 4.0}, "azimuth"),
        ({"beam_polarization": 1.1}, "polarization"),
    ],
)
def test_count_table_rejects_malformed_serialized_rows(
    event_sample, count_authority, mutation, match
):
    table = _project(event_sample, count_authority)
    rows = (replace(table.rows[0], **mutation), *table.rows[1:])
    with pytest.raises(PolarizationContractError, match=match):
        replace(table, rows=rows)


def test_sample_digest_must_be_present_in_authenticated_n2_inventory(
    event_sample, count_authority
):
    unrelated = replace(event_sample, file_sha256=np.array(["f" * 64] * 4))

    with pytest.raises(PolarizationContractError, match="N2 inventory"):
        _project(unrelated, count_authority)


def test_n4_or_unrelated_sample_cannot_claim_n2_provenance(
    event_sample, count_authority, count_authority_repo
):
    n4_path = count_authority_repo["root"] / "results/reco/n4.root"
    n4_path.parent.mkdir(parents=True)
    n4_path.write_bytes(b"synthetic N4 yields")
    n4_sample = replace(
        event_sample,
        file_sha256=np.array([sha256_file(n4_path)] * len(event_sample.file_sha256)),
    )

    with pytest.raises(PolarizationContractError, match="N2 inventory"):
        _project(n4_sample, count_authority)


def test_exposure_polarization_and_provenance_are_derived_from_authority(
    event_sample, count_authority
):
    table = _project(event_sample, count_authority)
    nominal = [row for row in table.rows if row.replica_id == 0]
    exposures = {
        (row.observable, row.source_period, row.orientation): row.exposure
        for row in nominal
    }
    for observable in PAIR_NAMES:
        assert exposures[observable, "period-a", "parallel"] == pytest.approx(150.0)
        assert exposures[observable, "period-a", "perpendicular"] == pytest.approx(140.0)
        assert exposures[observable, "period-b", "parallel"] == pytest.approx(30.0)
        assert exposures[observable, "period-b", "perpendicular"] == pytest.approx(40.0)
    polarization = {
        row.source_period: (
            row.beam_polarization,
            row.beam_polarization_variance,
        )
        for row in nominal
    }
    assert polarization["period-a"] == pytest.approx((0.8, 0.000078125))
    assert polarization["period-b"] == pytest.approx((0.7, 0.0003125))
    assert {row.gate0_handoff_sha256 for row in nominal} == {
        count_authority.gate0_handoff_file.sha256
    }
    assert {row.state_mapping_sha256 for row in nominal} == {
        count_authority.state_mapping_file.sha256
    }
    assert {row.config_sha256 for row in nominal} == {
        count_authority.config_file.sha256
    }


def test_caller_cannot_replace_authenticated_flux_with_altered_exposure(
    count_authority,
):
    altered_rows = tuple(
        replace(row, pol1_net=999999.0) for row in count_authority.flux_rows
    )
    with pytest.raises(PolarizationContractError, match="load_count_authority"):
        replace(count_authority, flux_rows=altered_rows)


def test_counts_require_both_orientations_for_each_physical_period(
    event_sample, count_authority_repo
):
    payload = json.loads(count_authority_repo["config"].read_text(encoding="utf-8"))
    payload["state_mapping"]["intervals"] = [
        interval
        for interval in payload["state_mapping"]["intervals"]
        if not (
            interval["source_period"] == "period-b"
            and interval["orientation"] == "perpendicular"
        )
    ]
    count_authority_repo["config"].write_text(json.dumps(payload), encoding="utf-8")
    authority = _load_count_authority(count_authority_repo)
    sample = _event_sample(count_authority_repo)

    with pytest.raises(PolarizationContractError, match="both orientations"):
        _project(sample, authority)


def test_counts_reject_duplicate_stable_event_identity(event_sample, count_authority):
    duplicate = replace(event_sample, tree_entry=np.array([0, 0, 2, 3]))
    with pytest.raises(PolarizationContractError, match="event identity"):
        _project(duplicate, count_authority)


def test_expected_universe_rejects_entire_missing_source_period(
    event_sample, count_authority
):
    table = _project(event_sample, count_authority)
    with pytest.raises(PolarizationContractError, match="complete reconstructed grid"):
        replace(
            table,
            rows=tuple(row for row in table.rows if row.source_period != "period-b"),
        )


def test_expected_universe_rejects_entire_missing_response_physical_key(
    event_sample, count_authority
):
    table = _project(event_sample, count_authority)
    missing = count_authority.response.keys[0]
    with pytest.raises(PolarizationContractError, match="complete reconstructed grid"):
        replace(
            table,
            rows=tuple(
                row
                for row in table.rows
                if not (
                    row.channel == missing.channel
                    and row.target == missing.target
                    and row.beam_group == missing.beam_group
                    and row.Egamma_low == missing.Egamma_low
                    and row.Egamma_high == missing.Egamma_high
                    and row.cos_theta_low == missing.cos_theta_low
                    and row.cos_theta_high == missing.cos_theta_high
                    and row.observable == missing.observable
                    and row.selection_id == missing.selection_id
                )
            ),
        )


def test_count_axes_are_exactly_the_authenticated_response_reco_axes(
    event_sample, count_authority
):
    table = _project(event_sample, count_authority)

    for expected in table.expected_universe:
        key = next(
            key
            for key in count_authority.response.keys
            if (
                key.channel,
                key.target,
                key.beam_group,
                key.Egamma_low,
                key.Egamma_high,
                key.cos_theta_low,
                key.cos_theta_high,
                key.observable,
                key.selection_id,
            )
            == expected.response_key
        )
        assert expected.reco_mass_edges == count_authority.response.mass_edges[key]
        assert expected.reco_phi_edges == count_authority.response.phi_edges[key]


def test_subdivided_cos_theta_response_is_rejected_fail_closed(
    event_sample, count_authority_repo
):
    with count_authority_repo["response"].open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
        fields = tuple(rows[0])
    for row in rows:
        row["cos_theta_low"] = "-0.5"
        row["cos_theta_high"] = "0.5"
    with count_authority_repo["response"].open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    _reanchor_response(count_authority_repo)
    authority = _load_count_authority(count_authority_repo)
    sample = _event_sample(count_authority_repo)

    with pytest.raises(PolarizationContractError, match="cos_theta"):
        _project(sample, authority)
