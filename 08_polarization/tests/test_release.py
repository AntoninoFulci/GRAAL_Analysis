from __future__ import annotations

import csv
import hashlib
import json
import shutil

import numpy as np
import pytest

from contracts import PolarizationContractError
from release import (
    validate_aggregation_mapping,
    validate_publication_mapping,
    validate_sigma_release,
)
from validate_sigma_release import main as release_main
from validate_publication_binning import main as publication_main


CSV_FIELDS = [
    "analysis_version", "bin_key", "channel", "target", "beam_group",
    "Egamma_low", "Egamma_high", "cos_theta_low", "cos_theta_high",
    "observable", "selection_id", "mass_low_gev", "mass_high_gev", "sigma",
    "stat_uncertainty", "systematic_components_json", "validity_mask",
    "fit_id", "input_sha256", "config_sha256", "event_count",
    "fit_deviance", "fit_ndof",
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_gate0(repo):
    manifest = repo / "config/run_manifest.csv"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("run_number,target\n101,proton\n")
    bundle_dir = repo / "results/observable_runs"
    bundle_dir.mkdir(parents=True)
    names = [
        "run_manifest_observables.csv", "run_quality.csv",
        "strip_energy_lookup.csv", "flux_by_run_energy.csv",
        "flux_by_group_energy.csv", "observable_run_qa.json",
    ]
    for name in names:
        target = bundle_dir / name
        if name == "run_manifest_observables.csv":
            target.write_text("run_number,target\n101,P\n")
        else:
            target.write_text('{"valid":true}' if name.endswith(".json") else "x\n1\n")
    handoff = {
        "schema_version": 1,
        "producer_commit": "a" * 40,
        "manifest_path": "config/run_manifest.csv",
        "manifest_sha256": sha(manifest),
        "files": [
            {
                "path": f"results/observable_runs/{name}",
                "sha256": sha(bundle_dir / name),
            }
            for name in names
        ],
        "observable_run_qa_path": "results/observable_runs/observable_run_qa.json",
        "observable_run_qa_sha256": sha(bundle_dir / "observable_run_qa.json"),
        "observable_run_qa_valid": True,
        "energy_binning_mev": [1100.0, 1200.0],
        "created_at_utc": "2026-09-10T12:00:00Z",
    }
    path = bundle_dir / "HANDOFF.json"
    path.write_text(json.dumps(handoff))
    return path


def file_record(path, repo):
    return {"path": str(path.relative_to(repo)), "sha256": sha(path)}


def source_record(path, repo):
    return file_record(path, repo) | {
        "authority": "synthetic-test-authority",
        "approval_id": "TEST-ONLY",
        "reviewers": ["test-owner-1", "test-owner-2"],
    }


def combined_input_sha256(inputs):
    payload = []
    for name in (
        "gate0_handoff", "acceptance_csv", "acceptance_qa",
        "reconstruction_inventory",
    ):
        payload.append([name, inputs[name]["sha256"]])
    for name in ("state_mapping_sources", "compton_sources"):
        payload.extend([name, record["sha256"]] for record in inputs[name])
    encoded = json.dumps(payload, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def write_valid_release(path):
    repo = path.parent
    path = repo / "results/physics/polarization"
    thresholds = {
        "status": "approved",
        "approval_id": "QA-4",
        "reviewers": ["owner-1", "owner-2"],
        "minimum_events_per_bin": 1000,
        "maximum_deviance_per_ndof": 1.2,
        "closure_bias_absolute_max": 0.02,
        "closure_pull_mean_absolute_max": 0.2,
        "closure_pull_width_tolerance": 0.2,
        "minimum_systematic_sources": 1,
        "systematic_combination_policy": "independent_sources_quadrature",
    }
    gate0 = write_gate0(repo)
    acceptance_dir = repo / "results/physics/normalization"
    acceptance_dir.mkdir(parents=True)
    acceptance_csv = acceptance_dir / "acceptance_v1.csv"
    acceptance_csv.write_text(
        "analysis_version,channel,target,beam_group,Egamma_low,Egamma_high,"
        "cos_theta_low,cos_theta_high,observable,selection_id,n_generated,"
        "n_thrown_in_bin,n_reconstructed_selected,acceptance,"
        "acceptance_stat_uncertainty,validity_mask,input_sha256,config_sha256\n"
        + "polarization-v1,eta_pi0,P,P_UV,1.1,1.2,-1.0,1.0,p_pi0,selection-v1,"
        + f"10000,5000,2500,0.5,0.02,valid,{'1' * 64},{'2' * 64}\n"
        + "polarization-v1,eta_pi0,P,P_UV,1.1,1.2,-1.0,1.0,p_eta,selection-v1,"
        + f"10000,0,0,,,invalid,{'1' * 64},{'2' * 64}\n"
    )
    acceptance_qa = acceptance_dir / "acceptance_qa.json"
    acceptance_qa.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "producer_commit": "b" * 40,
                "valid": True,
                "acceptance_csv_sha256": sha(acceptance_csv),
                "gate0_handoff_sha256": sha(gate0),
                "input_sha256": "1" * 64,
                "config_sha256": "2" * 64,
                "count_checks": {"valid": True},
                "closure": {"valid": True},
            }
        )
    )
    authority = repo / "data/authorities"
    authority.mkdir(parents=True)
    state_source = authority / "state.csv"
    state_source.write_text("run,state\n101,H\n")
    compton_source = authority / "compton.csv"
    compton_source.write_text("energy,polarization\n1150,0.6\n")
    config = repo / "config/physics/polarization_v1.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "analysis_version": "polarization-v1",
                "state_mapping": {
                    "status": "ready",
                    "source": source_record(state_source, repo),
                    "intervals": [
                        {
                            "run_start": 101, "run_end": 101, "state_code": 2,
                            "orientation": "parallel", "source_period": "test",
                            "flux_component": "pol1_net",
                        }
                    ],
                },
                "compton_polarization": {
                    "status": "ready",
                    "periods": [
                        {
                            "source_period": "test",
                            "source": source_record(compton_source, repo),
                            "energies_mev": [1100.0, 1200.0],
                            "polarization": [0.6, 0.6],
                            "covariance": [[0.0001, 0.0], [0.0, 0.0001]],
                        }
                    ],
                },
                "sign_convention": {
                    "status": "approved",
                    "orientation_signs": {"parallel": 1, "perpendicular": -1},
                },
                "figure4_comparison": {
                    "energy_edges_gev": [1.1, 1.2, 1.3, 1.4, 1.5],
                    "mass_bins": 10, "phi_bins": 12, "target": "P",
                    "tree": "reco_eta_pi0_chi2", "vectors": "kinematic_fit",
                },
                "release_qa_thresholds": thresholds,
            }
        )
    )
    reconstruction_dir = repo / "results/reconstruction"
    reconstruction_dir.mkdir(parents=True)
    reconstruction_root = reconstruction_dir / "reco.root"
    reconstruction_root.write_bytes(b"synthetic-root-placeholder")
    ledger = reconstruction_dir / "processed_runs.csv"
    ledger.write_text("run_number,status\n101,complete\n")
    reconstruction = reconstruction_dir / "inventory.json"
    reconstruction.write_text(
        json.dumps(
            {
                "schema_version": 1, "producer_commit": "c" * 40,
                "gate0_handoff_sha256": sha(gate0),
                "complete_run_coverage": True,
                "tree": "reco_eta_pi0_chi2", "vectors": "kinematic_fit",
                "run_numbers": [101], "observed_event_run_numbers": [101],
                "zero_selected_event_run_numbers": [],
                "processed_run_ledger": file_record(ledger, repo),
                "files": [file_record(reconstruction_root, repo)],
            }
        )
    )
    inputs = {
        "config": file_record(config, repo),
        "gate0_handoff": file_record(gate0, repo),
        "acceptance_csv": file_record(acceptance_csv, repo),
        "acceptance_qa": file_record(acceptance_qa, repo),
        "reconstruction_inventory": file_record(reconstruction, repo),
        "state_mapping_sources": [file_record(state_source, repo)],
        "compton_sources": [file_record(compton_source, repo)],
    }
    input_digest = combined_input_sha256(inputs)
    path.mkdir(parents=True)
    csv_path = path / "sigma_v1.csv"
    rows = [
        [
            "polarization-v1", "e0:p_pi0:m0", "eta_pi0", "P", "P_UV",
            1.1, 1.2, -1.0, 1.0, "p_pi0", "selection-v1",
            1.07, 1.12, -0.2, 0.08, '{"beam_polarization":0.03}',
            "valid", "fit-000", input_digest, sha(config), 1800, 9.0, 11,
        ],
        [
            "polarization-v1", "e0:p_pi0:m1", "eta_pi0", "P", "P_UV",
            1.1, 1.2, -1.0, 1.0, "p_pi0", "selection-v1",
            1.12, 1.17, 0.3, 0.10, '{"beam_polarization":0.04}',
            "valid", "fit-001", input_digest, sha(config), 1500, 7.0, 11,
        ],
    ]
    with csv_path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(CSV_FIELDS)
        writer.writerows(rows)
    stat = np.diag([0.08**2, 0.10**2])
    systematic = np.array([[0.0009, 0.0002], [0.0002, 0.0016]])
    npz_path = path / "sigma_covariance.npz"
    np.savez(
        npz_path,
        bin_keys=np.array([row[1] for row in rows]),
        stat_covariance=stat,
        systematic_covariance=systematic,
        covariance=stat + systematic,
        schema_version=np.array(1),
    )
    qa = {
        "schema_version": 1,
        "analysis_version": "polarization-v1",
        "producer_commit": "a" * 40,
        "valid": True,
        "files": {
            "sigma_v1.csv": sha(csv_path),
            "sigma_covariance.npz": sha(npz_path),
        },
        "fit_qa": {"valid": True},
        "closure": {
            "valid": True, "sign_check_passed": True,
            "bias": 0.01, "pull_mean": 0.05, "pull_width": 1.04,
        },
        "systematic_sources": [
            {
                "name": "beam_polarization",
                "path": inputs["config"]["path"],
                "sha256": inputs["config"]["sha256"],
            }
        ],
        "inputs": inputs,
        "input_sha256": input_digest,
        "config_sha256": sha(config),
        "gate0_handoff_sha256": sha(gate0),
        "acceptance_qa_sha256": sha(acceptance_qa),
        "qa_thresholds": thresholds,
    }
    (path / "polarization_qa.json").write_text(json.dumps(qa))
    return path


def repo_of(release):
    return release.parents[2]


def rewrite_config_binding(release, mutate, *, sync_qa_policy):
    config = repo_of(release) / "config/physics/polarization_v1.json"
    payload = json.loads(config.read_text())
    mutate(payload)
    config.write_text(json.dumps(payload))
    config_hash = sha(config)
    qa_path = release / "polarization_qa.json"
    qa = json.loads(qa_path.read_text())
    qa["inputs"]["config"]["sha256"] = config_hash
    qa["config_sha256"] = config_hash
    qa["systematic_sources"][0]["sha256"] = config_hash
    if sync_qa_policy:
        qa["qa_thresholds"] = payload["release_qa_thresholds"]
    rows = list(csv.reader((release / "sigma_v1.csv").open()))
    config_index = rows[0].index("config_sha256")
    for row in rows[1:]:
        row[config_index] = config_hash
    with (release / "sigma_v1.csv").open("w", newline="") as handle:
        csv.writer(handle).writerows(rows)
    qa["files"]["sigma_v1.csv"] = sha(release / "sigma_v1.csv")
    qa_path.write_text(json.dumps(qa))


def rewrite_input_binding(release, mutate):
    qa_path = release / "polarization_qa.json"
    qa = json.loads(qa_path.read_text())
    mutate(qa)
    qa["input_sha256"] = combined_input_sha256(qa["inputs"])
    rows = list(csv.reader((release / "sigma_v1.csv").open()))
    input_index = rows[0].index("input_sha256")
    for row in rows[1:]:
        row[input_index] = qa["input_sha256"]
    with (release / "sigma_v1.csv").open("w", newline="") as handle:
        csv.writer(handle).writerows(rows)
    qa["files"]["sigma_v1.csv"] = sha(release / "sigma_v1.csv")
    qa_path.write_text(json.dumps(qa))


def test_release_accepts_cross_hashed_csv_npz_and_valid_qa(tmp_path):
    release = write_valid_release(tmp_path / "release")
    summary = validate_sigma_release(release, repo_of(release))
    assert summary.bin_keys == ("e0:p_pi0:m0", "e0:p_pi0:m1")
    assert summary.total_covariance.shape == (2, 2)


def test_release_rejects_noncanonical_or_extra_bundle_files(tmp_path):
    release = write_valid_release(tmp_path / "release")
    staged = tmp_path / "staged"
    shutil.copytree(release, staged)
    with pytest.raises(PolarizationContractError, match="canonical"):
        validate_sigma_release(staged, repo_of(release))
    (release / "unexpected.txt").write_text("not part of S6")
    with pytest.raises(PolarizationContractError, match="exactly three"):
        validate_sigma_release(release, repo_of(release))


@pytest.mark.parametrize("mutation", ["hash", "order", "sum", "indefinite", "qa"])
def test_release_rejects_hash_order_covariance_and_qa_failures(tmp_path, mutation):
    release = write_valid_release(tmp_path / "release")
    qa_path = release / "polarization_qa.json"
    qa = json.loads(qa_path.read_text())
    npz_path = release / "sigma_covariance.npz"
    arrays = dict(np.load(npz_path))
    if mutation == "hash":
        qa["files"]["sigma_v1.csv"] = "0" * 64
    elif mutation == "order":
        arrays["bin_keys"] = arrays["bin_keys"][::-1]
        np.savez(npz_path, **arrays)
        qa["files"]["sigma_covariance.npz"] = sha(npz_path)
    elif mutation == "sum":
        arrays["covariance"] = arrays["covariance"] + np.eye(2)
        np.savez(npz_path, **arrays)
        qa["files"]["sigma_covariance.npz"] = sha(npz_path)
    elif mutation == "indefinite":
        arrays["systematic_covariance"] = np.array(
            [[1.0, 2.0], [2.0, 1.0]]
        )
        arrays["covariance"] = (
            arrays["stat_covariance"]
            + arrays["systematic_covariance"]
        )
        np.savez(npz_path, **arrays)
        qa["files"]["sigma_covariance.npz"] = sha(npz_path)
    else:
        qa["closure"]["sign_check_passed"] = False
    qa_path.write_text(json.dumps(qa))
    with pytest.raises(PolarizationContractError):
        validate_sigma_release(release, repo_of(release))


def test_release_preserves_precise_covariance_validation_error(tmp_path):
    release = write_valid_release(tmp_path / "release")
    npz_path = release / "sigma_covariance.npz"
    arrays = dict(np.load(npz_path))
    arrays["systematic_covariance"] = np.array([[1.0, 2.0], [2.0, 1.0]])
    arrays["covariance"] = arrays["stat_covariance"] + arrays["systematic_covariance"]
    np.savez(npz_path, **arrays)
    qa_path = release / "polarization_qa.json"
    qa = json.loads(qa_path.read_text())
    qa["files"]["sigma_covariance.npz"] = sha(npz_path)
    qa_path.write_text(json.dumps(qa))
    with pytest.raises(PolarizationContractError, match="positive semidefinite"):
        validate_sigma_release(release, repo_of(release))


def test_publication_aggregation_checks_w_c_wt(tmp_path):
    release = write_valid_release(tmp_path / "release")
    summary = validate_sigma_release(release, repo_of(release))
    mapping = {
        "schema_version": 1,
        "paper": "P1",
        "source_bin_keys": list(summary.bin_keys),
        "aggregate_bin_keys": ["p1:a0"],
        "weights": [[0.5, 0.5]],
        "aggregate_covariance": [[0.004825]],
    }
    path = tmp_path / "p1_binning.json"
    path.write_text(json.dumps(mapping))
    validate_aggregation_mapping(mapping, "P1", summary)

    mapping["aggregate_covariance"] = [[0.99]]
    path.write_text(json.dumps(mapping))
    with pytest.raises(PolarizationContractError, match="covariance"):
        validate_aggregation_mapping(mapping, "P1", summary)


def test_publication_mapping_stays_blocked_until_shared_p0_interface_exists(tmp_path):
    release = write_valid_release(tmp_path / "release")
    summary = validate_sigma_release(release, repo_of(release))
    path = tmp_path / "p2_binning.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "paper": "P2",
                "source_bin_keys": list(summary.bin_keys),
                "aggregate_bin_keys": ["p2:a0"],
                "weights": [[0.5, 0.5]],
                "aggregate_covariance": [[0.004825]],
            }
        )
    )
    with pytest.raises(PolarizationContractError, match="shared P0"):
        validate_publication_mapping(path, "P2", summary)


def test_publication_cli_reads_mapping_outside_exact_s6_bundle(tmp_path, capsys):
    release = write_valid_release(tmp_path / "release")
    mapping_dir = tmp_path / "publication_mappings"
    mapping_dir.mkdir()
    (mapping_dir / "p1_binning.json").write_text(
        json.dumps(
            {
                "schema_version": 1, "paper": "P1",
                "source_bin_keys": ["e0:p_pi0:m0", "e0:p_pi0:m1"],
                "aggregate_bin_keys": ["p1:a0"],
                "weights": [[0.5, 0.5]],
                "aggregate_covariance": [[0.004825]],
            }
        )
    )
    assert publication_main(
        [
            "--results", str(release), "--repository-root", str(repo_of(release)),
            "--mapping-dir", str(mapping_dir), "--papers", "P1",
        ]
    ) == 1
    assert "shared P0" in capsys.readouterr().err


def test_release_cli_requires_explicit_full_checks(tmp_path, capsys):
    release = write_valid_release(tmp_path / "release")
    assert release_main(
        ["--results", str(release), "--repository-root", str(repo_of(release))]
    ) == 2
    assert "required" in capsys.readouterr().err
    assert release_main(
        [
                "--results", str(release),
                "--repository-root", str(repo_of(release)),
                "--check-covariance", "--check-qa",
        ]
    ) == 0


def test_release_rejects_unapproved_qa_thresholds(tmp_path):
    release = write_valid_release(tmp_path / "release")
    qa_path = release / "polarization_qa.json"
    qa = json.loads(qa_path.read_text())
    qa["qa_thresholds"]["status"] = "pending_owner_approval"
    qa_path.write_text(json.dumps(qa))
    with pytest.raises(PolarizationContractError, match="threshold policy"):
        validate_sigma_release(release, repo_of(release))


def test_release_rejects_qa_policy_not_approved_in_canonical_config(tmp_path):
    release = write_valid_release(tmp_path / "release")
    rewrite_config_binding(
        release,
        lambda payload: payload["release_qa_thresholds"].update(
            status="pending_owner_approval"
        ),
        sync_qa_policy=False,
    )
    with pytest.raises(PolarizationContractError, match="canonical config"):
        validate_sigma_release(release, repo_of(release))


def test_release_applies_approved_numeric_qa_thresholds(tmp_path):
    release = write_valid_release(tmp_path / "release")
    rewrite_config_binding(
        release,
        lambda payload: payload["release_qa_thresholds"].update(
            minimum_events_per_bin=2000
        ),
        sync_qa_policy=True,
    )
    with pytest.raises(PolarizationContractError, match="event"):
        validate_sigma_release(release, repo_of(release))


def test_release_rejects_missing_acceptance_for_sigma_bin(tmp_path):
    release = write_valid_release(tmp_path / "release")
    acceptance_csv = repo_of(release) / "results/physics/normalization/acceptance_v1.csv"
    lines = acceptance_csv.read_text().splitlines()
    acceptance_csv.write_text("\n".join(lines[:1]) + "\n")
    acceptance_qa_path = acceptance_csv.with_name("acceptance_qa.json")
    acceptance_qa = json.loads(acceptance_qa_path.read_text())
    acceptance_qa["acceptance_csv_sha256"] = sha(acceptance_csv)
    acceptance_qa_path.write_text(json.dumps(acceptance_qa))
    qa_path = release / "polarization_qa.json"
    qa = json.loads(qa_path.read_text())
    qa["inputs"]["acceptance_csv"]["sha256"] = sha(acceptance_csv)
    qa["inputs"]["acceptance_qa"]["sha256"] = sha(acceptance_qa_path)
    qa["acceptance_qa_sha256"] = sha(acceptance_qa_path)
    qa["input_sha256"] = combined_input_sha256(qa["inputs"])
    qa_path.write_text(json.dumps(qa))
    rows = list(csv.reader((release / "sigma_v1.csv").open()))
    input_index = rows[0].index("input_sha256")
    for row in rows[1:]:
        row[input_index] = qa["input_sha256"]
    with (release / "sigma_v1.csv").open("w", newline="") as handle:
        csv.writer(handle).writerows(rows)
    qa["files"]["sigma_v1.csv"] = sha(release / "sigma_v1.csv")
    qa_path.write_text(json.dumps(qa))
    with pytest.raises(PolarizationContractError, match="acceptance"):
        validate_sigma_release(release, repo_of(release))


def test_release_rejects_acceptance_row_hashes_not_bound_to_acceptance_qa(tmp_path):
    release = write_valid_release(tmp_path / "release")
    repo = repo_of(release)
    acceptance_csv = repo / "results/physics/normalization/acceptance_v1.csv"
    rows = list(csv.reader(acceptance_csv.open()))
    input_index = rows[0].index("input_sha256")
    for row in rows[1:]:
        row[input_index] = "3" * 64
    with acceptance_csv.open("w", newline="") as handle:
        csv.writer(handle).writerows(rows)
    acceptance_qa_path = acceptance_csv.with_name("acceptance_qa.json")
    acceptance_qa = json.loads(acceptance_qa_path.read_text())
    acceptance_qa["acceptance_csv_sha256"] = sha(acceptance_csv)
    acceptance_qa_path.write_text(json.dumps(acceptance_qa))

    def refresh_outer(qa):
        qa["inputs"]["acceptance_csv"]["sha256"] = sha(acceptance_csv)
        qa["inputs"]["acceptance_qa"]["sha256"] = sha(acceptance_qa_path)
        qa["acceptance_qa_sha256"] = sha(acceptance_qa_path)

    rewrite_input_binding(release, refresh_outer)
    with pytest.raises(PolarizationContractError, match="acceptance.*QA"):
        validate_sigma_release(release, repo)


def test_release_rejects_state_source_substituted_outside_canonical_config(tmp_path):
    release = write_valid_release(tmp_path / "release")

    def substitute(qa):
        qa["inputs"]["state_mapping_sources"] = qa["inputs"]["compton_sources"]

    rewrite_input_binding(release, substitute)
    with pytest.raises(PolarizationContractError, match="state.*config"):
        validate_sigma_release(release, repo_of(release))


def test_release_rejects_invalid_reconstruction_inventory_with_fresh_hash(tmp_path):
    release = write_valid_release(tmp_path / "release")
    inventory = repo_of(release) / "results/reconstruction/inventory.json"
    payload = json.loads(inventory.read_text())
    payload["complete_run_coverage"] = False
    inventory.write_text(json.dumps(payload))

    def refresh_inventory(qa):
        qa["inputs"]["reconstruction_inventory"]["sha256"] = sha(inventory)

    rewrite_input_binding(release, refresh_inventory)
    with pytest.raises(PolarizationContractError, match="complete_run_coverage"):
        validate_sigma_release(release, repo_of(release))
