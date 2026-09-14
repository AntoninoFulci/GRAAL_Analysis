"""Acceptance-aware binned Poisson fit for beam asymmetry Sigma."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

import numpy as np
from scipy.optimize import minimize
from scipy.special import xlogy

from analysis_config import (
    AnalysisConfig,
    RESPONSE_SCHEMA_APPROVAL_ID,
    RESPONSE_SCHEMA_PATH,
)
from azimuth_counts import (
    AzimuthCountRow,
    AzimuthCountTable,
    CountAuthority,
    _authority_fingerprint,
    _reload_count_authority,
    _validate_table_for_publication,
)
from contracts import PolarizationContractError, SHA256_PATTERN
from phi_response import PhiResponse, ResponseKey, TrueCellKey


@dataclass(frozen=True)
class SigmaFitResult:
    """Fit estimate, covariance, and bin-level diagnostics."""

    sigma: float
    stat_uncertainty: float
    state_scales: tuple[float, float]
    covariance: np.ndarray
    converged: bool
    pearson_chi2: float
    ndof: int
    residuals: np.ndarray
    expected: np.ndarray


@dataclass(frozen=True)
class JointSigmaFitResult:
    """Canonical aggregate of independent physical-group joint fits."""

    bin_keys: tuple[str, ...]
    nuisance_keys: tuple[str, ...]
    row_keys: tuple[str, ...]
    sigma: np.ndarray
    log_yield: np.ndarray
    hessian_covariance: np.ndarray
    expected: np.ndarray
    residuals: np.ndarray
    deviance_contributions: np.ndarray
    deviance: float
    ndof: int
    converged: bool
    rank: int
    replica_id: int


@dataclass(frozen=True)
class _GroupFit:
    """One independently fitted response-key block in canonical row order."""

    sigma: np.ndarray
    log_yield: np.ndarray
    sigma_covariance: np.ndarray
    rows: tuple[AzimuthCountRow, ...]
    expected: np.ndarray
    rank: int


_ORIENTATIONS = ("parallel", "perpendicular")
_ACCEPTANCE_HANDOFF_PARENT = "results/physics/normalization/handoffs"


def _approved_reviewers(reviewers: object) -> bool:
    return (
        isinstance(reviewers, tuple)
        and len(reviewers) >= 2
        and all(
            isinstance(reviewer, str) and reviewer.strip()
            for reviewer in reviewers
        )
        and len(set(reviewers)) == len(reviewers)
    )


def _approved_digest(value: object) -> bool:
    return isinstance(value, str) and SHA256_PATTERN.fullmatch(value) is not None


def _positive_definite_covariance(
    raw: object, dimension: int, label: str
) -> np.ndarray:
    """Return symmetric covariance after explicit scale-aware PD validation."""
    covariance = np.asarray(raw, dtype=float)
    if covariance.shape != (dimension, dimension) or not np.all(
        np.isfinite(covariance)
    ):
        raise PolarizationContractError(f"{label} must be finite and square")
    scale = max(float(np.max(np.abs(covariance))), np.finfo(float).tiny)
    tolerance = 64.0 * np.finfo(float).eps * dimension * scale
    if not np.allclose(covariance, covariance.T, rtol=0.0, atol=tolerance):
        raise PolarizationContractError(f"{label} must be symmetric positive definite")
    symmetric = (covariance + covariance.T) / 2.0
    eigenvalues = np.linalg.eigvalsh(symmetric)
    if (
        eigenvalues[0] <= tolerance
        or np.linalg.matrix_rank(symmetric, tol=tolerance) != dimension
    ):
        raise PolarizationContractError(f"{label} must be symmetric positive definite")
    return symmetric


def azimuth_bin_average(low: np.ndarray, high: np.ndarray) -> np.ndarray:
    """Return the exact average of cos(2 phi) over each half-open bin."""
    low_array = np.asarray(low, dtype=float)
    high_array = np.asarray(high, dtype=float)
    if (
        low_array.ndim != 1
        or high_array.ndim != 1
        or low_array.shape != high_array.shape
        or low_array.size == 0
        or not np.all(np.isfinite(low_array))
        or not np.all(np.isfinite(high_array))
        or np.any(high_array <= low_array)
    ):
        raise PolarizationContractError("azimuth bin edges must be finite intervals")
    return (np.sin(2.0 * high_array) - np.sin(2.0 * low_array)) / (
        2.0 * (high_array - low_array)
    )


def _sigma_bin_key(key: ResponseKey, mass_bin: int) -> str:
    fields = (
        key.channel,
        key.target,
        key.beam_group,
        format(key.Egamma_low, ".17g"),
        format(key.Egamma_high, ".17g"),
        format(key.cos_theta_low, ".17g"),
        format(key.cos_theta_high, ".17g"),
        key.observable,
        key.selection_id,
        str(mass_bin),
    )
    return "|".join(fields)


def _row_key(row: AzimuthCountRow) -> ResponseKey:
    return ResponseKey(
        row.channel,
        row.target,
        row.beam_group,
        row.Egamma_low,
        row.Egamma_high,
        row.cos_theta_low,
        row.cos_theta_high,
        row.observable,
        row.selection_id,
    )


def canonical_count_row_key(row: AzimuthCountRow) -> str:
    """Return the stable result-vector key for one reconstructed count cell."""
    key = _row_key(row)
    fields = (
        _sigma_bin_key(key, row.reco_mass_bin),
        row.source_period,
        row.orientation,
        str(row.replica_id),
        str(row.reco_phi_bin),
    )
    return "|".join(fields)


def _row_order(row: AzimuthCountRow) -> tuple[object, ...]:
    return (
        _row_key(row),
        row.source_period,
        row.orientation,
        row.replica_id,
        row.reco_mass_bin,
        row.reco_phi_bin,
    )


def _require_approved_fit_config(config: AnalysisConfig) -> dict[str, int]:
    if not isinstance(config, AnalysisConfig) or config.status != "approved" or config.blocked_reasons:
        raise PolarizationContractError(
            "forward-folded fit requires an approved canonical config"
        )
    if (
        type(config.schema_version) is not int
        or config.schema_version != 1
        or config.analysis_version != "polarization-v1"
    ):
        raise PolarizationContractError(
            "forward-folded fit config schema/analysis version is unsupported"
        )
    release_id = config.acceptance_release_id
    if (
        not isinstance(release_id, str)
        or not release_id.strip()
        or "/" in release_id
        or config.acceptance_handoff_directory
        != f"{_ACCEPTANCE_HANDOFF_PARENT}/{release_id}"
        or not _approved_digest(config.acceptance_qa_sha256)
    ):
        raise PolarizationContractError(
            "forward-folded fit requires an approved acceptance authority"
        )
    if (
        config.phi_response_schema_path != RESPONSE_SCHEMA_PATH
        or not _approved_digest(config.phi_response_schema_sha256)
        or config.phi_response_schema_approval_id != RESPONSE_SCHEMA_APPROVAL_ID
        or not _approved_reviewers(config.phi_response_schema_reviewers)
    ):
        raise PolarizationContractError(
            "forward-folded fit requires an approved response schema authority"
        )
    if (
        config.sign_status != "approved"
        or not isinstance(config.sign_approval_id, str)
        or not config.sign_approval_id.strip()
        or not _approved_reviewers(config.sign_reviewers)
    ):
        raise PolarizationContractError(
            "forward-folded fit requires an approved sign authority"
        )
    signs = dict(config.orientation_signs)
    if (
        len(signs) != len(config.orientation_signs)
        or tuple(sorted(signs.items())) != config.orientation_signs
        or set(signs) != set(_ORIENTATIONS)
        or set(signs.values()) != {-1, 1}
    ):
        raise PolarizationContractError(
            "forward-folded fit requires the approved exact orientation sign mapping"
        )
    qa = config.release_qa
    if (
        qa.status != "approved"
        or not isinstance(qa.approval_id, str)
        or not qa.approval_id.strip()
        or not _approved_reviewers(qa.reviewers)
        or type(qa.minimum_events_per_bin) is not int
        or qa.minimum_events_per_bin <= 0
        or not isinstance(qa.maximum_deviance_per_ndof, (float, int))
        or isinstance(qa.maximum_deviance_per_ndof, bool)
        or not math.isfinite(float(qa.maximum_deviance_per_ndof))
        or qa.maximum_deviance_per_ndof <= 0.0
    ):
        raise PolarizationContractError(
            "forward-folded fit requires an approved finite release QA policy"
        )
    return signs


def _require_approved_bootstrap_config(config: AnalysisConfig):
    bootstrap = config.bootstrap
    numeric = (
        bootstrap.maximum_failed_fraction,
        bootstrap.hessian_diagonal_ratio_min,
        bootstrap.hessian_diagonal_ratio_max,
    )
    if (
        type(bootstrap.replicas) is not int
        or bootstrap.replicas <= 0
        or bootstrap.algorithm_version != "poisson1-sha256-v1"
        or type(bootstrap.seed) is not int
        or bootstrap.seed < 0
        or any(
            not isinstance(value, (float, int))
            or isinstance(value, bool)
            or not math.isfinite(float(value))
            for value in numeric
        )
        or bootstrap.maximum_failed_fraction < 0.0
        or bootstrap.maximum_failed_fraction > 1.0
        or bootstrap.hessian_diagonal_ratio_min <= 0.0
        or bootstrap.hessian_diagonal_ratio_max
        < bootstrap.hessian_diagonal_ratio_min
    ):
        raise PolarizationContractError(
            "bootstrap covariance requires an approved bootstrap config"
        )
    return bootstrap


def _axis(raw: object, label: str, *, phi: bool = False) -> np.ndarray:
    try:
        axis = np.asarray(raw, dtype=float)
    except (TypeError, ValueError) as exc:
        raise PolarizationContractError(f"response {label} axis must be numeric") from exc
    if (
        axis.ndim != 1
        or axis.size < 2
        or not np.all(np.isfinite(axis))
        or np.any(np.diff(axis) <= 0.0)
    ):
        raise PolarizationContractError(
            f"response {label} axis must be a finite increasing partition"
        )
    if phi and (
        not np.isclose(axis[0], 0.0, rtol=0.0, atol=1e-14)
        or not np.isclose(axis[-1], np.pi, rtol=0.0, atol=1e-14)
    ):
        raise PolarizationContractError("response azimuth axis must cover [0, pi]")
    return axis


def _require_valid_response_blocks(
    response: PhiResponse, config: AnalysisConfig
) -> dict[ResponseKey, tuple[np.ndarray, np.ndarray]]:
    if not isinstance(response, PhiResponse):
        raise PolarizationContractError("forward-folded fit requires a PhiResponse")
    if not all(
        _approved_digest(value)
        for value in (
            response.source_sha256,
            response.input_sha256,
            response.config_sha256,
        )
    ):
        raise PolarizationContractError(
            "forward-folded fit response authority identity is invalid"
        )
    if not response.keys or response.keys != tuple(sorted(response.keys)) or len(set(response.keys)) != len(response.keys):
        raise PolarizationContractError("response keys must be unique and canonical")
    if set(response.mass_edges) != set(response.keys) or set(response.phi_edges) != set(response.keys):
        raise PolarizationContractError("response keys and axes must match exactly")
    axes = {}
    expected = {
        TrueCellKey(key, orientation, true_cell)
        for key in response.keys
        for orientation in _ORIENTATIONS
        for true_cell in range(
            (len(response.mass_edges[key]) - 1)
            * (len(response.phi_edges[key]) - 1)
        )
    }
    if set(response.validity) != expected or any(
        response.validity[cell] != "valid" for cell in expected
    ):
        raise PolarizationContractError(
            "forward-folded fit requires every response block to be valid"
        )
    expected_matrices = {(key, orientation) for key in response.keys for orientation in _ORIENTATIONS}
    if set(response.matrices) != expected_matrices:
        raise PolarizationContractError("response requires both mandatory orientations")
    tolerance = config.response_validation.probability_absolute_tolerance
    if not isinstance(tolerance, (float, int)) or isinstance(tolerance, bool) or not math.isfinite(float(tolerance)) or tolerance < 0.0:
        raise PolarizationContractError("response probability tolerance must be finite")
    for key in response.keys:
        mass_axis = _axis(response.mass_edges[key], "mass")
        phi_axis = _axis(response.phi_edges[key], "azimuth", phi=True)
        if mass_axis.size - 1 != config.figure4_mass_bins or phi_axis.size - 1 != config.figure4_phi_bins:
            raise PolarizationContractError("response axes disagree with approved fit binning")
        cells = (mass_axis.size - 1) * (phi_axis.size - 1)
        for orientation in _ORIENTATIONS:
            matrix = np.asarray(response.matrix(key, orientation), dtype=float)
            if matrix.shape != (cells, cells) or not np.all(np.isfinite(matrix)) or np.any(matrix < 0.0):
                raise PolarizationContractError("response matrix must be finite, nonnegative, and square")
            if np.any(np.sum(matrix, axis=0) > 1.0 + tolerance):
                raise PolarizationContractError("response matrix exceeds its generated normalization")
        axes[key] = (mass_axis, phi_axis)
    return axes


def _same_axis(actual: Sequence[float], expected: np.ndarray) -> bool:
    return len(actual) == expected.size and np.allclose(
        actual, expected, rtol=0.0, atol=1e-14
    )


def _validate_counts_for_fit(
    counts: AzimuthCountTable,
    response: PhiResponse,
    axes: dict[ResponseKey, tuple[np.ndarray, np.ndarray]],
    *,
    config: AnalysisConfig,
    replica_id: int,
) -> tuple[AzimuthCountRow, ...]:
    if not isinstance(counts, AzimuthCountTable):
        raise PolarizationContractError("forward-folded fit requires an azimuth count table")
    expected_replicas = tuple(range(config.bootstrap.replicas + 1))
    if counts.expected_replica_ids != expected_replicas:
        raise PolarizationContractError(
            "forward-folded fit count replica universe disagrees with approved B"
        )
    if any(
        expected.analysis_version != config.analysis_version
        for expected in counts.expected_universe
    ) or any(
        row.schema_version != config.schema_version
        or row.analysis_version != config.analysis_version
        for row in counts.rows
    ):
        raise PolarizationContractError(
            "forward-folded fit count/config analysis version mismatch"
        )
    if type(replica_id) is not int or replica_id < 0 or replica_id not in counts.replica_ids:
        raise PolarizationContractError("forward-folded fit replica ID is not present in counts")
    selected = tuple(sorted(
        (row for row in counts.rows if row.replica_id == replica_id), key=_row_order
    ))
    if not selected:
        raise PolarizationContractError("forward-folded fit replica has no count rows")
    expected_states = {
        (expected.response_key, expected.source_period, expected.orientation): expected
        for expected in counts.expected_universe
    }
    if len(expected_states) != len(counts.expected_universe):
        raise PolarizationContractError(
            "forward-folded fit expected universe must be unique and canonical"
        )
    actual_states: dict[tuple[ResponseKey, str, str], list[AzimuthCountRow]] = {}
    for row in selected:
        state = (_row_key(row), row.source_period, row.orientation)
        actual_states.setdefault(state, []).append(row)
    if set(axes) != {state[0] for state in expected_states}:
        raise PolarizationContractError("forward-folded fit response/count keys must match exactly")
    if set(expected_states) != set(actual_states):
        if {state[0] for state in actual_states} != set(axes):
            raise PolarizationContractError(
                "forward-folded fit response/count keys must match exactly"
            )
        raise PolarizationContractError(
            "forward-folded fit requires a complete canonical count grid"
        )
    periods: dict[ResponseKey, dict[str, set[str]]] = {}
    for state, expected in expected_states.items():
        key, period, orientation = state
        periods.setdefault(key, {}).setdefault(period, set()).add(orientation)
        mass_axis, phi_axis = axes[key]
        if not _same_axis(expected.reco_mass_edges, mass_axis) or not _same_axis(expected.reco_phi_edges, phi_axis):
            raise PolarizationContractError("count expected axis disagrees with response axis")
        actual = actual_states[state]
        cell_count = (mass_axis.size - 1) * (phi_axis.size - 1)
        actual_cells = {
            (
                row.reco_mass_bin,
                row.reco_phi_bin,
                row.reco_mass_low_gev,
                row.reco_mass_high_gev,
                row.reco_phi_low,
                row.reco_phi_high,
            )
            for row in actual
        }
        wanted_cells = {
            (
                mass_bin,
                phi_bin,
                mass_axis[mass_bin],
                mass_axis[mass_bin + 1],
                phi_axis[phi_bin],
                phi_axis[phi_bin + 1],
            )
            for mass_bin in range(mass_axis.size - 1)
            for phi_bin in range(phi_axis.size - 1)
        }
        if len(actual) != cell_count or actual_cells != wanted_cells:
            raise PolarizationContractError("count axis/cell grid disagrees with response")
        for row in actual:
            for value, label in (
                (row.exposure, "exposure"),
                (row.beam_polarization, "polarization"),
            ):
                if (
                    not isinstance(value, (float, int))
                    or isinstance(value, bool)
                    or not math.isfinite(float(value))
                ):
                    raise PolarizationContractError(f"count finite {label} is required")
        exposure = {row.exposure for row in actual}
        polarization = {row.beam_polarization for row in actual}
        if len(exposure) != 1 or len(polarization) != 1:
            raise PolarizationContractError("count state has inconsistent exposure or polarization")
        if next(iter(exposure)) <= 0.0 or not 0.0 < next(iter(polarization)) <= 1.0:
            raise PolarizationContractError("count exposure/polarization must be positive")
        if any(type(row.observed_count) is not int or row.observed_count < 0 for row in actual):
            raise PolarizationContractError("count observed values must be nonnegative integers")
    if any(orients != set(_ORIENTATIONS) for group in periods.values() for orients in group.values()):
        raise PolarizationContractError("forward-folded fit requires both orientations per period")
    if not counts.has_every_reco_cell():
        raise PolarizationContractError(
            "forward-folded fit requires a complete canonical count grid"
        )
    return selected


def _fit_one_response_key(
    key: ResponseKey,
    rows: tuple[AzimuthCountRow, ...],
    response: PhiResponse,
    signs: dict[str, int],
) -> _GroupFit:
    mass_edges = np.asarray(response.mass_edges[key], dtype=float)
    phi_edges = np.asarray(response.phi_edges[key], dtype=float)
    mass_bins = mass_edges.size - 1
    phi_bins = phi_edges.size - 1
    cells = mass_bins * phi_bins
    widths = np.diff(phi_edges)
    averages = azimuth_bin_average(phi_edges[:-1], phi_edges[1:])
    by_state: dict[tuple[str, str], list[AzimuthCountRow]] = {}
    for row in rows:
        by_state.setdefault((row.source_period, row.orientation), []).append(row)

    state_data: list[tuple[tuple[AzimuthCountRow, ...], str, np.ndarray, float, float]] = []
    observed_parts = []
    design_parts = []
    for (_, orientation), state_rows in sorted(by_state.items()):
        matrix = np.asarray(response.matrix(key, orientation), dtype=float)
        ordered = tuple(sorted(state_rows, key=lambda row: (row.reco_mass_bin, row.reco_phi_bin)))
        exposure = float(ordered[0].exposure)
        polarization = float(ordered[0].beam_polarization)
        observed = np.asarray([row.observed_count for row in ordered], dtype=float)
        design = np.empty((cells, mass_bins), dtype=float)
        for mass_bin in range(mass_bins):
            truth = np.zeros((mass_bins, phi_bins), dtype=float)
            truth[mass_bin, :] = widths / np.pi
            design[:, mass_bin] = exposure * (matrix @ truth.reshape(-1))
        state_data.append((ordered, orientation, matrix, exposure, polarization))
        observed_parts.append(observed)
        design_parts.append(design)

    observed_all = np.concatenate(observed_parts)
    design_all = np.vstack(design_parts)
    initial_yield = np.linalg.lstsq(design_all, observed_all, rcond=None)[0]
    initial_yield = np.clip(initial_yield, np.exp(-30.0), np.exp(30.0))
    initial = np.concatenate((np.zeros(mass_bins), np.log(initial_yield)))

    def model_and_jacobian(parameters: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        sigma = parameters[:mass_bins]
        yields = np.exp(parameters[mass_bins:])
        expected_parts = []
        jacobian_parts = []
        for _, orientation, matrix, exposure, polarization in state_data:
            modulation = signs[orientation] * polarization
            truth = yields[:, None] * widths[None, :] / np.pi
            truth = truth * (
                1.0 + modulation * sigma[:, None] * averages[None, :]
            )
            expected = exposure * (matrix @ truth.reshape(-1))
            jacobian = np.empty((cells, 2 * mass_bins), dtype=float)
            for mass_bin in range(mass_bins):
                derivative_sigma = np.zeros((mass_bins, phi_bins), dtype=float)
                derivative_sigma[mass_bin, :] = (
                    yields[mass_bin]
                    * widths
                    / np.pi
                    * modulation
                    * averages
                )
                derivative_log_yield = np.zeros((mass_bins, phi_bins), dtype=float)
                derivative_log_yield[mass_bin, :] = truth[mass_bin, :]
                jacobian[:, mass_bin] = exposure * (
                    matrix @ derivative_sigma.reshape(-1)
                )
                jacobian[:, mass_bins + mass_bin] = exposure * (
                    matrix @ derivative_log_yield.reshape(-1)
                )
            expected_parts.append(expected)
            jacobian_parts.append(jacobian)
        return np.concatenate(expected_parts), np.vstack(jacobian_parts)

    def objective_and_gradient(parameters: np.ndarray) -> tuple[float, np.ndarray]:
        expected, jacobian = model_and_jacobian(parameters)
        if np.any(expected <= 0.0) or not np.all(np.isfinite(expected)):
            return float("inf"), np.zeros_like(parameters)
        factor = 1.0 - observed_all / expected
        return float(np.sum(expected - xlogy(observed_all, expected))), jacobian.T @ factor

    initial_expected, _ = model_and_jacobian(initial)
    if np.any(initial_expected <= 0.0) or not np.all(np.isfinite(initial_expected)):
        raise PolarizationContractError(
            "forward-folded Sigma fit requires positive finite expected counts"
        )

    optimization = minimize(
        objective_and_gradient,
        initial,
        method="L-BFGS-B",
        jac=True,
        bounds=((-1.0, 1.0),) * mass_bins + ((-30.0, 30.0),) * mass_bins,
        options={"ftol": 1e-12, "gtol": 1e-8, "maxiter": 2000},
    )
    if not optimization.success or not np.all(np.isfinite(optimization.x)):
        raise PolarizationContractError(
            f"forward-folded Sigma fit did not converge: {optimization.message}"
        )
    if np.any(np.abs(optimization.x[:mass_bins]) >= 0.995) or np.any(
        np.abs(optimization.x[mass_bins:]) >= 29.5
    ):
        raise PolarizationContractError(
            "forward-folded Sigma fit is pegged at a parameter boundary"
        )
    expected_all, jacobian = model_and_jacobian(optimization.x)
    fisher = jacobian.T @ (jacobian / expected_all[:, None])
    rank = int(np.linalg.matrix_rank(fisher))
    if rank != 2 * mass_bins:
        raise PolarizationContractError("forward-folded Sigma fit has insufficient rank")
    try:
        covariance = np.linalg.inv(fisher)
    except np.linalg.LinAlgError as exc:
        raise PolarizationContractError(
            "forward-folded Sigma fit covariance is singular"
        ) from exc
    covariance = _positive_definite_covariance(
        covariance, 2 * mass_bins, "forward-folded Sigma fit covariance"
    )
    return _GroupFit(
        sigma=optimization.x[:mass_bins].copy(),
        log_yield=optimization.x[mass_bins:].copy(),
        sigma_covariance=covariance[:mass_bins, :mass_bins].copy(),
        rows=tuple(row for ordered, *_ in state_data for row in ordered),
        expected=expected_all.copy(),
        rank=rank,
    )


def _fit_sigma_forward_folded_core(
    counts: AzimuthCountTable,
    response: PhiResponse,
    *,
    config: AnalysisConfig,
    replica_id: int = 0,
) -> JointSigmaFitResult:
    """Fit trusted inputs or synthetic fixtures through the numerical core."""
    signs = _require_approved_fit_config(config)
    _require_approved_bootstrap_config(config)
    axes = _require_valid_response_blocks(response, config)
    selected_rows = _validate_counts_for_fit(
        counts, response, axes, config=config, replica_id=replica_id
    )
    grouped = {
        key: tuple(row for row in selected_rows if _row_key(row) == key)
        for key in response.keys
    }
    sigma_parts = []
    log_yield_parts = []
    covariance_parts = []
    ordered_rows = []
    expected_parts = []
    ranks = []
    bin_keys = []
    for key in response.keys:
        group = _fit_one_response_key(
            key, grouped[key], response, signs
        )
        mass_bins = group.sigma.size
        observed = np.asarray([row.observed_count for row in group.rows], dtype=float)
        contributions = 2.0 * (
            xlogy(observed, observed / group.expected) - (observed - group.expected)
        )
        ndof = observed.size - 2 * mass_bins
        if ndof <= 0 or not np.all(np.isfinite(contributions)):
            raise PolarizationContractError("forward-folded Sigma fit has invalid residual QA")
        if float(np.sum(contributions)) / ndof > config.release_qa.maximum_deviance_per_ndof:
            raise PolarizationContractError(
                "forward-folded Sigma fit exceeds approved deviance/ndof"
            )
        for mass_bin in range(mass_bins):
            event_count = sum(
                row.observed_count for row in group.rows if row.reco_mass_bin == mass_bin
            )
            if event_count < config.release_qa.minimum_events_per_bin:
                raise PolarizationContractError(
                    "forward-folded Sigma fit fails approved minimum event count"
                )
        sigma_parts.append(group.sigma)
        log_yield_parts.append(group.log_yield)
        covariance_parts.append(group.sigma_covariance)
        ordered_rows.extend(group.rows)
        expected_parts.append(group.expected)
        ranks.append(group.rank)
        bin_keys.extend(_sigma_bin_key(key, index) for index in range(mass_bins))
    sigma_all = np.concatenate(sigma_parts)
    log_yield_all = np.concatenate(log_yield_parts)
    covariance_all = np.zeros((sigma_all.size, sigma_all.size), dtype=float)
    offset = 0
    for block in covariance_parts:
        size = block.shape[0]
        covariance_all[offset : offset + size, offset : offset + size] = block
        offset += size
    expected = np.concatenate(expected_parts)
    observed = np.asarray([row.observed_count for row in ordered_rows], dtype=float)
    residuals = (observed - expected) / np.sqrt(expected)
    deviance_contributions = 2.0 * (
        xlogy(observed, observed / expected) - (observed - expected)
    )
    return JointSigmaFitResult(
        bin_keys=tuple(bin_keys),
        nuisance_keys=tuple(f"{key}|log_yield" for key in bin_keys),
        row_keys=tuple(canonical_count_row_key(row) for row in ordered_rows),
        sigma=sigma_all,
        log_yield=log_yield_all,
        hessian_covariance=covariance_all,
        expected=expected,
        residuals=residuals,
        deviance_contributions=deviance_contributions,
        deviance=float(np.sum(deviance_contributions)),
        ndof=len(ordered_rows) - 2 * sigma_all.size,
        converged=True,
        rank=sum(ranks),
        replica_id=replica_id,
    )


def fit_sigma_forward_folded(
    counts: AzimuthCountTable,
    *,
    authority: CountAuthority,
    replica_id: int = 0,
) -> JointSigmaFitResult:
    """Fit counts using only freshly authenticated config and N3 response bytes.

    ``CountAuthority`` is loader-sealed and retains every transitive source
    byte used by N2 count construction and the N3 handoff.  Reloading from its
    canonical paths prevents caller-provided digest strings or detached
    ``AnalysisConfig``/``PhiResponse`` objects from becoming fit authority.
    """
    if type(authority) is not CountAuthority:
        raise PolarizationContractError(
            "forward-folded fit requires authenticated authority"
        )
    original_fingerprint = _authority_fingerprint(authority)
    fresh = _reload_count_authority(authority)
    if _authority_fingerprint(fresh) != original_fingerprint:
        raise PolarizationContractError(
            "forward-folded fit authority changed after authentication"
        )
    _validate_table_for_publication(counts, fresh)
    return _fit_sigma_forward_folded_core(
        counts,
        fresh.response,
        config=fresh.config,
        replica_id=replica_id,
    )


def bootstrap_sigma_covariance(
    sigma_vectors: np.ndarray,
    bin_keys: Sequence[str],
    *,
    replica_ids: Sequence[int],
    config: AnalysisConfig,
    hessian_covariance: np.ndarray,
    failed_replica_ids: Sequence[int] = (),
) -> np.ndarray:
    """Validate and return bootstrap covariance in canonical shared-event order.

    The caller supplies the already-concatenated vectors for every observable
    and kinematic group.  Keeping that concatenation outside this module is
    what retains cross-observable covariance from shared event multipliers.
    """
    _require_approved_fit_config(config)
    bootstrap = _require_approved_bootstrap_config(config)
    values = np.asarray(sigma_vectors, dtype=float)
    keys = tuple(bin_keys)
    successful = tuple(replica_ids)
    failed = tuple(failed_replica_ids)
    dimension = len(keys)
    if (
        values.ndim != 2
        or values.shape[1] != dimension
        or values.shape[0] != len(successful)
        or dimension == 0
        or len(set(keys)) != dimension
        or any(not isinstance(key, str) or not key for key in keys)
        or not np.all(np.isfinite(values))
    ):
        raise PolarizationContractError("bootstrap Sigma matrix and bin keys are invalid")
    if (
        any(type(identifier) is not int or identifier < 1 for identifier in (*successful, *failed))
        or successful != tuple(sorted(successful))
        or failed != tuple(sorted(failed))
        or len(set(successful)) != len(successful)
        or len(set(failed)) != len(failed)
        or set(successful) & set(failed)
        or set((*successful, *failed)) != set(range(1, bootstrap.replicas + 1))
    ):
        raise PolarizationContractError("bootstrap replica IDs must canonically cover 1..B")
    failed_fraction = len(failed) / bootstrap.replicas
    if failed_fraction > bootstrap.maximum_failed_fraction:
        raise PolarizationContractError("bootstrap failed replica fraction exceeds approved limit")
    if values.shape[0] <= dimension:
        raise PolarizationContractError("bootstrap successful replica count must exceed Sigma dimension")
    covariance = np.cov(values, rowvar=False, ddof=1)
    covariance = np.atleast_2d(np.asarray(covariance, dtype=float))
    if covariance.shape != (dimension, dimension) or not np.all(np.isfinite(covariance)):
        raise PolarizationContractError("bootstrap covariance must be finite and square")
    covariance = (covariance + covariance.T) / 2.0
    scale = max(1.0, float(np.max(np.abs(covariance))))
    if np.linalg.eigvalsh(covariance)[0] < -1e-12 * scale:
        raise PolarizationContractError("bootstrap covariance is not positive semidefinite")
    if np.linalg.matrix_rank(covariance) != dimension:
        raise PolarizationContractError("bootstrap covariance has insufficient rank")
    hessian = _positive_definite_covariance(
        hessian_covariance, dimension, "Hessian covariance"
    )
    bootstrap_diagonal = np.diag(covariance)
    if np.any(bootstrap_diagonal <= 0.0):
        raise PolarizationContractError("bootstrap covariance has nonpositive diagonal")
    ratio = np.diag(hessian) / bootstrap_diagonal
    if np.any(
        (ratio < bootstrap.hessian_diagonal_ratio_min)
        | (ratio > bootstrap.hessian_diagonal_ratio_max)
    ):
        raise PolarizationContractError(
            "Hessian/bootstrap diagonal ratio exceeds approved limits"
        )
    return covariance


def _array(raw, label: str) -> np.ndarray:
    try:
        value = np.asarray(raw, dtype=float)
    except (TypeError, ValueError) as exc:
        raise PolarizationContractError(f"{label} must be numeric") from exc
    if value.ndim != 1:
        raise PolarizationContractError(f"{label} must be one-dimensional")
    if not np.all(np.isfinite(value)):
        raise PolarizationContractError(f"{label} must be finite")
    return value


def _validated_inputs(
    phi,
    orientation_sign,
    polarization,
    acceptance,
    exposure,
    observed,
) -> tuple[np.ndarray, ...]:
    arrays = tuple(
        _array(raw, label)
        for raw, label in (
            (phi, "phi"),
            (orientation_sign, "orientation_sign"),
            (polarization, "polarization"),
            (acceptance, "acceptance"),
            (exposure, "exposure"),
            (observed, "observed"),
        )
    )
    if len({value.shape for value in arrays}) != 1:
        raise PolarizationContractError("fit inputs must all have same shape")
    phi_array, sign, pol, acc, exp, counts = arrays
    if phi_array.size < 8:
        raise PolarizationContractError("fit needs at least eight populated angular bins")
    if np.any((phi_array < 0.0) | (phi_array >= np.pi)):
        raise PolarizationContractError("phi must lie in [0, pi)")
    if not np.all(np.isin(sign, (-1.0, 1.0))) or set(sign) != {-1.0, 1.0}:
        raise PolarizationContractError("orientation_sign must contain both -1 and +1")
    if np.any((pol <= 0.0) | (pol > 1.0)):
        raise PolarizationContractError("polarization must lie in (0, 1]")
    if np.any((acc <= 0.0) | (acc > 1.0)):
        raise PolarizationContractError("acceptance must lie in (0, 1]")
    if np.any(exp <= 0.0):
        raise PolarizationContractError("exposure must be positive")
    if np.any(counts < 0.0):
        raise PolarizationContractError("observed counts must be nonnegative")
    modulation = np.cos(2.0 * phi_array)
    if np.unique(np.round(phi_array, 12)).size < 4 or np.ptp(modulation) < 1.0:
        raise PolarizationContractError("insufficient angular coverage for cos(2phi) fit")
    return arrays


def fit_sigma_binned(
    *,
    phi,
    orientation_sign,
    polarization,
    acceptance,
    exposure,
    observed,
) -> SigmaFitResult:
    """Fit Sigma and one positive normalization nuisance per orientation."""
    phi_array, sign, pol, acc, exp, counts = _validated_inputs(
        phi, orientation_sign, polarization, acceptance, exposure, observed
    )
    base = exp * acc
    modulation = sign * pol * np.cos(2.0 * phi_array)
    state_masks = (sign < 0.0, sign > 0.0)
    initial_scales = []
    for mask in state_masks:
        denominator = float(np.sum(base[mask]))
        numerator = float(np.sum(counts[mask]))
        initial_scales.append(max(numerator / denominator, 1e-9))
    initial = np.array([0.0, np.log(initial_scales[0]), np.log(initial_scales[1])])

    def model(parameters: np.ndarray) -> np.ndarray:
        sigma = parameters[0]
        scales = np.where(sign < 0.0, np.exp(parameters[1]), np.exp(parameters[2]))
        return base * scales * (1.0 + sigma * modulation)

    def objective_and_gradient(parameters: np.ndarray) -> tuple[float, np.ndarray]:
        expected = model(parameters)
        if np.any(expected <= 0.0) or not np.all(np.isfinite(expected)):
            return float("inf"), np.zeros(3)
        nll = float(np.sum(expected - counts * np.log(expected)))
        factor = 1.0 - counts / expected
        scales = np.where(sign < 0.0, np.exp(parameters[1]), np.exp(parameters[2]))
        derivative_sigma = base * scales * modulation
        gradient = np.array(
            [
                np.sum(factor * derivative_sigma),
                np.sum(factor[state_masks[0]] * expected[state_masks[0]]),
                np.sum(factor[state_masks[1]] * expected[state_masks[1]]),
            ],
            dtype=float,
        )
        return nll, gradient

    optimization = minimize(
        objective_and_gradient,
        initial,
        method="L-BFGS-B",
        jac=True,
        bounds=((-1.0, 1.0), (-30.0, 30.0), (-30.0, 30.0)),
        options={"ftol": 1e-12, "gtol": 1e-8, "maxiter": 2000},
    )
    if not optimization.success or not np.all(np.isfinite(optimization.x)):
        raise PolarizationContractError(
            f"Sigma fit did not converge: {optimization.message}"
        )
    expected = model(optimization.x)
    sigma = float(optimization.x[0])
    scales = np.where(sign < 0.0, np.exp(optimization.x[1]), np.exp(optimization.x[2]))
    derivatives = np.column_stack(
        (
            base * scales * modulation,
            np.where(sign < 0.0, expected, 0.0),
            np.where(sign > 0.0, expected, 0.0),
        )
    )
    fisher = derivatives.T @ (derivatives / expected[:, None])
    try:
        covariance = np.linalg.inv(fisher)
    except np.linalg.LinAlgError as exc:
        raise PolarizationContractError("Sigma fit covariance is singular") from exc
    if not np.all(np.isfinite(covariance)) or covariance[0, 0] <= 0.0:
        raise PolarizationContractError("Sigma fit covariance is nonphysical")
    residuals = (counts - expected) / np.sqrt(expected)
    pearson_chi2 = float(np.sum(residuals**2))
    return SigmaFitResult(
        sigma=sigma,
        stat_uncertainty=float(np.sqrt(covariance[0, 0])),
        state_scales=(float(np.exp(optimization.x[1])), float(np.exp(optimization.x[2]))),
        covariance=covariance,
        converged=True,
        pearson_chi2=pearson_chi2,
        ndof=int(phi_array.size - 3),
        residuals=residuals,
        expected=expected,
    )
