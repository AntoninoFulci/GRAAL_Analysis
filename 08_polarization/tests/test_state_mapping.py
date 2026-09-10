from __future__ import annotations

import pytest

from contracts import PolarizationContractError
from state_mapping import StateInterval, resolve_orientation, validate_intervals


def test_mapping_resolves_only_matching_run_and_state():
    intervals = [
        StateInterval(100, 199, 1, "parallel", "2002_p"),
        StateInterval(100, 199, 2, "perpendicular", "2002_p"),
    ]
    assert resolve_orientation(150, 1, intervals) == "parallel"
    assert resolve_orientation(150, 2, intervals) == "perpendicular"
    with pytest.raises(PolarizationContractError, match="unmapped"):
        resolve_orientation(200, 2, intervals)


def test_mapping_rejects_overlapping_same_state_intervals():
    intervals = [
        StateInterval(100, 150, 1, "parallel", "2002_p"),
        StateInterval(150, 200, 1, "perpendicular", "2002_p"),
    ]
    with pytest.raises(PolarizationContractError, match="overlap"):
        validate_intervals(intervals)


@pytest.mark.parametrize("orientation", ["POL1", "POL2", "unknown", "Parallel"])
def test_mapping_rejects_noncanonical_orientation(orientation):
    with pytest.raises(PolarizationContractError, match="orientation"):
        StateInterval(100, 199, 1, orientation, "2002_p")


def test_mapping_rejects_invalid_ranges_codes_and_periods():
    with pytest.raises(PolarizationContractError, match="run range"):
        StateInterval(200, 100, 1, "parallel", "2002_p")
    with pytest.raises(PolarizationContractError, match="state_code"):
        StateInterval(100, 200, True, "parallel", "2002_p")
    with pytest.raises(PolarizationContractError, match="source_period"):
        StateInterval(100, 200, 1, "parallel", "")


def test_mapping_rejects_ambiguous_resolution_even_before_validation():
    intervals = [
        StateInterval(100, 200, 1, "parallel", "2002_p"),
        StateInterval(150, 250, 1, "parallel", "2002_p"),
    ]
    with pytest.raises(PolarizationContractError, match="ambiguous"):
        resolve_orientation(175, 1, intervals)
