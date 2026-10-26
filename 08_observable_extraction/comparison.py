"""Common extraction and paired-run bootstrap for selection diagnostics."""
import numpy as np

from graal_common.parallel import validate_workers
from observable_extraction.extraction import extract_sample
from observable_extraction.core.binning import PHI_EDGES_RAD
from observable_extraction.core.gate_comparison import paired_difference_summary, point_map
from observable_extraction.core.systematics import paired_bootstrap_by_run


def extract_comparison_samples(samples, exposures, edges, *, workers=1):
    validate_workers(workers)
    if not exposures:
        return {name: () for name in samples}
    return {name: extract_sample(sample_name=name, events=events, exposures=exposures,
                                 estimator="both", retain_ratio_objects=False,
                                 energy_edges=edges, phi_edges=PHI_EDGES_RAD, workers=workers).points
            for name, events in samples.items()}


def bootstrap_comparison(samples, exposures, strata, keys, edges, replicas, seed,
                         *, sample_names=("pairing", "bdt"), workers=1):
    """Return diagnostics and raw draws, including an explicit empty-grid result."""
    validate_workers(workers)
    if not keys:
        return (dict(status="no_common_estimable_bins", replicas=0, seed=seed,
                     available_keys=[], unavailable_keys=[], difference_covariance=None,
                     failed_replicas_by_key={}, run_strata=strata),
                np.empty((0, 0)), (), ())
    counter = 0
    def estimate(replica_samples, replica_exposures):
        nonlocal counter
        counter += 1
        extracted = extract_comparison_samples(replica_samples, replica_exposures, edges)
        lookup = {name: point_map(items) for name, items in extracted.items()}
        if workers == 1 and counter % 10 == 0:
            print(f"paired replica {counter}/{replicas}", flush=True)
        return np.array([lookup[name][key].point.sigma
                         if key in lookup[name] and lookup[name][key].point.diagnostics.converged else np.nan
                         for name in sample_names for key in keys])
    ensemble = paired_bootstrap_by_run(
        estimate, samples, exposures, run_strata=strata,
        point_keys=[f"{name}:{key}" for name in sample_names for key in keys],
        replicas=replicas, seed=seed, workers=workers)
    diagnostic = paired_difference_summary(ensemble.replicas, keys)
    diagnostic.update(status="diagnostic_only", seed=seed, effective_runs=ensemble.effective_runs,
                      zero_event_runs=ensemble.zero_event_runs, run_strata=strata,
                      whole_ensemble_failures=ensemble.failures)
    return diagnostic, ensemble.replicas, ensemble.point_keys, ensemble.run_draws
