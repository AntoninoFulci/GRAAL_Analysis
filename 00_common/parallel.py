"""Ordered process execution with bounded native thread pools."""

from __future__ import annotations

import os


def validate_workers(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("workers must be a positive integer")
    return value


def available_cpus() -> int:
    """Respect Linux affinity, including scheduler-assigned CPU sets."""
    if hasattr(os, "sched_getaffinity"):
        return max(1, len(os.sched_getaffinity(0)))
    return os.cpu_count() or 1


def thread_environment(threads: int) -> dict[str, str]:
    validate_workers(threads)
    return {name: str(threads) for name in (
        "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS", "BLIS_NUM_THREADS",
    )}


def ordered_map(function, items, *, workers: int = 1) -> list:
    """Map in input order; worker errors propagate without partial publication.

    Loky isolates ROOT/global RNG state and serializes Python closures. Native
    BLAS/OpenMP pools inside each process are limited to one thread. Callers
    must keep ROOT objects inside workers and avoid nested process pools.
    """
    validate_workers(workers)
    items = list(items)
    if not items:
        return []
    workers = min(workers, len(items))
    if workers == 1:
        return [function(item) for item in items]
    from joblib import Parallel, delayed, parallel_config

    def evaluate(item):
        # Return ordinary failures so pools shut down normally rather than
        # killing unrelated native work. No partial result reaches callers.
        try:
            return True, function(item)
        except Exception as exc:
            return False, exc

    with parallel_config(backend="loky", inner_max_num_threads=1):
        outcomes = Parallel(n_jobs=workers)(delayed(evaluate)(item) for item in items)
    for success, result in outcomes:
        if not success:
            raise result
    return [result for _, result in outcomes]
