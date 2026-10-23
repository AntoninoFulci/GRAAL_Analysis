import numpy as np
import pytest

from graal_theory.observables import Histogram
from graal_theory.validation import (
    ReferenceCurve,
    _check_observable_integrity,
    compare_curve,
    compare_factor_two,
    validate_figure14_tree,
)


def test_curve_validation_rejects_twenty_one_percent_shift():
    reference = ReferenceCurve(
        np.array([1.50, 1.51, 1.52]),
        np.array([10.0, 20.0, 10.0]),
        relative_uncertainty=0.0,
    )
    result = compare_curve(reference.y * 1.21, reference, relative_tolerance=0.20)
    assert not result.passed


def test_factor_two_validation_uses_partial_over_full_ratio():
    result = compare_factor_two(partial=0.50, full=1.00, relative_tolerance=0.20)
    assert result.passed
    assert result.ratio == pytest.approx(0.5)


def test_curve_interpolation_rejects_outside_physical_histogram_support():
    histogram = Histogram(np.array([1.50, 1.51, 1.52]), np.array([2.0, 2.0]))
    reference = ReferenceCurve(np.array([1.49, 1.505]), np.array([1.0, 2.0]))
    with pytest.raises(ValueError, match="outside"):
        validate_figure14_tree(histogram, reference)


def test_zero_reference_points_are_reported_but_not_compared():
    reference = ReferenceCurve(np.array([1.50, 1.51]), np.array([0.0, 2.0]))
    result = compare_curve(np.array([100.0, 2.0]), reference)
    assert result.passed
    assert result.compared_points == 1


def test_bundle_integrity_rejects_nonfinite_or_inconsistent_total():
    arrays = {
        "partial_cross_section_microbarn": np.array([2.0]),
        "phase_space_volume_gev2": np.array([1e-6]),
    }
    for name in ("eta_p", "pi0_p", "eta_pi0"):
        arrays[f"{name}_edges_0"] = np.array([1.0, 2.0])
        arrays[f"{name}_density_0"] = np.array([2.0])
    _check_observable_integrity(arrays, np.array([1.2]))
    arrays["partial_cross_section_microbarn"] = np.array([np.nan])
    with pytest.raises(ValueError, match="cross section"):
        _check_observable_integrity(arrays, np.array([1.2]))
    arrays["partial_cross_section_microbarn"] = np.array([1.0])
    with pytest.raises(ValueError, match="integral"):
        _check_observable_integrity(arrays, np.array([1.2]))
