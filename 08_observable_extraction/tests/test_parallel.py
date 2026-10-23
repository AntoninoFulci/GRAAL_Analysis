"""Worker-count invariance at numerical and diagnostic boundaries."""
from dataclasses import fields, is_dataclass

import numpy as np
import pytest

from observable_extraction import beam_asymmetry as beam
from observable_extraction.core.models import FitNotEstimableError, FluxExposure
from observable_extraction.core.systematics import bootstrap_by_run, paired_bootstrap_by_run
from observable_extraction.tests.test_beam_asymmetry_cli import _synthetic_events
from observable_extraction.tests.test_systematics import _run_events, _run_exposures


def assert_same(left, right):
    if is_dataclass(left):
        for field in fields(left):
            assert_same(getattr(left, field.name), getattr(right, field.name))
    elif isinstance(left, dict):
        assert left.keys() == right.keys()
        for key in left:
            assert_same(left[key], right[key])
    elif isinstance(left, (tuple, list)):
        assert len(left) == len(right)
        for a, b in zip(left, right):
            assert_same(a, b)
    elif isinstance(left, (np.ndarray, float)):
        np.testing.assert_allclose(left, right, rtol=1e-12, atol=1e-12, equal_nan=True)
    else:
        assert left == right


@pytest.mark.parametrize('best_binning', [False, True])
def test_parallel_extraction_preserves_points_candidates_and_curves(best_binning):
    kwargs = dict(sample_name='raw_bdt', events=_synthetic_events(),
                  exposures={(811, 17): FluxExposure(811, 17, 1.15, 1.2, .9, .2, .6, .55)},
                  estimator='both', retain_ratio_objects=True,
                  energy_edges=np.array([1.1, 1.2, 1.3]), best_binning=best_binning)
    serial = beam._extract_sample(**kwargs)
    parallel = beam._extract_sample(**kwargs, workers=2)
    assert len(serial.points) == 6
    assert_same(serial, parallel)


def test_parallel_paired_bootstrap_preserves_draws_empty_runs_and_covariance():
    def estimate(samples, exposures):
        flux = sum(row.flux_vertical for row in exposures.values())
        return np.array([len(samples[name]) / flux for name in ('a', 'b')])
    kwargs = dict(samples={'a': _run_events([11, 11, 12]), 'b': _run_events([11, 11, 12])},
                  exposures=_run_exposures([11, 12, 13]),
                  run_strata={11: 'a', 12: 'a', 13: 'b'}, point_keys=('a', 'b'), replicas=12, seed=8)
    serial = paired_bootstrap_by_run(estimate, **kwargs)
    parallel = paired_bootstrap_by_run(estimate, **kwargs, workers=2)
    assert_same(serial, parallel)
    assert all(draw.count(13) == 1 for draw in parallel.run_draws)
    np.testing.assert_array_equal(parallel.replicas[:, 0], parallel.replicas[:, 1])


def test_parallel_bootstrap_preserves_expected_failures_without_redrawing():
    def estimate(samples, exposures):
        if not len(samples['a']):
            raise FitNotEstimableError('empty replica')
        return np.array([len(samples['a']), np.nan])
    kwargs = dict(samples={'a': _run_events([11])}, exposures=_run_exposures([11, 12]),
                  run_strata={11: 'a', 12: 'a'}, point_keys=('a', 'missing'), replicas=12, seed=4)
    serial = paired_bootstrap_by_run(estimate, **kwargs)
    parallel = paired_bootstrap_by_run(estimate, **kwargs, workers=2)
    assert_same(serial, parallel)
    assert len(parallel.failures) == 12
    assert 'empty replica' in parallel.failures.values()
    assert parallel.covariance is None


def test_parallel_bootstrap_propagates_software_errors():
    def broken(samples, exposures):
        raise RuntimeError('software defect')
    with pytest.raises(RuntimeError, match='software defect'):
        paired_bootstrap_by_run(broken, {'a': _run_events([11])}, _run_exposures([11]),
                                run_strata={11: 'a'}, point_keys=('a',), replicas=2, seed=4, workers=2)


def test_parallel_legacy_bootstrap_preserves_seeded_ensemble():
    def estimate(events, exposures):
        return np.array([len(events), sum(row.flux_vertical for row in exposures.values())])
    kwargs = dict(events=_run_events([11, 11, 12]), exposures=_run_exposures([11, 12]), replicas=8, seed=4)
    assert_same(bootstrap_by_run(estimate, **kwargs), bootstrap_by_run(estimate, **kwargs, workers=2))


def test_worker_cli_defaults_and_rejects_nonpositive_values():
    assert beam.build_parser().parse_args([]).workers == 1
    assert beam.build_parser().parse_args(['--workers', '2']).workers == 2
    with pytest.raises(SystemExit):
        beam.build_parser().parse_args(['--workers', '0'])


def test_parallel_mass_comparison_keeps_common_draws_and_complete_report():
    from observable_extraction.compare_mass_selection import compare_mass_samples
    from .test_mass_comparison import sample, exposures
    kwargs = dict(before=sample(), exposures=exposures(), periods={1: 'p', 2: 'p', 3: 'zero'},
                  edges=[1.1, 1.3], polygon=None, replicas=3, seed=12)
    serial_report, serial_arrays = compare_mass_samples(**kwargs)
    parallel_report, parallel_arrays = compare_mass_samples(**kwargs, workers=2)
    assert_same(serial_report, parallel_report)
    for key in serial_arrays:
        np.testing.assert_array_equal(serial_arrays[key], parallel_arrays[key])
    assert parallel_report['event_counts'] == {'before': 1200, 'after': 1200}
    np.testing.assert_allclose(parallel_report['bootstrap']['difference_covariance'], 0., atol=1e-18)


def test_comparison_clis_accept_workers_and_reject_zero():
    from observable_extraction.compare_gate import build_parser as gate_parser
    from observable_extraction.compare_mass_selection import build_parser as mass_parser
    gate_args = ['--pairing', 'a', '--bdt', 'b', '--flux-file', 'f', '--run-manifest', 'm',
                 '--profile', 'uv', '--output-dir', 'o']
    mass_args = ['compare', '--input', 'a', '--flux-file', 'f', '--run-manifest', 'm',
                 '--profile', 'uv', '--output-dir', 'o']
    for parser, argv in ((gate_parser(), gate_args), (mass_parser(), mass_args)):
        assert parser.parse_args(argv).workers == 1
        assert parser.parse_args([*argv, '--workers', '2']).workers == 2
        with pytest.raises(SystemExit):
            parser.parse_args([*argv, '--workers', '0'])


@pytest.mark.parametrize('kind', ['ratio', 'likelihood'])
def test_parallel_fit_grid_keeps_multiple_energy_mass_bins_in_order(kind):
    from observable_extraction.core.ratio_fit import extract_ratio_grid
    from observable_extraction.core.conditional_likelihood import extract_likelihood_grid
    centers = (np.arange(12) + .5) * (2 * np.pi / 12)
    phi = np.tile(np.repeat(centers, 40), 4)
    states = np.tile([1, 2], len(phi) // 2)
    energy = np.repeat([1.15, 1.15, 1.25, 1.25], 480)
    mass = np.repeat([1.02, 1.06, 1.02, 1.06], 480)
    runs = np.repeat([11, 11, 12, 12], 480)
    kwargs = dict(pair='p_pi0', mass_gev=mass, phi_rad=phi, beam_energy_gev=energy,
                  polarization=states, energy_edges=np.array([1.1, 1.2, 1.3]),
                  exposures={(run, 1): FluxExposure(run, 1, value, 10., 10., 0., .6, .6)
                             for run, value in [(11, 1.15), (12, 1.25)]})
    function = extract_ratio_grid
    if kind == 'likelihood':
        function = extract_likelihood_grid
        kwargs.update(run_number=runs, xstrip=np.ones(len(phi), dtype=int))
    serial = function(**kwargs)
    parallel = function(**kwargs, workers=2)
    assert [(row.point.energy_bin, row.point.mass_bin) for row in parallel] == [(0, 0), (0, 1), (1, 0), (1, 1)]
    assert all(abs(row.point.sigma) < 1e-5 for row in parallel)
    assert_same(serial, parallel)


def test_parallel_likelihood_propagates_missing_event_exposure():
    from observable_extraction.core.conditional_likelihood import extract_likelihood_grid
    with pytest.raises(ValueError, match='missing exposure'):
        extract_likelihood_grid(pair='p_pi0', mass_gev=np.full(20, 1.02),
                                phi_rad=np.zeros(20), beam_energy_gev=np.full(20, 1.15),
                                polarization=np.tile([1, 2], 10), run_number=np.full(20, 999),
                                xstrip=np.ones(20), exposures={}, workers=2)
