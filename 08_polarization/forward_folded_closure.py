"""Deterministic full-vector closure for the authenticated S4 forward model."""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Sequence

import numpy as np

from analysis_config import AnalysisConfig
from azimuth_counts import AzimuthCountRow, AzimuthCountTable
from contracts import PolarizationContractError
from phi_response import PhiResponse, ResponseKey
from sigma_fit import (
    _fit_sigma_forward_folded_core,
    _row_order,
    _sigma_bin_key,
    azimuth_bin_average,
)


ALGORITHM_VERSION = "forward-folded-poisson-ensemble-v1"
DEFAULT_INJECTED_CYCLE = (-0.35, 0.20, 0.50, -0.45, 0.10)


def _readonly(raw: object) -> np.ndarray:
    value = np.asarray(raw, dtype=float)
    return np.frombuffer(value.tobytes(), dtype=value.dtype).reshape(value.shape)


@dataclass(frozen=True)
class ForwardFoldedClosureResult:
    algorithm_version: str
    bin_keys: tuple[str, ...]
    injected_sigma: np.ndarray
    fitted_sigma_vectors: np.ndarray
    fitted_mean: np.ndarray
    bias: np.ndarray
    pull_mean: np.ndarray
    pull_width: np.ndarray
    sign_swapped_sigma: np.ndarray
    experiments: int
    seed: int
    bias_threshold: float
    pull_mean_threshold: float
    pull_width_tolerance: float
    sign_tolerance: float
    sign_check_passed: bool
    valid: bool


def _controls(
    *,
    seed: int,
    experiments: int,
    bias_threshold: float,
    pull_mean_threshold: float,
    pull_width_tolerance: float,
    sign_tolerance: float,
) -> tuple[int, int, tuple[float, float, float, float]]:
    if type(seed) is not int or seed < 0:
        raise PolarizationContractError("closure seed must be a nonnegative integer")
    if type(experiments) is not int or experiments < 2:
        raise PolarizationContractError("closure experiments must be an integer >= 2")
    thresholds = (
        bias_threshold,
        pull_mean_threshold,
        pull_width_tolerance,
        sign_tolerance,
    )
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) < 0.0
        for value in thresholds
    ):
        raise PolarizationContractError(
            "closure thresholds must be finite and nonnegative"
        )
    return seed, experiments, tuple(float(value) for value in thresholds)


def _canonical_injection(bin_keys: Sequence[str]) -> np.ndarray:
    if not bin_keys:
        raise PolarizationContractError("closure requires non-empty S4 bin keys")
    cycle = np.asarray(DEFAULT_INJECTED_CYCLE, dtype=float)
    return cycle[np.arange(len(bin_keys)) % cycle.size]


def _expected_counts(
    counts: AzimuthCountTable,
    response: PhiResponse,
    config: AnalysisConfig,
    *,
    bin_keys: tuple[str, ...],
    injected_sigma: np.ndarray,
    log_yield: np.ndarray,
) -> tuple[tuple[AzimuthCountRow, ...], np.ndarray]:
    signs = dict(config.orientation_signs)
    nominal_rows = tuple(
        sorted((row for row in counts.rows if row.replica_id == 0), key=_row_order)
    )
    expected_parts: list[np.ndarray] = []
    ordered_rows: list[AzimuthCountRow] = []
    offset = 0
    for key in response.keys:
        mass_edges = np.asarray(response.mass_edges[key], dtype=float)
        phi_edges = np.asarray(response.phi_edges[key], dtype=float)
        mass_bins = mass_edges.size - 1
        phi_bins = phi_edges.size - 1
        widths = np.diff(phi_edges)
        averages = azimuth_bin_average(phi_edges[:-1], phi_edges[1:])
        wanted = tuple(_sigma_bin_key(key, index) for index in range(mass_bins))
        if bin_keys[offset : offset + mass_bins] != wanted:
            raise PolarizationContractError(
                "closure bin layout disagrees with S4 forward model"
            )
        sigma = injected_sigma[offset : offset + mass_bins]
        yields = np.exp(log_yield[offset : offset + mass_bins])
        key_rows = tuple(
            row
            for row in nominal_rows
            if ResponseKey(
                row.channel,
                row.target,
                row.beam_group,
                row.Egamma_low,
                row.Egamma_high,
                row.cos_theta_low,
                row.cos_theta_high,
                row.observable,
                row.selection_id,
            ) == key
        )
        by_state: dict[tuple[str, str], list[AzimuthCountRow]] = {}
        for row in key_rows:
            by_state.setdefault((row.source_period, row.orientation), []).append(row)
        for (_, orientation), state_rows in sorted(by_state.items()):
            ordered = tuple(
                sorted(
                    state_rows,
                    key=lambda row: (row.reco_mass_bin, row.reco_phi_bin),
                )
            )
            if len(ordered) != mass_bins * phi_bins:
                raise PolarizationContractError(
                    "closure count layout is not the exact S4 grid"
                )
            exposure = float(ordered[0].exposure)
            polarization = float(ordered[0].beam_polarization)
            truth = yields[:, None] * widths[None, :] / np.pi
            truth *= 1.0 + (
                signs[orientation]
                * polarization
                * sigma[:, None]
                * averages[None, :]
            )
            expected = exposure * (
                np.asarray(response.matrix(key, orientation), dtype=float)
                @ truth.reshape(-1)
            )
            if np.any(expected <= 0.0) or not np.all(np.isfinite(expected)):
                raise PolarizationContractError(
                    "closure generated nonpositive expected counts"
                )
            ordered_rows.extend(ordered)
            expected_parts.append(expected)
        offset += mass_bins
    if offset != len(bin_keys) or tuple(ordered_rows) != nominal_rows:
        raise PolarizationContractError("closure row layout disagrees with S4")
    return nominal_rows, np.concatenate(expected_parts)


def _with_nominal_observed(
    counts: AzimuthCountTable,
    nominal_rows: tuple[AzimuthCountRow, ...],
    observed: np.ndarray,
) -> AzimuthCountTable:
    if observed.shape != (len(nominal_rows),):
        raise PolarizationContractError("closure observation vector is misaligned")
    replacements = {
        row: replace(row, observed_count=int(value))
        for row, value in zip(nominal_rows, observed, strict=True)
    }
    return AzimuthCountTable(
        tuple(replacements.get(row, row) for row in counts.rows),
        counts.expected_universe,
        counts.expected_replica_ids,
    )


def run_forward_folded_closure(
    counts: AzimuthCountTable,
    response: PhiResponse,
    config: AnalysisConfig,
    *,
    seed: int,
    experiments: int,
    bias_threshold: float,
    pull_mean_threshold: float,
    pull_width_tolerance: float,
    sign_tolerance: float | None = None,
) -> ForwardFoldedClosureResult:
    """Replay deterministic Poisson closure through exact S4 mass-phi fit."""
    if sign_tolerance is None:
        sign_tolerance = config.response_validation.replay_absolute_tolerance
    seed, experiments, thresholds = _controls(
        seed=seed,
        experiments=experiments,
        bias_threshold=bias_threshold,
        pull_mean_threshold=pull_mean_threshold,
        pull_width_tolerance=pull_width_tolerance,
        sign_tolerance=sign_tolerance,
    )
    bias_limit, pull_mean_limit, pull_width_limit, sign_limit = thresholds
    nominal = _fit_sigma_forward_folded_core(
        counts, response, config=config, replica_id=0
    )
    injected = _canonical_injection(nominal.bin_keys)
    nominal_rows, expected = _expected_counts(
        counts,
        response,
        config,
        bin_keys=nominal.bin_keys,
        injected_sigma=injected,
        log_yield=nominal.log_yield,
    )
    generator = np.random.default_rng(seed)
    fitted = []
    pulls = []
    for _ in range(experiments):
        synthetic = _with_nominal_observed(
            counts, nominal_rows, generator.poisson(expected)
        )
        result = _fit_sigma_forward_folded_core(
            synthetic, response, config=config, replica_id=0
        )
        if result.bin_keys != nominal.bin_keys:
            raise PolarizationContractError("closure fit changed S4 bin order")
        uncertainty = np.sqrt(np.diag(result.hessian_covariance))
        if np.any(uncertainty <= 0.0) or not np.all(np.isfinite(uncertainty)):
            raise PolarizationContractError("closure fit uncertainty is invalid")
        fitted.append(result.sigma)
        pulls.append((result.sigma - injected) / uncertainty)
    fitted_matrix = np.asarray(fitted, dtype=float)
    pull_matrix = np.asarray(pulls, dtype=float)
    fitted_mean = np.mean(fitted_matrix, axis=0)
    bias = fitted_mean - injected
    pull_mean = np.mean(pull_matrix, axis=0)
    pull_width = np.std(pull_matrix, axis=0, ddof=1)

    asimov_counts = _with_nominal_observed(
        counts, nominal_rows, np.rint(expected).astype(np.int64)
    )
    asimov = _fit_sigma_forward_folded_core(
        asimov_counts, response, config=config, replica_id=0
    )
    swapped_config = replace(
        config,
        orientation_signs=tuple(
            sorted((name, -value) for name, value in config.orientation_signs)
        ),
    )
    swapped = _fit_sigma_forward_folded_core(
        asimov_counts, response, config=swapped_config, replica_id=0
    )
    sign_check = bool(
        np.allclose(swapped.sigma, -asimov.sigma, rtol=0.0, atol=sign_limit)
    )
    valid = bool(
        np.all(np.abs(bias) <= bias_limit)
        and np.all(np.abs(pull_mean) <= pull_mean_limit)
        and np.all(np.abs(pull_width - 1.0) <= pull_width_limit)
        and sign_check
    )
    return ForwardFoldedClosureResult(
        ALGORITHM_VERSION,
        nominal.bin_keys,
        _readonly(injected),
        _readonly(fitted_matrix),
        _readonly(fitted_mean),
        _readonly(bias),
        _readonly(pull_mean),
        _readonly(pull_width),
        _readonly(swapped.sigma),
        experiments,
        seed,
        bias_limit,
        pull_mean_limit,
        pull_width_limit,
        sign_limit,
        sign_check,
        valid,
    )
