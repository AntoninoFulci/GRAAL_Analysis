from __future__ import annotations

import csv
from dataclasses import replace
import json

import numpy as np
import pytest

import azimuth_counts
from analysis_config import BootstrapConfig
from azimuth_counts import (
    AZIMUTH_COUNT_FIELDS,
    AzimuthCountTable,
    CountExposure,
    build_azimuth_counts,
    event_bootstrap_weight,
    write_azimuth_counts,
)
from compton import PolarizationCurve
from contracts import PolarizationContractError, sha256_file
from root_events import EventSample
from state_mapping import StateInterval


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


@pytest.fixture
def event_sample():
    proton = np.tile([0.10, 0.20, 0.00, 1.00], (4, 1))
    eta = np.tile([0.20, 0.10, 0.00, 0.70], (4, 1))
    pi0 = np.tile([0.30, 0.10, 0.00, 0.50], (4, 1))
    return EventSample(
        beam_energy=np.full(4, 1.15),
        run_number=np.array([100, 100, 101, 101]),
        state_code=np.array([1, 1, 2, 2]),
        xstrip=np.array([40.0, 41.0, 42.0, 43.0]),
        proton=proton,
        eta=eta,
        pi0=pi0,
        file_sha256=np.array([FILE_HASH] * 4),
        tree_entry=np.arange(4),
    )


@pytest.fixture
def authorities(response_fixture):
    config = replace(
        response_fixture.config,
        figure4_energy_edges_gev=(1.1, 1.2),
        figure4_phi_bins=4,
        bootstrap=BootstrapConfig(
            8, "poisson1-sha256-v1", 1701, 0.05, 0.5, 2.0
        ),
    )
    state_map = (
        StateInterval(100, 100, 1, "parallel", "period-a", "pol1_net"),
        StateInterval(101, 101, 2, "perpendicular", "period-a", "pol2_net"),
    )
    compton = {
        "period-a": PolarizationCurve(
            [1100.0, 1200.0], [0.8, 0.8], [[0.01, 0.0], [0.0, 0.01]]
        )
    }
    common = dict(
        fit_release_id="fit-test",
        bin_set_id="figure4-v1",
        channel="eta_pi0",
        target="P",
        beam_group="group-a",
        source_period="period-a",
        Egamma_low=1.1,
        Egamma_high=1.2,
        cos_theta_low=-1.0,
        cos_theta_high=1.0,
        selection_id="selection-v1",
        exposure=1000.0,
        beam_polarization=0.8,
        beam_polarization_variance=0.005,
        source_stage="N2",
        n2_inventory_path="results/reconstruction/inventory.json",
        gate0_handoff_sha256="a" * 64,
        n2_reconstruction_sha256="b" * 64,
        state_mapping_sha256="c" * 64,
        compton_source_sha256="d" * 64,
        config_sha256="e" * 64,
        input_sha256="f" * 64,
    )
    exposures = (
        CountExposure(orientation="parallel", **common),
        CountExposure(orientation="perpendicular", **common),
    )
    return {
        "config": config,
        "state_map": state_map,
        "exposures": exposures,
        "compton": compton,
        "mass_edges": {
            "p_pi0": np.array([1.0, 1.5, 2.0]),
            "p_eta": np.array([1.0, 1.7, 2.4]),
            "eta_pi0": np.array([0.5, 1.2, 2.0]),
        },
    }


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
    manifest.write_text("run_number,target\n101,P\n", encoding="utf-8")
    (bundle_dir / "run_manifest_observables.csv").write_text(
        "run_number,source_period,target,beam_type,group,classification_source,source_file\n"
        "101,period-a,P,UV,group-a,synthetic,reco.root\n",
        encoding="utf-8",
    )
    (bundle_dir / "run_quality.csv").write_text(
        "run_number,status\n101,good\n", encoding="utf-8"
    )
    (bundle_dir / "strip_energy_lookup.csv").write_text(
        "run_number,xstrip,energy_median_gev\n101,42,1.15\n", encoding="utf-8"
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
        for low in (1.1, 1.2, 1.3, 1.4):
            writer.writerow(
                {
                    "binning": "ajaka_sigma",
                    "run_number": 101,
                    "source_period": "period-a",
                    "target": "P",
                    "beam_type": "UV",
                    "group": "group-a",
                    "energy_low_gev": low,
                    "energy_high_gev": low + 0.1,
                    "pol1": 101.0,
                    "brem": 1.0,
                    "pol2": 101.0,
                    "pol1_net": 100.0,
                    "pol2_net": 100.0,
                    "total_net": 200.0,
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
    ledger_path.write_text("run_number,status\n101,complete\n", encoding="utf-8")
    inventory_path = reconstruction_dir / "inventory.json"
    inventory_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "producer_commit": "b" * 40,
                "gate0_handoff_sha256": sha256_file(gate0_path),
                "complete_run_coverage": True,
                "tree": "reco_eta_pi0_chi2",
                "vectors": "kinematic_fit",
                "run_numbers": [101],
                "observed_event_run_numbers": [101],
                "zero_selected_event_run_numbers": [],
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
    state_source.write_text("run,state\n101,1\n", encoding="utf-8")
    compton_source = authority_dir / "compton.csv"
    compton_source.write_text(
        "energy_mev,polarization\n1100,0.8\n1500,0.8\n", encoding="utf-8"
    )

    release_dir = (
        repository_root
        / "results/physics/normalization/handoffs/n3-test"
    )
    release_dir.mkdir(parents=True)
    acceptance_path = release_dir / "acceptance_v1.csv"
    acceptance_path.write_text(
        "channel,acceptance\neta_pi0,0.5\n", encoding="utf-8"
    )
    response_path = release_dir / "acceptance_phi_response_v1.csv"
    response_path.write_bytes(response_fixture.path.read_bytes())
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
                    "N3-MASS-PHI-RESPONSE-V1-2026-09-13"
                ),
                "gate0_handoff_sha256": sha256_file(gate0_path),
                "n2_reconstruction_sha256": sha256_file(inventory_path),
                "input_sha256": "b" * 64,
                "config_sha256": "c" * 64,
                "count_checks": {"valid": True},
                "matrix_checks": {"valid": True},
                "weighted_covariance_checks": {"valid": True},
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
                        "N3-MASS-PHI-RESPONSE-V1-2026-09-13"
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
                        }
                    ],
                },
                "angle": {
                    "observable": "reaction_plane_phi",
                    "range_radians": [0.0, np.pi],
                    "period_radians": np.pi,
                    "degenerate_plane_policy": "invalid",
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
        "flux": flux_path,
        "inventory": inventory_path,
        "reco": reco_path,
        "state": state_source,
        "compton": compton_source,
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


def test_count_authority_loader_retains_only_actual_authenticated_bytes(
    count_authority_repo,
):
    authority = _load_count_authority(count_authority_repo)

    assert authority.config_file.sha256 == sha256_file(count_authority_repo["config"])
    assert authority.gate0_handoff_file.sha256 == sha256_file(
        count_authority_repo["gate0"]
    )
    assert authority.flux_file.sha256 == sha256_file(count_authority_repo["flux"])
    assert authority.n2_inventory_file.sha256 == sha256_file(
        count_authority_repo["inventory"]
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
        *authority.gate0_bundle_files,
        authority.n2_inventory_file,
        *authority.n2_files,
        authority.state_mapping_file,
        *[item.file for item in authority.compton_files],
        *authority.acceptance_files,
    )
    assert all(record.sha256 == sha256_file(record.path) for record in retained)
    assert authority.response.source_sha256 == sha256_file(
        count_authority_repo["response"]
    )
    assert len(authority.flux_rows) == 4


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


def test_bootstrap_multiplier_is_shared_across_observables(event_sample, authorities):
    table = build_azimuth_counts(event_sample, **authorities)
    totals = [
        table.sum_for(name, replica_id=7)
        for name in ("p_pi0", "p_eta", "eta_pi0")
    ]
    assert len(set(totals)) == 1
    assert [table.sum_for(name, replica_id=0) for name in authorities["mass_edges"]] == [4, 4, 4]


def test_shared_replicas_retain_nonzero_cross_observable_covariance(event_sample, authorities):
    table = build_azimuth_counts(event_sample, **authorities)
    replica_totals = np.array(
        [
            [table.sum_for(name, replica_id=replica_id) for name in authorities["mass_edges"]]
            for replica_id in table.replica_ids[1:]
        ]
    )
    covariance = np.cov(replica_totals, rowvar=False)
    assert covariance[0, 1] > 0.0
    assert covariance[0, 2] > 0.0


def test_counts_publish_complete_nominal_and_replica_grids(event_sample, authorities):
    table = build_azimuth_counts(event_sample, **authorities)
    assert table.replica_ids == tuple(
        range(authorities["config"].bootstrap.replicas + 1)
    )
    assert table.has_every_reco_cell()
    assert len(table.rows) == 2 * 9 * 3 * 2 * 4
    assert any(row.observed_count == 0 for row in table.rows)


def test_counts_require_more_replicas_than_the_published_sigma_dimension(
    event_sample, authorities
):
    undersized = replace(
        authorities["config"],
        bootstrap=BootstrapConfig(6, "poisson1-sha256-v1", 1701, 0.05, 0.5, 2.0),
    )

    with pytest.raises(PolarizationContractError, match="Sigma-vector dimension"):
        build_azimuth_counts(event_sample, **{**authorities, "config": undersized})


def test_complete_grid_check_detects_wholly_missing_orientation(event_sample, authorities):
    table = build_azimuth_counts(event_sample, **authorities)
    incomplete = AzimuthCountTable(
        tuple(row for row in table.rows if row.orientation != "parallel")
    )
    assert not incomplete.has_every_reco_cell()


def test_count_grid_rejects_noncontiguous_azimuth_partition(
    event_sample, authorities, tmp_path
):
    table = build_azimuth_counts(event_sample, **authorities)
    malformed = AzimuthCountTable(
        tuple(
            replace(row, reco_phi_high=0.7) if row.reco_phi_bin == 0 else row
            for row in table.rows
        )
    )

    assert not malformed.has_every_reco_cell()
    with pytest.raises(PolarizationContractError, match="incomplete"):
        write_azimuth_counts(malformed, tmp_path / "azimuth_counts_v1.csv")


def test_counts_serialize_exact_ordered_schema_and_hash(event_sample, authorities, tmp_path):
    table = build_azimuth_counts(event_sample, **authorities)
    output = tmp_path / "azimuth_counts_v1.csv"

    digest = write_azimuth_counts(table, output)

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
    assert rows[0]["n2_reconstruction_sha256"] == "b" * 64
    assert rows[0]["input_sha256"] == "f" * 64


@pytest.mark.parametrize(
    "mutation,match",
    [
        ({"input_sha256": "bad"}, "SHA-256"),
        ({"reco_phi_high": 4.0}, "azimuth"),
        ({"beam_polarization": 1.1}, "polarization"),
    ],
)
def test_count_table_rejects_malformed_serialized_rows(
    event_sample, authorities, mutation, match
):
    table = build_azimuth_counts(event_sample, **authorities)
    rows = (replace(table.rows[0], **mutation), *table.rows[1:])
    with pytest.raises(PolarizationContractError, match=match):
        AzimuthCountTable(rows)


@pytest.mark.parametrize(
    "mutation,match",
    [
        ({"source_stage": "N4"}, "N2"),
        ({"n2_reconstruction_sha256": "not-a-hash"}, "SHA-256"),
        ({"beam_polarization": 0.7}, "Compton"),
        ({"beam_polarization_variance": 0.004}, "Compton"),
    ],
)
def test_counts_reject_non_n2_or_unbound_authority(
    event_sample, authorities, mutation, match
):
    exposures = tuple(replace(item, **mutation) for item in authorities["exposures"])
    with pytest.raises(PolarizationContractError, match=match):
        build_azimuth_counts(event_sample, **{**authorities, "exposures": exposures})


def test_counts_require_both_orientations_for_each_physical_period(event_sample, authorities):
    with pytest.raises(PolarizationContractError, match="both orientations"):
        build_azimuth_counts(
            event_sample,
            **{**authorities, "exposures": authorities["exposures"][:1]},
        )


def test_counts_reject_duplicate_stable_event_identity(event_sample, authorities):
    duplicate = replace(event_sample, tree_entry=np.array([0, 0, 2, 3]))
    with pytest.raises(PolarizationContractError, match="event identity"):
        build_azimuth_counts(duplicate, **authorities)
