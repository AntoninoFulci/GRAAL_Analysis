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
