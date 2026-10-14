"""Run-block bootstrap, false-label controls, and systematic covariance."""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from typing import Callable, Mapping, Sequence

import numpy as np
from graal_common.parallel import ordered_map, validate_workers

from observable_extraction.core.models import FluxExposure, FitNotEstimableError
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


@dataclass(frozen=True)
class PairedBootstrapResult:
    """Diagnostic ensemble; any failed point makes the joint covariance unavailable."""

    point_keys: tuple[str, ...]
    replicas: np.ndarray
    run_draws: tuple[tuple[int, ...], ...]
    failures: Mapping[int, str]
    covariance: np.ndarray | None
    covariance_standard_error: np.ndarray | None
    rank: int | None
    zero_event_runs: Mapping[str, tuple[int, ...]]
    effective_runs: float
    seed: int


def paired_bootstrap_by_run(
    estimator: Callable,
    samples: Mapping[str, EventArrays],
    exposures: Mapping[tuple[int, int], FluxExposure],
    *,
    run_strata: Mapping[int, str],
    point_keys: Sequence[str],
    replicas: int,
    seed: int,
    workers: int = 1,
) -> PairedBootstrapResult:
    """Resample common run blocks within explicit profile/period strata.

    The exposure mapping defines the universe, including zero-yield runs.
    The callback redoes every compared estimator and any background procedure.
    A NaN marks an unestimable point. No row is discarded or redrawn. This is
    a run-clustering diagnostic, not an event/Poisson or detector-bias estimate.
    """
    validate_workers(workers)
    if replicas < 2:
        raise ValueError("paired bootstrap needs at least two replicas")
    keys = tuple(point_keys)
    if not keys or len(set(keys)) != len(keys) or not all(isinstance(key, str) for key in keys):
        raise ValueError("point keys must be nonempty unique strings")
    runs = sorted({exposure.run_number for exposure in exposures.values()})
    if not runs or set(runs) != set(run_strata) or any(not run_strata[run] for run in runs):
        raise ValueError("run strata must exactly cover the exposure universe")
    if any(key != (exposure.run_number, exposure.xstrip) for key, exposure in exposures.items()):
        raise ValueError("exposure key does not match run/strip")
    if not samples:
        raise ValueError("at least one sample is required")
    indices = {}
    zero_runs = {}
    for name, events in samples.items():
        if not set(map(int, events.run_number)).issubset(runs):
            raise ValueError(f"sample {name!r} contains a run without exposure")
        indices[name] = {run: np.flatnonzero(events.run_number == run) for run in runs}
        zero_runs[name] = tuple(run for run in runs if not len(indices[name][run]))
    groups = {}
    for run in runs:
        groups.setdefault(run_strata[run], []).append(run)
    rng = np.random.default_rng(seed)
    values = np.full((replicas, len(keys)), np.nan)
    # Draw in the parent, in historical RNG order; workers never draw or retry.
    draws = [tuple(int(run) for group in sorted(groups)
                   for run in rng.choice(groups[group], size=len(groups[group]), replace=True))
             for _ in range(replicas)]
    failures = {}

    def evaluate(draw):
        selected = {name: _events_at_indices(events, np.concatenate([indices[name][run] for run in draw]))
                    for name, events in samples.items()}
        multiplicity = dict(zip(*np.unique(draw, return_counts=True)))
        scaled = {
            key: replace(exposure,
                         flux_vertical=exposure.flux_vertical * multiplicity[exposure.run_number],
                         flux_horizontal=exposure.flux_horizontal * multiplicity[exposure.run_number],
                         flux_brem=exposure.flux_brem * multiplicity[exposure.run_number])
            for key, exposure in exposures.items() if exposure.run_number in multiplicity
        }
        try:
            estimate = np.asarray(estimator(selected, scaled), dtype=np.float64)
        except FitNotEstimableError as exc:
            return None, str(exc)
        if estimate.shape != (len(keys),):
            raise ValueError("bootstrap estimator dimension does not match point keys")
        missing = np.flatnonzero(~np.isfinite(estimate))
        error = ("non-estimable points: " + ", ".join(keys[index] for index in missing)
                 if missing.size else None)
        return estimate, error

    for replica, (estimate, error) in enumerate(ordered_map(evaluate, draws, workers=workers)):
        if estimate is not None:
            values[replica] = estimate
        if error is not None:
            failures[replica] = error
    covariance = standard_error = rank = None
    if not failures:
        covariance = validate_covariance(np.atleast_2d(np.cov(values, rowvar=False, ddof=1)))
        # IID-replica Monte Carlo SE from centered outer products. Approximate
        # (the center is estimated); measures numerical precision, not physics.
        centered = values - values.mean(axis=0)
        sum_squares = np.zeros_like(covariance)
        for row in centered:
            contribution = np.outer(row, row) * replicas / (replicas - 1)
            sum_squares += (contribution - covariance)**2
        standard_error = np.sqrt(sum_squares / ((replicas - 1) * replicas))
        rank = int(np.linalg.matrix_rank(covariance))
    run_flux = np.array([sum(exp.flux_vertical + exp.flux_horizontal
                            for exp in exposures.values() if exp.run_number == run) for run in runs])
    effective_runs = float(run_flux.sum()**2 / np.dot(run_flux, run_flux))
    return PairedBootstrapResult(keys, values, tuple(draws), failures, covariance,
                                 standard_error, rank, zero_runs, effective_runs, seed)


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


def validate_covariance(values: np.ndarray, *, size: int | None = None) -> np.ndarray:
    """Validate a finite symmetric PSD covariance without repairing its entries."""
    matrix = np.asarray(values, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("covariance must be square")
    if size is not None and matrix.shape != (size, size):
        raise ValueError("covariance dimension does not match point keys")
    if not np.all(np.isfinite(matrix)):
        raise ValueError("covariance must be finite")
    tolerance = 1e-12 + 1e-10 * float(np.max(np.abs(matrix), initial=0.0))
    if not np.allclose(matrix, matrix.T, rtol=0.0, atol=tolerance):
        raise ValueError("covariance must be symmetric")
    if matrix.size and np.linalg.eigvalsh((matrix + matrix.T) / 2).min() < -tolerance:
        raise ValueError("covariance must be positive semidefinite")
    return matrix


def difference_covariance(
    covariance_a: np.ndarray, covariance_b: np.ndarray, cross_covariance: np.ndarray,
) -> np.ndarray:
    """Cov(A-B); cross_covariance is Cov(A,B), never inferred as zero."""
    a = validate_covariance(covariance_a)
    b = validate_covariance(covariance_b, size=len(a))
    cross = np.asarray(cross_covariance, dtype=np.float64)
    if cross.shape != a.shape:
        raise ValueError("cross covariance dimension does not match point keys")
    validate_covariance(np.block([[a, cross], [cross.T, b]]))
    return validate_covariance(a + b - cross - cross.T)


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
    workers: int = 1,
) -> BootstrapResult:
    validate_workers(workers)
    index_draws = bootstrap_run_indices(
        events.run_number, replicas=replicas, seed=seed
    )
    def evaluate(indices):
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
        return estimate, drawn_runs

    results = ordered_map(evaluate, index_draws, workers=workers)
    values, run_draws = zip(*results)
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
