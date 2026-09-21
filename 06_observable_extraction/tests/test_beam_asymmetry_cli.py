from pathlib import Path

import numpy as np
import ROOT
import pytest

from observable_extraction import beam_asymmetry
from observable_extraction.core.binning import PHI_EDGES_RAD
from observable_extraction.core.models import FluxExposure
from observable_extraction.io.reconstructed_events import EventArrays
from observable_extraction.io.root_output import OutputPoint
from observable_extraction.core.models import FitDiagnostics, SigmaPoint
from observable_extraction.core.ratio_fit import RatioBinResult, RatioFitResult
from observable_extraction.core.background import BackgroundEstimate


def test_cli_defaults_to_raw_bdt_nominal_and_public_root_pdf_only():
    args = beam_asymmetry.build_parser().parse_args([])

    assert args.nominal_sample == "raw_bdt"
    assert args.estimator == "both"
    assert args.phi_bins == 12
    assert args.mass_bins == 10
    assert not hasattr(args, "csv_output")
    assert not hasattr(args, "json_output")


def _synthetic_events(sigma=0.30):
    centers = 0.5 * (PHI_EDGES_RAD[:-1] + PHI_EDGES_RAD[1:])
    flux_v, flux_h = 1.2, 0.9
    pol_v, pol_h = 0.6, 0.55
    ratio = sigma * np.cos(2.0 * centers)
    yield_v = np.full(12, 150.0)
    yield_h = yield_v * (1.0 - pol_h * ratio) / (1.0 + pol_v * ratio)
    counts_v = np.rint(flux_v * yield_v).astype(int)
    counts_h = np.rint(flux_h * yield_h).astype(int)
    phi = np.concatenate(
        [np.repeat(centers, counts_v), np.repeat(centers, counts_h)]
    )
    polarization = np.concatenate(
        [np.ones(counts_v.sum(), dtype=int), np.full(counts_h.sum(), 2, dtype=int)]
    )

    cosine = np.cos(phi)
    sine = np.sin(phi)
    proton = np.column_stack(
        (0.10 * cosine, 0.10 * sine, np.full(len(phi), 0.10), np.full(len(phi), 0.949))
    )
    eta = np.column_stack(
        (0.10 * cosine, 0.10 * sine, np.full(len(phi), 0.05), np.full(len(phi), 0.559))
    )
    pi0 = np.column_stack(
        (-0.20 * cosine, -0.20 * sine, np.full(len(phi), 0.05), np.full(len(phi), 0.245))
    )
    return EventArrays(
        run_number=np.full(len(phi), 811),
        xstrip=np.full(len(phi), 17),
        polarization=polarization,
        beam_energy_gev=np.full(len(phi), 1.15),
        eta=eta,
        pi0=pi0,
        proton=proton,
        missing_mass_gev=np.full(len(phi), 0.938),
        eta_mass_gev=np.full(len(phi), 0.548),
        pi0_mass_gev=np.full(len(phi), 0.135),
        bdt_score=np.full(len(phi), 0.9),
        n_photons_input=np.full(len(phi), 4),
    )


def test_standalone_workflow_writes_root_pdf_and_recovers_injected_sigma(
    tmp_path, monkeypatch
):
    events = _synthetic_events()
    exposures = {
        (811, 17): FluxExposure(811, 17, 1.15, 1.2, 0.9, 0.2, 0.6, 0.55)
    }
    monkeypatch.setattr(beam_asymmetry, "load_exposures", lambda _path: exposures)
    monkeypatch.setattr(
        beam_asymmetry,
        "read_reconstructed",
        lambda _path, _tree, vector_mode: events,
    )
    output = tmp_path / "beam_asymmetry"

    exit_code = beam_asymmetry.main(
        [
            "--raw-bdt", str(tmp_path / "nominal.root"),
            "--calibration-dir", str(tmp_path / "calibration"),
            "--output-dir", str(output),
        ]
    )

    assert exit_code == 0
    assert (output / "beam_asymmetry.root").is_file()
    assert (output / "figure4_experimental.pdf").is_file()
    assert (output / "comparison_reconstruction_samples.pdf").is_file()
    assert (output / "comparison_estimators.pdf").is_file()
    assert (output / "fit_diagnostics.pdf").is_file()
    assert (output / "systematic_summary.pdf").is_file()
    assert (output / "false_asymmetry_controls.pdf").is_file()
    assert (output / "photon_multiplicity.pdf").is_file()
    assert not list(output.glob("*.csv"))
    assert not list(output.glob("*.json"))
    source = ROOT.TFile.Open(str(output / "beam_asymmetry.root"))
    try:
        tree = source.Get("sigma_points")
        assert tree.GetEntries() == 6
        sigmas = [float(entry.sigma) for entry in tree]
        assert all(abs(value - 0.30) < 0.05 for value in sigmas)
        covariance = source.Get("covariance/systematic/polarization_scale_3pct")
        assert covariance
        assert covariance.GetBinContent(1, 1) > 0.0
    finally:
        source.Close()


def test_background_correction_keeps_uncorrected_value_and_propagates_error():
    diagnostics = FitDiagnostics(True, 1.0, 4, 0.9, False)
    point = OutputPoint(
        sample="raw_bdt",
        estimator="ratio",
        point=SigmaPoint(
            "p_pi0", 0, 0, 1.1, 1.2, 1.07, 1.10, 1.08,
            0.25, 0.04, 0.04, diagnostics,
        ),
        sigma_uncorrected=0.25,
        systematic_total=0.0,
        background_fraction=0.0,
        count_vertical=100,
        count_horizontal=90,
        flux_vertical=1000.0,
        flux_horizontal=900.0,
        polarization_vertical=0.6,
        polarization_horizontal=0.58,
    )
    background_point = SigmaPoint(
        "p_pi0", 0, 0, 1.1, 1.2, 1.07, 1.10, 1.08,
        -0.10, 0.05, 0.05, diagnostics,
    )
    background_fit = RatioFitResult(
        -0.10, 0.05, np.array([]), np.array([]), np.array([], dtype=bool), diagnostics
    )
    background = RatioBinResult(
        background_point, background_fit, np.array([]), np.array([]),
        1.0, 1.0, 0.5, 0.5,
    )

    corrected = beam_asymmetry._apply_background_correction(
        [point],
        {0: BackgroundEstimate(0.2, 0.03, 1.0, True)},
        {("p_pi0", 0, 0): background},
    )[0]

    assert corrected.sigma_uncorrected == 0.25
    np.testing.assert_allclose(corrected.point.sigma, 0.3375, rtol=0, atol=1e-12)


def test_background_inputs_must_be_supplied_together(tmp_path, monkeypatch):
    monkeypatch.setattr(
        beam_asymmetry,
        "load_exposures",
        lambda _path: {
            (811, 17): FluxExposure(811, 17, 1.15, 1.2, 0.9, 0.2, 0.6, 0.55)
        },
    )
    monkeypatch.setattr(
        beam_asymmetry,
        "read_reconstructed",
        lambda _path, _tree, vector_mode: _synthetic_events(),
    )

    with pytest.raises(ValueError, match="supplied together"):
        beam_asymmetry.main(
            [
                "--raw-bdt", str(tmp_path / "nominal.root"),
                "--sideband", str(tmp_path / "sideband.root"),
                "--calibration-dir", str(tmp_path / "calibration"),
                "--output-dir", str(tmp_path / "output"),
            ]
        )


def _mass_only_events(pulls):
    pulls = np.asarray(pulls, dtype=float)
    count = len(pulls)
    windows = beam_asymmetry.SIDEBAND_WINDOWS
    vectors = np.zeros((count, 4), dtype=float)
    return EventArrays(
        run_number=np.full(count, 811),
        xstrip=np.full(count, 17),
        polarization=np.ones(count, dtype=int),
        beam_energy_gev=np.full(count, 1.15),
        eta=vectors,
        pi0=vectors,
        proton=vectors,
        missing_mass_gev=windows.missing_center + pulls[:, 2] * windows.missing_half_width,
        eta_mass_gev=windows.eta_center + pulls[:, 0] * windows.eta_half_width,
        pi0_mass_gev=windows.pi0_center + pulls[:, 1] * windows.pi0_half_width,
        bdt_score=np.full(count, 0.9),
        n_photons_input=np.full(count, 4),
    )


def test_three_dimensional_sideband_fit_produces_signal_region_fraction():
    signal_pulls = np.tile(
        np.array([[0.1, -0.1, 0.2], [-0.2, 0.2, -0.1]]),
        (100, 1),
    )
    hard_patterns = np.array(
        [
            [2.5, 2.5, 0.0],
            [2.5, 0.0, -2.5],
            [0.0, -2.5, 2.5],
            [-2.5, -2.5, 0.0],
            [-2.5, 0.0, 2.5],
            [0.0, 2.5, -2.5],
        ]
    )
    broad = _mass_only_events(
        np.concatenate((signal_pulls, np.tile(hard_patterns, (15, 1))))
    )
    signal_mc = _mass_only_events(signal_pulls)

    estimates, leakage = beam_asymmetry._estimate_background_fractions(
        broad,
        signal_mc,
    )

    assert leakage == 0.0
    assert estimates[0].converged
    assert 0.0 < estimates[0].fraction < 1.0
