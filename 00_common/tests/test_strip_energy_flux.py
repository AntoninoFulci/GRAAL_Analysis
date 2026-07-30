import math

import pytest

from graal_common.strip_energy_flux import (
    AJAKA_CROSS_SECTION,
    AJAKA_SIGMA,
    EnergySample,
    StripEnergyFluxError,
    build_strip_energy_lookup,
    energy_bin_index,
    find_monotonic_inversions,
    normalize_xstrip,
)


def test_ajaka_binning_presets_are_exact():
    assert len(AJAKA_CROSS_SECTION.edges_gev) == 16
    assert AJAKA_CROSS_SECTION.edges_gev[0] == pytest.approx(0.95)
    assert AJAKA_CROSS_SECTION.edges_gev[-1] == pytest.approx(1.50)
    assert AJAKA_SIGMA.edges_gev == (1.10, 1.20, 1.30, 1.40, 1.50)


def test_energy_bins_are_left_closed_and_final_bin_is_right_closed():
    assert energy_bin_index(1.10, AJAKA_SIGMA) == 0
    assert energy_bin_index(1.20, AJAKA_SIGMA) == 1
    assert energy_bin_index(1.50, AJAKA_SIGMA) == 3
    assert energy_bin_index(math.nextafter(1.50, math.inf), AJAKA_SIGMA) is None


def test_lookup_uses_median_and_mad_per_run_strip():
    records = build_strip_energy_lookup(
        [
            EnergySample(7, 12.0, 1.20),
            EnergySample(7, 12.0, 1.22),
            EnergySample(7, 12.0, 1.80),
            EnergySample(7, 13.0, 1.30),
        ]
    )
    first = records[0]
    assert (first.run_number, first.xstrip, first.event_count) == (7, 12, 3)
    assert first.energy_median_gev == pytest.approx(1.22)
    assert first.energy_mad_gev == pytest.approx(0.02)
    assert first.energy_min_gev == pytest.approx(1.20)
    assert first.energy_max_gev == pytest.approx(1.80)


@pytest.mark.parametrize("value", [0.0, 129.0, 12.25, math.nan, math.inf])
def test_xstrip_rejects_out_of_domain_or_nonintegral_values(value):
    with pytest.raises(StripEnergyFluxError):
        normalize_xstrip(value)


def test_monotonicity_accepts_decreasing_map_and_reports_local_inversion():
    records = build_strip_energy_lookup(
        [
            EnergySample(7, 1, 1.50),
            EnergySample(7, 2, 1.40),
            EnergySample(7, 3, 1.45),
            EnergySample(7, 4, 1.20),
        ]
    )
    inversions = find_monotonic_inversions(records)
    assert len(inversions) == 1
    assert inversions[0]["left_strip"] == 2
    assert inversions[0]["right_strip"] == 3
    assert inversions[0]["delta_gev"] == pytest.approx(0.05)


def test_monotonicity_marks_zero_covariance_direction_as_undetermined():
    records = build_strip_energy_lookup(
        [
            EnergySample(7, 1, 1.40),
            EnergySample(7, 2, 1.50),
            EnergySample(7, 3, 1.40),
        ]
    )
    assert find_monotonic_inversions(records) == (
        {"run_number": 7, "direction": "undetermined"},
    )
