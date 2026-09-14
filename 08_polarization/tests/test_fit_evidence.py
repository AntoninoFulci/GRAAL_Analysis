from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest
from scipy.special import xlogy

from contracts import PolarizationContractError, sha256_file
from fit_evidence import (
    FIT_EVIDENCE_FILENAMES,
    validate_fit_evidence,
    write_fit_evidence,
)
from response_uncertainty import ResponsePropagationResult
from sigma_fit import (
    JointSigmaFitResult,
    _row_order,
    _sigma_bin_key,
    canonical_count_row_key,
)


def test_fit_evidence_triplet_is_exact():
    assert FIT_EVIDENCE_FILENAMES == frozenset(
        {"azimuth_counts_v1.csv", "sigma_fit_v1.csv", "sigma_fit_qa.json"}
    )


def _count_test_module():
    path = Path(__file__).with_name("test_azimuth_counts.py")
    spec = importlib.util.spec_from_file_location("task4_count_tests", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def evidence_problem(response_fixture):
    module = _count_test_module()
    paths = module.count_authority_repo.__wrapped__(response_fixture)
    authority = module._load_count_authority(paths)
    counts = module._project(module._event_sample(paths), authority)
    bin_keys = tuple(
        _sigma_bin_key(key, index)
        for key in authority.response.keys
        for index in range(len(authority.response.mass_edges[key]) - 1)
    )
    dimension = len(bin_keys)
    nominal_rows = tuple(
        sorted(
            (row for row in counts.rows if row.replica_id == 0),
            key=_row_order,
        )
    )
    rng = np.random.default_rng(1701)
    centered = rng.normal(size=(32, dimension))
    centered -= np.mean(centered, axis=0)
    orthonormal, _ = np.linalg.qr(centered)
    variances = np.linspace(0.1, 0.2, dimension)
    vectors = orthonormal * np.sqrt(31.0 * variances)
    statistical_covariance = np.cov(vectors, rowvar=False, ddof=1)
    observed = np.asarray([row.observed_count for row in nominal_rows], dtype=float)
    expected = observed + 2.0
    residuals = (observed - expected) / np.sqrt(expected)
    contributions = 2.0 * (
        xlogy(observed, observed / expected) - (observed - expected)
    )
    nominal = JointSigmaFitResult(
        bin_keys=bin_keys,
        nuisance_keys=tuple(f"{item}|log_yield" for item in bin_keys),
        row_keys=tuple(canonical_count_row_key(row) for row in nominal_rows),
        sigma=np.linspace(-0.2, 0.2, dimension),
        log_yield=np.log(np.linspace(15.0, 25.0, dimension)),
        hessian_covariance=statistical_covariance,
        expected=expected,
        residuals=residuals,
        deviance_contributions=contributions,
        deviance=float(np.sum(contributions)),
        ndof=len(expected) - 2 * dimension,
        converged=True,
        rank=2 * dimension,
        replica_id=0,
    )
    response = ResponsePropagationResult(
        np.zeros((dimension, dimension)), (), (), True
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
        np.diag(np.linspace(0.1, 0.2, len(evidence.nominal_fit.bin_keys))),
        atol=1e-15,
    )
    assert evidence.counts.replica_ids == tuple(range(33))
    assert evidence.bootstrap_sigma_vectors.shape == (
        32,
        len(evidence.nominal_fit.bin_keys),
    )
    with pytest.raises(ValueError):
        evidence.statistical_covariance[0, 0] = 9.0


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
    text = fit_path.read_text(encoding="utf-8").replace("0.20000000000000001", "0.3")
    fit_path.write_text(text, encoding="utf-8")
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

    with pytest.raises(PolarizationContractError, match="residual"):
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
