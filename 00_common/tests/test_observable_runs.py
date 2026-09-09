import csv
import hashlib
import json

import pytest

from graal_common.observable_runs import (
    BremMetric,
    ObservableRunError,
    RunQuality,
    calculate_brem_metrics,
    classify_run_quality,
    read_lookup_artifact,
    read_run_flux_artifact,
    read_source_qa,
    sha256_file,
    validate_source_qa_errors,
    write_run_quality_csv,
)
from graal_common.run_manifest import RunRecord
from graal_common.strip_energy_flux import (
    LOOKUP_FIELDS,
    RUN_FLUX_FIELDS,
    FluxBinRecord,
    StripEnergyRecord,
)


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


def write_artifact(path, fields, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def lookup_artifact_row(run=7, **overrides):
    row = {
        "run_number": run,
        "source_period": "period",
        "target": "P",
        "beam_type": "UV",
        "group": "P_UV",
        "xstrip": 1,
        "event_count": 10,
        "energy_median_gev": 1.2,
        "energy_mad_gev": 0.01,
        "energy_min_gev": 1.1,
        "energy_max_gev": 1.3,
        "provenance": "observed",
    }
    row.update(overrides)
    return row


def run_flux_artifact_row(run=7, **overrides):
    row = {
        "binning": "ajaka_cross_section",
        "run_number": run,
        "source_period": "period",
        "target": "P",
        "beam_type": "UV",
        "group": "P_UV",
        "energy_low_gev": 1.0,
        "energy_high_gev": 1.1,
        "pol1": 4.0,
        "brem": 1.0,
        "pol2": 5.0,
        "pol1_net": 3.0,
        "pol2_net": 4.0,
        "total_net": 7.0,
        "status": "valid",
    }
    row.update(overrides)
    return row


def source_qa(**overrides):
    qa = {
        "schema_version": 1,
        "inputs": {},
        "thresholds": {},
        "binnings": {},
        "manifest_run_count": 1,
        "h80_run_count": 1,
        "flux_run_count": 1,
        "lookup_strip_count": 1,
        "h80": {},
        "flux": {},
        "missing_h80_runs": [],
        "extra_h80_runs": [],
        "extra_h80_run_count": 0,
        "extra_h80_runs_truncated": False,
        "extra_flux_runs": [],
        "malformed_flux_triplets": [],
        "empty_strips": [],
        "nonzero_unmapped_strips": [],
        "monotonic_inversions": [],
        "mad_warnings": [],
        "low_stat_warnings": [],
        "underflow_overflow": [],
        "out_of_range": {},
        "negative_net_errors": [],
        "conservation": {"failures": []},
        "run_flux_bin_count": 1,
        "errors": [],
        "valid": True,
    }
    qa.update(overrides)
    return qa


def quality_row(run=7, *, brem=BremMetric(1.0, 1.0, 1.0)):
    return RunQuality(manifest_rows(run)[0], "good", (), 0, 0, brem)


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
        mad_warnings=[{"run_number": 3, "xstrip": 1, "energy_mad_gev": 0.02}],
        low_stat_warnings=[{"run_number": 4, "xstrip": 1, "event_count": 1}],
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


def test_finite_negative_raw_brem_is_review_not_a_global_error():
    rows = (
        flux_row(1, brem=100.0),
        flux_row(1, brem=-1.0),
        flux_row(2, brem=10.0),
    )

    quality = classify_run_quality(
        manifest_rows(1, 2), qa_for_runs(), rows, minimum_period_runs=1
    )

    assert quality[0].quality_status == "review"
    assert quality[0].reason_codes == ("negative_raw_brem",)
    assert quality[0].brem.reference_sum == pytest.approx(99.0)
    assert quality[0].brem.period_median == pytest.approx(54.5)
    assert quality[1].quality_status == "good"


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
    ("section", "entry", "match"),
    [
        (
            "mad_warnings",
            {"run_number": 7, "xstrip": 129, "energy_mad_gev": 0.01},
            "mad_warnings.*xstrip",
        ),
        (
            "mad_warnings",
            {"run_number": 7, "xstrip": 1, "energy_mad_gev": -0.01},
            "mad_warnings.*energy_mad",
        ),
        (
            "low_stat_warnings",
            {"run_number": 7, "xstrip": 1, "event_count": 1.5},
            "low_stat_warnings.*event_count",
        ),
        (
            "underflow_overflow",
            {"histogram": "run7_POL1_extra", "underflow": 1.0, "overflow": 0.0},
            "underflow_overflow.*histogram",
        ),
        (
            "underflow_overflow",
            {"run_number": 8, "histogram": "run7_POL1", "underflow": 1.0, "overflow": 0.0},
            "underflow_overflow.*run_number",
        ),
    ],
)
def test_warning_payloads_are_strict_and_reconcile_histogram_identity(section, entry, match):
    """Relaxing a warning shape could silently assign it to the wrong run."""
    qa = qa_for_runs(**{section: [entry]})

    with pytest.raises(ObservableRunError, match=match):
        classify_run_quality(manifest_rows(7), qa, valid_flux_rows(7), minimum_period_runs=1)


def test_warning_payloads_reject_unknown_manifest_runs():
    """A producer warning for a non-manifest run is not safe to ignore."""
    qa = qa_for_runs(
        low_stat_warnings=[{"run_number": 99, "xstrip": 1, "event_count": 0}]
    )

    with pytest.raises(ObservableRunError, match="unknown manifest run 99.*low_stat_warnings"):
        classify_run_quality(manifest_rows(7), qa, valid_flux_rows(7), minimum_period_runs=1)


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

    qa = qa_for_runs(
        mad_warnings=[{"run_number": 99, "xstrip": 1, "energy_mad_gev": 0.02}]
    )
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


def test_lookup_reader_reconstructs_records_from_the_exact_source_schema(tmp_path):
    path = tmp_path / "strip_energy_lookup.csv"
    write_artifact(path, LOOKUP_FIELDS, [lookup_artifact_row()])

    records = read_lookup_artifact(path, {7: manifest_rows(7)[0]})

    assert records == (
        StripEnergyRecord(7, 1, 10, 1.2, 0.01, 1.1, 1.3, "observed"),
    )


@pytest.mark.parametrize(
    ("fields", "rows", "match"),
    [
        (LOOKUP_FIELDS[:-1], [lookup_artifact_row()], "header"),
        (LOOKUP_FIELDS, [lookup_artifact_row(), lookup_artifact_row()], "duplicate.*7.*1"),
        (LOOKUP_FIELDS, [lookup_artifact_row(energy_mad_gev="nan")], "row 2.*finite"),
        (LOOKUP_FIELDS, [lookup_artifact_row(event_count=0)], "row 2.*positive integer"),
        (LOOKUP_FIELDS, [lookup_artifact_row(energy_mad_gev=-0.01)], "row 2.*energy_mad"),
        (LOOKUP_FIELDS, [lookup_artifact_row(energy_min_gev=1.25)], "row 2.*energy statistics"),
        (LOOKUP_FIELDS, [lookup_artifact_row(target="D")], "row 2.*metadata"),
        (LOOKUP_FIELDS, [lookup_artifact_row(run=99)], "row 2.*unknown manifest run 99"),
    ],
)
def test_lookup_reader_rejects_invalid_source_rows(tmp_path, fields, rows, match):
    path = tmp_path / "strip_energy_lookup.csv"
    write_artifact(path, fields, rows)

    with pytest.raises(ObservableRunError, match=match):
        read_lookup_artifact(path, {7: manifest_rows(7)[0]})


def test_run_flux_reader_reconstructs_records_from_the_exact_source_schema(tmp_path):
    path = tmp_path / "flux_by_run_energy.csv"
    write_artifact(path, RUN_FLUX_FIELDS, [run_flux_artifact_row()])

    records = read_run_flux_artifact(path, {7: manifest_rows(7)[0]})

    assert records == (
        FluxBinRecord(
            "ajaka_cross_section", 7, "period", "P", "UV", "P_UV", 1.0, 1.1,
            4.0, 1.0, 5.0, 3.0, 4.0, 7.0, "valid",
        ),
    )


@pytest.mark.parametrize(
    ("row", "match"),
    [
        (run_flux_artifact_row(energy_low_gev="inf"), "row 2.*finite"),
        (run_flux_artifact_row(run_number=0), "row 2.*positive integer"),
        (run_flux_artifact_row(status="unknown"), "row 2.*status"),
        (run_flux_artifact_row(pol1_net=3.1), "row 2.*pol1_net"),
        (run_flux_artifact_row(total_net=6.9), "row 2.*total_net"),
        (run_flux_artifact_row(group="D_UV"), "row 2.*metadata"),
        (run_flux_artifact_row(run_number=99), "row 2.*unknown manifest run 99"),
    ],
)
def test_run_flux_reader_rejects_invalid_source_rows(tmp_path, row, match):
    path = tmp_path / "flux_by_run_energy.csv"
    write_artifact(path, RUN_FLUX_FIELDS, [row])

    with pytest.raises(ObservableRunError, match=match):
        read_run_flux_artifact(path, {7: manifest_rows(7)[0]})


def test_run_flux_reader_rejects_duplicate_bin_key(tmp_path):
    path = tmp_path / "flux_by_run_energy.csv"
    row = run_flux_artifact_row()
    write_artifact(path, RUN_FLUX_FIELDS, [row, row])

    with pytest.raises(ObservableRunError, match="duplicate.*ajaka_cross_section.*7"):
        read_run_flux_artifact(path, {7: manifest_rows(7)[0]})


def test_source_qa_reader_requires_schema_v1_and_valid_json(tmp_path):
    path = tmp_path / "strip_energy_flux_qa.json"
    path.write_text(json.dumps(source_qa(schema_version=2)))
    with pytest.raises(ObservableRunError, match="schema_version"):
        read_source_qa(path)

    path.write_text(json.dumps(source_qa(schema_version=True)))
    with pytest.raises(ObservableRunError, match="schema_version"):
        read_source_qa(path)

    path.write_text("{")
    with pytest.raises(ObservableRunError, match="malformed JSON"):
        read_source_qa(path)


def test_source_qa_reader_requires_its_exact_schema(tmp_path):
    path = tmp_path / "strip_energy_flux_qa.json"
    payload = source_qa()
    payload.pop("errors")
    path.write_text(json.dumps(payload))

    with pytest.raises(ObservableRunError, match="schema"):
        read_source_qa(path)


def test_source_qa_errors_match_their_structured_findings():
    qa = source_qa(
        missing_h80_runs=[7],
        nonzero_unmapped_strips=[{"run_number": 7, "xstrip": 4}],
        negative_net_errors=[{"run_number": 7, "binning": "ajaka_cross_section", "bin_index": 2}],
        conservation={
            "failures": [
                {
                    "scope": "run", "binning": "ajaka_cross_section",
                    "run_number": 7, "state": "brem",
                }
            ]
        },
        errors=[
            "manifest runs absent from h80: [7]",
            "run 7 binning ajaka_cross_section bin 2: negative net flux",
            "run 7 strip 4: nonzero flux without lookup",
            "structural run raw-flux conservation failure: binning ajaka_cross_section run 7 state brem",
        ],
        valid=False,
    )

    validate_source_qa_errors(qa)

    qa["errors"].append("something unrelated")
    qa["errors"].sort()
    with pytest.raises(ObservableRunError, match="^unclassified source QA error$"):
        validate_source_qa_errors(qa)


def test_source_qa_reader_rejects_duplicate_keys_and_nonfinite_nested_numbers(tmp_path):
    path = tmp_path / "strip_energy_flux_qa.json"
    serialized = json.dumps(source_qa())
    path.write_text(f'{serialized[:-1]}, "schema_version": 1}}')
    with pytest.raises(ObservableRunError, match="duplicate JSON key"):
        read_source_qa(path)

    path.write_text(
        json.dumps(source_qa()).replace(
            '"thresholds": {}', '"thresholds": {"max_mad_gev": 1e9999}'
        )
    )
    with pytest.raises(ObservableRunError, match="non-finite"):
        read_source_qa(path)

    path.write_text(json.dumps(source_qa(schema_version=1.0)))
    with pytest.raises(ObservableRunError, match="schema_version"):
        read_source_qa(path)

    path.write_text(json.dumps(source_qa(extra_h80_runs_truncated=True)))
    with pytest.raises(ObservableRunError, match="extra_h80 run counters"):
        read_source_qa(path)

    path.write_text(json.dumps(source_qa(extra_h80_runs=[9], extra_h80_run_count=1, extra_h80_runs_truncated=True)))
    with pytest.raises(ObservableRunError, match="extra_h80 run counters"):
        read_source_qa(path)

    path.write_text(json.dumps(source_qa(negative_net_errors=[{
        "run_number": 7,
        "binning": "ajaka_cross_section",
        "bin_index": 0,
        "energy_low_gev": 1.0,
        "energy_high_gev": 1.1,
        "pol1_net": 1.0,
        "pol2_net": 2.0,
    }])))
    with pytest.raises(ObservableRunError, match="negative_net_errors.*negative"):
        read_source_qa(path)

    path.write_text(json.dumps(source_qa(thresholds={"max_mad_gev": 10 ** 4000})))
    with pytest.raises(ObservableRunError, match="thresholds.max_mad_gev.*finite"):
        read_source_qa(path)


@pytest.mark.parametrize(
    "payload",
    [
        source_qa(valid=False),
        source_qa(errors=["unexpected"], valid=True),
        source_qa(nonzero_unmapped_strips=[{"run_number": 0, "xstrip": 1}]),
    ],
)
def test_source_qa_reader_rejects_inconsistent_state_and_malformed_nested_entries(tmp_path, payload):
    path = tmp_path / "strip_energy_flux_qa.json"
    path.write_text(json.dumps(payload))

    with pytest.raises(ObservableRunError):
        read_source_qa(path)


def test_source_qa_errors_accept_exact_extra_h80_and_monotonic_messages():
    qa = source_qa(
        extra_h80_runs=[9],
        extra_h80_run_count=1,
        monotonic_inversions=[
            {
                "run_number": 7,
                "direction": "increasing",
                "left_strip": 1,
                "right_strip": 2,
                "left_energy_gev": 1.2,
                "right_energy_gev": 1.1,
                "delta_gev": -0.1,
            }
        ],
        errors=[
            "h80 runs absent from manifest: [9]",
            "run 7 strips 1-2: monotonic inversion -0.1 GeV",
        ],
        valid=False,
    )

    validate_source_qa_errors(qa)


@pytest.mark.parametrize(
    "qa",
    [
        source_qa(
            missing_h80_runs=[7],
            errors=["manifest runs absent from h80: [7]"] * 2,
            valid=False,
        ),
        source_qa(
            nonzero_unmapped_strips=[
                {"run_number": 7, "xstrip": 4},
                {"run_number": 7, "xstrip": 4},
            ],
            errors=["run 7 strip 4: nonzero flux without lookup"],
            valid=False,
        ),
    ],
)
def test_source_qa_error_validation_rejects_duplicate_identities(qa):
    with pytest.raises(ObservableRunError, match="duplicate"):
        validate_source_qa_errors(qa)


def test_quality_writer_uses_fixed_schema_and_empty_missing_metrics(tmp_path):
    path = tmp_path / "run_quality.csv"
    write_run_quality_csv(path, [quality_row(7, brem=BremMetric(None, None, None))])

    row = next(csv.DictReader(path.open(newline="")))
    assert tuple(row) == (
        "run_number", "source_period", "target", "beam_type", "group",
        "classification_source", "source_file", "quality_status", "reason_codes",
        "nonzero_unmapped_strip_count", "negative_net_bin_count",
        "brem_reference_sum", "brem_period_median", "brem_ratio",
    )
    assert row["brem_reference_sum"] == ""
    assert row["brem_period_median"] == ""
    assert row["brem_ratio"] == ""


def test_quality_writer_rejects_invalid_status_and_has_stable_digest(tmp_path):
    path = tmp_path / "run_quality.csv"
    invalid = RunQuality(manifest_rows(7)[0], "invalid", (), 0, 0, BremMetric(None, None, None))
    with pytest.raises(ObservableRunError, match="quality_status"):
        write_run_quality_csv(path, [invalid])

    write_run_quality_csv(path, [quality_row(8), quality_row(7)])
    assert [row["run_number"] for row in csv.DictReader(path.open(newline=""))] == ["7", "8"]
    assert sha256_file(path) == hashlib.sha256(path.read_bytes()).hexdigest()
