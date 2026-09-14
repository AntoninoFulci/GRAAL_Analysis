from __future__ import annotations

from dataclasses import fields, replace
from types import SimpleNamespace
from types import MappingProxyType

import numpy as np
import pytest

from analysis_config import (
    AnalysisConfig,
    BootstrapConfig,
    ReleaseQAConfig,
    RESPONSE_SCHEMA_APPROVAL_ID,
    RESPONSE_SCHEMA_PATH,
    ResponseValidationConfig,
)
from azimuth_counts import (
    AzimuthCountRow,
    AzimuthCountTable,
    ExpectedRecoGrid,
)
from contracts import PolarizationContractError
from phi_response import PhiResponse, ResponseKey, TrueCellKey
import sigma_fit
from sigma_fit import fit_sigma_binned


HASH = "0123456789abcdef" * 4


def _joint_config() -> AnalysisConfig:
    return AnalysisConfig(
        schema_version=1,
        analysis_version="polarization-v1",
        status="approved",
        blocked_reasons=(),
        acceptance_release_id="n3-test",
        acceptance_handoff_directory=(
            "results/physics/normalization/handoffs/n3-test"
        ),
        acceptance_qa_sha256=HASH,
        phi_response_schema_path=RESPONSE_SCHEMA_PATH,
        phi_response_schema_sha256=HASH,
        phi_response_schema_approval_id=RESPONSE_SCHEMA_APPROVAL_ID,
        phi_response_schema_reviewers=("one", "two"),
        sign_status="approved",
        sign_approval_id="sign-test",
        sign_reviewers=("one", "two"),
        orientation_signs=(("parallel", -1), ("perpendicular", 1)),
        figure4_energy_edges_gev=(0.6, 0.7, 0.8, 0.9, 1.0),
        figure4_mass_bins=2,
        figure4_phi_bins=8,
        figure4_target="P",
        figure4_tree="reco",
        figure4_vectors="kinematic_fit",
        response_validation=ResponseValidationConfig(
            100.0, 1e-12, 1e-12, 1e-9, 1e-12, 1e-4, 1e-6, 1e-10, 1e-8
        ),
        bootstrap=BootstrapConfig(6, "poisson1-sha256-v1", 1701, 0.2, 0.5, 2.0),
        release_qa=ReleaseQAConfig(
            "approved",
            "qa-test",
            ("one", "two"),
            10,
            2.0,
            0.02,
            0.2,
            0.2,
            1,
            "independent_sources_quadrature",
        ),
    )


def _smearing(phi_bins: int, *, center: float, side: float) -> np.ndarray:
    matrix = np.zeros((phi_bins, phi_bins), dtype=float)
    for truth in range(phi_bins):
        matrix[truth, truth] = center
        matrix[(truth - 1) % phi_bins, truth] = side
        matrix[(truth + 1) % phi_bins, truth] = side
    return matrix


def _replace_injected_sigma(problem, sigma):
    response = problem["response"]
    config = problem["config"]
    key = response.keys[0]
    phi_edges = np.asarray(response.phi_edges[key])
    widths = np.diff(phi_edges)
    averages = (np.sin(2 * phi_edges[1:]) - np.sin(2 * phi_edges[:-1])) / (
        2 * widths
    )
    true_yield = np.array([8.0e6, 5.0e6])
    sigma = np.asarray(sigma, dtype=float)
    signs = dict(config.orientation_signs)
    updated = []
    for row in problem["counts"].rows:
        truth = true_yield[:, None] * widths[None, :] / np.pi
        truth *= (
            1.0
            + signs[row.orientation]
            * row.beam_polarization
            * sigma[:, None]
            * averages[None, :]
        )
        expected = row.exposure * (
            response.matrix(key, row.orientation) @ truth.reshape(-1)
        )
        cell = row.reco_mass_bin * 8 + row.reco_phi_bin
        updated.append(replace(row, observed_count=int(round(expected[cell]))))
    problem["counts"] = AzimuthCountTable(
        tuple(updated),
        problem["counts"].expected_universe,
        problem["counts"].expected_replica_ids,
    )


def _row_sort_key(row: AzimuthCountRow) -> tuple[object, ...]:
    return tuple(getattr(row, field.name) for field in fields(AzimuthCountRow))


def _with_second_response_group(problem):
    """Add a canonical independent physical group with the same Asimov shape."""
    response = problem["response"]
    counts = problem["counts"]
    original = response.keys[0]
    duplicate = ResponseKey(
        original.channel,
        original.target,
        "coherent-b",
        0.8,
        0.9,
        original.cos_theta_low,
        original.cos_theta_high,
        original.observable,
        original.selection_id,
    )
    matrices = dict(response.matrices)
    matrices[duplicate, "parallel"] = matrices[original, "parallel"]
    matrices[duplicate, "perpendicular"] = matrices[original, "perpendicular"]
    covariance = dict(response.covariance_by_true_cell)
    validity = dict(response.validity)
    for orientation in ("parallel", "perpendicular"):
        for true_cell in range(16):
            source = TrueCellKey(original, orientation, true_cell)
            target = TrueCellKey(duplicate, orientation, true_cell)
            covariance[target] = covariance[source]
            validity[target] = validity[source]
    problem["response"] = replace(
        response,
        keys=tuple(sorted((*response.keys, duplicate))),
        matrices=MappingProxyType(matrices),
        covariance_by_true_cell=MappingProxyType(covariance),
        validity=MappingProxyType(validity),
        mass_edges=MappingProxyType(
            {**response.mass_edges, duplicate: response.mass_edges[original]}
        ),
        phi_edges=MappingProxyType(
            {**response.phi_edges, duplicate: response.phi_edges[original]}
        ),
    )
    duplicated_rows = tuple(
        replace(
            row,
            beam_group=duplicate.beam_group,
            Egamma_low=duplicate.Egamma_low,
            Egamma_high=duplicate.Egamma_high,
        )
        for row in counts.rows
    )
    duplicated_universe = tuple(
        replace(expected, response_key=duplicate)
        for expected in counts.expected_universe
    )
    problem["counts"] = AzimuthCountTable(
        tuple(sorted((*counts.rows, *duplicated_rows), key=_row_sort_key)),
        tuple(
            sorted(
                (*counts.expected_universe, *duplicated_universe),
                key=lambda expected: (
                    expected.response_key,
                    expected.source_period,
                    expected.orientation,
                ),
            )
        ),
        counts.expected_replica_ids,
    )
@pytest.fixture
def asimov_problem():
    config = _joint_config()
    key = ResponseKey(
        "eta_pi0", "P", "coherent-a", 0.7, 0.8, -1.0, 1.0, "p_pi0", "sel-v1"
    )
    mass_edges = (1.0, 1.2, 1.4)
    phi_edges = tuple(np.linspace(0.0, np.pi, config.figure4_phi_bins + 1))
    mass_response = np.array([[0.72, 0.16], [0.21, 0.67]])
    matrices = {
        (key, "parallel"): np.kron(
            mass_response, _smearing(8, center=0.59, side=0.17)
        ),
        (key, "perpendicular"): np.kron(
            mass_response, _smearing(8, center=0.63, side=0.15)
        ),
    }
    covariance = {}
    validity = {}
    for orientation in ("parallel", "perpendicular"):
        for true_cell in range(16):
            cell = TrueCellKey(key, orientation, true_cell)
            covariance[cell] = np.zeros((16, 16))
            validity[cell] = "valid"
    response = PhiResponse(
        keys=(key,),
        matrices=MappingProxyType(matrices),
        covariance_by_true_cell=MappingProxyType(covariance),
        validity=MappingProxyType(validity),
        source_sha256=HASH,
        input_sha256=HASH,
        config_sha256=HASH,
        mass_edges=MappingProxyType({key: mass_edges}),
        phi_edges=MappingProxyType({key: phi_edges}),
    )
    states = {
        ("period-a", "parallel"): (1.25, 0.72),
        ("period-a", "perpendicular"): (0.91, 0.65),
        ("period-b", "parallel"): (0.84, 0.69),
        ("period-b", "perpendicular"): (1.14, 0.61),
    }
    sigma = np.array([-0.35, 0.20])
    true_yield = np.array([8.0e6, 5.0e6])
    phi_low = np.asarray(phi_edges[:-1])
    phi_high = np.asarray(phi_edges[1:])
    widths = phi_high - phi_low
    averages = (np.sin(2 * phi_high) - np.sin(2 * phi_low)) / (2 * widths)
    signs = dict(config.orientation_signs)
    expected_universe = []
    rows = []
    for period, orientation in states:
        exposure, polarization = states[period, orientation]
        expected_universe.append(
            ExpectedRecoGrid(
                "polarization-v1",
                "fit-test",
                "bins-test",
                key,
                period,
                orientation,
                mass_edges,
                phi_edges,
            )
        )
        truth = true_yield[:, None] * widths[None, :] / np.pi
        truth = truth * (
            1.0
            + signs[orientation]
            * polarization
            * sigma[:, None]
            * averages[None, :]
        )
        mu = exposure * (matrices[key, orientation] @ truth.reshape(-1))
        for replica_id in range(7):
            for mass_bin in range(2):
                for phi_bin in range(8):
                    cell = mass_bin * 8 + phi_bin
                    rows.append(
                        AzimuthCountRow(
                            1,
                            "polarization-v1",
                            "fit-test",
                            "bins-test",
                            key.channel,
                            key.target,
                            key.beam_group,
                            period,
                            key.Egamma_low,
                            key.Egamma_high,
                            key.cos_theta_low,
                            key.cos_theta_high,
                            key.observable,
                            key.selection_id,
                            orientation,
                            replica_id,
                            mass_bin,
                            mass_edges[mass_bin],
                            mass_edges[mass_bin + 1],
                            phi_bin,
                            phi_edges[phi_bin],
                            phi_edges[phi_bin + 1],
                            int(round(mu[cell])),
                            exposure,
                            polarization,
                            0.001,
                            HASH,
                            HASH,
                            HASH,
                            HASH,
                            HASH,
                            HASH,
                        )
                    )
    counts = AzimuthCountTable(tuple(rows), tuple(expected_universe), tuple(range(7)))
    return {"counts": counts, "response": response, "config": config}


def asimov_sample(sigma: float = 0.35) -> dict[str, np.ndarray]:
    phi_one_state = (np.arange(16, dtype=float) + 0.5) * np.pi / 16.0
    phi = np.concatenate([phi_one_state, phi_one_state])
    orientation_sign = np.concatenate([-np.ones(16), np.ones(16)])
    polarization = np.concatenate([np.full(16, 0.72), np.full(16, 0.64)])
    # Different phi response in each state catches dropping acceptance from model.
    acceptance = np.concatenate(
        [
            0.25 + 0.65 * np.sin(phi_one_state) ** 2,
            0.30 + 0.55 * np.cos(phi_one_state - 0.2) ** 2,
        ]
    )
    exposure = np.concatenate([np.full(16, 1.3), np.full(16, 0.8)])
    state_scale = np.where(orientation_sign < 0, 1100.0, 850.0)
    observed = (
        exposure
        * acceptance
        * state_scale
        * (1.0 + orientation_sign * polarization * sigma * np.cos(2.0 * phi))
    )
    return {
        "phi": phi,
        "orientation_sign": orientation_sign,
        "polarization": polarization,
        "acceptance": acceptance,
        "exposure": exposure,
        "observed": observed,
    }


def test_acceptance_aware_fit_recovers_exact_asimov_sigma():
    result = fit_sigma_binned(**asimov_sample(0.35))
    assert result.converged
    assert result.sigma == pytest.approx(0.35, abs=2e-6)
    assert result.stat_uncertainty > 0.0
    assert result.covariance.shape == (3, 3)
    assert result.ndof == 29
    assert result.pearson_chi2 == pytest.approx(0.0, abs=1e-8)
    assert np.max(np.abs(result.residuals)) < 1e-4


def test_orientation_sign_swap_inverts_fitted_sigma():
    sample = asimov_sample(-0.42)
    nominal = fit_sigma_binned(**sample)
    sample["orientation_sign"] = -sample["orientation_sign"]
    swapped = fit_sigma_binned(**sample)
    assert nominal.sigma == pytest.approx(-0.42, abs=2e-6)
    assert swapped.sigma == pytest.approx(0.42, abs=2e-6)


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("acceptance", 0.0, "acceptance"),
        ("polarization", 1.1, "polarization"),
        ("exposure", 0.0, "exposure"),
        ("observed", -1.0, "observed"),
        ("orientation_sign", 0.0, "orientation_sign"),
    ],
)
def test_fit_rejects_nonphysical_inputs(field, value, match):
    sample = asimov_sample()
    sample[field] = sample[field].copy()
    sample[field][0] = value
    with pytest.raises(PolarizationContractError, match=match):
        fit_sigma_binned(**sample)


def test_fit_rejects_incomplete_angular_coverage():
    sample = asimov_sample()
    sample["phi"] = np.full_like(sample["phi"], 0.1)
    with pytest.raises(PolarizationContractError, match="angular coverage"):
        fit_sigma_binned(**sample)


def test_fit_rejects_shape_mismatch_and_nonfinite_values():
    sample = asimov_sample()
    sample["observed"] = sample["observed"][:-1]
    with pytest.raises(PolarizationContractError, match="same shape"):
        fit_sigma_binned(**sample)

    sample = asimov_sample()
    sample["phi"][0] = np.nan
    with pytest.raises(PolarizationContractError, match="finite"):
        fit_sigma_binned(**sample)


def test_forward_folded_joint_fit_recovers_sigma_with_mass_and_phi_migration(
    asimov_problem,
):
    result = sigma_fit.fit_sigma_forward_folded(**asimov_problem)

    np.testing.assert_allclose(result.sigma, [-0.35, 0.20], atol=2e-4)
    assert abs(result.hessian_covariance[0, 1]) > 0.0


def test_forward_folded_aggregate_has_canonical_group_and_row_alignment(
    asimov_problem,
):
    _with_second_response_group(asimov_problem)

    result = sigma_fit.fit_sigma_forward_folded(**asimov_problem)

    assert result.bin_keys == tuple(sorted(result.bin_keys))
    assert len(result.bin_keys) == 4
    assert result.nuisance_keys == tuple(
        f"{key}|log_yield" for key in result.bin_keys
    )
    assert result.row_keys == tuple(
        sigma_fit.canonical_count_row_key(row)
        for row in asimov_problem["counts"].rows
        if row.replica_id == 0
    )
    assert result.expected.shape == result.residuals.shape == result.deviance_contributions.shape
    assert result.expected.shape == (len(result.row_keys),)
    np.testing.assert_allclose(result.hessian_covariance[:2, 2:], 0.0)
    np.testing.assert_allclose(result.hessian_covariance[2:, :2], 0.0)


def test_forward_folded_fit_rejects_unapproved_config(asimov_problem):
    asimov_problem["config"] = replace(asimov_problem["config"], status="blocked")

    with pytest.raises(PolarizationContractError, match="approved canonical config"):
        sigma_fit.fit_sigma_forward_folded(**asimov_problem)


@pytest.mark.parametrize(
    ("changes", "match"),
    [
        ({"schema_version": 2}, "schema/analysis version"),
        ({"schema_version": True}, "schema/analysis version"),
        ({"analysis_version": "forged-v1"}, "schema/analysis version"),
        ({"acceptance_release_id": None}, "acceptance authority"),
        (
            {"acceptance_handoff_directory": "results/physics/normalization/handoffs/other"},
            "acceptance authority",
        ),
        ({"acceptance_qa_sha256": None}, "acceptance authority"),
        (
            {"phi_response_schema_path": "config/schemas/forged.json"},
            "schema authority",
        ),
        ({"phi_response_schema_sha256": None}, "schema authority"),
        ({"phi_response_schema_approval_id": "forged"}, "schema authority"),
        ({"phi_response_schema_reviewers": ("one",)}, "schema authority"),
        ({"phi_response_schema_reviewers": (["one"], "two")}, "schema authority"),
    ],
)
def test_forward_folded_fit_rejects_forged_config_authorities(
    asimov_problem, changes, match
):
    asimov_problem["config"] = replace(asimov_problem["config"], **changes)

    with pytest.raises(PolarizationContractError, match=match):
        sigma_fit.fit_sigma_forward_folded(**asimov_problem)


def test_forward_folded_fit_rejects_counts_analysis_version_mismatch(asimov_problem):
    counts = asimov_problem["counts"]
    altered = tuple(
        replace(row, analysis_version="forged-v1") for row in counts.rows
    )
    object.__setattr__(counts, "rows", altered)

    with pytest.raises(PolarizationContractError, match="analysis version"):
        sigma_fit.fit_sigma_forward_folded(**asimov_problem)


def test_forward_folded_fit_rejects_bootstrap_universe_mismatch(asimov_problem):
    object.__setattr__(
        asimov_problem["counts"], "expected_replica_ids", tuple(range(6))
    )

    with pytest.raises(PolarizationContractError, match="replica universe"):
        sigma_fit.fit_sigma_forward_folded(**asimov_problem)


def test_forward_folded_fit_rejects_unapproved_bootstrap_authority(asimov_problem):
    config = asimov_problem["config"]
    asimov_problem["config"] = replace(
        config, bootstrap=replace(config.bootstrap, replicas=None)
    )

    with pytest.raises(PolarizationContractError, match="approved bootstrap"):
        sigma_fit.fit_sigma_forward_folded(**asimov_problem)


def test_forward_folded_fit_rejects_forged_response_identity(asimov_problem):
    asimov_problem["response"] = replace(
        asimov_problem["response"], source_sha256="forged"
    )

    with pytest.raises(PolarizationContractError, match="response.*identity"):
        sigma_fit.fit_sigma_forward_folded(**asimov_problem)


def test_forward_folded_fit_rejects_count_axis_mismatch(asimov_problem):
    counts = asimov_problem["counts"]
    altered = list(counts.rows)
    altered[0] = replace(altered[0], reco_phi_high=0.123)
    object.__setattr__(counts, "rows", tuple(altered))

    with pytest.raises(PolarizationContractError, match="count.*axis"):
        sigma_fit.fit_sigma_forward_folded(**asimov_problem)


def test_forward_folded_fit_rejects_noncanonical_expected_universe(asimov_problem):
    counts = asimov_problem["counts"]
    object.__setattr__(
        counts,
        "expected_universe",
        (*counts.expected_universe, counts.expected_universe[0]),
    )

    with pytest.raises(PolarizationContractError, match="expected universe"):
        sigma_fit.fit_sigma_forward_folded(**asimov_problem)


def test_forward_folded_fit_rejects_response_count_key_mismatch(asimov_problem):
    response = asimov_problem["response"]
    missing_key = ResponseKey(
        "p_eta", "P", "coherent-b", 0.8, 0.9, -1.0, 1.0, "p_eta", "sel-v1"
    )
    matrices = {
        (missing_key, orientation): response.matrix(response.keys[0], orientation)
        for orientation in ("parallel", "perpendicular")
    }
    covariance = {
        TrueCellKey(missing_key, orientation, cell): np.zeros((16, 16))
        for orientation in ("parallel", "perpendicular")
        for cell in range(16)
    }
    validity = {cell: "valid" for cell in covariance}
    asimov_problem["response"] = PhiResponse(
        keys=(missing_key,),
        matrices=MappingProxyType(matrices),
        covariance_by_true_cell=MappingProxyType(covariance),
        validity=MappingProxyType(validity),
        source_sha256=HASH,
        input_sha256=HASH,
        config_sha256=HASH,
        mass_edges=MappingProxyType({missing_key: (1.0, 1.2, 1.4)}),
        phi_edges=MappingProxyType(
            {missing_key: tuple(np.linspace(0.0, np.pi, 9))}
        ),
    )

    with pytest.raises(PolarizationContractError, match="response/count.*key"):
        sigma_fit.fit_sigma_forward_folded(**asimov_problem)


def test_forward_folded_fit_rejects_nonfinite_state_inputs(asimov_problem):
    counts = asimov_problem["counts"]
    altered = list(counts.rows)
    altered[0] = replace(altered[0], beam_polarization=float("nan"))
    object.__setattr__(counts, "rows", tuple(altered))

    with pytest.raises(PolarizationContractError, match="finite.*polarization"):
        sigma_fit.fit_sigma_forward_folded(**asimov_problem)


def test_forward_folded_fit_enforces_minimum_event_qa(asimov_problem):
    config = asimov_problem["config"]
    asimov_problem["config"] = replace(
        config,
        release_qa=replace(config.release_qa, minimum_events_per_bin=10**9),
    )

    with pytest.raises(PolarizationContractError, match="minimum event"):
        sigma_fit.fit_sigma_forward_folded(**asimov_problem)


def test_forward_folded_fit_enforces_deviance_qa(asimov_problem):
    config = asimov_problem["config"]
    asimov_problem["config"] = replace(
        config,
        release_qa=replace(config.release_qa, maximum_deviance_per_ndof=1e-12),
    )

    with pytest.raises(PolarizationContractError, match="deviance/ndof"):
        sigma_fit.fit_sigma_forward_folded(**asimov_problem)


def test_forward_folded_sign_mapping_inverts_sigma(asimov_problem):
    nominal = sigma_fit.fit_sigma_forward_folded(**asimov_problem)
    config = asimov_problem["config"]
    asimov_problem["config"] = replace(
        config,
        orientation_signs=(("parallel", 1), ("perpendicular", -1)),
    )

    inverted = sigma_fit.fit_sigma_forward_folded(**asimov_problem)

    np.testing.assert_allclose(inverted.sigma, -nominal.sigma, atol=2e-4)


def test_forward_folded_fit_rejects_invalid_sign_mapping(asimov_problem):
    config = asimov_problem["config"]
    asimov_problem["config"] = replace(
        config,
        orientation_signs=(("parallel", 1), ("perpendicular", 1)),
    )

    with pytest.raises(PolarizationContractError, match="sign mapping"):
        sigma_fit.fit_sigma_forward_folded(**asimov_problem)


def test_forward_folded_fit_rejects_pending_sign_authority(asimov_problem):
    config = asimov_problem["config"]
    asimov_problem["config"] = replace(config, sign_status="pending")

    with pytest.raises(PolarizationContractError, match="approved sign authority"):
        sigma_fit.fit_sigma_forward_folded(**asimov_problem)


def test_forward_folded_fit_is_deterministic(asimov_problem):
    first = sigma_fit.fit_sigma_forward_folded(**asimov_problem)
    second = sigma_fit.fit_sigma_forward_folded(**asimov_problem)

    np.testing.assert_array_equal(first.sigma, second.sigma)
    np.testing.assert_array_equal(first.log_yield, second.log_yield)
    np.testing.assert_array_equal(first.expected, second.expected)


def test_forward_folded_fit_rejects_optimizer_failure(asimov_problem, monkeypatch):
    monkeypatch.setattr(
        sigma_fit,
        "minimize",
        lambda *args, **kwargs: SimpleNamespace(
            success=False, x=np.zeros(4), message="test optimizer failure"
        ),
    )

    with pytest.raises(PolarizationContractError, match="did not converge"):
        sigma_fit.fit_sigma_forward_folded(**asimov_problem)


def test_forward_folded_fit_rejects_nonpositive_expectation(asimov_problem):
    response = asimov_problem["response"]
    asimov_problem["response"] = replace(
        response,
        matrices=MappingProxyType(
            {
                identity: np.zeros_like(matrix)
                for identity, matrix in response.matrices.items()
            }
        ),
    )

    with pytest.raises(PolarizationContractError, match="positive finite expected"):
        sigma_fit.fit_sigma_forward_folded(**asimov_problem)


def test_bootstrap_covariance_preserves_cross_observable_covariance(
    asimov_problem,
):
    vectors = np.array(
        [
            [-0.38, 0.16],
            [-0.35, 0.20],
            [-0.31, 0.25],
            [-0.37, 0.18],
            [-0.33, 0.22],
            [-0.30, 0.27],
        ]
    )
    hessian = np.cov(vectors, rowvar=False, ddof=1)

    covariance = sigma_fit.bootstrap_sigma_covariance(
        vectors,
        ("p_pi0-bin-0", "eta_pi0-bin-0"),
        replica_ids=(1, 2, 3, 4, 5, 6),
        config=asimov_problem["config"],
        hessian_covariance=hessian,
    )

    np.testing.assert_allclose(covariance, hessian)
    assert covariance[0, 1] > 0.0
    assert np.linalg.eigvalsh(covariance)[0] >= -1e-14


def test_bootstrap_covariance_accepts_explicit_failed_replica_ids(asimov_problem):
    vectors = np.array(
        [[-0.38, 0.16], [-0.35, 0.20], [-0.31, 0.25], [-0.33, 0.22], [-0.30, 0.27]]
    )
    hessian = np.cov(vectors, rowvar=False, ddof=1)

    covariance = sigma_fit.bootstrap_sigma_covariance(
        vectors,
        ("p_pi0-bin-0", "eta_pi0-bin-0"),
        replica_ids=(1, 2, 4, 5, 6),
        failed_replica_ids=(3,),
        config=asimov_problem["config"],
        hessian_covariance=hessian,
    )

    assert covariance.shape == (2, 2)


def test_bootstrap_covariance_rejects_excess_failed_replicas(asimov_problem):
    vectors = np.array(
        [[-0.38, 0.16], [-0.35, 0.20], [-0.31, 0.25], [-0.33, 0.22]]
    )
    hessian = np.cov(vectors, rowvar=False, ddof=1)

    with pytest.raises(PolarizationContractError, match="failed replica fraction"):
        sigma_fit.bootstrap_sigma_covariance(
            vectors,
            ("p_pi0-bin-0", "eta_pi0-bin-0"),
            replica_ids=(1, 2, 3, 4),
            failed_replica_ids=(5, 6),
            config=asimov_problem["config"],
            hessian_covariance=hessian,
        )


def test_bootstrap_covariance_rejects_malformed_approved_config(asimov_problem):
    config = asimov_problem["config"]
    asimov_problem["config"] = replace(
        config, bootstrap=replace(config.bootstrap, replicas=None)
    )

    with pytest.raises(PolarizationContractError, match="approved bootstrap"):
        sigma_fit.bootstrap_sigma_covariance(
            np.array(
                [
                    [-0.38, 0.16],
                    [-0.35, 0.20],
                    [-0.31, 0.25],
                    [-0.37, 0.18],
                    [-0.33, 0.22],
                    [-0.30, 0.27],
                ]
            ),
            ("p_pi0-bin-0", "eta_pi0-bin-0"),
            replica_ids=(1, 2, 3, 4, 5, 6),
            config=asimov_problem["config"],
            hessian_covariance=np.eye(2),
        )


def test_bootstrap_covariance_rejects_indefinite_hessian_with_positive_diagonal(
    asimov_problem,
):
    vectors = np.array(
        [
            [-0.38, 0.16],
            [-0.35, 0.20],
            [-0.31, 0.25],
            [-0.37, 0.18],
            [-0.33, 0.22],
            [-0.30, 0.27],
        ]
    )
    indefinite = np.array([[1.0, 2.0], [2.0, 1.0]])

    with pytest.raises(
        PolarizationContractError,
        match="Hessian covariance.*positive definite",
    ):
        sigma_fit.bootstrap_sigma_covariance(
            vectors,
            ("p_pi0-bin-0", "eta_pi0-bin-0"),
            replica_ids=(1, 2, 3, 4, 5, 6),
            config=asimov_problem["config"],
            hessian_covariance=indefinite,
        )


def test_forward_folded_fit_rejects_indefinite_fisher_covariance(
    asimov_problem, monkeypatch
):
    real_inverse = np.linalg.inv

    def indefinite_inverse(matrix):
        covariance = real_inverse(matrix)
        covariance[0, 1] = covariance[1, 0] = 2.0 * np.sqrt(
            covariance[0, 0] * covariance[1, 1]
        )
        return covariance

    monkeypatch.setattr(sigma_fit.np.linalg, "inv", indefinite_inverse)

    with pytest.raises(
        PolarizationContractError,
        match="fit covariance.*positive definite",
    ):
        sigma_fit.fit_sigma_forward_folded(**asimov_problem)


@pytest.mark.parametrize(
    ("replica_ids", "failed_ids", "vectors", "hessian", "match"),
    [
        (
            (1, 2, 3, 4, 6),
            (),
            np.array(
                [[-0.38, 0.16], [-0.35, 0.20], [-0.31, 0.25], [-0.33, 0.22], [-0.30, 0.27]]
            ),
            np.eye(2),
            "replica IDs",
        ),
        (
            (1, 2, 3, 4, 5, 6),
            (),
            np.array(
                [[-0.38, 0.16]] * 6),
            np.eye(2),
            "rank",
        ),
        (
            (1, 2, 3, 4, 5, 6),
            (),
            np.array(
                [
                    [-0.38, 0.16],
                    [-0.35, 0.20],
                    [-0.31, 0.25],
                    [-0.37, 0.18],
                    [-0.33, 0.22],
                    [-0.30, 0.27],
                ]
            ),
            np.eye(2) * 100.0,
            "Hessian/bootstrap",
        ),
    ],
)
def test_bootstrap_covariance_rejects_invalid_qa(
    asimov_problem, replica_ids, failed_ids, vectors, hessian, match
):
    with pytest.raises(PolarizationContractError, match=match):
        sigma_fit.bootstrap_sigma_covariance(
            vectors,
            ("p_pi0-bin-0", "eta_pi0-bin-0"),
            replica_ids=replica_ids,
            failed_replica_ids=failed_ids,
            config=asimov_problem["config"],
            hessian_covariance=hessian,
        )


def test_forward_folded_fit_rejects_invalid_response_block(asimov_problem):
    response = asimov_problem["response"]
    validity = dict(response.validity)
    validity[next(iter(validity))] = "invalid_low_effective_statistics"
    asimov_problem["response"] = replace(
        response, validity=MappingProxyType(validity)
    )

    with pytest.raises(PolarizationContractError, match="response block"):
        sigma_fit.fit_sigma_forward_folded(**asimov_problem)


def test_forward_folded_fit_rejects_lost_angular_rank(asimov_problem):
    response = asimov_problem["response"]
    flat_phi = np.full((8, 8), 0.9 / 8.0)
    mass_response = np.array([[0.72, 0.16], [0.21, 0.67]])
    flat = np.kron(mass_response, flat_phi)
    asimov_problem["response"] = replace(
        response,
        matrices=MappingProxyType(
            {
                (response.keys[0], "parallel"): flat,
                (response.keys[0], "perpendicular"): flat,
            }
        ),
    )

    with pytest.raises(PolarizationContractError, match="rank"):
        sigma_fit.fit_sigma_forward_folded(**asimov_problem)


def test_forward_folded_fit_rejects_boundary_pathology(asimov_problem):
    _replace_injected_sigma(asimov_problem, [0.999, -0.999])

    with pytest.raises(PolarizationContractError, match="boundary"):
        sigma_fit.fit_sigma_forward_folded(**asimov_problem)


def test_forward_folded_fit_rejects_incomplete_count_grid(asimov_problem):
    counts = asimov_problem["counts"]
    object.__setattr__(
        counts,
        "rows",
        tuple(row for row in counts.rows if row.orientation != "perpendicular"),
    )

    with pytest.raises(PolarizationContractError, match="complete.*count"):
        sigma_fit.fit_sigma_forward_folded(**asimov_problem)
