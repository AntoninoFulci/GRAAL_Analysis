"""Run-block bootstrap, false-label controls, and systematic covariance."""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from typing import Callable, Mapping, Sequence

import numpy as np

from observable_extraction.core.models import FluxExposure
from observable_extraction.io.reconstructed_events import EventArrays


REQUIRED_SYSTEMATICS = (
    "polarization_scale_3pct",
    "flux_balance",
    "estimator_ratio_vs_likelihood",
    "raw_vs_kinematic_fit",
    "bdt_threshold",
    "background_template",
    "sideband_definition",
    "photon_multiplicity",
    "fit_fallback",
    "mass_phi_binning",
    "run_period_stability",
    "angular_offset_sine_leakage",
)


@dataclass(frozen=True)
class SystematicComponent:
    name: str
    shift: np.ndarray
    magnitude: np.ndarray
    covariance: np.ndarray


@dataclass(frozen=True)
class BootstrapResult:
    replicas: np.ndarray
    mean: np.ndarray
    covariance: np.ndarray
    correlation: np.ndarray
    run_draws: tuple[tuple[int, ...], ...]


def component_from_shift(name: str, shift: np.ndarray) -> SystematicComponent:
    shift = np.asarray(shift, dtype=np.float64)
    if shift.ndim != 1 or np.any(~np.isfinite(shift)):
        raise ValueError("systematic shift must be finite and one-dimensional")
    return SystematicComponent(
        name=name,
        shift=shift,
        magnitude=np.abs(shift),
        covariance=np.outer(shift, shift),
    )


def polarization_scale_component(
    nominal_sigma: np.ndarray,
    *,
    relative_uncertainty: float = 0.03,
) -> SystematicComponent:
    if relative_uncertainty < 0.0:
        raise ValueError("relative_uncertainty must be non-negative")
    nominal_sigma = np.asarray(nominal_sigma, dtype=np.float64)
    # Sigma is inversely proportional to polarization scale.
    return component_from_shift(
        "polarization_scale_3pct",
        -relative_uncertainty * nominal_sigma,
    )


def bootstrap_run_indices(
    run_number: np.ndarray,
    *,
    replicas: int,
    seed: int,
) -> tuple[np.ndarray, ...]:
    run_number = np.asarray(run_number, dtype=np.int64)
    if run_number.ndim != 1 or len(run_number) == 0:
        raise ValueError("run_number must be a non-empty one-dimensional array")
    if replicas <= 0:
        raise ValueError("replicas must be positive")
    unique_runs = np.unique(run_number)
    indices = {run: np.flatnonzero(run_number == run) for run in unique_runs}
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(replicas):
        selected_runs = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        draws.append(np.concatenate([indices[run] for run in selected_runs]))
    return tuple(draws)


def _events_at_indices(events: EventArrays, indices: np.ndarray) -> EventArrays:
    return EventArrays(
        **{field.name: getattr(events, field.name)[indices] for field in fields(events)}
    )


def bootstrap_by_run(
    estimator: Callable[
        [EventArrays, Mapping[tuple[int, int], FluxExposure]], np.ndarray
    ],
    events: EventArrays,
    exposures: Mapping[tuple[int, int], FluxExposure],
    *,
    replicas: int,
    seed: int,
) -> BootstrapResult:
    index_draws = bootstrap_run_indices(
        events.run_number, replicas=replicas, seed=seed
    )
    values = []
    run_draws = []
    for indices in index_draws:
        selected_events = _events_at_indices(events, indices)
        drawn_runs = tuple(int(run) for run in np.unique(events.run_number[indices]))
        multiplicities = {
            int(run): int(np.count_nonzero(events.run_number[indices] == run))
            // int(np.count_nonzero(events.run_number == run))
            for run in np.unique(events.run_number)
        }
        scaled_exposures = {
            key: replace(
                exposure,
                flux_vertical=exposure.flux_vertical
                * multiplicities.get(exposure.run_number, 0),
                flux_horizontal=exposure.flux_horizontal
                * multiplicities.get(exposure.run_number, 0),
                flux_brem=exposure.flux_brem
                * multiplicities.get(exposure.run_number, 0),
            )
            for key, exposure in exposures.items()
            if multiplicities.get(exposure.run_number, 0) > 0
        }
        estimate = np.asarray(
            estimator(selected_events, scaled_exposures), dtype=np.float64
        )
        if estimate.ndim != 1 or np.any(~np.isfinite(estimate)):
            raise ValueError("bootstrap estimator must return finite 1D values")
        values.append(estimate)
        run_draws.append(drawn_runs)

    replica_values = np.stack(values)
    mean = np.mean(replica_values, axis=0)
    covariance = (
        np.cov(replica_values, rowvar=False, ddof=1)
        if replicas > 1
        else np.zeros((replica_values.shape[1], replica_values.shape[1]))
    )
    covariance = np.atleast_2d(covariance)
    scale = np.sqrt(np.clip(np.diag(covariance), 0.0, None))
    denominator = np.outer(scale, scale)
    correlation = np.divide(
        covariance,
        denominator,
        out=np.zeros_like(covariance),
        where=denominator > 0.0,
    )
    return BootstrapResult(
        replicas=replica_values,
        mean=mean,
        covariance=covariance,
        correlation=correlation,
        run_draws=tuple(run_draws),
    )


def combine_covariances(
    components: Sequence[SystematicComponent],
    bootstrap_covariance: np.ndarray,
) -> np.ndarray:
    total = np.asarray(bootstrap_covariance, dtype=np.float64).copy()
    if total.ndim != 2 or total.shape[0] != total.shape[1]:
        raise ValueError("bootstrap covariance must be square")
    for component in components:
        if component.covariance.shape != total.shape:
            raise ValueError(
                f"component {component.name!r} covariance shape mismatch"
            )
        total += component.covariance
    return total


def randomize_polarization_labels(
    polarization: np.ndarray,
    *,
    seed: int,
) -> np.ndarray:
    polarization = np.asarray(polarization, dtype=np.int64)
    if not np.all(np.isin(polarization, (1, 2))):
        raise ValueError("randomized labels accept only states 1 and 2")
    return np.random.default_rng(seed).permutation(polarization)
