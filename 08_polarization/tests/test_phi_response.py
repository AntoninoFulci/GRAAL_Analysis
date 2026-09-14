from __future__ import annotations

import importlib
from dataclasses import replace

import numpy as np
import pytest

from contracts import PolarizationContractError, sha256_file


def load(fixture, **kwargs):
    return importlib.import_module("phi_response").load_phi_response(
        fixture.path, repository_root=fixture.path.parent,
        config=kwargs.pop("config", fixture.config),
        expected_release_id=kwargs.pop("expected_release_id", "n3-test"), **kwargs)


def test_response_parser_is_available():
    module = importlib.import_module("phi_response")
    assert callable(module.load_phi_response)


def test_row_probability_endpoint_uses_approved_absolute_tolerance(response_fixture):
    module = importlib.import_module("phi_response")
    tolerance = response_fixture.config.response_validation.probability_absolute_tolerance
    raw = {key: str(value) for key, value in response_fixture.rows[0].items()}
    raw["response_probability"] = str(1.0 + 0.5 * tolerance)

    parsed = module._parse_row(raw, response_fixture.config, "n3-test")

    assert parsed["response_probability"] > 1.0
    raw["response_probability"] = str(1.0 + 2.0 * tolerance)
    with pytest.raises(PolarizationContractError, match=r"\[0,1\]"):
        module._parse_row(raw, response_fixture.config, "n3-test")


def test_response_requires_every_joint_mass_phi_cell(response_fixture):
    response_fixture.rows.pop()
    response_fixture.write()
    with pytest.raises(PolarizationContractError, match="complete Cartesian grid"):
        load(response_fixture)


def test_response_reconstructs_mass_major_phi_matrix_without_renormalizing(response_fixture):
    response = load(response_fixture)
    matrix = response.matrix(response_fixture.key, "parallel")
    assert matrix.shape == (24, 24)
    assert matrix[0, 0] == 2/15
    assert matrix[1, 0] == 1/10
    assert matrix[12, 11] == 1/10  # migration across a mass boundary
    assert matrix[0, 23] == 1/10
    np.testing.assert_allclose(matrix.sum(axis=0), 7/30, rtol=1e-15)
    assert response.source_sha256 == sha256_file(response_fixture.path)


def test_weighted_covariance_matches_independent_hand_calculation(response_fixture):
    response = load(response_fixture)
    expected = np.zeros((24, 24))
    expected[0, 0] = 38/50625
    expected[1, 1] = 29/90000
    expected[0, 1] = expected[1, 0] = -1/16875
    blocks = response.covariance_blocks(response_fixture.key, "parallel")
    assert len(blocks) == 24
    np.testing.assert_allclose(blocks[0], expected, rtol=1e-12, atol=1e-14)


@pytest.mark.parametrize("mutation", [
    "duplicate", "reorder", "missing_orientation", "reversed_header",
    "unequal_axes", "phi_gap", "phi_wrap", "mass_shift", "inconsistent_generated",
    "inconsistent_input_hash", "inconsistent_config_hash", "unknown_mask", "mixed_mask",
    "negative_weight", "sum_probability_gt_one", "wrong_uncertainty",
    "negative_eigenvalue", "selected_count_exceeds_generated", "zero_generation_valid",
    "low_statistics_valid", "fractional_count", "nonfinite", "invalid_digest",
    "wrong_release", "wrong_analysis", "wrong_energy", "wrong_target", "empty_key",
])
def test_response_rejects_contract_violations(response_fixture, mutation):
    rows = response_fixture.rows
    first = rows[0]
    if mutation == "duplicate":
        rows.insert(1, first.copy())
    elif mutation == "reorder":
        rows[0], rows[1] = rows[1], rows[0]
    elif mutation == "missing_orientation":
        rows[:] = [row for row in rows if row["orientation"] == "parallel"]
    elif mutation == "reversed_header":
        response_fixture.write(fields=tuple(reversed(tuple(first))))
    elif mutation == "unequal_axes":
        first["reco_phi_high"] += .01
    elif mutation == "phi_gap":
        for row in rows:
            if row["true_phi_bin"] == 1:
                row["true_phi_low"] += .01
            if row["reco_phi_bin"] == 1:
                row["reco_phi_low"] += .01
    elif mutation == "phi_wrap":
        for row in rows:
            for field in ("true_phi_low", "true_phi_high", "reco_phi_low", "reco_phi_high"):
                row[field] += np.pi
    elif mutation == "mass_shift":
        for row in rows:
            for field in ("true_mass_low_gev", "true_mass_high_gev", "reco_mass_low_gev", "reco_mass_high_gev"):
                row[field] += .01
    elif mutation == "inconsistent_generated":
        first["sumw_generated_true"] += 1
    elif mutation in {"inconsistent_input_hash", "inconsistent_config_hash"}:
        first["input_sha256" if mutation == "inconsistent_input_hash" else "config_sha256"] = "d" * 64
    elif mutation == "unknown_mask":
        first["validity_mask"] = "invalid_unknown"
    elif mutation == "mixed_mask":
        first["validity_mask"] = "invalid_incomplete_coverage"
    elif mutation == "negative_weight":
        first["sumw_selected_migration"] = -1
    elif mutation == "sum_probability_gt_one":
        first["response_probability"] = 1.01
    elif mutation == "wrong_uncertainty":
        first["response_stat_uncertainty"] *= 2
    elif mutation == "negative_eigenvalue":
        # Equal p=.4, G=300, G2=500, S2=400 gives positive diagonals
        # but covariance [[.001777..., -.002666...], [..., .001777...]].
        for row in response_fixture.block()[:2]:
            row.update(n_selected_migration=50, sumw_selected_migration=120.,
                       sumw2_selected_migration=400., response_probability=.4,
                       response_stat_uncertainty=np.sqrt(160/90000))
    elif mutation == "selected_count_exceeds_generated":
        first["n_selected_migration"] = 201
    elif mutation == "zero_generation_valid":
        for row in response_fixture.block():
            row.update(n_generated_true=0, sumw_generated_true=0., sumw2_generated_true=0.,
                       n_selected_migration=0, sumw_selected_migration=0.,
                       sumw2_selected_migration=0., response_probability=0., response_stat_uncertainty=0.)
    elif mutation == "low_statistics_valid":
        response_fixture.config = replace(response_fixture.config,
            response_validation=replace(response_fixture.config.response_validation,
                minimum_generated_effective_events_per_true_phi=181.))
    elif mutation == "fractional_count":
        first["n_generated_true"] = "200.5"
    elif mutation == "nonfinite":
        first["sumw_generated_true"] = "nan"
    elif mutation == "invalid_digest":
        first["input_sha256"] = "B" * 64
    elif mutation == "wrong_release":
        first["acceptance_release_id"] = "other"
    elif mutation == "wrong_analysis":
        first["analysis_version"] = "other"
    elif mutation == "wrong_energy":
        for row in rows:
            row["Egamma_low"] = 1.11
    elif mutation == "wrong_target":
        first["target"] = "D2"
    elif mutation == "empty_key":
        first["selection_id"] = " "
    if mutation != "reversed_header":
        response_fixture.write()
    with pytest.raises(PolarizationContractError):
        load(response_fixture)


@pytest.mark.parametrize("field,value", [
    ("acceptance_release_id", "other"),
    ("phi_response_schema_sha256", "d" * 64),
    ("phi_response_schema_approval_id", "other"),
    ("phi_response_schema_path", "/tmp/schema.json"),
    ("status", "blocked"),
])
def test_response_rejects_wrong_config_authorities(response_fixture, field, value):
    with pytest.raises(PolarizationContractError):
        load(response_fixture, config=replace(response_fixture.config, **{field: value}))


@pytest.mark.parametrize("field", ["finite_difference_relative_step", "finite_difference_absolute_step"])
def test_response_rejects_zero_finite_difference_steps(response_fixture, field):
    validation = replace(response_fixture.config.response_validation, **{field: 0.})
    config = replace(response_fixture.config, response_validation=validation)
    with pytest.raises(PolarizationContractError, match=f"{field} must be positive"):
        load(response_fixture, config=config)


@pytest.mark.parametrize("mask", ["invalid_zero_generated", "invalid_low_effective_statistics",
                                  "invalid_nonphysical_weights", "invalid_incomplete_coverage"])
def test_invalid_blocks_retain_cartesian_cells_and_validity(response_fixture, mask):
    for row in response_fixture.block():
        row["validity_mask"] = mask
        if mask == "invalid_zero_generated":
            row.update(n_generated_true=0, sumw_generated_true=0., sumw2_generated_true=0.,
                       n_selected_migration=0, sumw_selected_migration=0.,
                       sumw2_selected_migration=0., response_probability=0., response_stat_uncertainty=0.)
    if mask == "invalid_low_effective_statistics":
        for row in response_fixture.rows:
            row["validity_mask"] = mask
        response_fixture.config = replace(response_fixture.config,
            response_validation=replace(response_fixture.config.response_validation,
                minimum_generated_effective_events_per_true_phi=181.))
    response_fixture.write()
    response = load(response_fixture)
    assert response.matrix(response_fixture.key, "parallel").shape == (24, 24)
    assert response.validity[(response_fixture.key, "parallel", 0)] == mask
    if mask == "invalid_zero_generated":
        assert np.count_nonzero(response.covariance_blocks(response_fixture.key, "parallel")[0]) == 0


def test_parsed_arrays_and_mappings_cannot_be_mutated(response_fixture):
    response = load(response_fixture)
    with pytest.raises(ValueError):
        response.matrix(response_fixture.key, "parallel")[0, 0] = 1.
    with pytest.raises(TypeError):
        response.validity[(response_fixture.key, "parallel", 0)] = "invalid_zero_generated"


def test_extreme_finite_invalid_diagnostics_do_not_overflow(response_fixture):
    for row in response_fixture.block():
        row.update(sumw_generated_true=1e200, validity_mask="invalid_nonphysical_weights",
                   response_probability=row["sumw_selected_migration"] / 1e200,
                   response_stat_uncertainty=0.)
    response_fixture.write()
    response = load(response_fixture)
    assert response.validity[(response_fixture.key, "parallel", 0)] == "invalid_nonphysical_weights"


def test_unit_weight_covariance_reduces_to_multinomial_with_loss(response_fixture):
    for row in response_fixture.rows:
        count = row["n_selected_migration"]
        probability = count / 200
        row.update(sumw_generated_true=200., sumw2_generated_true=200.,
                   sumw_selected_migration=float(count), sumw2_selected_migration=float(count),
                   response_probability=probability,
                   response_stat_uncertainty=np.sqrt(probability * (1 - probability) / 200))
    response_fixture.write()
    block = load(response_fixture).covariance_blocks(response_fixture.key, "parallel")[0]
    np.testing.assert_allclose(block[:2, :2], [[.00045, -.000075], [-.000075, .0006375]], atol=1e-15)


def test_nonuniform_contiguous_phi_partition_is_retained(response_fixture):
    edges = np.pi * (np.arange(13) / 12) ** 2
    for row in response_fixture.rows:
        for axis in ("true", "reco"):
            index = row[f"{axis}_phi_bin"]
            row[f"{axis}_phi_low"], row[f"{axis}_phi_high"] = edges[index:index + 2]
    response_fixture.write()
    np.testing.assert_array_equal(load(response_fixture).phi_edges[response_fixture.key], edges)


def test_undefined_invalid_normalization_retains_nonzero_raw_diagnostics(response_fixture):
    for row in response_fixture.block():
        row.update(sumw_generated_true=0., sumw2_generated_true=0.,
                   response_probability=0., response_stat_uncertainty=0.,
                   validity_mask="invalid_nonphysical_weights")
    response_fixture.write()
    original = response_fixture.path.read_bytes()
    response = load(response_fixture)
    assert response_fixture.path.read_bytes() == original
    assert response.validity[(response_fixture.key, "parallel", 0)] == "invalid_nonphysical_weights"
    np.testing.assert_array_equal(response.matrix(response_fixture.key, "parallel")[:, 0], 0.)


def test_schema_tampering_rejects_actual_changed_bytes(response_fixture):
    schema = response_fixture.path.parent / response_fixture.config.phi_response_schema_path
    schema.write_text(schema.read_text() + "\n")
    with pytest.raises(PolarizationContractError, match="schema SHA-256 mismatch"):
        load(response_fixture)


def test_response_rejects_symlink_input(response_fixture):
    original = response_fixture.path
    link = original.with_name("linked.csv")
    link.symlink_to(original)
    response_fixture.path = link
    with pytest.raises(PolarizationContractError, match="symbolic link"):
        load(response_fixture)


def test_response_rejects_negative_variance_even_if_marked_invalid(response_fixture):
    for row in response_fixture.block():
        row["validity_mask"] = "invalid_nonphysical_weights"
    response_fixture.rows[0].update(sumw_selected_migration=270., response_probability=.9,
                                   sumw2_selected_migration=1000., response_stat_uncertainty=0.)
    response_fixture.rows[1].update(n_selected_migration=0, sumw_selected_migration=0.,
                                   sumw2_selected_migration=0., response_probability=0., response_stat_uncertainty=0.)
    response_fixture.write()
    with pytest.raises(PolarizationContractError, match="negative variance"):
        load(response_fixture)
