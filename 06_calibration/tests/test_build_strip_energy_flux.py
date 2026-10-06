from array import array
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import sys
from types import SimpleNamespace

import pytest

from calibration.run_manifest import RunRecord, write_manifest
from calibration.strip_energy_flux import (
    EnergyBinning,
    StripEnergyRecord,
    StripEnergyFluxError,
)

SCRIPT = Path(__file__).parents[1] / "build_strip_energy_flux.py"
SPEC = importlib.util.spec_from_file_location("build_strip_energy_flux_task4", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
cli = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cli)


def write_h80(
    path: Path,
    entries,
    branches=("beam", "RunNumber", "Polarization", "Xstrip"),
):
    import ROOT

    output = ROOT.TFile(str(path), "RECREATE")
    tree = ROOT.TTree("h80", "h80")
    vector_type = "ROOT::Math::LorentzVector<ROOT::Math::PxPyPzE4D<double> >"
    vector = getattr(ROOT, vector_type)
    beam = vector()
    run_number = array("i", [0])
    polarization = array("i", [1])
    xstrip = array("f", [0.0])
    if "beam" in branches:
        tree.Branch("beam", vector_type, beam)
    if "RunNumber" in branches:
        tree.Branch("RunNumber", run_number, "RunNumber/I")
    if "Polarization" in branches:
        tree.Branch("Polarization", polarization, "Polarization/I")
    if "Xstrip" in branches:
        tree.Branch("Xstrip", xstrip, "Xstrip/F")
    for entry in entries:
        if len(entry) == 3:
            run, strip, energy = entry
            pol = 1
        else:
            run, pol, strip, energy = entry
        run_number[0] = run
        polarization[0] = pol
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


def write_flux(
    path: Path,
    runs: dict[int, dict[str, dict[int, float]]],
    *,
    bins: int = 128,
    low: float = 0.0,
    high: float = 128.0,
    bin_error: float | None = None,
):
    import ROOT

    output = ROOT.TFile(str(path), "RECREATE")
    for run, values in runs.items():
        for suffix, contents in values.items():
            histogram = ROOT.TH1D(f"run{run}_{suffix}", "", bins, low, high)
            for strip, value in contents.items():
                histogram.SetBinContent(strip, value)
                if bin_error is not None:
                    histogram.SetBinError(strip, bin_error)
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
    return pre, flux, manifest_path, tmp_path / "flux_calibrated.root"


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
            str(output.parent),
            *extra,
        ],
        text=True,
        capture_output=True,
    )


def test_cli_writes_only_root_file_in_requested_directory(tmp_path):
    pre, flux, manifest_path, _ = make_complete_fixture(tmp_path)
    output = tmp_path / "published" / "flux_calibrated.root"

    result = subprocess.run(
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
            str(output.parent),
        ],
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert output.is_file()
    assert [path.name for path in output.parent.iterdir()] == [output.name]


def test_cli_defaults_to_external_output_directory(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT),
            "--preanalysis-dir",
            "pre",
            "--manifest",
            "manifest.csv",
            "--flux",
            "flux.root",
        ],
    )

    args = cli.parse_args()

    assert args.output_dir == SCRIPT.parents[1] / "data/00_external"


def test_atomic_root_write_preserves_previous_file_on_failure(tmp_path, monkeypatch):
    output = tmp_path / "flux_calibrated.root"
    output.write_text("previous")

    def fail_write(*args, **kwargs):
        raise RuntimeError("ROOT write failed")

    monkeypatch.setattr(cli, "write_calibrated_flux_root", fail_write)

    with pytest.raises(RuntimeError, match="ROOT write failed"):
        cli._write_calibrated_flux_root_atomic(
            tmp_path / "flux.root",
            output,
            (),
            (),
        )

    assert output.read_text() == "previous"
    assert sorted(path.name for path in tmp_path.iterdir()) == [output.name]


def test_cli_writes_pol4_calibrated_root_and_ignores_calcerr(tmp_path):
    def energy(strip):
        return (
            0.8
            + 0.006 * strip
            + 2.0e-6 * strip**2
            - 1.0e-8 * strip**3
            + 2.0e-11 * strip**4
        )

    entries = {
        run: [
            (run, polarization, strip, energy(strip))
            for polarization in (0, 1, 2)
            for strip in range(1, 129)
        ]
        for run in (7, 8)
    }
    entries[7].extend(
        [
            (7, 1, 64.0, energy(64.0) - 0.01),
            (7, 1, 64.0, energy(64.0) + 0.01),
        ]
    )
    entries[7] = [
        entry
        for entry in entries[7]
        if not (entry[1] == 0 and entry[2] == 50)
    ]
    flux_by_run = {
        run: {
            suffix: {
                strip: (
                    -5.0
                    if run == 7 and suffix == "POL1" and strip == 1
                    else 10.0
                )
                for strip in range(1, 129)
            }
            for suffix in ("POL1", "POL2", "BREM")
        }
        for run in (7, 8)
    }
    pre, flux, manifest_path, output = make_complete_fixture(
        tmp_path,
        entries_by_run=entries,
        flux_by_run=flux_by_run,
    )
    append_histogram(flux, "run7calcerr_POL1")
    append_histogram(flux, "run7calcerr_POL2")
    append_histogram(flux, "run7calcerr_BREM")
    import ROOT

    source = ROOT.TFile.Open(str(flux), "UPDATE")
    source_histogram = source.Get("run7_POL1")
    source_histogram.SetBinError(2, 3.5)
    source_histogram.Write("", ROOT.TObject.kOverwrite)
    source.Close()

    result = run_cli(pre, flux, manifest_path, output)

    assert result.returncode == 0, result.stderr

    calibrated = ROOT.TFile.Open(str(output))
    try:
        assert calibrated and not calibrated.IsZombie()
        top_level_keys = [
            (key.GetName(), key.GetCycle()) for key in calibrated.GetListOfKeys()
        ]
        assert len(top_level_keys) == len({name for name, cycle in top_level_keys})
        assert all(cycle == 1 for name, cycle in top_level_keys)
        assert not calibrated.Get("run7calcerr_POL1")
        assert calibrated.Get("run7_POL2")
        assert calibrated.Get("run7_BREM")
        histogram = calibrated.Get("run7_POL1")
        assert histogram
        assert histogram.GetNbinsX() == 128
        assert histogram.GetXaxis().GetTitle() == "E_{#gamma} [GeV]"
        assert all(
            histogram.GetXaxis().GetBinLowEdge(index)
            < histogram.GetXaxis().GetBinUpEdge(index)
            for index in range(1, 129)
        )
        assert histogram.GetBinContent(1) == 0.0
        assert histogram.GetBinContent(2) == pytest.approx(10.0)
        assert histogram.GetBinError(2) == pytest.approx(3.5)

        calibration = calibrated.Get("calibration/run7_POL1_h2")
        profile = calibrated.Get("calibration/run7_POL1_profile")
        fit = calibrated.Get("calibration/run7_POL1_fit")
        assert calibration and profile and fit
        assert calibration.GetDimension() == 2
        occupied_energy_bins = sum(
            calibration.GetBinContent(64, energy_bin) > 0.0
            for energy_bin in range(calibration.GetNbinsY() + 2)
        )
        assert occupied_energy_bins >= 3
        assert fit.GetNpar() == 5
        assert fit.Eval(64.0) == pytest.approx(energy(64.0), abs=2.0e-4)
    finally:
        calibrated.Close()


def test_calibration_profile_anchors_fractional_events_to_integer_strip():
    import ROOT

    cells = [
        cli.CalibrationCell(
            7,
            1,
            strip,
            10,
            strip + 0.75,
            0.8 + 0.006 * strip,
        )
        for strip in range(1, 129)
    ]

    unused_h2, profile, unused_fit, unused_edges = cli._fit_calibration_group(
        ROOT,
        7,
        "POL1",
        cells,
        (),
    )

    assert all(profile.GetBinEntries(strip) > 0 for strip in range(1, 129))


def test_calibration_requires_full_strip_span():
    cells = [
        cli.CalibrationCell(7, 1, strip, 10, float(strip), 0.8 + 0.006 * strip)
        for strip in range(1, 128)
    ]

    assert cli.has_full_calibration_span(cells) is False


def test_pol4_monotonicity_finds_narrow_negative_derivative_between_grid_points():
    import ROOT

    center = 64.0625
    epsilon = 0.002
    fit = ROOT.TF1("narrow_derivative_dip", "pol4", 0.5, 128.5)
    fit.SetParameters(
        0.0,
        center**2 - epsilon,
        -center,
        1.0 / 3.0,
        0.0,
    )

    assert cli.minimum_pol4_derivative(fit, 0.5, 128.5) == pytest.approx(
        -epsilon
    )


def test_cli_reports_phase_file_run_and_event_progress(tmp_path):
    pre, flux, manifest_path, output = make_complete_fixture(tmp_path)

    result = run_cli(
        pre,
        flux,
        manifest_path,
        output,
        "--progress-every-events",
        "100",
    )

    assert result.returncode == 0, result.stderr
    for message in (
        "starting strip-energy/flux build",
        "manifest loaded: 2 runs",
        "h80 files discovered: 2",
        "h80 file 1/2:",
        f"RDataFrame implicit multithreading: {os.cpu_count() or 1} threads",
        "h80 events processed: 100",
        "flux run 1/2:",
        "building strip-energy lookup",
        "integrating flux binning: ajaka_sigma",
        "writing calibrated ROOT:",
        "completed successfully",
    ):
        assert message in result.stderr
    assert re.search(
        r"\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}\] "
        r"\[\+\d+\.\d+s\] h80 events processed: 100(?:\D|$)",
        result.stderr,
    )


def test_cli_rejects_nonpositive_rdataframe_thread_count(tmp_path):
    pre, flux, manifest_path, output = make_complete_fixture(tmp_path)

    result = run_cli(pre, flux, manifest_path, output, "--threads", "0")

    assert result.returncode == 1
    assert "threads must be at least 1" in result.stderr
    assert not output.exists()


def test_cli_rejects_nonpositive_sample_capacity(tmp_path):
    pre, flux, manifest_path, output = make_complete_fixture(tmp_path)

    result = run_cli(
        pre,
        flux,
        manifest_path,
        output,
        "--samples-per-run-strip",
        "0",
    )

    assert result.returncode == 1
    assert "samples-per-run-strip must be at least 1" in result.stderr
    assert not output.exists()


def test_zero_event_interval_disables_only_inner_event_updates(tmp_path):
    pre, flux, manifest_path, output = make_complete_fixture(tmp_path)

    result = run_cli(
        pre,
        flux,
        manifest_path,
        output,
        "--progress-every-events",
        "0",
    )

    assert result.returncode == 0, result.stderr
    assert "h80 file 1/2:" in result.stderr
    assert "h80 events processed:" not in result.stderr


def test_cli_complete_extra_flux_run_is_warning_only(tmp_path):
    pre, flux, manifest_path, output = make_complete_fixture(tmp_path)
    append_histogram(flux, "run99_POL1")
    append_histogram(flux, "run99_POL2")
    append_histogram(flux, "run99_BREM")

    result = run_cli(pre, flux, manifest_path, output)

    assert result.returncode == 0, result.stderr
    assert "WARNING: unused complete flux run 99" in result.stderr
    assert output.is_file()


def test_flux_histogram_bin_errors_do_not_change_final_flux(tmp_path):
    flux = tmp_path / "flux.root"
    write_flux(
        flux,
        {7: {"POL1": {12: 100.0}, "POL2": {12: 80.0}, "BREM": {12: 25.0}}},
        bin_error=1.0e12,
    )

    strips, _ = cli.read_flux_histograms(flux, [7])

    assert strips[11].flux_pol1 == 100.0
    assert strips[11].flux_pol2 == 80.0
    assert strips[11].flux_brem == 25.0


def test_parse_custom_binnings_rejects_duplicate_name():
    custom = cli.parse_custom_binnings(["fine:1.0,1.1,1.2"])

    assert custom == (EnergyBinning("fine", (1.0, 1.1, 1.2)),)
    with pytest.raises(StripEnergyFluxError, match="duplicate binning name"):
        cli.parse_custom_binnings(["fine:1.0,1.1", "fine:1.1,1.2"])


def test_cli_missing_h80_manifest_run_is_warning_only(tmp_path):
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

    assert result.returncode == 0, result.stderr
    assert "manifest runs absent from h80: [8]" in result.stderr
    assert "QA WARNING [1/1]" in result.stderr
    assert output.is_file()


def test_cli_interpolates_missing_lookup_with_nonzero_flux(tmp_path):
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

    assert result.returncode == 0, result.stderr
    assert "strip-energy lookup built: 256 run/strip rows" in result.stderr
    assert "filled missing rows: 1" in result.stderr
    assert output.is_file()


def test_cli_accepts_single_observed_strip_when_all_other_flux_is_zero(tmp_path):
    entries = {
        7: [(7, 24, 1.20)],
        8: [
            (8, strip, 1.00 + (strip - 1) * 0.5 / 127)
            for strip in range(1, 129)
        ],
    }
    flux_by_run = {
        7: {
            "POL1": {24: 10.0},
            "POL2": {24: 8.0},
            "BREM": {24: 1.0},
        },
        8: {
            "POL1": {strip: 10.0 for strip in range(1, 129)},
            "POL2": {strip: 8.0 for strip in range(1, 129)},
            "BREM": {strip: 1.0 for strip in range(1, 129)},
        },
    }
    pre, flux, manifest_path, output = make_complete_fixture(
        tmp_path,
        entries_by_run=entries,
        flux_by_run=flux_by_run,
    )

    result = run_cli(pre, flux, manifest_path, output)

    assert result.returncode == 0, result.stderr
    assert "strip-energy lookup built: 129 run/strip rows" in result.stderr
    assert "filled missing rows: 0" in result.stderr
    assert output.is_file()


def test_cli_target_filter_ignores_unmapped_deuterium_flux(tmp_path):
    entries = {
        7: [
            (7, strip, 1.00 + (strip - 1) * 0.5 / 127)
            for strip in range(1, 129)
        ],
        8: [(8, 23, 0.8394)],
        9: [
            (9, strip, 1.00 + (strip - 1) * 0.5 / 127)
            for strip in range(1, 129)
        ],
    }
    flux_by_run = {
        7: {
            "POL1": {strip: 10.0 for strip in range(1, 129)},
            "POL2": {strip: 8.0 for strip in range(1, 129)},
            "BREM": {strip: 1.0 for strip in range(1, 129)},
        },
        8: {
            "POL1": {24: 100.0},
            "POL2": {24: 80.0},
            "BREM": {24: 1.0},
        },
        9: {
            "POL1": {strip: 10.0 for strip in range(1, 129)},
            "POL2": {strip: 8.0 for strip in range(1, 129)},
            "BREM": {strip: 1.0 for strip in range(1, 129)},
        },
    }
    pre, flux, manifest_path, output = make_complete_fixture(
        tmp_path,
        entries_by_run=entries,
        flux_by_run=flux_by_run,
    )
    (pre / "pre_7.root").rename(pre / "pre_analisi_1999_uv1.root")
    (pre / "pre_8.root").rename(pre / "pre_analisi_2001_d.root")
    write_h80(pre / "pre_analisi_1999_uv2.root", entries[9])
    write_flux(flux, flux_by_run)
    write_manifest(
        [
            RunRecord(7, "1999_uv1", "P", "UV", "P_UV", "manual", "1999_uv1/run7.root"),
            RunRecord(8, "2001_d", "D", "VIS", "D_VIS", "manual", "2001_d/run8.root"),
            RunRecord(9, "1999_uv2", "P", "UV", "P_UV", "manual", "1999_uv2/run9.root"),
        ],
        manifest_path,
    )

    result = run_cli(pre, flux, manifest_path, output, "--target", "P")

    assert result.returncode == 0, result.stderr
    assert output.is_file()
    assert "nonzero flux without lookup" not in result.stderr
    import ROOT

    calibrated = ROOT.TFile.Open(str(output))
    try:
        assert calibrated.Get("run7_POL1")
        assert calibrated.Get("run9_POL1")
        assert not calibrated.Get("run8_POL1")
    finally:
        calibrated.Close()

    unfiltered_output = tmp_path / "unfiltered" / "flux_calibrated.root"
    unfiltered = run_cli(pre, flux, manifest_path, unfiltered_output)
    assert unfiltered.returncode == 1
    assert "run 8 strip 24: nonzero flux without lookup" in unfiltered.stderr
    assert not unfiltered_output.exists()


def test_cli_negative_flux_content_is_clamped_and_warned(tmp_path):
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

    assert result.returncode == 0, result.stderr
    assert "negative flux histogram bin clamped to zero" in result.stderr
    assert "run/strip exposure with non-positive POL1/POL2" in result.stderr
    import ROOT

    calibrated = ROOT.TFile.Open(str(output))
    try:
        assert calibrated.Get("run7_POL1").GetBinContent(1) == 0.0
    finally:
        calibrated.Close()


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
    assert "QA ERROR [1/" in result.stderr
    assert "monotonic inversion" in result.stderr
    assert not output.exists()


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
    assert output.is_file()


def test_run_preserves_existing_output_when_root_reading_raises(tmp_path):
    pre, flux, manifest_path, output = make_complete_fixture(tmp_path)
    (pre / "pre_7.root").write_text("not a ROOT file")
    output.write_text("old")
    args = SimpleNamespace(
        preanalysis_dir=pre,
        manifest=manifest_path,
        flux=flux,
        output_dir=output.parent,
        min_events_per_strip=1,
        max_mad_gev=0.005,
        monotonic_tolerance_gev=0.002,
        binning=[],
    )

    with pytest.raises(StripEnergyFluxError, match="zombie"):
        cli.run(args)

    assert output.read_text() == "old"


def test_cli_malformed_root_does_not_publish_output(tmp_path):
    pre, flux, manifest_path, output = make_complete_fixture(tmp_path)
    (pre / "pre_7.root").write_text("not a ROOT file")

    result = run_cli(pre, flux, manifest_path, output)

    assert result.returncode == 1
    assert f"zombie ROOT file: {pre / 'pre_7.root'}" in result.stderr
    assert not output.exists()


def test_cli_h80_beam_without_energy_method_reports_context_without_output(
    tmp_path,
):
    pre, flux, manifest_path, output = make_complete_fixture(tmp_path)
    malformed = pre / "pre_7.root"
    write_h80_with_scalar_beam(malformed)

    result = run_cli(pre, flux, manifest_path, output)

    assert result.returncode == 1
    assert (
        f"{malformed}: h80 entry 0: cannot convert RunNumber/Xstrip/beam.E()"
        in result.stderr
    )
    assert not output.exists()


def test_cli_duplicate_custom_binning_reports_error_without_output(tmp_path):
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
    assert "duplicate binning name: fine" in result.stderr
    assert not output.exists()


def test_cli_custom_binning_does_not_add_output_files(tmp_path):
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
    assert output.is_file()
    assert sorted(path.name for path in output.parent.iterdir() if path != pre) == [
        "flux.root",
        output.name,
        "run_manifest.csv",
    ]


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
    assert output.is_file()


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
    assert output.is_file()


def test_cli_argument_syntax_error_exits_two_without_output(tmp_path):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--output-dir", str(tmp_path / "out")],
        text=True,
        capture_output=True,
    )

    assert result.returncode == 2
    assert not (tmp_path / "out").exists()


def test_cli_rejects_output_equal_to_input_without_deleting_it(tmp_path):
    pre, flux, manifest_path, _ = make_complete_fixture(tmp_path)
    input_flux = tmp_path / "flux_calibrated.root"
    flux.rename(input_flux)

    result = run_cli(pre, input_flux, manifest_path, input_flux)

    assert result.returncode == 1
    assert "output path overlaps input path" in result.stderr
    assert pre.is_dir()
    assert input_flux.is_file()
    assert manifest_path.is_file()


def test_cli_rejects_lexical_input_symlink_inside_output_without_deleting_it(
    tmp_path,
):
    pre, flux, manifest_path, _ = make_complete_fixture(tmp_path)
    output_dir = tmp_path / "published"
    output_dir.mkdir()
    supplied_pre = output_dir / "preanalysis-link"
    supplied_pre.symlink_to(pre, target_is_directory=True)
    output = supplied_pre / "flux_calibrated.root"

    result = run_cli(supplied_pre, flux, manifest_path, output)

    assert result.returncode == 1
    assert "output path overlaps pre-analysis input" in result.stderr
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

    lookup, h80_qa = cli.read_h80_lookup(
        pre, run_numbers=[7], samples_per_run_strip=256, threads=1
    )
    strips, flux_qa = cli.read_flux_histograms(flux, [7])

    assert [(row.run_number, row.xstrip) for row in lookup] == [
        (7, 12), (7, 13)
    ]
    assert strips[11].flux_pol1 == pytest.approx(100.0)
    assert strips[11].flux_pol2 == pytest.approx(80.0)
    assert strips[11].flux_brem == pytest.approx(10.0)
    assert h80_qa["entries"] == 2
    assert flux_qa["run_count"] == 1


def test_h80_reader_recursively_sorts_root_files(tmp_path):
    pre = tmp_path / "pre"
    (pre / "b").mkdir(parents=True)
    (pre / "a").mkdir()
    write_h80(pre / "b" / "second.root", [(8, 2, 1.2)])
    write_h80(pre / "a" / "first.root", [(7, 1, 1.3)])

    lookup, _ = cli.read_h80_lookup(
        pre, run_numbers=[7, 8], samples_per_run_strip=256, threads=1
    )

    assert [row.run_number for row in lookup] == [7, 8]


def test_rdataframe_lookup_computes_sample_statistics_across_files_and_runs(
    tmp_path,
):
    pre = tmp_path / "pre"
    pre.mkdir()
    write_h80(
        pre / "first.root",
        [(7, 1, 1.0), (8, 2, 1.8), (7, 1, 1.2)],
    )
    write_h80(
        pre / "second.root",
        [(7, 1, 1.4), (8, 2, 2.0), (7, 3, 1.5)],
    )

    lookup, qa = cli.read_h80_lookup(
        pre, run_numbers=[7, 8], samples_per_run_strip=256, threads=1
    )

    assert lookup == (
        StripEnergyRecord(7, 1, 3, 1.2, pytest.approx(0.2), 1.0, 1.4, "sampled"),
        StripEnergyRecord(7, 3, 1, 1.5, 0.0, 1.5, 1.5, "sampled"),
        StripEnergyRecord(8, 2, 2, 1.9, pytest.approx(0.1), 1.8, 2.0, "sampled"),
    )
    assert qa == {
        "entries": 6,
        "file_count": 2,
        "sample_capacity": 256,
        "sampled_entries": 6,
        "fractional_xstrip_entries": 0,
        "invalid_xstrip_entries": 0,
        "extra_runs": [],
    }


def test_rdataframe_lookup_samples_once_and_reports_strip_conversion_qa(tmp_path):
    pre = tmp_path / "pre"
    pre.mkdir()
    write_h80(
        pre / "mixed.root",
        [
            (7, 3.75, 1.0),
            (7, 3.75, 1.2),
            (7, 3.75, 9.0),
            (7, 0.75, 1.1),
            (8, 4.25, 1.4),
            (99, 5.5, 1.5),
        ],
    )

    lookup, qa = cli.read_h80_lookup(
        pre,
        run_numbers=[7, 8],
        samples_per_run_strip=2,
        threads=1,
    )

    assert lookup == (
        StripEnergyRecord(7, 3, 3, 1.1, pytest.approx(0.1), 1.0, 1.2, "sampled"),
        StripEnergyRecord(8, 4, 1, 1.4, 0.0, 1.4, 1.4, "sampled"),
    )
    assert qa == {
        "entries": 6,
        "file_count": 1,
        "sample_capacity": 2,
        "sampled_entries": 3,
        "fractional_xstrip_entries": 6,
        "invalid_xstrip_entries": 1,
        "extra_runs": [99],
    }


def test_calibration_cells_skip_events_with_invalid_xstrip(tmp_path):
    pre = tmp_path / "pre"
    pre.mkdir()
    write_h80(
        pre / "mixed.root",
        [
            (7, 1, 1.0, 1.1),
            (7, 1, 0.0, 1.2),
            (7, 1, 129.0, 1.3),
            (7, 1, float("nan"), 1.4),
            (7, 1, float("inf"), 1.5),
            (7, 1, 128.0, 1.6),
        ],
    )

    cells, energy_bins = cli.read_calibration_cells(
        pre, run_numbers=[7], threads=16
    )

    assert [
        (
            cell.run_number,
            cell.polarization,
            cell.xstrip,
            cell.event_count,
            cell.xstrip_mean,
            cell.energy_mean_gev,
        )
        for cell in cells
    ] == [
        (7, 1, 1, 1, pytest.approx(1.0), pytest.approx(1.1)),
        (7, 1, 128, 1, pytest.approx(128.0), pytest.approx(1.6)),
    ]
    assert sum(item.event_count for item in energy_bins) == 2


def test_rdataframe_lookup_is_identical_with_one_and_multiple_threads(tmp_path):
    pre = tmp_path / "pre"
    pre.mkdir()
    write_h80(
        pre / "events.root",
        [
            (run, strip, 1.0 + 0.001 * event)
            for event in range(40)
            for run in (7, 8)
            for strip in (1, 2, 3)
        ],
    )

    serial, serial_qa = cli.read_h80_lookup(
        pre, run_numbers=[7, 8], samples_per_run_strip=100, threads=1
    )
    parallel, parallel_qa = cli.read_h80_lookup(
        pre, run_numbers=[7, 8], samples_per_run_strip=100, threads=2
    )

    assert parallel == serial
    assert parallel_qa == serial_qa


def test_h80_reader_rejects_no_root_files(tmp_path):
    pre = tmp_path / "pre"
    pre.mkdir()

    with pytest.raises(StripEnergyFluxError, match="no ROOT files"):
        cli.read_h80_lookup(
            pre, run_numbers=[7], samples_per_run_strip=256, threads=1
        )


def test_h80_reader_rejects_zombie_file(tmp_path):
    pre = tmp_path / "pre"
    pre.mkdir()
    (pre / "broken.root").write_text("not a ROOT file")

    with pytest.raises(StripEnergyFluxError, match="zombie"):
        cli.read_h80_lookup(
            pre, run_numbers=[7], samples_per_run_strip=256, threads=1
        )


def test_h80_reader_rejects_missing_tree(tmp_path):
    import ROOT

    pre = tmp_path / "pre"
    pre.mkdir()
    output = ROOT.TFile(str(pre / "missing_tree.root"), "RECREATE")
    ROOT.TH1D("other", "", 1, 0.0, 1.0).Write()
    output.Close()

    with pytest.raises(StripEnergyFluxError, match="missing h80"):
        cli.read_h80_lookup(
            pre, run_numbers=[7], samples_per_run_strip=256, threads=1
        )


def test_h80_reader_rejects_missing_required_branch(tmp_path):
    pre = tmp_path / "pre"
    pre.mkdir()
    write_h80(pre / "missing_beam.root", [(7, 12, 1.2)], branches=("RunNumber", "Xstrip"))

    with pytest.raises(StripEnergyFluxError, match="missing branch beam"):
        cli.read_h80_lookup(
            pre, run_numbers=[7], samples_per_run_strip=256, threads=1
        )


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
