"""Full/subset comparisons must keep overlap and non-estimable bins explicit."""
import numpy as np

from observable_extraction.tests.test_beam_asymmetry_cli import _synthetic_events
from observable_extraction.core.models import FluxExposure
from observable_extraction.core.binning import PHI_EDGES_RAD
from observable_extraction.extraction import extract_sample


def test_candle_difference_no_independent_error_and_shared_bootstrap_closure():
    from observable_extraction.candle_comparison import compare_candle_samples
    events = _synthetic_events()
    samples = dict(raw_bdt=events, raw_bdt_core=events, raw_bdt_tails=events)
    exposures = {(811, 17): FluxExposure(811, 17, 1.15, 1.2, .9, .2, .6, .55),
                 (812, 17): FluxExposure(812, 17, 1.15, 1.2, .9, .2, .6, .55)}
    edges = np.array([1.1, 1.2])
    points = {name: extract_sample(sample_name=name, events=data, exposures=exposures,
                                  estimator='ratio', retain_ratio_objects=False,
                                  energy_edges=edges).points for name, data in samples.items()}
    report, _ = compare_candle_samples(samples, points, exposures, edges, PHI_EDGES_RAD, estimator='ratio')
    assert report['uncertainty_status'] == 'not_evaluated'
    common = [row for row in report['comparisons']['full_core']['rows'] if row['status'] == 'both_estimable']
    assert common and all(row['delta'] == 0 and row['delta_run_error'] is None for row in common)
    report, arrays = compare_candle_samples(samples, points, exposures, edges, PHI_EDGES_RAD,
        estimator='ratio', replicas=5, seed=20, run_strata={811: 'a', 812: 'b'})
    assert arrays['run_draws'].shape == (5, 2)
    diagnostic = report['comparisons']['full_core']['bootstrap']
    np.testing.assert_allclose(diagnostic['difference_covariance'], 0., atol=1e-14)
    assert all(list(runs) == [812] for runs in report['zero_event_runs'].values())
