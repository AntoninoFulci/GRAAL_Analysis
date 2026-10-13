import numpy as np
import pytest

from observable_extraction.core.models import FluxExposure
from observable_extraction.core.systematics import (
    REQUIRED_SYSTEMATICS,
    bootstrap_run_indices,
    combine_covariances,
    component_from_shift,
    polarization_scale_component,
    randomize_polarization_labels,
)


def test_polarization_scale_is_relative_three_percent():
    nominal = np.array([0.2, -0.4])

    component = polarization_scale_component(nominal, relative_uncertainty=0.03)

    np.testing.assert_allclose(component.magnitude, [0.006, 0.012])
    np.testing.assert_allclose(
        np.diag(component.covariance), [0.006**2, 0.012**2]
    )


def test_bootstrap_resamples_whole_run_blocks():
    runs = np.array([11, 11, 12, 12, 12, 13])

    draws = bootstrap_run_indices(runs, replicas=20, seed=8)

    original_sizes = {11: 2, 12: 3, 13: 1}
    for draw in draws:
        drawn_runs = runs[draw]
        for run, size in original_sizes.items():
            assert np.count_nonzero(drawn_runs == run) % size == 0


def test_bootstrap_is_seeded_and_draws_number_of_unique_runs():
    runs = np.array([11, 11, 12, 13])

    first = bootstrap_run_indices(runs, replicas=3, seed=44)
    second = bootstrap_run_indices(runs, replicas=3, seed=44)

    assert all(np.array_equal(a, b) for a, b in zip(first, second))
    assert all(len(np.unique(runs[draw], return_counts=False)) <= 3 for draw in first)


def test_component_covariance_is_fully_correlated_outer_product():
    component = component_from_shift("background_template", np.array([0.1, -0.2]))

    np.testing.assert_allclose(
        component.covariance,
        [[0.01, -0.02], [-0.02, 0.04]],
    )


def test_covariance_combiner_adds_named_components_and_bootstrap():
    components = [
        component_from_shift("a", np.array([0.1, 0.0])),
        component_from_shift("b", np.array([0.0, 0.2])),
    ]
    bootstrap = np.array([[0.03, 0.01], [0.01, 0.04]])

    total = combine_covariances(components, bootstrap)

    np.testing.assert_allclose(total, [[0.04, 0.01], [0.01, 0.08]])


def test_required_systematics_exclude_root_flux_bin_errors():
    assert "polarization_scale_3pct" in REQUIRED_SYSTEMATICS
    assert "flux_balance" in REQUIRED_SYSTEMATICS
    assert "mass_phi_binning" in REQUIRED_SYSTEMATICS
    assert not any("bin_error" in name for name in REQUIRED_SYSTEMATICS)


def test_randomized_labels_preserve_vertical_horizontal_counts():
    labels = np.array([1, 1, 1, 2, 2, 2, 2])

    randomized = randomize_polarization_labels(labels, seed=19)

    assert sorted(randomized.tolist()) == sorted(labels.tolist())
    assert not np.array_equal(randomized, labels)


def test_randomized_labels_reject_brem_state():
    with pytest.raises(ValueError, match="only states 1 and 2"):
        randomize_polarization_labels(np.array([0, 1, 2]), seed=1)


def test_covariance_rejects_indefinite_and_nonfinite_inputs():
    from observable_extraction.core.systematics import validate_covariance

    for matrix in (np.array([[1., 2.], [2., 1.]]), np.array([[np.nan]]),
                   np.array([[1., 0.], [1., 1.]])):
        with pytest.raises(ValueError):
            validate_covariance(matrix)


def test_paired_difference_uses_cross_covariance_and_preserves_order():
    from observable_extraction.core.systematics import difference_covariance

    covariance = np.array([[1., -0.5], [-0.5, 2.]])
    np.testing.assert_allclose(difference_covariance(covariance, covariance, covariance), 0.)
    np.testing.assert_allclose(difference_covariance(covariance, covariance, np.zeros((2, 2))), 2 * covariance)
    perm = [1, 0]
    result = difference_covariance(covariance, covariance, covariance / 2)
    np.testing.assert_allclose(
        difference_covariance(covariance[np.ix_(perm, perm)], covariance[np.ix_(perm, perm)],
                              covariance[np.ix_(perm, perm)] / 2), result[np.ix_(perm, perm)])
    with pytest.raises(ValueError):
        difference_covariance(covariance, covariance, covariance * 2)


def _run_events(runs):
    from dataclasses import fields
    from observable_extraction.io.reconstructed_events import EventArrays
    values = {field.name: np.zeros(len(runs)) for field in fields(EventArrays)}
    values['run_number'] = np.array(runs, dtype=int)
    return EventArrays(**values)


def _run_exposures(runs):
    return {(run, 1): FluxExposure(run, 1, 1.15, 10., 10., 0., .6, .6) for run in runs}


def test_paired_bootstrap_includes_empty_runs_and_keeps_identical_samples_paired():
    from observable_extraction.core.systematics import paired_bootstrap_by_run, difference_covariance

    events = _run_events([11, 11, 12])  # run 13 has exposure but no selected events
    def estimate(samples, exposures):
        total_flux = sum(exposure.flux_vertical for exposure in exposures.values())
        return np.array([len(samples[name]) / total_flux for name in ('a', 'b')])
    result = paired_bootstrap_by_run(
        estimate, {'a': events, 'b': events}, _run_exposures([11, 12, 13]),
        run_strata={11: 'uv:1998', 12: 'uv:1998', 13: 'uv:1999'},
        point_keys=('a', 'b'), replicas=50, seed=8)
    assert all(draw.count(13) == 1 and len(draw) == 3 for draw in result.run_draws)
    assert result.zero_event_runs == {'a': (13,), 'b': (13,)}
    assert result.covariance is not None
    assert result.rank == 1
    assert result.effective_runs == pytest.approx(3.)
    np.testing.assert_allclose(result.replicas[:, 0], result.replicas[:, 1])
    np.testing.assert_allclose(difference_covariance(
        result.covariance[:1, :1], result.covariance[1:, 1:], result.covariance[:1, 1:]), 0.)
    assert result.covariance_standard_error.shape == (2, 2)
    again = paired_bootstrap_by_run(
        estimate, {'a': events, 'b': events}, _run_exposures([11, 12, 13]),
        run_strata={11: 'uv:1998', 12: 'uv:1998', 13: 'uv:1999'},
        point_keys=('a', 'b'), replicas=50, seed=8)
    np.testing.assert_array_equal(result.replicas, again.replicas)


def test_paired_bootstrap_retains_failed_bins_without_selective_replica_deletion():
    from observable_extraction.core.systematics import paired_bootstrap_by_run

    def estimate(samples, exposures):
        return np.array([len(samples['a']), np.nan])
    result = paired_bootstrap_by_run(
        estimate, {'a': _run_events([11])}, _run_exposures([11, 12]),
        run_strata={11: 'uv:1998', 12: 'uv:1998'}, point_keys=('valid', 'empty'),
        replicas=10, seed=4)
    assert result.replicas.shape == (10, 2)
    assert np.isfinite(result.replicas[:, 0]).all()
    assert np.isnan(result.replicas[:, 1]).all()
    assert len(result.failures) == 10
    assert result.covariance is None
    assert result.rank is None
    assert result.covariance_standard_error is None


def test_paired_bootstrap_rejects_incomplete_strata_and_missing_exposure():
    from observable_extraction.core.systematics import paired_bootstrap_by_run

    common = dict(point_keys=('a',), replicas=10, seed=4)
    with pytest.raises(ValueError, match='strata'):
        paired_bootstrap_by_run(lambda samples, exposures: [0.],
            {'a': _run_events([11])}, _run_exposures([11, 12]), run_strata={11: 'uv'}, **common)
    with pytest.raises(ValueError, match='exposure'):
        paired_bootstrap_by_run(lambda samples, exposures: [0.],
            {'a': _run_events([13])}, _run_exposures([11, 12]),
            run_strata={11: 'uv', 12: 'uv'}, **common)
    with pytest.raises(ValueError, match='at least two'):
        paired_bootstrap_by_run(lambda samples, exposures: [0.],
            {'a': _run_events([11])}, _run_exposures([11]), run_strata={11: 'uv'},
            point_keys=('a',), replicas=1, seed=4)
