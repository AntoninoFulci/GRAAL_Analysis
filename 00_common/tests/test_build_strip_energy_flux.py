from array import array
import csv
from dataclasses import replace
import json
import importlib.util
from pathlib import Path
import sqlite3
import subprocess
import sys
from types import SimpleNamespace

import pytest

from graal_common.run_manifest import RunRecord, write_manifest
from graal_common.strip_energy_flux import EnergyBinning, StripEnergyFluxError

SCRIPT = Path(__file__).parents[2] / "scripts" / "build_strip_energy_flux.py"
SPEC = importlib.util.spec_from_file_location("build_strip_energy_flux_task4", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
cli = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cli)


def write_h80(path: Path, entries, branches=("beam", "RunNumber", "Xstrip")):
    import ROOT

    output = ROOT.TFile(str(path), "RECREATE")
    tree = ROOT.TTree("h80", "h80")
    vector_type = "ROOT::Math::LorentzVector<ROOT::Math::PxPyPzE4D<double> >"
    vector = getattr(ROOT, vector_type)
    beam = vector()
    run_number = array("i", [0])
    xstrip = array("f", [0.0])
    if "beam" in branches:
        tree.Branch("beam", vector_type, beam)
    if "RunNumber" in branches:
        tree.Branch("RunNumber", run_number, "RunNumber/I")
    if "Xstrip" in branches:
        tree.Branch("Xstrip", xstrip, "Xstrip/F")
    for run, strip, energy in entries:
        run_number[0] = run
        xstrip[0] = strip
        beam.SetPxPyPzE(0.0, 0.0, energy, energy)
        tree.Fill()
    tree.Write()
    output.Close()


def write_h80_with_scalar_beam(path: Path):
    import ROOT

    output = ROOT.TFile(str(path), "RECREATE")
    tree = ROOT.TTree("h80", "h80")
    beam = array("d", [1.2])
    run_number = array("i", [7])
    xstrip = array("f", [1.0])
    tree.Branch("beam", beam, "beam/D")
    tree.Branch("RunNumber", run_number, "RunNumber/I")
    tree.Branch("Xstrip", xstrip, "Xstrip/F")
    tree.Fill()
    tree.Write()
    output.Close()


def write_h80_with_double_xstrip(path: Path, strip: float):
    import ROOT

    output = ROOT.TFile(str(path), "RECREATE")
    tree = ROOT.TTree("h80", "h80")
    vector_type = "ROOT::Math::LorentzVector<ROOT::Math::PxPyPzE4D<double> >"
    beam = getattr(ROOT, vector_type)()
    run_number = array("i", [1321])
    xstrip = array("d", [strip])
    tree.Branch("beam", vector_type, beam)
    tree.Branch("RunNumber", run_number, "RunNumber/I")
    tree.Branch("Xstrip", xstrip, "Xstrip/D")
    beam.SetPxPyPzE(0.0, 0.0, 1.3195386, 1.3195386)
    tree.Fill()
    tree.Write()
    output.Close()


def write_flux(
    path: Path,
    runs: dict[int, dict[str, dict[int, float]]],
    *,
    bins: int = 128,
    low: float = 0.0,
    high: float = 128.0,
):
    import ROOT

    output = ROOT.TFile(str(path), "RECREATE")
    for run, values in runs.items():
        for suffix, contents in values.items():
            histogram = ROOT.TH1D(f"run{run}_{suffix}", "", bins, low, high)
            for strip, value in contents.items():
                histogram.SetBinContent(strip, value)
            histogram.Write()
    output.Close()


def append_histogram(path: Path, name: str):
    import ROOT

    output = ROOT.TFile(str(path), "UPDATE")
    histogram = ROOT.TH1D(name, "", 128, 0.0, 128.0)
    histogram.Write()
    output.Close()


def write_flux_with_edges(path: Path, edges):
    import ROOT

    output = ROOT.TFile(str(path), "RECREATE")
    root_edges = array("d", edges)
    for suffix in ("POL1", "POL2", "BREM"):
        histogram = ROOT.TH1D(f"run7_{suffix}", "", 128, root_edges)
        histogram.Write()
    output.Close()


def make_complete_fixture(tmp_path, *, entries_by_run=None, flux_by_run=None):
    pre = tmp_path / "pre"
    pre.mkdir()
    runs = (7, 8)
    if entries_by_run is None:
        entries_by_run = {
            run: [
                (run, strip, 1.00 + (strip - 1) * 0.5 / 127)
                for strip in range(1, 129)
            ]
            for run in runs
        }
    for run in runs:
        if run in entries_by_run:
            write_h80(pre / f"pre_{run}.root", entries_by_run[run])

    flux = tmp_path / "flux.root"
    if flux_by_run is None:
        flux_by_run = {
            run: {
                "POL1": {strip: 10.0 for strip in range(1, 129)},
                "POL2": {strip: 8.0 for strip in range(1, 129)},
                "BREM": {strip: 1.0 for strip in range(1, 129)},
            }
            for run in runs
        }
    write_flux(flux, flux_by_run)
    manifest_path = tmp_path / "run_manifest.csv"
    write_manifest(
        [
            RunRecord(
                7, "uv_period", "P", "UV", "P_UV", "manual",
                "uv_period/run7.root",
            ),
            RunRecord(
                8, "vis_d", "D", "VIS", "D_VIS", "manual",
                "vis_d/run8.root",
            ),
        ],
        manifest_path,
    )
    return pre, flux, manifest_path, tmp_path / "output"


def run_cli(pre, flux, manifest_path, output, *extra):
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--preanalysis-dir",
            str(pre),
            "--manifest",
            str(manifest_path),
            "--flux",
            str(flux),
            "--output-dir",
            str(output),
            *extra,
        ],
        text=True,
        capture_output=True,
    )


def complete_flux_runs(*run_numbers):
    return {
        run: {
            "POL1": {strip: 10.0 for strip in range(1, 129)},
            "POL2": {strip: 8.0 for strip in range(1, 129)},
            "BREM": {strip: 1.0 for strip in range(1, 129)},
        }
        for run in run_numbers
    }


def test_cli_writes_lookup_run_group_and_valid_qa(tmp_path):
    pre, flux, manifest_path, output = make_complete_fixture(tmp_path)

    result = run_cli(pre, flux, manifest_path, output)

    assert result.returncode == 0, result.stderr
    assert sorted(path.name for path in output.iterdir()) == [
        "flux_by_group_energy.csv",
        "flux_by_run_energy.csv",
        "strip_energy_flux_qa.json",
        "strip_energy_lookup.csv",
    ]
    qa = json.loads((output / "strip_energy_flux_qa.json").read_text())
    assert qa["valid"] is True
    assert qa["manifest_run_count"] == 2
    assert qa["h80_run_count"] == 2
    assert qa["flux_run_count"] == 2
    assert qa["conservation"]["valid"] is True
    assert qa["conservation"]["failures"] == []
    assert "Wrote 2-run strip-energy flux analysis" in result.stdout


def test_parse_custom_binnings_rejects_duplicate_name():
    custom = cli.parse_custom_binnings(["fine:1.0,1.1,1.2"])

    assert custom == (EnergyBinning("fine", (1.0, 1.1, 1.2)),)
    with pytest.raises(StripEnergyFluxError, match="duplicate binning name"):
        cli.parse_custom_binnings(["fine:1.0,1.1", "fine:1.1,1.2"])


def test_cli_missing_h80_manifest_run_writes_invalid_analysis(tmp_path):
    entries = {
        7: [
            (7, strip, 1.00 + (strip - 1) * 0.5 / 127)
            for strip in range(1, 129)
        ]
    }
    pre, flux, manifest_path, output = make_complete_fixture(
        tmp_path, entries_by_run=entries
    )

    result = run_cli(pre, flux, manifest_path, output)

    assert result.returncode == 1
    qa = json.loads((output / "strip_energy_flux_qa.json").read_text())
    assert qa["valid"] is False
    assert qa["missing_h80_runs"] == [8]
    assert "manifest runs absent from h80: [8]" in qa["errors"]
    assert (output / "flux_by_run_energy.csv").is_file()


def test_cli_nonzero_flux_without_lookup_is_diagnostic(tmp_path):
    entries = {
        run: [
            (run, strip, 1.00 + (strip - 1) * 0.5 / 127)
            for strip in range(1, 129)
            if not (run == 7 and strip == 128)
        ]
        for run in (7, 8)
    }
    pre, flux, manifest_path, output = make_complete_fixture(
        tmp_path, entries_by_run=entries
    )

    result = run_cli(pre, flux, manifest_path, output)

    assert result.returncode == 1
    qa = json.loads((output / "strip_energy_flux_qa.json").read_text())
    assert qa["nonzero_unmapped_strips"] == [
        {
            "run_number": 7,
            "xstrip": 128,
            "pol1": 10.0,
            "brem": 1.0,
            "pol2": 8.0,
        }
    ]
    assert any("nonzero flux without lookup" in error for error in qa["errors"])


def test_cli_negative_net_flux_is_diagnostic(tmp_path):
    flux_by_run = {
        run: {
            "POL1": {
                strip: (-1000.0 if run == 7 and strip == 1 else 10.0)
                for strip in range(1, 129)
            },
            "POL2": {strip: 8.0 for strip in range(1, 129)},
            "BREM": {strip: 1.0 for strip in range(1, 129)},
        }
        for run in (7, 8)
    }
    pre, flux, manifest_path, output = make_complete_fixture(
        tmp_path, flux_by_run=flux_by_run
    )

    result = run_cli(pre, flux, manifest_path, output)

    assert result.returncode == 1
    qa = json.loads((output / "strip_energy_flux_qa.json").read_text())
    assert qa["valid"] is False
    assert any("negative net flux" in error for error in qa["errors"])
    assert [
        (item["binning"], item["run_number"], item["bin_index"])
        for item in qa["negative_net_errors"]
    ] == [("ajaka_cross_section", 7, 1)]
    with (output / "flux_by_run_energy.csv").open(newline="") as stream:
        run_rows = list(csv.DictReader(stream))
    with (output / "flux_by_group_energy.csv").open(newline="") as stream:
        group_rows = list(csv.DictReader(stream))
    assert len(run_rows) == 38
    invalid_run_rows = [row for row in run_rows if row["status"] == "invalid"]
    assert len(invalid_run_rows) == 1
    invalid = invalid_run_rows[0]
    assert (invalid["binning"], invalid["run_number"]) == (
        "ajaka_cross_section",
        "7",
    )
    assert (
        float(invalid["pol1"]),
        float(invalid["brem"]),
        float(invalid["pol2"]),
    ) == (-950.0, 6.0, 48.0)
    assert (
        float(invalid["pol1_net"]),
        float(invalid["pol2_net"]),
        float(invalid["total_net"]),
    ) == (-956.0, 42.0, -914.0)
    assert any(
        row["binning"] == "ajaka_cross_section"
        and row["group"] == "P_UV"
        and row["status"] == "invalid"
        for row in group_rows
    )


def test_cli_local_monotonic_inversion_above_tolerance_is_invalid(tmp_path):
    entries = {}
    for run in (7, 8):
        values = [
            (run, strip, 1.00 + (strip - 1) * 0.5 / 127)
            for strip in range(1, 129)
        ]
        if run == 7:
            values[63] = (7, 64, 1.10)
        entries[run] = values
    pre, flux, manifest_path, output = make_complete_fixture(
        tmp_path, entries_by_run=entries
    )

    result = run_cli(pre, flux, manifest_path, output)

    assert result.returncode == 1
    qa = json.loads((output / "strip_energy_flux_qa.json").read_text())
    assert qa["monotonic_inversions"]
    assert any("monotonic inversion" in error for error in qa["errors"])


def test_cli_mad_and_low_stat_findings_are_warnings_only(tmp_path):
    entries = {
        run: [
            (run, strip, 1.00 + (strip - 1) * 0.5 / 127)
            for strip in range(1, 129)
        ]
        for run in (7, 8)
    }
    center = 1.00 + 63 * 0.5 / 127
    entries[7].extend([(7, 64, center - 0.02), (7, 64, center + 0.02)])
    pre, flux, manifest_path, output = make_complete_fixture(
        tmp_path, entries_by_run=entries
    )

    result = run_cli(
        pre,
        flux,
        manifest_path,
        output,
        "--min-events-per-strip",
        "2",
        "--max-mad-gev",
        "0.01",
    )

    assert result.returncode == 0, result.stderr
    qa = json.loads((output / "strip_energy_flux_qa.json").read_text())
    assert qa["valid"] is True
    assert qa["mad_warnings"] == [
        {
            "run_number": 7,
            "xstrip": 64,
            "energy_mad_gev": pytest.approx(0.02),
        }
    ]
    assert qa["low_stat_warnings"]
    assert qa["errors"] == []


def test_run_completes_invalid_analysis_when_root_file_is_unreadable(tmp_path):
    pre, flux, manifest_path, output = make_complete_fixture(tmp_path)
    (pre / "pre_7.root").write_text("not a ROOT file")
    output.mkdir()
    (output / "sentinel").write_text("old")
    args = SimpleNamespace(
        preanalysis_dir=pre,
        manifest=manifest_path,
        flux=flux,
        output_dir=output,
        min_events_per_strip=1,
        max_mad_gev=0.005,
        monotonic_tolerance_gev=0.002,
        binning=[],
    )

    result = cli.run(args)

    assert result == 1
    assert not (output / "sentinel").exists()
    qa = json.loads((output / "strip_energy_flux_qa.json").read_text())
    assert qa["missing_h80_runs"] == [7]
    assert qa["h80"]["skipped_file_count"] == 1
    assert qa["h80"]["skipped_files"][0]["path"] == str(pre / "pre_7.root")
    assert not list(tmp_path.glob(".output.energy-spool.*"))


def test_cli_unreadable_root_replaces_previous_output_with_completed_qa(
    tmp_path,
):
    pre, flux, manifest_path, output = make_complete_fixture(tmp_path)
    completed = run_cli(pre, flux, manifest_path, output)
    assert completed.returncode == 0, completed.stderr
    previous_bytes = {
        path.name: path.read_bytes()
        for path in output.iterdir()
        if path.is_file()
    }
    assert sorted(previous_bytes) == [
        "flux_by_group_energy.csv",
        "flux_by_run_energy.csv",
        "strip_energy_flux_qa.json",
        "strip_energy_lookup.csv",
    ]
    (pre / "pre_7.root").write_text("not a ROOT file")

    rerun = run_cli(pre, flux, manifest_path, output)

    assert rerun.returncode == 1
    current_bytes = {
        path.name: path.read_bytes()
        for path in output.iterdir()
        if path.is_file()
    }
    assert sorted(current_bytes) == sorted(previous_bytes)
    assert current_bytes != previous_bytes
    qa = json.loads(current_bytes["strip_energy_flux_qa.json"])
    assert qa["valid"] is False
    assert qa["missing_h80_runs"] == [7]
    assert qa["h80"]["skipped_file_count"] == 1
    assert f"WARNING: zombie ROOT file: {pre / 'pre_7.root'}" in rerun.stderr
    assert not list(tmp_path.glob("output.failure.*"))


def test_main_sqlite_failure_preserves_existing_output_and_writes_sibling_qa(
    tmp_path, monkeypatch, capsys
):
    output = tmp_path / "output"
    output.mkdir()
    sentinel = output / "sentinel"
    sentinel.write_bytes(b"completed output")
    args = SimpleNamespace(
        preanalysis_dir=tmp_path / "pre",
        manifest=tmp_path / "manifest.csv",
        flux=tmp_path / "flux.root",
        output_dir=output,
        min_events_per_strip=1,
        max_mad_gev=0.005,
        monotonic_tolerance_gev=0.002,
        binning=[],
    )
    monkeypatch.setattr(cli, "parse_args", lambda: args)

    def fail_with_sqlite_error(_args):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(cli, "run", fail_with_sqlite_error)

    result = cli.main()

    assert result == 1
    assert sentinel.read_bytes() == b"completed output"
    failure_directories = list(tmp_path.glob("output.failure.*"))
    assert len(failure_directories) == 1
    failure_directory = failure_directories[0]
    qa = json.loads(
        (failure_directory / "strip_energy_flux_qa.json").read_text()
    )
    assert qa["valid"] is False
    assert qa["errors"] == ["database is locked"]
    stderr = capsys.readouterr().err
    assert "ERROR: database is locked" in stderr
    assert f"Failure QA: {failure_directory.resolve()}" in stderr


def test_cli_h80_beam_without_energy_method_writes_contextual_minimal_qa(
    tmp_path,
):
    pre, flux, manifest_path, output = make_complete_fixture(tmp_path)
    malformed = pre / "pre_7.root"
    write_h80_with_scalar_beam(malformed)

    result = run_cli(pre, flux, manifest_path, output)

    assert result.returncode == 1
    assert sorted(path.name for path in output.iterdir()) == [
        "strip_energy_flux_qa.json"
    ]
    qa = json.loads((output / "strip_energy_flux_qa.json").read_text())
    assert qa["errors"] == [
        f"{malformed}: h80 entry 0: cannot convert RunNumber/Xstrip/beam.E()"
    ]


def test_cli_duplicate_custom_binning_writes_diagnostic_qa(tmp_path):
    pre, flux, manifest_path, output = make_complete_fixture(tmp_path)

    result = run_cli(
        pre,
        flux,
        manifest_path,
        output,
        "--binning",
        "fine:1.0,1.1",
        "--binning",
        "fine:1.1,1.2",
    )

    assert result.returncode == 1
    qa = json.loads((output / "strip_energy_flux_qa.json").read_text())
    assert qa["valid"] is False
    assert qa["errors"] == ["duplicate binning name: fine"]


def test_cli_custom_binning_appears_in_csv_and_qa(tmp_path):
    pre, flux, manifest_path, output = make_complete_fixture(tmp_path)

    result = run_cli(
        pre,
        flux,
        manifest_path,
        output,
        "--binning",
        "fine:1.0,1.25,1.5",
    )

    assert result.returncode == 0, result.stderr
    with (output / "flux_by_run_energy.csv").open(newline="") as stream:
        run_rows = list(csv.DictReader(stream))
    with (output / "flux_by_group_energy.csv").open(newline="") as stream:
        group_rows = list(csv.DictReader(stream))
    assert {
        (row["energy_low_gev"], row["energy_high_gev"])
        for row in run_rows
        if row["binning"] == "fine"
    } == {("1.0", "1.25"), ("1.25", "1.5")}
    assert any(row["binning"] == "fine" for row in group_rows)
    qa = json.loads((output / "strip_energy_flux_qa.json").read_text())
    assert qa["binnings"]["fine"] == [1.0, 1.25, 1.5]


def test_cli_reports_raw_flux_excluded_outside_binning_without_folding(tmp_path):
    entries = {
        run: [
            (
                run,
                strip,
                0.90 if run == 7 and strip == 1
                else 1.00 + (strip - 1) * 0.5 / 127,
            )
            for strip in range(1, 129)
        ]
        for run in (7, 8)
    }
    pre, flux, manifest_path, output = make_complete_fixture(
        tmp_path, entries_by_run=entries
    )

    result = run_cli(pre, flux, manifest_path, output)

    assert result.returncode == 0, result.stderr
    with (output / "flux_by_run_energy.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    included_pol1 = sum(
        float(row["pol1"])
        for row in rows
        if row["binning"] == "ajaka_cross_section"
        and row["run_number"] == "7"
    )
    assert included_pol1 == pytest.approx(1270.0)
    qa = json.loads((output / "strip_energy_flux_qa.json").read_text())
    excluded = qa["out_of_range"]["ajaka_cross_section"]
    assert excluded["below_lookup_count"] == 1
    assert excluded["above_lookup_count"] == 0
    assert excluded["raw_flux_excluded"] == {
        "pol1": 10.0,
        "brem": 1.0,
        "pol2": 8.0,
    }


def test_cli_reports_underflow_overflow_as_warning_without_folding(tmp_path):
    flux_by_run = {
        run: {
            "POL1": {
                **{strip: 10.0 for strip in range(1, 129)},
                **({0: 50.0, 129: 60.0} if run == 7 else {}),
            },
            "POL2": {strip: 8.0 for strip in range(1, 129)},
            "BREM": {strip: 1.0 for strip in range(1, 129)},
        }
        for run in (7, 8)
    }
    pre, flux, manifest_path, output = make_complete_fixture(
        tmp_path, flux_by_run=flux_by_run
    )

    result = run_cli(pre, flux, manifest_path, output)

    assert result.returncode == 0, result.stderr
    qa = json.loads((output / "strip_energy_flux_qa.json").read_text())
    assert qa["valid"] is True
    assert qa["errors"] == []
    assert qa["underflow_overflow"] == [
        {"histogram": "run7_POL1", "underflow": 50.0, "overflow": 60.0}
    ]
    with (output / "flux_by_run_energy.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert sum(
        float(row["pol1"])
        for row in rows
        if row["binning"] == "ajaka_cross_section"
        and row["run_number"] == "7"
    ) == pytest.approx(1280.0)


def test_cli_argument_syntax_error_exits_two_without_qa(tmp_path):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--output-dir", str(tmp_path / "out")],
        text=True,
        capture_output=True,
    )

    assert result.returncode == 2
    assert not (tmp_path / "out").exists()


def test_cli_rejects_output_containing_inputs_without_deleting_them(tmp_path):
    pre, flux, manifest_path, _ = make_complete_fixture(tmp_path)

    result = run_cli(pre, flux, manifest_path, tmp_path)

    assert result.returncode == 1
    assert "output directory contains input path" in result.stderr
    assert pre.is_dir()
    assert flux.is_file()
    assert manifest_path.is_file()
    assert not (tmp_path / "strip_energy_flux_qa.json").exists()


def test_cli_rejects_lexical_input_symlink_inside_output_without_deleting_it(
    tmp_path,
):
    pre, flux, manifest_path, output = make_complete_fixture(tmp_path)
    output.mkdir()
    supplied_pre = output / "preanalysis-link"
    supplied_pre.symlink_to(pre, target_is_directory=True)

    result = run_cli(supplied_pre, flux, manifest_path, output)

    assert result.returncode == 1
    assert "output directory contains input path" in result.stderr
    assert supplied_pre.is_symlink()
    assert pre.is_dir()


def test_root_adapters_read_h80_and_flux_triplet(tmp_path):
    pre = tmp_path / "pre"
    pre.mkdir()
    write_h80(pre / "pre_7.root", [(7, 12, 1.2), (7, 13, 1.3)])
    flux = tmp_path / "flux.root"
    write_flux(flux, {7: {
        "POL1": {12: 100}, "POL2": {12: 80}, "BREM": {12: 10},
    }})

    samples, h80_qa = cli.read_h80_samples(pre)
    strips, flux_qa = cli.read_flux_histograms(flux, [7])

    assert [(row.run_number, row.xstrip) for row in samples] == [
        (7, 12.0), (7, 13.0)
    ]
    assert strips[11].pol1 == pytest.approx(100.0)
    assert strips[11].brem == pytest.approx(10.0)
    assert h80_qa["entries"] == 2
    assert flux_qa["run_count"] == 1


def test_cli_bounded_lookup_is_exact_for_runs_spanning_multi_run_files(
    tmp_path,
):
    pre, flux, manifest_path, output = make_complete_fixture(
        tmp_path,
        entries_by_run={},
        flux_by_run=complete_flux_runs(7, 8),
    )
    write_h80(
        pre / "a.root",
        [
            (7, 1, 1.0),
            (8, 1, 1.2),
            (7, 2, 1.1),
            (8, 2, 1.3),
        ],
    )
    write_h80(
        pre / "b.root",
        [
            (8, 1, 1.4),
            (7, 1, 1.4),
            (8, 2, 1.5),
            (7, 2, 1.5),
        ],
    )
    write_flux(
        flux,
        {
            7: {"POL1": {}, "POL2": {}, "BREM": {}},
            8: {"POL1": {}, "POL2": {}, "BREM": {}},
        },
    )

    result = run_cli(pre, flux, manifest_path, output)

    assert result.returncode == 0, result.stderr
    with (output / "strip_energy_lookup.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    expected = [
        (7, 1, 2, 1.2, 0.2, 1.0, 1.4),
        (7, 2, 2, 1.3, 0.2, 1.1, 1.5),
        (8, 1, 2, 1.3, 0.1, 1.2, 1.4),
        (8, 2, 2, 1.4, 0.1, 1.3, 1.5),
    ]
    assert [
        (
            int(row["run_number"]),
            int(row["xstrip"]),
            int(row["event_count"]),
        )
        for row in rows
    ] == [item[:3] for item in expected]
    for row, item in zip(rows, expected):
        assert (
            float(row["energy_median_gev"]),
            float(row["energy_mad_gev"]),
            float(row["energy_min_gev"]),
            float(row["energy_max_gev"]),
        ) == pytest.approx(item[3:])
    assert not list(tmp_path.glob(".output.energy-spool.*"))


def test_run_streams_h80_into_disk_lookup_without_event_list(
    tmp_path, monkeypatch
):
    pre, flux, manifest_path, output = make_complete_fixture(tmp_path)
    build_on_disk = cli.build_strip_energy_lookup_on_disk
    observed = {}

    def require_stream(samples, database, **kwargs):
        observed["is_materialized"] = isinstance(samples, (list, tuple))
        return build_on_disk(samples, database, **kwargs)

    monkeypatch.setattr(
        cli,
        "build_strip_energy_lookup_on_disk",
        require_stream,
    )
    args = SimpleNamespace(
        preanalysis_dir=pre,
        manifest=manifest_path,
        flux=flux,
        output_dir=output,
        min_events_per_strip=1,
        max_mad_gev=0.005,
        monotonic_tolerance_gev=0.002,
        binning=[],
    )

    result = cli.run(args)

    assert result == 0
    assert observed == {"is_materialized": False}


def test_h80_reader_recursively_sorts_root_files(tmp_path):
    pre = tmp_path / "pre"
    (pre / "b").mkdir(parents=True)
    (pre / "a").mkdir()
    write_h80(pre / "b" / "second.root", [(8, 2, 1.2)])
    write_h80(pre / "a" / "first.root", [(7, 1, 1.3)])

    samples, _ = cli.read_h80_samples(pre)

    assert [row.run_number for row in samples] == [7, 8]


def test_h80_path_discovery_is_lazy(tmp_path):
    pre = tmp_path / "pre"
    pre.mkdir()
    write_h80(pre / "one.root", [(7, 1, 1.3)])

    paths = cli._h80_paths(pre)

    assert not isinstance(paths, (list, tuple))
    assert list(paths) == [pre / "one.root"]


def test_h80_reader_rejects_no_root_files(tmp_path):
    pre = tmp_path / "pre"
    pre.mkdir()

    with pytest.raises(StripEnergyFluxError, match="no ROOT files"):
        cli.read_h80_samples(pre)


def test_h80_reader_rejects_missing_tree(tmp_path):
    import ROOT

    pre = tmp_path / "pre"
    pre.mkdir()
    output = ROOT.TFile(str(pre / "missing_tree.root"), "RECREATE")
    ROOT.TH1D("other", "", 1, 0.0, 1.0).Write()
    output.Close()

    with pytest.raises(StripEnergyFluxError, match="missing h80"):
        cli.read_h80_samples(pre)


def test_h80_reader_rejects_missing_required_branch(tmp_path):
    pre = tmp_path / "pre"
    pre.mkdir()
    write_h80(pre / "missing_beam.root", [(7, 12, 1.2)], branches=("RunNumber", "Xstrip"))

    with pytest.raises(StripEnergyFluxError, match="missing branch beam"):
        cli.read_h80_samples(pre)


@pytest.mark.parametrize(
    ("invalid_entry", "message"),
    [
        ((0, 2, 1.2), "run_number must be positive"),
        ((7, 129, 1.2), "Xstrip outside 1..128"),
        ((7, 2, 0.0), "beam energy must be finite and positive"),
        ((7, 2, float("nan")), "beam energy must be finite and positive"),
    ],
)
def test_h80_reader_semantic_warnings_include_file_and_entry(
    tmp_path, invalid_entry, message, capsys
):
    pre = tmp_path / "pre"
    pre.mkdir()
    source = pre / "semantic_error.root"
    write_h80(source, [(7, 1, 1.1), invalid_entry])

    samples, qa = cli.read_h80_samples(pre)

    assert len(samples) == 1
    assert qa["skipped_entry_count"] == 1
    warning = capsys.readouterr().err
    assert f"WARNING: {source}: h80 entry 1:" in warning
    assert message in warning


def test_h80_reader_rounds_fractional_xstrip_to_nearest_integer(tmp_path):
    pre = tmp_path / "pre"
    pre.mkdir()
    write_h80(pre / "fractional.root", [(1321, 69.50387573242188, 1.3195386)])

    samples, _ = cli.read_h80_samples(pre)

    assert samples[0].xstrip == 70


def test_h80_reader_warns_and_skips_invalid_entries(tmp_path, capsys):
    pre = tmp_path / "pre"
    pre.mkdir()
    source = pre / "entries.root"
    write_h80(source, [(7, 1, 1.1), (7, 129, 1.2), (7, 2, 1.3)])

    samples, qa = cli.read_h80_samples(pre)

    assert [sample.xstrip for sample in samples] == [1, 2]
    assert qa["entries"] == 2
    assert qa["skipped_entry_count"] == 1
    assert qa["skipped_entries"] == [
        {
            "path": str(source),
            "entry": 1,
            "error": "Xstrip outside 1..128: 129.0",
        }
    ]
    assert qa["skipped_entries_truncated"] is False
    assert (
        f"WARNING: {source}: h80 entry 1: Xstrip outside 1..128: 129.0"
        in capsys.readouterr().err
    )


def test_h80_reader_warns_and_skips_unreadable_files(tmp_path, capsys):
    pre = tmp_path / "pre"
    pre.mkdir()
    unreadable = pre / "a-broken.root"
    unreadable.write_text("not a ROOT file")
    write_h80(pre / "b-valid.root", [(7, 2, 1.3)])

    samples, qa = cli.read_h80_samples(pre)

    assert [sample.xstrip for sample in samples] == [2]
    assert qa["file_count"] == 2
    assert qa["skipped_file_count"] == 1
    assert qa["skipped_files"] == [
        {"path": str(unreadable), "error": f"zombie ROOT file: {unreadable}"}
    ]
    assert qa["skipped_files_truncated"] is False
    assert (
        f"WARNING: zombie ROOT file: {unreadable}" in capsys.readouterr().err
    )


def test_h80_reader_uses_declared_double_xstrip_type(tmp_path):
    pre = tmp_path / "pre"
    pre.mkdir()
    write_h80_with_double_xstrip(pre / "double.root", 69.50387573242188)

    samples, _ = cli.read_h80_samples(pre)

    assert samples[0].xstrip == 70


def test_h80_reader_uses_bound_buffers_instead_of_dynamic_tree_access(
    tmp_path, monkeypatch
):
    import ROOT

    pre = tmp_path / "pre"
    pre.mkdir()
    write_h80(
        pre / "bound.root",
        [(1321, 69.50387573242188, 1.3195386)],
    )
    original_getattr = ROOT.TTree.__getattr__

    def reject_dynamic_branch_access(tree, name):
        if name in {"RunNumber", "Xstrip", "beam"}:
            raise AssertionError(f"dynamic branch access: {name}")
        return original_getattr(tree, name)

    def reject_dynamic_iteration(tree):
        raise AssertionError("dynamic TTree iteration")

    monkeypatch.setattr(ROOT.TTree, "__getattr__", reject_dynamic_branch_access)
    monkeypatch.setattr(ROOT.TTree, "__iter__", reject_dynamic_iteration)

    samples, qa = cli.read_h80_samples(pre)

    assert samples == [cli.EnergySample(1321, 70, pytest.approx(1.3195386))]
    assert qa["entries"] == 1
    assert qa["file_count"] == 1
    assert qa["skipped_entry_count"] == 0
    assert qa["skipped_file_count"] == 0


def test_flux_reader_rejects_missing_requested_triplet_member(tmp_path):
    flux = tmp_path / "flux.root"
    write_flux(flux, {7: {"POL1": {}, "POL2": {}}})

    with pytest.raises(StripEnergyFluxError, match="run7_BREM"):
        cli.read_flux_histograms(flux, [7])


def test_flux_reader_rejects_wrong_bin_count(tmp_path):
    flux = tmp_path / "flux.root"
    write_flux(
        flux,
        {7: {"POL1": {}, "POL2": {}, "BREM": {}}},
        bins=127,
        high=127.0,
    )

    with pytest.raises(StripEnergyFluxError, match="run7_POL1.*128 bins"):
        cli.read_flux_histograms(flux, [7])


def test_flux_reader_rejects_wrong_axis_edges(tmp_path):
    flux = tmp_path / "flux.root"
    write_flux(
        flux,
        {7: {"POL1": {}, "POL2": {}, "BREM": {}}},
        low=1.0,
        high=129.0,
    )

    with pytest.raises(StripEnergyFluxError, match="run7_POL1.*x-axis edge"):
        cli.read_flux_histograms(flux, [7])


def test_flux_reader_reports_nonzero_underflow_and_overflow(tmp_path):
    flux = tmp_path / "flux.root"
    write_flux(flux, {7: {
        "POL1": {0: 2.0, 129: 3.0}, "POL2": {}, "BREM": {},
    }})

    _, qa = cli.read_flux_histograms(flux, [7])

    assert qa["underflow_overflow"] == [
        {"histogram": "run7_POL1", "underflow": 2.0, "overflow": 3.0}
    ]


def test_flux_reader_rejects_requested_run_absent(tmp_path):
    flux = tmp_path / "flux.root"
    write_flux(flux, {8: {"POL1": {}, "POL2": {}, "BREM": {}}})

    with pytest.raises(StripEnergyFluxError, match="run 7"):
        cli.read_flux_histograms(flux, [7])


def test_flux_reader_reports_complete_extra_run_and_incomplete_triplets(tmp_path):
    flux = tmp_path / "flux.root"
    write_flux(flux, {
        7: {"POL1": {}, "POL2": {}, "BREM": {}},
        8: {"POL1": {}, "POL2": {}, "BREM": {}},
        9: {"POL1": {}, "POL2": {}},
    })

    _, qa = cli.read_flux_histograms(flux, [7])

    assert qa["extra_runs"] == [8]
    assert qa["malformed_triplets"] == [
        {"run_number": 9, "missing": ["BREM"], "present": ["POL1", "POL2"]}
    ]


def test_cli_complete_extra_flux_run_is_warning_only(tmp_path):
    pre, flux, manifest_path, output = make_complete_fixture(
        tmp_path,
        flux_by_run=complete_flux_runs(7, 8, 99),
    )

    result = run_cli(pre, flux, manifest_path, output)

    assert result.returncode == 0, result.stderr
    qa = json.loads((output / "strip_energy_flux_qa.json").read_text())
    assert qa["valid"] is True
    assert qa["errors"] == []
    assert qa["extra_flux_runs"] == [99]
    with (output / "flux_by_run_energy.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert {int(row["run_number"]) for row in rows} == {7, 8}
    assert len(rows) == 38


def test_cli_incomplete_extra_flux_run_is_warning_only(tmp_path):
    flux_by_run = complete_flux_runs(7, 8)
    flux_by_run[99] = {"POL1": {}, "POL2": {}}
    pre, flux, manifest_path, output = make_complete_fixture(
        tmp_path,
        flux_by_run=flux_by_run,
    )

    result = run_cli(pre, flux, manifest_path, output)

    assert result.returncode == 0, result.stderr
    qa = json.loads((output / "strip_energy_flux_qa.json").read_text())
    assert qa["valid"] is True
    assert qa["errors"] == []
    assert qa["malformed_flux_triplets"] == [
        {"run_number": 99, "missing": ["BREM"], "present": ["POL1", "POL2"]}
    ]


def test_flux_reader_rejects_duplicate_root_key_cycles(tmp_path):
    flux = tmp_path / "flux.root"
    write_flux(flux, {7: {"POL1": {}, "POL2": {}, "BREM": {}}})
    append_histogram(flux, "run7_POL1")

    with pytest.raises(
        StripEnergyFluxError, match=r"run7_POL1.*exactly one.*found 2"
    ):
        cli.read_flux_histograms(flux, [7])


def test_flux_reader_rejects_noncanonical_run_alias(tmp_path):
    flux = tmp_path / "flux.root"
    write_flux(flux, {7: {"POL1": {}, "POL2": {}, "BREM": {}}})
    append_histogram(flux, "run007_POL1")

    with pytest.raises(
        StripEnergyFluxError, match=r"noncanonical.*run007_POL1.*run7_POL1"
    ):
        cli.read_flux_histograms(flux, [7])


def test_flux_reader_rejects_nonfinite_axis_edge(tmp_path):
    flux = tmp_path / "flux.root"
    edges = [float(edge) for edge in range(129)]
    edges[64] = float("nan")
    write_flux_with_edges(flux, edges)

    with pytest.raises(
        StripEnergyFluxError, match=r"run7_POL1.*x-axis edge 64.*finite"
    ):
        cli.read_flux_histograms(flux, [7])


def test_open_root_file_closes_truthy_zombie_before_raising(monkeypatch, tmp_path):
    class TruthyZombie:
        closed = False

        def IsZombie(self):
            return True

        def Close(self):
            self.closed = True

    zombie = TruthyZombie()
    root = SimpleNamespace(
        TFile=SimpleNamespace(Open=lambda path, mode: zombie),
    )
    monkeypatch.setattr(cli, "_import_root", lambda: root)

    with pytest.raises(StripEnergyFluxError, match="zombie"):
        cli._open_root_file(tmp_path / "broken.root")

    assert zombie.closed is True


def test_group_conservation_failure_is_fatal_in_full_qa(tmp_path, monkeypatch):
    pre, flux, manifest_path, output = make_complete_fixture(tmp_path)
    aggregate = cli.aggregate_group_flux

    def corrupt_group_total(records):
        result = aggregate(records)
        return (replace(result[0], pol1=result[0].pol1 + 1.0), *result[1:])

    monkeypatch.setattr(cli, "aggregate_group_flux", corrupt_group_total)
    args = SimpleNamespace(
        preanalysis_dir=pre,
        manifest=manifest_path,
        flux=flux,
        output_dir=output,
        min_events_per_strip=1,
        max_mad_gev=0.005,
        monotonic_tolerance_gev=0.002,
        binning=[],
    )

    result = cli.run(args)

    assert result == 1
    qa = json.loads((output / "strip_energy_flux_qa.json").read_text())
    assert qa["conservation"]["valid"] is False
    assert any(
        failure["scope"] == "group"
        for failure in qa["conservation"]["failures"]
    )
    assert any(
        "group raw-flux conservation failure" in error
        for error in qa["errors"]
    )


def test_run_conservation_failure_is_fatal_in_full_qa(tmp_path, monkeypatch):
    pre, flux, manifest_path, output = make_complete_fixture(tmp_path)
    integrate = cli.integrate_run_flux

    def corrupt_run_total(manifest, lookup, strips, binning):
        result = integrate(manifest, lookup, strips, binning)
        if manifest.run_number == 7 and binning.name == "ajaka_cross_section":
            return (replace(result[0], pol1=result[0].pol1 + 1.0), *result[1:])
        return result

    monkeypatch.setattr(cli, "integrate_run_flux", corrupt_run_total)
    args = SimpleNamespace(
        preanalysis_dir=pre,
        manifest=manifest_path,
        flux=flux,
        output_dir=output,
        min_events_per_strip=1,
        max_mad_gev=0.005,
        monotonic_tolerance_gev=0.002,
        binning=[],
    )

    result = cli.run(args)

    assert result == 1
    qa = json.loads((output / "strip_energy_flux_qa.json").read_text())
    assert qa["conservation"]["valid"] is False
    assert any(
        failure["scope"] == "run"
        for failure in qa["conservation"]["failures"]
    )
    assert any(
        "run raw-flux conservation failure" in error
        for error in qa["errors"]
    )
