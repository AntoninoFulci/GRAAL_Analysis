from __future__ import annotations

import pytest

from contracts import PolarizationContractError
from state_mapping import (
    StateInterval,
    resolve_flux_component,
    resolve_orientation,
    validate_intervals,
)


def test_mapping_resolves_only_matching_run_and_state():
    intervals = [
        StateInterval(100, 199, 1, "parallel", "2002_p", "pol1_net"),
        StateInterval(100, 199, 2, "perpendicular", "2002_p", "pol2_net"),
    ]
    assert resolve_orientation(150, 1, intervals) == "parallel"
    assert resolve_orientation(150, 2, intervals) == "perpendicular"
    assert resolve_flux_component(150, 1, intervals) == "pol1_net"
    assert resolve_flux_component(150, 2, intervals) == "pol2_net"
    with pytest.raises(PolarizationContractError, match="unmapped"):
        resolve_orientation(200, 2, intervals)


def test_mapping_rejects_overlapping_same_state_intervals():
    intervals = [
        StateInterval(100, 150, 1, "parallel", "2002_p", "pol1_net"),
        StateInterval(150, 200, 1, "perpendicular", "2002_p", "pol2_net"),
    ]
    with pytest.raises(PolarizationContractError, match="overlap"):
        validate_intervals(intervals)


@pytest.mark.parametrize("orientation", ["POL1", "POL2", "unknown", "Parallel"])
def test_mapping_rejects_noncanonical_orientation(orientation):
    with pytest.raises(PolarizationContractError, match="orientation"):
        StateInterval(100, 199, 1, orientation, "2002_p", "pol1_net")


def test_mapping_rejects_invalid_ranges_codes_and_periods():
    with pytest.raises(PolarizationContractError, match="run range"):
        StateInterval(200, 100, 1, "parallel", "2002_p", "pol1_net")
    with pytest.raises(PolarizationContractError, match="state_code"):
        StateInterval(100, 200, True, "parallel", "2002_p", "pol1_net")
    with pytest.raises(PolarizationContractError, match="source_period"):
        StateInterval(100, 200, 1, "parallel", "", "pol1_net")


@pytest.mark.parametrize("component", ["POL1", "pol1", "total_net", ""])
def test_mapping_rejects_noncanonical_flux_component(component):
    with pytest.raises(PolarizationContractError, match="flux_component"):
        StateInterval(100, 199, 1, "parallel", "2002_p", component)


def test_mapping_rejects_ambiguous_resolution_even_before_validation():
    intervals = [
        StateInterval(100, 200, 1, "parallel", "2002_p", "pol1_net"),
        StateInterval(150, 250, 1, "parallel", "2002_p", "pol1_net"),
    ]
    with pytest.raises(PolarizationContractError, match="ambiguous"):
        resolve_orientation(175, 1, intervals)
