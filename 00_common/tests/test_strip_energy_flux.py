import math

import pytest

from graal_common.run_manifest import RunRecord
from graal_common.strip_energy_flux import (
    AJAKA_CROSS_SECTION,
    AJAKA_SIGMA,
    EnergySample,
    EnergyBinning,
    FluxBinRecord,
    StripEnergyFluxError,
    StripEnergyRecord,
    StripFlux,
    aggregate_group_flux,
    build_strip_energy_lookup,
    energy_bin_index,
    find_monotonic_inversions,
    integrate_run_flux,
    normalize_xstrip,
)


def lookup(run, strip, energy):
    return StripEnergyRecord(run, strip, 10, energy, 0.0, energy, energy)


def manifest(run, group="P_UV"):
    target, beam = group.split("_")
    return RunRecord(
        run, "period", target, beam, group, "manual", f"period/run{run}.root"
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


def test_flux_integration_sums_whole_strips_and_subtracts_brem_twice():
    bins = EnergyBinning("two_bins", (1.0, 1.2, 1.4))
    result = integrate_run_flux(
        manifest(7),
        [lookup(7, 1, 1.10), lookup(7, 2, 1.19), lookup(7, 3, 1.30)],
        [
            StripFlux(7, 1, 100.0, 10.0, 80.0),
            StripFlux(7, 2, 50.0, 5.0, 40.0),
            StripFlux(7, 3, 20.0, 2.0, 16.0),
        ],
        bins,
    )
    assert (result[0].pol1, result[0].brem, result[0].pol2) == (
        150.0,
        15.0,
        120.0,
    )
    assert result[0].pol1_net == 135.0
    assert result[0].pol2_net == 105.0
    assert result[0].total_net == 240.0


def test_nonzero_flux_without_lookup_is_fatal():
    with pytest.raises(StripEnergyFluxError, match="nonzero flux"):
        integrate_run_flux(
            manifest(7), [], [StripFlux(7, 12, 1.0, 0.0, 1.0)],
            EnergyBinning("one", (1.0, 1.5)),
        )


def test_negative_net_flux_is_fatal():
    with pytest.raises(StripEnergyFluxError, match="negative net flux"):
        integrate_run_flux(
            manifest(7), [lookup(7, 1, 1.2)],
            [StripFlux(7, 1, 2.0, 3.0, 4.0)],
            EnergyBinning("one", (1.0, 1.5)),
        )


def test_group_aggregation_never_mixes_manifest_groups():
    bins = EnergyBinning("one", (1.0, 1.5))
    p = integrate_run_flux(
        manifest(7, "P_UV"), [lookup(7, 1, 1.2)],
        [StripFlux(7, 1, 10.0, 1.0, 8.0)], bins,
    )
    d = integrate_run_flux(
        manifest(8, "D_UV"), [lookup(8, 1, 1.2)],
        [StripFlux(8, 1, 20.0, 2.0, 16.0)], bins,
    )
    grouped = aggregate_group_flux((*p, *d))
    assert [row.group for row in grouped] == ["D_UV", "P_UV"]
    assert [row.total_net for row in grouped] == [32.0, 16.0]


def test_group_aggregation_recomputes_net_flux_from_raw_sums():
    grouped = aggregate_group_flux(
        (
            FluxBinRecord(
                "one", 7, "period", "P", "UV", "P_UV", 1.0, 1.5,
                10.0, 3.0, 8.0, 999.0, 999.0, 999.0, "valid",
            ),
            FluxBinRecord(
                "one", 8, "period", "P", "UV", "P_UV", 1.0, 1.5,
                5.0, 1.0, 4.0, -999.0, -999.0, -999.0, "valid",
            ),
        )
    )
    assert (grouped[0].pol1, grouped[0].brem, grouped[0].pol2) == (
        15.0,
        4.0,
        12.0,
    )
    assert (grouped[0].pol1_net, grouped[0].pol2_net, grouped[0].total_net) == (
        11.0,
        8.0,
        19.0,
    )


def test_group_aggregation_rejects_negative_net_flux_from_raw_sums():
    with pytest.raises(StripEnergyFluxError, match="negative net flux"):
        aggregate_group_flux(
            (
                FluxBinRecord(
                    "one", 7, "period", "P", "UV", "P_UV", 1.0, 1.5,
                    1.0, 2.0, 3.0, 99.0, 99.0, 198.0, "valid",
                ),
            )
        )


def test_flux_run_conflict_error_includes_manifest_run_and_flux_strip():
    with pytest.raises(StripEnergyFluxError, match=r"run 7 strip 12"):
        integrate_run_flux(
            manifest(7), [], [StripFlux(8, 12, 1.0, 0.0, 1.0)],
            EnergyBinning("one", (1.0, 1.5)),
        )


def test_nonfinite_flux_error_includes_manifest_run_and_flux_strip():
    with pytest.raises(StripEnergyFluxError, match=r"run 7 strip 12"):
        integrate_run_flux(
            manifest(7), [lookup(7, 12, 1.2)],
            [StripFlux(7, 12, math.nan, 0.0, 1.0)],
            EnergyBinning("one", (1.0, 1.5)),
        )
