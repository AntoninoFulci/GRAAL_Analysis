from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pytest

from contracts import PolarizationContractError, sha256_file
from release import CSV_FIELDS, validate_sigma_release


def _load_fit_test_module():
    path = Path(__file__).with_name("test_fit_evidence.py")
    spec = importlib.util.spec_from_file_location("release_fit_fixture", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _record(path: Path, root: Path) -> dict[str, str]:
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": sha256_file(path),
    }


def _input_digest(inputs: dict[str, object]) -> str:
    records = []
    for name in (
        "gate0_handoff", "acceptance_csv", "acceptance_phi_response_csv",
        "acceptance_qa", "reconstruction_inventory",
    ):
        records.append((name, inputs[name]["sha256"]))
    for name in ("state_mapping_sources", "compton_sources"):
        records.extend((name, record["sha256"]) for record in inputs[name])
    return hashlib.sha256(
        json.dumps(records, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@pytest.fixture
def replay_release(tmp_path, response_fixture, monkeypatch):
    module = _load_fit_test_module()
    paths, authority, s4_dir = module.evidence_problem.__wrapped__(
        response_fixture, monkeypatch
    )
    evidence = module.validate_fit_evidence(
        s4_dir, paths["root"], config=authority.config
    )
    root = paths["root"]
    acceptance_csv = paths["acceptance_qa"].with_name("acceptance_v1.csv")
    inputs = {
        "config": _record(paths["config"], root),
        "gate0_handoff": _record(paths["gate0"], root),
        "acceptance_csv": _record(acceptance_csv, root),
        "acceptance_phi_response_csv": _record(paths["response"], root),
        "acceptance_qa": _record(paths["acceptance_qa"], root),
        "reconstruction_inventory": _record(paths["inventory"], root),
        "state_mapping_sources": [_record(paths["state"], root)],
        "compton_sources": [
            _record(paths["compton"], root),
            _record(paths["compton_b"], root),
        ],
    }
    input_sha = _input_digest(inputs)
    config_sha = sha256_file(paths["config"])
    with (s4_dir / "sigma_fit_v1.csv").open(newline="", encoding="utf-8") as stream:
        fit_rows = list(csv.DictReader(stream))
    release = root / "results/physics/polarization"
    release.mkdir(parents=True)
    csv_path = release / "sigma_v1.csv"
    rows = []
    physical_bins = tuple(
        (response_key, mass_index)
        for response_key in authority.response.keys
        for mass_index in range(len(authority.response.mass_edges[response_key]) - 1)
    )
    for index, (key, (response_key, mass_index)) in enumerate(
        zip(evidence.nominal_fit.bin_keys, physical_bins, strict=True)
    ):
        edges = authority.response.mass_edges[response_key]
        fit_row = fit_rows[index]
        rows.append(
            [
                authority.config.analysis_version, key, response_key.channel,
                response_key.target, response_key.beam_group,
                response_key.Egamma_low, response_key.Egamma_high,
                response_key.cos_theta_low, response_key.cos_theta_high,
                response_key.observable, response_key.selection_id,
                edges[mass_index], edges[mass_index + 1],
                evidence.nominal_fit.sigma[index],
                np.sqrt(evidence.statistical_covariance[index, index]),
                json.dumps({"acceptance_response_statistics": 0.0}, separators=(",", ":")),
                "valid", f"fit-{index:03d}", input_sha, config_sha,
                int(fit_row["event_count"]), float(fit_row["fit_deviance"]),
                int(fit_row["fit_ndof"]),
            ]
        )
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(CSV_FIELDS)
        writer.writerows(rows)
    response_covariance = evidence.response_propagation.covariance
    npz_path = release / "sigma_covariance.npz"
    np.savez(
        npz_path,
        bin_keys=np.asarray(evidence.nominal_fit.bin_keys),
        stat_covariance=evidence.statistical_covariance,
        systematic_covariance=response_covariance,
        covariance=evidence.statistical_covariance + response_covariance,
        schema_version=np.asarray(1),
    )
    config_payload = json.loads(paths["config"].read_text(encoding="utf-8"))
    qa = {
        "schema_version": 1,
        "analysis_version": authority.config.analysis_version,
        "status": "approved",
        "producer_commit": "d" * 40,
        "valid": True,
        "blocked_reasons": [],
        "files": {
            "sigma_v1.csv": sha256_file(csv_path),
            "sigma_covariance.npz": sha256_file(npz_path),
        },
        "fit_evidence": {
            "fit_release_id": s4_dir.name,
            "path": s4_dir.relative_to(root).as_posix(),
            "qa_sha256": sha256_file(s4_dir / "sigma_fit_qa.json"),
        },
        "fit_qa": {
            "valid": True,
            "acceptance_phi_response_sha256": sha256_file(paths["response"]),
            "response_application": "forward_folded",
        },
        "closure": {
            "valid": True,
            "sign_check_passed": True,
            "bias": 0.0,
            "pull_mean": 0.0,
            "pull_width": 1.0,
        },
        "systematic_sources": [{
            "name": "acceptance_response_statistics",
            "path": (s4_dir / "sigma_fit_qa.json").relative_to(root).as_posix(),
            "sha256": sha256_file(s4_dir / "sigma_fit_qa.json"),
        }],
        "systematic_covariances": {
            "acceptance_response_statistics": response_covariance.tolist()
        },
        "inputs": inputs,
        "input_sha256": input_sha,
        "config_sha256": config_sha,
        "gate0_handoff_sha256": sha256_file(paths["gate0"]),
        "acceptance_qa_sha256": sha256_file(paths["acceptance_qa"]),
        "qa_thresholds": config_payload["release_qa_thresholds"],
    }
    qa_path = release / "polarization_qa.json"
    qa_path.write_text(json.dumps(qa), encoding="utf-8")
    return root, release, s4_dir


def test_s6_replays_pinned_s4_and_returns_immutable_state(replay_release):
    root, release, _ = replay_release
    result = validate_sigma_release(release, root)
    assert result.bin_keys
    with pytest.raises(ValueError):
        result.total_covariance[0, 0] = 1.0
    with pytest.raises(TypeError):
        result.qa["valid"] = False


def test_s6_cannot_disable_replay(replay_release):
    root, release, _ = replay_release
    with pytest.raises(PolarizationContractError, match="cannot disable"):
        validate_sigma_release(release, root, replay_fit=False)


@pytest.mark.parametrize("target", ["missing", "legacy_path", "wrong_release", "qa_hash"])
def test_s6_rejects_invalid_s4_pin(replay_release, target):
    root, release, _ = replay_release
    qa_path = release / "polarization_qa.json"
    qa = json.loads(qa_path.read_text(encoding="utf-8"))
    if target == "missing":
        qa.pop("fit_evidence")
    elif target == "legacy_path":
        qa["fit_evidence"]["path"] = "results/physics/polarization/fit-test"
    elif target == "wrong_release":
        qa["fit_evidence"]["fit_release_id"] = "fit-other"
    else:
        qa["fit_evidence"]["qa_sha256"] = "0" * 64
    qa_path.write_text(json.dumps(qa), encoding="utf-8")
    with pytest.raises(PolarizationContractError, match="S4|triplet"):
        validate_sigma_release(release, root)


@pytest.mark.parametrize("target", ["expected", "nuisance", "deviance", "mode_metadata"])
def test_s6_rejects_coherently_rehashed_s4_claim_tamper(replay_release, target):
    root, release, s4_dir = replay_release
    s4_qa_path = s4_dir / "sigma_fit_qa.json"
    s4_qa = json.loads(s4_qa_path.read_text(encoding="utf-8"))
    if target == "expected":
        s4_qa["nominal_fit"]["expected"][0] += 1.0
    elif target == "nuisance":
        s4_qa["nominal_fit"]["log_yield"][0] += 0.01
    elif target == "deviance":
        s4_qa["nominal_fit"]["deviance_contributions"][0] += 0.01
        s4_qa["nominal_fit"]["deviance"] += 0.01
    else:
        dimension = len(s4_qa["nominal_fit"]["sigma"])
        s4_qa["response_propagation"] = {
            "covariance": np.zeros((dimension, dimension)).tolist(),
            "retained_modes": ["forged-mode"],
            "refits": [{
                "mode_id": "forged-mode",
                "eigenvalue": 1.0,
                "step": 0.01,
                "scheme": "central",
                "derivative": np.zeros(dimension).tolist(),
                "lower_sigma": s4_qa["nominal_fit"]["sigma"],
                "upper_sigma": s4_qa["nominal_fit"]["sigma"],
            }],
            "valid": True,
        }
    s4_qa_path.write_text(json.dumps(s4_qa), encoding="utf-8")
    qa_path = release / "polarization_qa.json"
    qa = json.loads(qa_path.read_text(encoding="utf-8"))
    qa["fit_evidence"]["qa_sha256"] = sha256_file(s4_qa_path)
    qa["systematic_sources"][0]["sha256"] = sha256_file(s4_qa_path)
    qa_path.write_text(json.dumps(qa), encoding="utf-8")
    with pytest.raises(PolarizationContractError, match="S4|replay|response"):
        validate_sigma_release(release, root)


@pytest.mark.parametrize("target", ["sigma", "stat_covariance", "response_covariance"])
def test_s6_replay_rejects_coherently_rehashed_scientific_tamper(
    replay_release, target
):
    root, release, _ = replay_release
    qa_path = release / "polarization_qa.json"
    qa = json.loads(qa_path.read_text(encoding="utf-8"))
    if target == "sigma":
        with (release / "sigma_v1.csv").open(newline="", encoding="utf-8") as stream:
            rows = list(csv.reader(stream))
        rows[1][rows[0].index("sigma")] = str(float(rows[1][rows[0].index("sigma")]) + 0.01)
        with (release / "sigma_v1.csv").open("w", newline="", encoding="utf-8") as stream:
            csv.writer(stream, lineterminator="\n").writerows(rows)
        qa["files"]["sigma_v1.csv"] = sha256_file(release / "sigma_v1.csv")
    else:
        npz_path = release / "sigma_covariance.npz"
        arrays = dict(np.load(npz_path, allow_pickle=False))
        field = "stat_covariance" if target == "stat_covariance" else "systematic_covariance"
        arrays[field] = arrays[field] + np.eye(len(arrays["bin_keys"])) * 1.0e-5
        arrays["covariance"] = arrays["stat_covariance"] + arrays["systematic_covariance"]
        np.savez(npz_path, **arrays)
        qa["files"]["sigma_covariance.npz"] = sha256_file(npz_path)
        with (release / "sigma_v1.csv").open(newline="", encoding="utf-8") as stream:
            csv_rows = list(csv.reader(stream))
        if target == "stat_covariance":
            field_index = csv_rows[0].index("stat_uncertainty")
            for index, row in enumerate(csv_rows[1:]):
                row[field_index] = str(np.sqrt(arrays[field][index, index]))
        if target == "response_covariance":
            qa["systematic_covariances"]["acceptance_response_statistics"] = arrays[field].tolist()
            field_index = csv_rows[0].index("systematic_components_json")
            for index, row in enumerate(csv_rows[1:]):
                row[field_index] = json.dumps(
                    {"acceptance_response_statistics": np.sqrt(arrays[field][index, index])},
                    separators=(",", ":"),
                )
        with (release / "sigma_v1.csv").open("w", newline="", encoding="utf-8") as stream:
            csv.writer(stream, lineterminator="\n").writerows(csv_rows)
        qa["files"]["sigma_v1.csv"] = sha256_file(release / "sigma_v1.csv")
    qa_path.write_text(json.dumps(qa), encoding="utf-8")
    with pytest.raises(PolarizationContractError, match="replayed|systematic component"):
        validate_sigma_release(release, root)
