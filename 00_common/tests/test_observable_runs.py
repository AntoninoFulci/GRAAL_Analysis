import pytest

from graal_common.observable_runs import (
    ObservableRunError,
    calculate_brem_metrics,
    classify_run_quality,
)
from graal_common.run_manifest import RunRecord
from graal_common.strip_energy_flux import FluxBinRecord


def manifest_rows(*runs, period="period"):
    return tuple(
        RunRecord(
            run, period, "P", "UV", "P_UV", "manual", f"{period}/run{run}.root"
        )
        for run in runs
    )


def flux_row(run, *, brem=1.0, binning="ajaka_cross_section", period="period",
             pol1_net=1.0, pol2_net=1.0):
    return FluxBinRecord(
        binning, run, period, "P", "UV", "P_UV", 1.0, 1.1,
        brem + pol1_net, brem, brem + pol2_net,
        pol1_net, pol2_net, pol1_net + pol2_net, "valid",
    )


def valid_flux_rows(*runs):
    return tuple(flux_row(run) for run in runs)


def brem_rows(totals, *, period="period"):
    return tuple(flux_row(run, brem=value, period=period) for run, value in totals.items())


def qa_for_runs(**overrides):
    qa = {
        "missing_h80_runs": [],
        "nonzero_unmapped_strips": [],
        "monotonic_inversions": [],
        "mad_warnings": [],
        "low_stat_warnings": [],
        "underflow_overflow": [],
        "conservation": {"failures": []},
    }
    qa.update(overrides)
    return qa


def test_bad_precedes_review_and_accumulates_sorted_reasons():
    qa = qa_for_runs(
        missing_h80_runs=[7],
        negative=[7],
        unmapped=[7, 7],
    )
    qa["negative_net_errors"] = [{"run_number": run} for run in qa.pop("negative")]
    qa["nonzero_unmapped_strips"] = [
        {"run_number": run} for run in qa.pop("unmapped")
    ]

    quality = classify_run_quality(manifest_rows(7), qa, valid_flux_rows(7))

    assert quality[0].quality_status == "bad"
    assert quality[0].reason_codes == (
        "missing_h80",
        "negative_net_flux",
        "nonzero_flux_without_lookup",
    )
    assert quality[0].nonzero_unmapped_strip_count == 2
    assert quality[0].negative_net_bin_count == 1


def test_brem_threshold_uses_period_median_without_run_ids():
    rows = brem_rows({1: 10, 2: 10, 3: 10, 4: 10, 5: 1000})

    metrics, outliers, unavailable = calculate_brem_metrics(
        manifest_rows(1, 2, 3, 4, 5), rows,
        reference_binning="ajaka_cross_section",
        outlier_ratio=100.0,
        minimum_period_runs=5,
    )

    assert outliers == {5}
    assert unavailable == set()
    assert metrics[5].ratio == pytest.approx(100.0)


def test_short_or_zero_median_period_is_review_not_good():
    quality = classify_run_quality(
        manifest_rows(1, 2), qa_for_runs(), brem_rows({1: 0, 2: 1}),
        minimum_period_runs=5,
    )

    assert {row.quality_status for row in quality} == {"review"}
    assert all("brem_baseline_unavailable" in row.reason_codes for row in quality)


def test_maps_each_other_run_scoped_qa_reason_and_keeps_clean_run_good():
    qa = qa_for_runs(
        monotonic_inversions=[{"run_number": 1}],
        conservation={"failures": [{"scope": "run", "run_number": 2}]},
        mad_warnings=[{"run_number": 3}],
        low_stat_warnings=[{"run_number": 4}],
        underflow_overflow=[{"histogram": "run5_POL1", "underflow": 1.0, "overflow": 0.0}],
    )

    quality = classify_run_quality(
        manifest_rows(1, 2, 3, 4, 5, 6), qa, valid_flux_rows(1, 2, 3, 4, 5, 6),
        minimum_period_runs=1,
    )

    assert [row.quality_status for row in quality] == [
        "bad", "bad", "review", "review", "review", "good",
    ]
    assert [row.reason_codes for row in quality] == [
        ("monotonic_inversion",),
        ("run_flux_conservation_failure",),
        ("high_energy_mad",),
        ("low_strip_statistics",),
        ("flux_underflow_overflow",),
        (),
    ]


def test_negative_net_flux_counts_run_flux_bins_without_qa_summary():
    rows = (
        flux_row(7, pol1_net=-0.5),
        flux_row(7, brem=2.0, pol2_net=-1.0),
    )

    quality = classify_run_quality(manifest_rows(7), qa_for_runs(), rows, minimum_period_runs=1)

    assert quality[0].quality_status == "review"
    assert quality[0].reason_codes == ("negative_net_flux",)
    assert quality[0].negative_net_bin_count == 2


def test_group_scope_conservation_failure_cannot_be_safely_assigned():
    qa = qa_for_runs(conservation={"failures": [{"scope": "group", "group": "P_UV"}]})

    with pytest.raises(ObservableRunError, match="group.*conservation"):
        classify_run_quality(manifest_rows(7), qa, valid_flux_rows(7))


def test_underflow_overflow_without_a_canonical_run_identifier_aborts():
    qa = qa_for_runs(
        underflow_overflow=[
            {"histogram": "bad_histogram", "underflow": 1.0, "overflow": 0.0}
        ]
    )

    with pytest.raises(ObservableRunError, match="underflow_overflow.*histogram"):
        classify_run_quality(manifest_rows(7), qa, valid_flux_rows(7))


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"outlier_ratio": float("nan")}, "outlier_ratio"),
        ({"outlier_ratio": -1.0}, "outlier_ratio"),
        ({"minimum_period_runs": 0}, "minimum_period_runs"),
    ],
)
def test_brem_threshold_configuration_is_validated(kwargs, match):
    with pytest.raises(ObservableRunError, match=match):
        calculate_brem_metrics(
            manifest_rows(7), valid_flux_rows(7),
            reference_binning="ajaka_cross_section", **({
                "minimum_period_runs": 1,
                "outlier_ratio": 100.0,
            } | kwargs),
        )


def test_duplicate_manifest_runs_and_unknown_qa_runs_abort():
    with pytest.raises(ObservableRunError, match="duplicate manifest run 7"):
        classify_run_quality(manifest_rows(7, 7), qa_for_runs(), valid_flux_rows(7))

    qa = qa_for_runs(mad_warnings=[{"run_number": 99}])
    with pytest.raises(ObservableRunError, match="unknown manifest run 99"):
        classify_run_quality(manifest_rows(7), qa, valid_flux_rows(7))


def test_brem_uses_only_reference_binning_and_rejects_invalid_flux_values():
    rows = (
        flux_row(1, brem=1.0),
        flux_row(1, brem=1000.0, binning="other"),
        flux_row(2, brem=float("inf")),
    )

    with pytest.raises(ObservableRunError, match="brem.*finite"):
        calculate_brem_metrics(
            manifest_rows(1, 2), rows,
            reference_binning="ajaka_cross_section", outlier_ratio=100.0,
            minimum_period_runs=1,
        )
