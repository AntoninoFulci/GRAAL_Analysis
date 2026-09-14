"""Deterministic propagation of N3 response statistical covariance."""

from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Literal

import numpy as np

from analysis_config import AnalysisConfig
from acceptance_handoff import ResponseCovarianceScope
from azimuth_counts import AzimuthCountTable
from contracts import PolarizationContractError
from phi_response import PhiResponse, ResponseKey, TrueCellKey
from sigma_fit import JointSigmaFitResult, _fit_sigma_forward_folded_core


@dataclass(frozen=True)
class ResponseModeRefit:
    """Auditable finite-difference action for one retained response mode."""

    mode_id: str
    eigenvalue: float
    step: float
    scheme: Literal["central", "forward", "backward"]
    derivative: np.ndarray
    lower_sigma: np.ndarray | None
    upper_sigma: np.ndarray | None


@dataclass(frozen=True)
class ResponsePropagationResult:
    """Response-statistical covariance aligned to canonical Sigma bin keys."""

    covariance: np.ndarray
    retained_modes: tuple[str, ...]
    refits: tuple[ResponseModeRefit, ...]
    valid: bool


def _covariance_eigenmodes(
    covariance: object, *, tolerance: float
) -> tuple[tuple[float, np.ndarray], ...]:
    """Return retained covariance eigenmodes in deterministic order."""
    try:
        matrix = np.asarray(covariance, dtype=float)
    except (TypeError, ValueError) as exc:
        raise PolarizationContractError(
            "response covariance must be numeric"
        ) from exc
    if (
        matrix.ndim != 2
        or matrix.shape[0] != matrix.shape[1]
        or matrix.shape[0] == 0
        or not np.all(np.isfinite(matrix))
        or not isinstance(tolerance, (float, int))
        or isinstance(tolerance, bool)
        or not math.isfinite(float(tolerance))
        or tolerance < 0.0
    ):
        raise PolarizationContractError(
            "response covariance and eigenvalue tolerance must be finite"
        )
    if not np.allclose(matrix, matrix.T, rtol=0.0, atol=tolerance):
        raise PolarizationContractError("response covariance must be symmetric")
    eigenvalues, eigenvectors = np.linalg.eigh((matrix + matrix.T) / 2.0)
    if eigenvalues[0] < -tolerance:
        raise PolarizationContractError(
            "response covariance has a materially negative eigenvalue"
        )
    modes = []
    for index in np.argsort(eigenvalues)[::-1]:
        eigenvalue = float(eigenvalues[index])
        if eigenvalue < tolerance:
            continue
        vector = eigenvectors[:, index].copy()
        anchor = int(np.argmax(np.abs(vector)))
        if vector[anchor] < 0.0:
            vector *= -1.0
        vector.setflags(write=False)
        modes.append((eigenvalue, vector))
    return tuple(modes)


def _readonly(array: object) -> np.ndarray:
    value = np.asarray(array, dtype=float)
    return np.frombuffer(value.tobytes(), dtype=value.dtype).reshape(value.shape)


def _mode_id(
    key: ResponseKey, orientation: str, true_cell: int, mode_index: int
) -> str:
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
        orientation,
        str(true_cell),
        str(mode_index),
    )
    return "|".join(fields)


def _validate_propagation_inputs(
    response: PhiResponse,
    config: AnalysisConfig,
    covariance_scope: ResponseCovarianceScope,
) -> tuple[float, float, float, float]:
    if type(response) is not PhiResponse or type(config) is not AnalysisConfig:
        raise PolarizationContractError(
            "response propagation requires exact response and config authorities"
        )
    validation = config.response_validation
    values = (
        validation.covariance_eigenvalue_absolute_tolerance,
        validation.probability_absolute_tolerance,
        validation.finite_difference_relative_step,
        validation.finite_difference_absolute_step,
    )
    if any(
        not isinstance(value, (float, int))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        for value in values
    ):
        raise PolarizationContractError(
            "response propagation requires approved finite tolerances"
        )
    eigenvalue_tolerance, probability_tolerance, relative_step, absolute_step = map(
        float, values
    )
    if (
        eigenvalue_tolerance < 0.0
        or probability_tolerance < 0.0
        or relative_step <= 0.0
        or absolute_step <= 0.0
    ):
        raise PolarizationContractError(
            "response propagation requires approved positive finite-difference steps"
        )

    if type(covariance_scope) is not ResponseCovarianceScope:
        raise PolarizationContractError(
            "response propagation requires loader-sealed covariance scope"
        )
    if covariance_scope.qa_sha256 != config.acceptance_qa_sha256:
        raise PolarizationContractError(
            "response covariance scope QA SHA-256 disagrees with config"
        )
    if (
        covariance_scope.shared_mc_across_blocks is not False
        or covariance_scope.cross_block_covariance is not False
    ):
        raise PolarizationContractError(
            "response schema v1 does not support cross-block covariance"
        )

    expected = {
        TrueCellKey(key, orientation, true_cell)
        for key in response.keys
        for orientation in ("parallel", "perpendicular")
        for true_cell in range(response.matrix(key, orientation).shape[1])
    }
    if set(response.covariance_by_true_cell) != expected:
        raise PolarizationContractError(
            "response covariance blocks must exactly cover canonical true cells"
        )
    for cell in sorted(expected):
        matrix = response.matrix(cell.key, cell.orientation)
        try:
            block = np.asarray(
                response.covariance_by_true_cell[cell], dtype=float
            )
        except (TypeError, ValueError) as exc:
            raise PolarizationContractError(
                "response covariance block must be numeric"
            ) from exc
        if block.shape != (matrix.shape[0], matrix.shape[0]):
            raise PolarizationContractError(
                "response covariance block shape disagrees with response matrix"
            )
    return (
        eigenvalue_tolerance,
        probability_tolerance,
        relative_step,
        absolute_step,
    )


def _physical_step_limits(
    probabilities: np.ndarray,
    direction: np.ndarray,
    *,
    tolerance: float,
) -> tuple[float, float]:
    """Return closed feasible interval for p + step * direction."""
    lower = -math.inf
    upper = math.inf
    for probability, component in zip(probabilities, direction, strict=True):
        if component > 0.0:
            lower = max(lower, -probability / component)
            upper = min(upper, (1.0 - probability) / component)
        elif component < 0.0:
            upper = min(upper, -probability / component)
            lower = max(lower, (1.0 - probability) / component)
    total_direction = float(np.sum(direction))
    if total_direction > 0.0:
        upper = min(
            upper,
            (1.0 + tolerance - float(np.sum(probabilities))) / total_direction,
        )
    elif total_direction < 0.0:
        lower = max(
            lower,
            (1.0 + tolerance - float(np.sum(probabilities))) / total_direction,
        )
    return lower, upper


def _perturbed_response(
    response: PhiResponse,
    cell: TrueCellKey,
    direction: np.ndarray,
    displacement: float,
    *,
    tolerance: float,
) -> PhiResponse:
    matrices = dict(response.matrices)
    target = np.asarray(matrices[cell.key, cell.orientation], dtype=float).copy()
    probabilities = target[:, cell.true_cell] + displacement * direction
    numerical = 32.0 * np.finfo(float).eps * max(
        1.0, float(np.max(np.abs(probabilities)))
    )
    if (
        np.any(probabilities < -numerical)
        or np.any(probabilities > 1.0 + numerical)
        or float(np.sum(probabilities)) > 1.0 + tolerance + numerical
    ):
        raise PolarizationContractError(
            "response eigenmode perturbation violates physical probability bounds"
        )
    probabilities = np.clip(probabilities, 0.0, 1.0)
    target[:, cell.true_cell] = probabilities
    matrices[cell.key, cell.orientation] = _readonly(target)
    return PhiResponse(
        response.keys,
        MappingProxyType(matrices),
        response.covariance_by_true_cell,
        response.validity,
        response.source_sha256,
        response.input_sha256,
        response.config_sha256,
        response.mass_edges,
        response.phi_edges,
    )


def _checked_sigma(
    result: JointSigmaFitResult, nominal: JointSigmaFitResult
) -> np.ndarray:
    if (
        type(result) is not JointSigmaFitResult
        or not result.converged
        or result.bin_keys != nominal.bin_keys
        or result.sigma.shape != nominal.sigma.shape
        or result.rank != nominal.rank
        or not np.all(np.isfinite(result.sigma))
    ):
        raise PolarizationContractError(
            "response eigenmode refit returned invalid canonical Sigma"
        )
    return np.asarray(result.sigma, dtype=float)


def _refit_response_mode(
    counts: AzimuthCountTable,
    response: PhiResponse,
    *,
    config: AnalysisConfig,
    nominal: JointSigmaFitResult,
    cell: TrueCellKey,
    direction: np.ndarray,
    eigenvalue: float,
    step: float,
    lower_limit: float,
    upper_limit: float,
    tolerance: float,
    identifier: str,
) -> ResponseModeRefit:
    """Refit one mode at validated endpoints and retain its exact denominator."""
    plus_ok = upper_limit >= step
    minus_ok = lower_limit <= -step
    lower_sigma = None
    upper_sigma = None
    if plus_ok:
        upper = _fit_sigma_forward_folded_core(
            counts,
            _perturbed_response(
                response, cell, direction, step, tolerance=tolerance
            ),
            config=config,
            replica_id=0,
        )
        upper_sigma = _checked_sigma(upper, nominal)
    if minus_ok:
        lower = _fit_sigma_forward_folded_core(
            counts,
            _perturbed_response(
                response, cell, direction, -step, tolerance=tolerance
            ),
            config=config,
            replica_id=0,
        )
        lower_sigma = _checked_sigma(lower, nominal)
    if plus_ok and minus_ok:
        derivative = (upper_sigma - lower_sigma) / (2.0 * step)
        scheme: Literal["central", "forward", "backward"] = "central"
    elif plus_ok:
        derivative = (upper_sigma - nominal.sigma) / step
        scheme = "forward"
    elif minus_ok:
        derivative = (nominal.sigma - lower_sigma) / step
        scheme = "backward"
    else:
        raise PolarizationContractError(
            "response eigenmode has no approved physical finite-difference step"
        )
    if not np.all(np.isfinite(derivative)):
        raise PolarizationContractError(
            "response eigenmode derivative is non-finite"
        )
    return ResponseModeRefit(
        identifier,
        eigenvalue,
        step,
        scheme,
        _readonly(derivative),
        None if lower_sigma is None else _readonly(lower_sigma),
        None if upper_sigma is None else _readonly(upper_sigma),
    )


def propagate_response_covariance(
    counts: AzimuthCountTable,
    response: PhiResponse,
    *,
    config: AnalysisConfig,
    covariance_scope: ResponseCovarianceScope,
) -> ResponsePropagationResult:
    """Refit deterministic response modes and return ``J C_R J^T``.

    This controlled propagation calls only Task 5's private numerical core.
    Public authority-only S4 entry points remain untouched.
    """
    if type(counts) is not AzimuthCountTable:
        raise PolarizationContractError(
            "response propagation requires an exact count table"
        )
    (
        eigenvalue_tolerance,
        probability_tolerance,
        relative_step,
        absolute_step,
    ) = _validate_propagation_inputs(response, config, covariance_scope)
    nominal = _fit_sigma_forward_folded_core(
        counts, response, config=config, replica_id=0
    )
    dimension = nominal.sigma.size
    covariance = np.zeros((dimension, dimension), dtype=float)
    retained = []
    refits = []

    for key in response.keys:
        for orientation in ("parallel", "perpendicular"):
            matrix = np.asarray(response.matrix(key, orientation), dtype=float)
            for true_cell, block in enumerate(
                response.covariance_blocks(key, orientation)
            ):
                cell = TrueCellKey(key, orientation, true_cell)
                probabilities = matrix[:, true_cell]
                modes = _covariance_eigenmodes(
                    block, tolerance=eigenvalue_tolerance
                )
                for mode_index, (eigenvalue, direction) in enumerate(modes):
                    step = max(
                        absolute_step,
                        relative_step * float(np.max(np.abs(probabilities))),
                    )
                    lower_limit, upper_limit = _physical_step_limits(
                        probabilities,
                        direction,
                        tolerance=probability_tolerance,
                    )
                    identifier = _mode_id(
                        key, orientation, true_cell, mode_index
                    )
                    refit = _refit_response_mode(
                        counts,
                        response,
                        config=config,
                        nominal=nominal,
                        cell=cell,
                        direction=direction,
                        eigenvalue=eigenvalue,
                        step=step,
                        lower_limit=lower_limit,
                        upper_limit=upper_limit,
                        tolerance=probability_tolerance,
                        identifier=identifier,
                    )
                    covariance += eigenvalue * np.outer(
                        refit.derivative, refit.derivative
                    )
                    retained.append(identifier)
                    refits.append(refit)
    if not np.all(np.isfinite(covariance)):
        raise PolarizationContractError(
            "response propagated covariance is non-finite"
        )
    covariance = (covariance + covariance.T) / 2.0
    scale = max(1.0, float(np.max(np.abs(covariance))))
    if (
        np.linalg.eigvalsh(covariance)[0]
        < -eigenvalue_tolerance * scale
    ):
        raise PolarizationContractError(
            "response propagated covariance is not positive semidefinite"
        )
    return ResponsePropagationResult(
        _readonly(covariance), tuple(retained), tuple(refits), True
    )
