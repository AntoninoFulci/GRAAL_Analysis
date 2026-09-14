from __future__ import annotations

import importlib.util
import csv
from dataclasses import replace
import json
from pathlib import Path

import numpy as np
import pytest

import fit_evidence
from contracts import PolarizationContractError, sha256_file
from azimuth_counts import AzimuthCountTable
from fit_evidence import (
    FIT_EVIDENCE_FILENAMES,
    FIT_FIELDS,
    validate_fit_evidence,
    write_fit_evidence,
)
from response_uncertainty import ResponsePropagationResult
from sigma_fit import (
    _fit_sigma_forward_folded_core,
    _sigma_bin_key,
)


def test_fit_evidence_triplet_is_exact():
    assert FIT_EVIDENCE_FILENAMES == frozenset(
        {"azimuth_counts_v1.csv", "sigma_fit_v1.csv", "sigma_fit_qa.json"}
    )


def test_fit_csv_carries_release_qa_and_exact_input_hashes():
    assert {
        "event_count",
        "deviance_contribution",
        "fit_deviance",
        "fit_ndof",
        "input_sha256",
        "config_sha256",
        "response_input_sha256",
        "response_config_sha256",
    } <= set(FIT_FIELDS)


def _count_test_module():
    path = Path(__file__).with_name("test_azimuth_counts.py")
    spec = importlib.util.spec_from_file_location("task4_count_tests", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def evidence_problem(response_fixture, monkeypatch):
    module = _count_test_module()
    paths = module.count_authority_repo.__wrapped__(response_fixture)
    config_path = paths["root"] / "config/physics/polarization_v1.json"
    config_payload = json.loads(config_path.read_text(encoding="utf-8"))
    config_payload["release_qa_thresholds"]["minimum_events_per_bin"] = 1
    config_payload["release_qa_thresholds"]["maximum_deviance_per_ndof"] = 1.0e9
    config_path.write_text(json.dumps(config_payload), encoding="utf-8")
    authority = module._load_count_authority(paths)
    projected = module._project(module._event_sample(paths), authority)
    counts = AzimuthCountTable(
        tuple(replace(row, observed_count=row.observed_count + 10) for row in projected.rows),
        projected.expected_universe,
        projected.expected_replica_ids,
    )
    bin_keys = tuple(
        _sigma_bin_key(key, index)
        for key in authority.response.keys
        for index in range(len(authority.response.mass_edges[key]) - 1)
    )
    dimension = len(bin_keys)
    nominal = _fit_sigma_forward_folded_core(
        counts, authority.response, config=authority.config, replica_id=0
    )
    rng = np.random.default_rng(1701)
    centered = rng.normal(size=(32, dimension))
    centered -= np.mean(centered, axis=0)
    orthonormal, _ = np.linalg.qr(centered)
    vectors = orthonormal @ (
        np.sqrt(31.0) * np.linalg.cholesky(nominal.hessian_covariance).T
    )
    statistical_covariance = np.cov(vectors, rowvar=False, ddof=1)
    response = ResponsePropagationResult(
        np.zeros((dimension, dimension)), (), (), True
    )
    monkeypatch.setattr(
        fit_evidence,
        "propagate_response_covariance",
        lambda *_args, **_kwargs: response,
    )
    output = paths["root"] / "results/physics/polarization_fits/fit-test"
    output.mkdir(parents=True)
    write_fit_evidence(
        output,
        authority=authority,
        counts=counts,
        nominal=nominal,
        statistical_covariance=statistical_covariance,
        bootstrap_sigma_vectors=vectors,
        successful_replica_ids=tuple(range(1, 33)),
        failed_replica_ids=(),
        response_propagation=response,
        producer_commit="a" * 40,
    )
    return paths, authority, output


def test_fit_evidence_round_trip_reconstructs_immutable_scientific_arrays(
    evidence_problem,
):
    paths, authority, output = evidence_problem

    evidence = validate_fit_evidence(
        output, paths["root"], config=authority.config
    )

    assert evidence.nominal_fit.bin_keys == tuple(
        sorted(evidence.nominal_fit.bin_keys)
    )
    np.testing.assert_allclose(
        evidence.statistical_covariance,
        evidence.nominal_fit.hessian_covariance,
        atol=1e-15,
    )
    assert evidence.counts.replica_ids == tuple(range(33))
    assert evidence.bootstrap_sigma_vectors.shape == (
        32,
        len(evidence.nominal_fit.bin_keys),
    )
    assert evidence.qa["release_qa"]["n3_closure_valid"] is True
    assert dict(evidence.qa["release_qa"]["orientation_signs"]) == dict(
        authority.config.orientation_signs
    )
    with pytest.raises(ValueError):
        evidence.statistical_covariance[0, 0] = 9.0
    with pytest.raises(TypeError):
        evidence.qa["optimizer"]["name"] = "forged"
    with pytest.raises(TypeError):
        evidence.qa["bootstrap"]["successful_replica_ids"][0] = 99


def test_fit_evidence_rejects_coherent_out_of_bounds_sigma_tamper(
    evidence_problem,
):
    paths, authority, output = evidence_problem
    qa_path = output / "sigma_fit_qa.json"
    fit_path = output / "sigma_fit_v1.csv"
    qa = json.loads(qa_path.read_text(encoding="utf-8"))
    qa["nominal_fit"]["sigma"][0] = 2.0
    with fit_path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
        fieldnames = tuple(reader.fieldnames or ())
    rows[0]["sigma"] = "2"
    with fit_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    qa["fit"]["sha256"] = sha256_file(fit_path)
    qa_path.write_text(json.dumps(qa), encoding="utf-8")

    with pytest.raises(PolarizationContractError, match="Sigma|replay|bound"):
        validate_fit_evidence(output, paths["root"], config=authority.config)


def test_fit_evidence_rejects_forged_response_mode_endpoints(evidence_problem):
    paths, authority, output = evidence_problem
    qa_path = output / "sigma_fit_qa.json"
    qa = json.loads(qa_path.read_text(encoding="utf-8"))
    sigma = qa["nominal_fit"]["sigma"]
    qa["response_propagation"] = {
        "covariance": np.zeros((len(sigma), len(sigma))).tolist(),
        "retained_modes": ["forged|mode|0"],
        "refits": [{
            "mode_id": "forged|mode|0",
            "eigenvalue": 1.0,
            "step": 0.01,
            "scheme": "central",
            "derivative": np.zeros(len(sigma)).tolist(),
            "lower_sigma": sigma,
            "upper_sigma": sigma,
        }],
        "valid": True,
    }
    qa_path.write_text(json.dumps(qa), encoding="utf-8")

    with pytest.raises(PolarizationContractError, match="response|mode|replay"):
        validate_fit_evidence(output, paths["root"], config=authority.config)


@pytest.mark.parametrize(
    "field,value",
    (("n3_closure_valid", False), ("orientation_signs", {"parallel": 1, "perpendicular": -1})),
)
def test_fit_evidence_rejects_release_qa_sign_or_closure_claim_tamper(
    evidence_problem, field, value
):
    paths, authority, output = evidence_problem
    qa_path = output / "sigma_fit_qa.json"
    qa = json.loads(qa_path.read_text(encoding="utf-8"))
    qa["release_qa"][field] = value
    qa_path.write_text(json.dumps(qa), encoding="utf-8")

    with pytest.raises(PolarizationContractError, match="release QA"):
        validate_fit_evidence(output, paths["root"], config=authority.config)


@pytest.mark.parametrize("field,value", [("valid", False), ("analysis_version", "legacy")])
def test_fit_evidence_rejects_qa_semantic_tampering(
    evidence_problem, field, value
):
    paths, authority, output = evidence_problem
    qa_path = output / "sigma_fit_qa.json"
    qa = json.loads(qa_path.read_text(encoding="utf-8"))
    qa[field] = value
    qa_path.write_text(json.dumps(qa), encoding="utf-8")

    with pytest.raises(PolarizationContractError):
        validate_fit_evidence(output, paths["root"], config=authority.config)


def test_fit_evidence_rejects_n4_claim_and_extra_file(evidence_problem):
    paths, authority, output = evidence_problem
    qa_path = output / "sigma_fit_qa.json"
    qa = json.loads(qa_path.read_text(encoding="utf-8"))
    qa["authorities"]["n2_source_kind"] = "N4_cross_section_yields"
    qa_path.write_text(json.dumps(qa), encoding="utf-8")
    with pytest.raises(PolarizationContractError, match="N2"):
        validate_fit_evidence(output, paths["root"], config=authority.config)

    qa["authorities"]["n2_source_kind"] = "N2_metadata_reconstruction"
    qa_path.write_text(json.dumps(qa), encoding="utf-8")
    (output / "legacy_sigma.csv").write_text("legacy\n", encoding="utf-8")
    with pytest.raises(PolarizationContractError, match="exact triplet"):
        validate_fit_evidence(output, paths["root"], config=authority.config)


def test_fit_evidence_rejects_changed_csv_even_when_claim_is_rehashed(
    evidence_problem,
):
    paths, authority, output = evidence_problem
    fit_path = output / "sigma_fit_v1.csv"
    with fit_path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
        fieldnames = tuple(reader.fieldnames or ())
    rows[0]["sigma"] = format(float(rows[0]["sigma"]) + 0.1, ".17g")
    with fit_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    qa_path = output / "sigma_fit_qa.json"
    qa = json.loads(qa_path.read_text(encoding="utf-8"))
    qa["fit"]["sha256"] = sha256_file(fit_path)
    qa_path.write_text(json.dumps(qa), encoding="utf-8")

    with pytest.raises(PolarizationContractError, match="disagrees"):
        validate_fit_evidence(output, paths["root"], config=authority.config)


def test_fit_evidence_rejects_rehashed_count_value_tampering(evidence_problem):
    paths, authority, output = evidence_problem
    counts_path = output / "azimuth_counts_v1.csv"
    lines = counts_path.read_text(encoding="utf-8").splitlines()
    cells = lines[1].split(",")
    observed_index = lines[0].split(",").index("observed_count")
    cells[observed_index] = str(int(cells[observed_index]) + 1)
    lines[1] = ",".join(cells)
    counts_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    qa_path = output / "sigma_fit_qa.json"
    qa = json.loads(qa_path.read_text(encoding="utf-8"))
    qa["counts"]["sha256"] = sha256_file(counts_path)
    qa_path.write_text(json.dumps(qa), encoding="utf-8")

    with pytest.raises(PolarizationContractError, match="residual|replay"):
        validate_fit_evidence(output, paths["root"], config=authority.config)


def test_fit_evidence_rejects_missing_file_and_noncanonical_directory(
    evidence_problem,
):
    paths, authority, output = evidence_problem
    (output / "sigma_fit_v1.csv").unlink()
    with pytest.raises(PolarizationContractError, match="exact triplet"):
        validate_fit_evidence(output, paths["root"], config=authority.config)

    alias = paths["root"] / "legacy-fit-test"
    alias.symlink_to(output, target_is_directory=True)
    with pytest.raises(PolarizationContractError, match="non-symlink"):
        validate_fit_evidence(alias, paths["root"], config=authority.config)
