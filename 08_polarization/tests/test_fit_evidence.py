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
from nuisance_uncertainty import NuisancePropagationResult
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
    config_payload["bootstrap"]["hessian_diagonal_ratio_min"] = 1.0e-9
    config_payload["bootstrap"]["hessian_diagonal_ratio_max"] = 1.0e9
    config_path.write_text(json.dumps(config_payload), encoding="utf-8")
    authority = module._load_count_authority(paths)
    projected = module._project(module._event_sample(paths), authority)

    def synthetic_count(row):
        phase = row.replica_id + 1
        frequency = (
            sum(ord(character) for character in row.observable)
            + round(100.0 * row.Egamma_low)
            + 7 * row.reco_mass_bin
        )
        injected = 0.14 * np.sin(0.017 * frequency * phase)
        orientation_sign = dict(authority.config.orientation_signs)[row.orientation]
        phi = 0.5 * (row.reco_phi_low + row.reco_phi_high)
        return round(
            250.0
            * (1.0 + orientation_sign * row.beam_polarization * injected * np.cos(2.0 * phi))
        )

    counts = AzimuthCountTable(
        tuple(
            replace(
                row,
                observed_count=synthetic_count(row),
            )
            for row in projected.rows
        ),
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
    vectors = np.asarray(
        [
            _fit_sigma_forward_folded_core(
                counts,
                authority.response,
                config=authority.config,
                replica_id=replica_id,
            ).sigma
            for replica_id in range(1, 33)
        ]
    )
    statistical_covariance = np.cov(vectors, rowvar=False, ddof=1)
    response = ResponsePropagationResult(
        np.zeros((dimension, dimension)), (), (), True
    )
    def nuisance(name):
        return NuisancePropagationResult(
            name,
            np.zeros((dimension, dimension)),
            (f"{name}|input",),
            np.zeros((1, 1)),
            (),
            (),
            True,
        )
    compton = nuisance("compton_polarization_statistics")
    flux_exposure = nuisance("flux_exposure_statistics")
    monkeypatch.setattr(
        fit_evidence,
        "propagate_response_covariance",
        lambda *_args, **_kwargs: response,
    )
    monkeypatch.setattr(
        fit_evidence, "propagate_compton_covariance", lambda *_args, **_kwargs: compton
    )
    monkeypatch.setattr(
        fit_evidence, "propagate_flux_exposure_covariance", lambda *_args, **_kwargs: flux_exposure
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
        compton_propagation=compton,
        flux_exposure_propagation=flux_exposure,
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

    authorities = evidence.qa["authorities"]
    assert authorities["strip_energy_lookup"]["sha256"] == sha256_file(
        paths["lookup"]
    )
    assert authorities["response_period_coverage"] == (
        {
            "beam_group": "group-a",
            "covered_source_periods": ("period-a", "period-b"),
            "coverage_valid": True,
            "detector_conditions_sha256": "1" * 64,
            "mc_config_sha256": "2" * 64,
            "selection_sha256": "3" * 64,
            "qa_sha256": authority.config.acceptance_qa_sha256,
        },
    )

    assert evidence.nominal_fit.bin_keys == tuple(
        sorted(evidence.nominal_fit.bin_keys)
    )
    np.testing.assert_allclose(
        evidence.statistical_covariance,
        np.cov(evidence.bootstrap_sigma_vectors, rowvar=False, ddof=1),
        atol=1e-15,
    )
    assert np.linalg.matrix_rank(evidence.statistical_covariance) == len(
        evidence.nominal_fit.bin_keys
    )
    assert evidence.counts.replica_ids == tuple(range(33))
    assert evidence.bootstrap_sigma_vectors.shape == (
        32,
        len(evidence.nominal_fit.bin_keys),
    )
    assert evidence.qa["release_qa"]["n3_closure_valid"] is True
    assert set(evidence.qa["nuisance_propagations"]) == {
        "compton_polarization_statistics", "flux_exposure_statistics"
    }
    assert evidence.compton_propagation.source_name == "compton_polarization_statistics"
    assert evidence.flux_exposure_propagation.source_name == "flux_exposure_statistics"
    assert dict(evidence.qa["release_qa"]["orientation_signs"]) == dict(
        authority.config.orientation_signs
    )
    with pytest.raises(ValueError):
        evidence.statistical_covariance[0, 0] = 9.0
    with pytest.raises(TypeError):
        evidence.qa["optimizer"]["name"] = "forged"
    with pytest.raises(TypeError):
        evidence.qa["bootstrap"]["successful_replica_ids"][0] = 99

    closure = evidence.forward_folded_closure
    assert closure.bin_keys == evidence.nominal_fit.bin_keys
    assert closure.fitted_sigma_vectors.shape == (
        closure.experiments,
        len(evidence.nominal_fit.bin_keys),
    )
    assert closure.sign_check_passed
    assert closure.valid
    with pytest.raises(ValueError):
        closure.fitted_sigma_vectors[0, 0] = 9.0


@pytest.mark.parametrize(
    "name",
    ["compton_polarization_statistics", "flux_exposure_statistics"],
)
def test_fit_evidence_rejects_named_nuisance_covariance_tamper(evidence_problem, name):
    paths, authority, output = evidence_problem
    qa_path = output / "sigma_fit_qa.json"
    qa = json.loads(qa_path.read_text(encoding="utf-8"))
    qa["nuisance_propagations"][name]["input_covariance"][0][0] = 1.0
    qa_path.write_text(json.dumps(qa), encoding="utf-8")

    with pytest.raises(PolarizationContractError, match="nuisance|replay|covariance"):
        validate_fit_evidence(output, paths["root"], config=authority.config)


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


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "blocked"),
        ("valid", False),
        ("blocked_reasons", ["not approved"]),
        ("analysis_version", "legacy"),
    ],
)
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


def test_fit_evidence_writer_emits_exact_approved_state(evidence_problem):
    paths, authority, output = evidence_problem
    qa = json.loads((output / "sigma_fit_qa.json").read_text(encoding="utf-8"))
    assert qa["status"] == "approved"
    assert qa["valid"] is True
    assert qa["blocked_reasons"] == []
    assert qa["forward_folded_closure"]["algorithm_version"] == (
        "forward-folded-poisson-ensemble-v1"
    )


@pytest.mark.parametrize(
    "target",
    ["fitted_vector", "sign_swapped", "threshold", "missing"],
)
def test_fit_evidence_rejects_forward_folded_closure_tamper_and_legacy_migration(
    evidence_problem, target
):
    paths, authority, output = evidence_problem
    qa_path = output / "sigma_fit_qa.json"
    qa = json.loads(qa_path.read_text(encoding="utf-8"))
    if target == "fitted_vector":
        qa["forward_folded_closure"]["fitted_sigma_vectors"][0][0] += 0.01
    elif target == "sign_swapped":
        qa["forward_folded_closure"]["sign_swapped_sigma"][0] *= -1.0
    elif target == "threshold":
        qa["forward_folded_closure"]["bias_threshold"] *= 2.0
    else:
        qa.pop("forward_folded_closure")
    qa_path.write_text(json.dumps(qa), encoding="utf-8")

    with pytest.raises(PolarizationContractError, match="closure|top-level"):
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


def test_fit_evidence_rejects_bootstrap_vectors_reassigned_to_other_replicas(
    evidence_problem,
):
    paths, authority, output = evidence_problem
    qa_path = output / "sigma_fit_qa.json"
    qa = json.loads(qa_path.read_text(encoding="utf-8"))
    qa["bootstrap"]["sigma_vectors"].reverse()
    qa_path.write_text(json.dumps(qa), encoding="utf-8")

    with pytest.raises(PolarizationContractError, match="bootstrap.*replay"):
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
