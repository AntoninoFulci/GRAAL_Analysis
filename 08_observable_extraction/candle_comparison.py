"""Selection differences and optional shared-run covariance for the mass candle."""
import numpy as np

from observable_extraction.core.gate_comparison import (
    align_points, point_map, paired_difference_summary, difference_errors,
)
from observable_extraction.core.systematics import paired_bootstrap_by_run
from observable_extraction.extraction import extract_sample


SAMPLE_NAMES = ('raw_bdt', 'raw_bdt_core', 'raw_bdt_tails')


def compare_candle_samples(samples, points, exposures, energy_edges, phi_edges, *, estimator,
                           selected_phi_bins=None, replicas=0, seed=1208, run_strata=None, workers=1):
    """Keep missing covariance missing; optional bootstrap holds the fitted contour fixed.

    Runs are drawn once for all three overlapping samples and their exposure
    records. These are conditional run-block diagnostics, not a final event
    uncertainty or an uncertainty on the fitted mass contour.
    """
    if replicas < 0 or replicas == 1:
        raise ValueError('candle comparison needs zero or at least two replicas')
    pairs = {'full_core': ('raw_bdt', 'raw_bdt_core'), 'core_tails': ('raw_bdt_core', 'raw_bdt_tails')}
    comparisons = {}
    for label, names in pairs.items():
        rows = align_points(points[names[0]], points[names[1]], energy_edges, sample_names=names)
        rows = [row for row in rows if estimator == 'both' or row['estimator'] == estimator]
        for row in rows:
            row['delta_run_error'] = None
        comparisons[label] = dict(sample_names=names, rows=rows, bootstrap=None)
    report = dict(schema=1, sample_counts={name: len(samples[name]) for name in SAMPLE_NAMES},
                  comparisons=comparisons, uncertainty_status='not_evaluated',
                  contour_uncertainty='not_evaluated; fitted contour held fixed',
                  interpretation='selection diagnostic; no independence assumption for full/core',
                  phi_edges_rad=np.asarray(phi_edges).tolist(),
                  energy_edges_gev=np.asarray(energy_edges).tolist())
    if not replicas:
        return report, {}
    if run_strata is None:
        raise ValueError('paired candle bootstrap requires inclusive run strata')
    keys = sorted({row['key'] for comparison in comparisons.values() for row in comparison['rows']
                   if row['status'] == 'both_estimable'})
    if not keys:
        report['uncertainty_status'] = 'no_common_estimable_bins'
        return report, {}

    def estimate(replica_samples, replica_exposures):
        lookups = {}
        for name in SAMPLE_NAMES:
            result = extract_sample(sample_name=name, events=replica_samples[name],
                exposures=replica_exposures, estimator=estimator, retain_ratio_objects=False,
                energy_edges=energy_edges, phi_edges=phi_edges, selected_phi_bins=selected_phi_bins)
            lookups[name] = point_map(result.points)
        return np.array([lookups[name][key].point.sigma
                         if key in lookups[name] and lookups[name][key].point.diagnostics.converged else np.nan
                         for name in SAMPLE_NAMES for key in keys])

    ensemble = paired_bootstrap_by_run(estimate, samples, exposures, run_strata=run_strata,
        point_keys=[f'{name}:{key}' for name in SAMPLE_NAMES for key in keys],
        replicas=replicas, seed=seed, workers=workers)
    size = len(keys)
    for label, names in pairs.items():
        selected_keys = [row['key'] for row in comparisons[label]['rows'] if row['status'] == 'both_estimable']
        indices = [keys.index(key) for key in selected_keys]
        columns = [SAMPLE_NAMES.index(name) * size + index for name in names for index in indices]
        diagnostic = paired_difference_summary(ensemble.replicas[:, columns], selected_keys)
        comparisons[label]['bootstrap'] = diagnostic
        errors = difference_errors(diagnostic)
        for row in comparisons[label]['rows']:
            row['delta_run_error'] = float(errors[row['key']]) if row['key'] in errors else None
    report.update(uncertainty_status='paired_run_diagnostic_only', replicas=replicas, seed=seed,
                  effective_runs=ensemble.effective_runs, zero_event_runs=ensemble.zero_event_runs,
                  run_strata=run_strata, failures=ensemble.failures)
    return report, dict(replicas=ensemble.replicas, keys=np.asarray(ensemble.point_keys),
                        run_draws=np.asarray(ensemble.run_draws, dtype=np.int64))
