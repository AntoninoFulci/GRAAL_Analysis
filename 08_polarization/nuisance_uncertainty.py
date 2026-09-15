"""Deterministic Compton and flux-exposure covariance propagation for S4."""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Callable, Literal

import numpy as np

from analysis_config import AnalysisConfig
from azimuth_counts import AzimuthCountTable, CountAuthority, FluxAuthorityRow
from contracts import PolarizationContractError
from phi_response import PhiResponse
from response_uncertainty import _covariance_eigenmodes
from sigma_fit import JointSigmaFitResult, _fit_sigma_forward_folded_core


COMPTON_SOURCE_NAME = "compton_polarization_statistics"
FLUX_SOURCE_NAME = "flux_exposure_statistics"


def _readonly(raw: object) -> np.ndarray:
    value = np.asarray(raw, dtype=float)
    return np.frombuffer(value.tobytes(), dtype=value.dtype).reshape(value.shape)


@dataclass(frozen=True)
class NuisanceModeRefit:
    mode_id: str
    eigenvalue: float
    step: float
    scheme: Literal["central", "forward", "backward"]
    derivative: np.ndarray
    lower_sigma: np.ndarray | None
    upper_sigma: np.ndarray | None


@dataclass(frozen=True)
class NuisancePropagationResult:
    source_name: str
    covariance: np.ndarray
    input_keys: tuple[str, ...]
    input_covariance: np.ndarray
    retained_modes: tuple[str, ...]
    refits: tuple[NuisanceModeRefit, ...]
    valid: bool


def flux_net_covariance(*, pol1: float, brem: float, pol2: float) -> np.ndarray:
    """Return covariance of `(pol1-brem, pol2-brem)` for raw Poisson counts."""
    values = (pol1, brem, pol2)
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or float(value) < 0.0
        for value in values
    ):
        raise PolarizationContractError("raw flux counts must be finite and non-negative")
    matrix = np.asarray(
        [[float(pol1) + float(brem), float(brem)],
         [float(brem), float(pol2) + float(brem)]],
        dtype=float,
    )
    return _readonly(matrix)


def _checked_sigma(result: JointSigmaFitResult, nominal: JointSigmaFitResult) -> np.ndarray:
    if (
        type(result) is not JointSigmaFitResult
        or not result.converged
        or result.bin_keys != nominal.bin_keys
        or result.sigma.shape != nominal.sigma.shape
        or not np.all(np.isfinite(result.sigma))
    ):
        raise PolarizationContractError("nuisance refit returned invalid canonical Sigma")
    return np.asarray(result.sigma, dtype=float)


def _refit_mode(
    counts: AzimuthCountTable,
    response: PhiResponse,
    config: AnalysisConfig,
    nominal: JointSigmaFitResult,
    *,
    identifier: str,
    eigenvalue: float,
    step: float,
    perturb: Callable[[float], AzimuthCountTable],
    minus_ok: bool,
    plus_ok: bool,
) -> NuisanceModeRefit:
    lower_sigma = upper_sigma = None
    if minus_ok:
        lower_sigma = _checked_sigma(
            _fit_sigma_forward_folded_core(
                perturb(-step), response, config=config, replica_id=0
            ),
            nominal,
        )
    if plus_ok:
        upper_sigma = _checked_sigma(
            _fit_sigma_forward_folded_core(
                perturb(step), response, config=config, replica_id=0
            ),
            nominal,
        )
    if minus_ok and plus_ok:
        derivative = (upper_sigma - lower_sigma) / (2.0 * step)
        scheme: Literal["central", "forward", "backward"] = "central"
    elif plus_ok:
        derivative = (upper_sigma - nominal.sigma) / step
        scheme = "forward"
    elif minus_ok:
        derivative = (nominal.sigma - lower_sigma) / step
        scheme = "backward"
    else:
        raise PolarizationContractError("nuisance mode has no physical refit endpoint")
    return NuisanceModeRefit(
        identifier, eigenvalue, step, scheme, _readonly(derivative),
        None if lower_sigma is None else _readonly(lower_sigma),
        None if upper_sigma is None else _readonly(upper_sigma),
    )


def _result(
    source_name: str,
    input_keys: list[str],
    blocks: list[np.ndarray],
    refits: list[NuisanceModeRefit],
    dimension: int,
) -> NuisancePropagationResult:
    input_dimension = sum(block.shape[0] for block in blocks)
    input_covariance = np.zeros((input_dimension, input_dimension), dtype=float)
    cursor = 0
    for block in blocks:
        width = block.shape[0]
        input_covariance[cursor:cursor + width, cursor:cursor + width] = block
        cursor += width
    covariance = np.zeros((dimension, dimension), dtype=float)
    for refit in refits:
        covariance += refit.eigenvalue * np.outer(refit.derivative, refit.derivative)
    covariance = (covariance + covariance.T) / 2.0
    if not np.all(np.isfinite(covariance)):
        raise PolarizationContractError("propagated nuisance covariance is non-finite")
    return NuisancePropagationResult(
        source_name, _readonly(covariance), tuple(input_keys),
        _readonly(input_covariance), tuple(item.mode_id for item in refits),
        tuple(refits), True,
    )


def _step(config: AnalysisConfig, scale: float) -> float:
    return max(
        float(config.response_validation.finite_difference_absolute_step),
        float(config.response_validation.finite_difference_relative_step) * scale,
    )


def propagate_compton_covariance(
    counts: AzimuthCountTable,
    response: PhiResponse,
    *,
    config: AnalysisConfig,
    authority: CountAuthority,
) -> NuisancePropagationResult:
    """Project period node covariance and refit every retained full-vector mode."""
    nominal = _fit_sigma_forward_folded_core(counts, response, config=config, replica_id=0)
    tolerance = float(config.response_validation.covariance_eigenvalue_absolute_tolerance)
    input_keys: list[str] = []
    blocks: list[np.ndarray] = []
    refits: list[NuisanceModeRefit] = []
    for period in sorted(authority.compton):
        curve = authority.compton[period]
        block = np.asarray(curve.covariance, dtype=float)
        blocks.append(block)
        input_keys.extend(f"{period}|node|{index}" for index in range(len(curve.values)))
        for mode_index, (eigenvalue, direction) in enumerate(
            _covariance_eigenmodes(block, tolerance=tolerance)
        ):
            step = _step(config, float(np.max(np.abs(curve.values))))
            minus_ok = bool(np.all(curve.values - step * direction >= 0.0))
            plus_ok = bool(np.all(curve.values + step * direction <= 1.0))

            def perturb(
                displacement: float,
                *,
                _period=period,
                _direction=direction,
                _curve=curve,
            ):
                changed = []
                for row in counts.rows:
                    if row.source_period != _period:
                        changed.append(row)
                        continue
                    weights = _curve.bin_average_weights(
                        1000.0 * row.Egamma_low, 1000.0 * row.Egamma_high
                    )
                    value = row.beam_polarization + displacement * float(weights @ _direction)
                    changed.append(replace(row, beam_polarization=value))
                return AzimuthCountTable(
                    tuple(changed), counts.expected_universe, counts.expected_replica_ids
                )

            refits.append(_refit_mode(
                counts, response, config, nominal,
                identifier=f"{COMPTON_SOURCE_NAME}|{period}|mode|{mode_index}",
                eigenvalue=eigenvalue, step=step, perturb=perturb,
                minus_ok=minus_ok, plus_ok=plus_ok,
            ))
    return _result(COMPTON_SOURCE_NAME, input_keys, blocks, refits, nominal.sigma.size)


def _flux_orientation_components(
    authority: CountAuthority, row: FluxAuthorityRow
) -> dict[str, str]:
    matching = tuple(
        interval for interval in authority.state_map
        if interval.source_period == row.source_period
        and interval.run_start <= row.run_number <= interval.run_end
    )
    result: dict[str, str] = {}
    for interval in matching:
        previous = result.setdefault(interval.orientation, interval.flux_component)
        if previous != interval.flux_component:
            raise PolarizationContractError("flux nuisance state mapping is ambiguous")
    return result


def propagate_flux_exposure_covariance(
    counts: AzimuthCountTable,
    response: PhiResponse,
    *,
    config: AnalysisConfig,
    authority: CountAuthority,
) -> NuisancePropagationResult:
    """Propagate independent raw-run Poisson flux blocks by deterministic refits."""
    nominal = _fit_sigma_forward_folded_core(counts, response, config=config, replica_id=0)
    tolerance = float(config.response_validation.covariance_eigenvalue_absolute_tolerance)
    input_keys: list[str] = []
    blocks: list[np.ndarray] = []
    refits: list[NuisanceModeRefit] = []
    for row_index, flux_row in enumerate(authority.flux_rows):
        block = np.asarray(flux_net_covariance(
            pol1=flux_row.pol1, brem=flux_row.brem, pol2=flux_row.pol2
        ))
        blocks.append(block)
        prefix = (
            f"run={flux_row.run_number}|period={flux_row.source_period}|"
            f"group={flux_row.beam_group}|E={flux_row.energy_low_gev:.17g}:"
            f"{flux_row.energy_high_gev:.17g}"
        )
        input_keys.extend((f"{prefix}|pol1_net", f"{prefix}|pol2_net"))
        components = _flux_orientation_components(authority, flux_row)
        for mode_index, (eigenvalue, direction) in enumerate(
            _covariance_eigenmodes(block, tolerance=tolerance)
        ):
            affected = {
                orientation: float(direction[0 if component == "pol1_net" else 1])
                for orientation, component in components.items()
            }
            matching_exposures = [
                count.exposure for count in counts.rows
                if count.replica_id == 0
                and count.target == flux_row.target
                and count.beam_group == flux_row.beam_group
                and count.source_period == flux_row.source_period
                and count.Egamma_low == flux_row.energy_low_gev
                and count.Egamma_high == flux_row.energy_high_gev
                and count.orientation in affected
            ]
            scale = max(matching_exposures, default=1.0)
            step = _step(config, scale)
            minus_ok = all(
                exposure - step * affected[orientation] > 0.0
                for orientation, exposure in (
                    (count.orientation, count.exposure)
                    for count in counts.rows if count.replica_id == 0
                    and count.target == flux_row.target
                    and count.beam_group == flux_row.beam_group
                    and count.source_period == flux_row.source_period
                    and count.Egamma_low == flux_row.energy_low_gev
                    and count.Egamma_high == flux_row.energy_high_gev
                    and count.orientation in affected
                )
            )
            plus_ok = all(
                exposure + step * affected[orientation] > 0.0
                for orientation, exposure in (
                    (count.orientation, count.exposure)
                    for count in counts.rows if count.replica_id == 0
                    and count.target == flux_row.target
                    and count.beam_group == flux_row.beam_group
                    and count.source_period == flux_row.source_period
                    and count.Egamma_low == flux_row.energy_low_gev
                    and count.Egamma_high == flux_row.energy_high_gev
                    and count.orientation in affected
                )
            )

            def perturb(
                displacement: float,
                *,
                _affected=affected,
                _flux_row=flux_row,
            ):
                changed = []
                for count in counts.rows:
                    applies = (
                        count.target == _flux_row.target
                        and count.beam_group == _flux_row.beam_group
                        and count.source_period == _flux_row.source_period
                        and count.Egamma_low == _flux_row.energy_low_gev
                        and count.Egamma_high == _flux_row.energy_high_gev
                        and count.orientation in _affected
                    )
                    changed.append(replace(
                        count,
                        exposure=count.exposure + displacement * _affected[count.orientation]
                        if applies else count.exposure,
                    ))
                return AzimuthCountTable(
                    tuple(changed), counts.expected_universe, counts.expected_replica_ids
                )

            refits.append(_refit_mode(
                counts, response, config, nominal,
                identifier=f"{FLUX_SOURCE_NAME}|row|{row_index}|mode|{mode_index}",
                eigenvalue=eigenvalue, step=step, perturb=perturb,
                minus_ok=minus_ok, plus_ok=plus_ok,
            ))
    return _result(FLUX_SOURCE_NAME, input_keys, blocks, refits, nominal.sigma.size)
