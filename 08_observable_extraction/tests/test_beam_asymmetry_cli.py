from pathlib import Path

import numpy as np
import ROOT
import pytest

from graal_common.physics.beam_profiles import VIS_PROFILE
from observable_extraction import beam_asymmetry
from observable_extraction.core.binning import ENERGY_EDGES_GEV, PHI_EDGES_RAD
from observable_extraction.core.models import FluxExposure
from observable_extraction.io.reconstructed_events import EventArrays
from observable_extraction.io.root_output import OutputPoint
from observable_extraction.io.root_input import read_output_contract, read_output_points
from observable_extraction.core.models import FitDiagnostics, SigmaPoint
from observable_extraction.core.ratio_fit import RatioBinResult, RatioFitResult
from observable_extraction.core.background import BackgroundEstimate


def test_cli_defaults_to_raw_bdt_nominal_and_public_root_pdf_only():
    args = beam_asymmetry.build_parser().parse_args([])

    assert args.nominal_sample == "raw_bdt"
    assert args.raw_bdt_fit is None
    assert args.estimator == "both"
    assert args.profile == "uv"
    assert args.flux_file == Path("data/00_external/flux_calibrated.root")
    assert args.run_manifest == Path("config/run_manifest.csv")
    assert args.phi_bins == 12
    assert args.mass_bins == 10
    assert not hasattr(args, "csv_output")
    assert not hasattr(args, "json_output")


def _synthetic_events(sigma=0.30, beam_energy_gev=1.15, phi_bins=12):
    edges = np.linspace(0.0, 2.0 * np.pi, phi_bins + 1)
    centers = 0.5 * (edges[:-1] + edges[1:])
    flux_v, flux_h = 1.2, 0.9
    pol_v, pol_h = 0.6, 0.55
    ratio = sigma * np.cos(2.0 * centers)
    yield_v = np.full(phi_bins, 150.0)
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
        beam_energy_gev=np.full(len(phi), beam_energy_gev),
        eta=eta,
        pi0=pi0,
        proton=proton,
        missing_mass_gev=np.full(len(phi), 0.938),
        eta_mass_gev=np.full(len(phi), 0.548),
        pi0_mass_gev=np.full(len(phi), 0.135),
        bdt_score=np.full(len(phi), 0.9),
        n_photons_input=np.full(len(phi), 4),
    )


def test_likelihood_metadata_survives_unestimable_ratio():
    from dataclasses import fields

    source = _synthetic_events()
    indices = np.concatenate([
        np.flatnonzero(source.polarization == state)[:20] for state in (1, 2)
    ])
    events = EventArrays(**{
        field.name: getattr(source, field.name)[indices] for field in fields(source)
    })
    exposures = {(811, 17): FluxExposure(811, 17, 1.15, 1.2, 0.9, 0.2, 0.6, 0.55)}

    bundle = beam_asymmetry._extract_sample(
        sample_name="raw_bdt", events=events, exposures=exposures,
        estimator="both", retain_ratio_objects=False, energy_edges=ENERGY_EDGES_GEV,
    )

    assert bundle.points
    assert all(item.estimator == "likelihood" for item in bundle.points)
    for item in bundle.points:
        assert (item.count_vertical, item.count_horizontal) == (20, 20)
        assert (item.flux_vertical, item.flux_horizontal) == (1.2, 0.9)
        assert (item.polarization_vertical, item.polarization_horizontal) == (0.6, 0.55)


def test_likelihood_metadata_allows_exposure_energy_in_another_bin():
    # The conditional estimator uses the event's run/strip exposure even when
    # measured event energy and calibrated strip energy fall in different bins.
    events = _synthetic_events()
    exposures = {(811, 17): FluxExposure(811, 17, 1.25, 1.2, 0.9, 0.2, 0.6, 0.55)}

    bundle = beam_asymmetry._extract_sample(
        sample_name="raw_bdt", events=events, exposures=exposures,
        estimator="likelihood", retain_ratio_objects=False,
        energy_edges=ENERGY_EDGES_GEV, selected_phi_bins={},
    )

    assert bundle.points
    for item in bundle.points:
        assert item.count_vertical + item.count_horizontal == len(events)
        assert (item.flux_vertical, item.flux_horizontal) == (0.0, 0.0)
        assert (item.polarization_vertical, item.polarization_horizontal) == (0.0, 0.0)


@pytest.mark.parametrize("phi_bins,divisor", [(8, 0.9003), (12, 0.9549), (16, 0.9745)])
def test_standalone_workflow_writes_corrected_ratio_and_raw_azimuth_curve(
    tmp_path, monkeypatch, phi_bins, divisor
):
    events = _synthetic_events(beam_energy_gev=1.0, phi_bins=phi_bins)
    exposures = {
        (811, 17): FluxExposure(811, 17, 1.0, 1.2, 0.9, 0.2, 0.6, 0.55)
    }

    def load_nominal_run_exposures(_path, **kwargs):
        assert set(kwargs["run_numbers"]) == {811}
        assert kwargs["target"] == "P"
        assert kwargs["beam_type"] == "VIS"
        assert kwargs["energy_range"] == (0.9313, 1.10)
        assert kwargs["polarization_model"](1.0) == pytest.approx(
            VIS_PROFILE.polarization(1.0)
        )
        return exposures

    monkeypatch.setattr(
        beam_asymmetry,
        "load_exposures",
        load_nominal_run_exposures,
    )
    monkeypatch.setattr(
        beam_asymmetry,
        "read_reconstructed",
        lambda _path, _tree, vector_mode, **kwargs: events,
    )
    output = tmp_path / "beam_asymmetry"

    exit_code = beam_asymmetry.main(
        [
            "--raw-bdt", str(tmp_path / "nominal.root"),
            "--flux-file", str(tmp_path / "flux_calibrated.root"),
            "--run-manifest", str(tmp_path / "run_manifest.csv"),
            "--profile", "vis",
            "--phi-bins", str(phi_bins),
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
        covariance = source.Get("covariance/systematic/polarization_scale_3pct")
        assert covariance
        assert covariance.GetBinContent(1, 1) > 0.0
        energy_edges = source.Get("binning/energy_edges")
        stored_edges = [
            float(energy_edges[index])
            for index in range(energy_edges.GetNrows())
        ]
        assert stored_edges == pytest.approx([0.9313, 1.10])
        assert "profile=vis" in source.Get("provenance").GetTitle()
        assert "raw_vs_kinematic_fit=disabled" in source.Get("provenance").GetTitle()
        assert not source.Get("covariance/systematic/raw_vs_kinematic_fit")
        assert f"phi_bins={phi_bins}" in source.Get("provenance").GetTitle()
        phi_edges = source.Get("binning/phi_edges")
        assert phi_edges.GetNrows() == phi_bins + 1
        np.testing.assert_allclose(
            [phi_edges[index] for index in range(phi_edges.GetNrows())],
            np.linspace(0.0, 2.0 * np.pi, phi_bins + 1),
        )
        ratios = source.Get("ratio_objects/p_pi0/e0")
        (mass_key,) = tuple(ratios.GetListOfKeys())
        graph = ratios.Get(mass_key.GetName()).Get("ratio")
        assert graph.GetN() == phi_bins
        # The curve fits the observed ratio; only the published Sigma is corrected.
        fit = ratios.Get(mass_key.GetName()).Get("fit")
        tree.GetEntry(0)
        assert float(tree.sigma) == pytest.approx(fit.GetParameter(0) / divisor)
        assert float(tree.sigma_uncorrected) == float(tree.sigma)
        assert f"phi_bin_divisor={divisor}" in source.Get("provenance").GetTitle()
        assert "phi_bin_correction=ratio_only_rounded" in source.Get("provenance").GetTitle()
        statistical = source.Get("covariance/statistical")
        assert statistical.GetBinContent(1, 1) == pytest.approx(float(tree.stat_low) ** 2)
        # All synthetic events have exactly four photons: selecting exactly four
        # must give the same result with the same phi binning.
        multiplicity = source.Get("covariance/systematic/photon_multiplicity")
        assert multiplicity
        for index in range(1, multiplicity.GetNbinsX() + 1):
            assert multiplicity.GetBinContent(index, index) == pytest.approx(0.0, abs=1e-15)
    finally:
        source.Close()
    points = read_output_points(output / "beam_asymmetry.root")
    assert [item.point.sigma for item in points if item.estimator == "ratio"] == pytest.approx(
        [0.30 / divisor] * 3, abs=0.01,
    )
    assert [item.point.sigma for item in points if item.estimator == "likelihood"] == pytest.approx(
        [0.30] * 3, abs=0.04,
    )
    assert len(read_output_contract(output / "beam_asymmetry.root").phi_edges_rad) == phi_bins + 1


def test_finite_bin_correction_leaves_unbinned_likelihood_unchanged():
    events = _synthetic_events()
    exposures = {(811, 17): FluxExposure(811, 17, 1.15, 1.2, 0.9, 0.2, 0.6, 0.55)}
    outputs = []
    for bins in (8, 12, 16):
        bundle = beam_asymmetry._extract_sample(
            sample_name="raw_bdt", events=events, exposures=exposures, estimator="both",
            retain_ratio_objects=False, energy_edges=ENERGY_EDGES_GEV,
            phi_edges=np.linspace(0.0, 2.0 * np.pi, bins + 1),
        )
        outputs.append(tuple(item.point for item in bundle.points if item.estimator == "likelihood"))
    assert outputs[0]
    assert outputs[0] == outputs[1] == outputs[2]


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
        lambda _path, **_kwargs: {
            (811, 17): FluxExposure(811, 17, 1.15, 1.2, 0.9, 0.2, 0.6, 0.55)
        },
    )
    monkeypatch.setattr(
        beam_asymmetry,
        "read_reconstructed",
        lambda _path, _tree, vector_mode, **kwargs: _synthetic_events(),
    )

    with pytest.raises(ValueError, match="supplied together"):
        beam_asymmetry.main(
            [
                "--raw-bdt", str(tmp_path / "nominal.root"),
                "--sideband", str(tmp_path / "sideband.root"),
                "--flux-file", str(tmp_path / "flux_calibrated.root"),
                "--run-manifest", str(tmp_path / "run_manifest.csv"),
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
        ENERGY_EDGES_GEV,
    )

    assert leakage == 0.0
    assert estimates[0].converged
    assert 0.0 < estimates[0].fraction < 1.0


def test_source_inventory_distinguishes_measured_zero_missing_and_retired():
    from dataclasses import replace
    from observable_extraction.tests.test_root_output import _point

    ratio = replace(_point(), sigma_uncorrected=.3, background_fraction=0.)
    likelihood = replace(ratio, estimator='likelihood')
    points = [ratio, likelihood]
    covariances = beam_asymmetry._systematic_covariances(points)
    assert 'estimator_ratio_vs_likelihood' in covariances
    np.testing.assert_array_equal(covariances['estimator_ratio_vs_likelihood'], np.zeros((2, 2)))
    inventory = beam_asymmetry._systematic_inventory(points, covariances)
    assert inventory['estimator_ratio_vs_likelihood']['status'] == 'executed'
    assert inventory['flux_balance']['status'] == 'unavailable'
    assert inventory['raw_vs_kinematic_fit']['status'] == 'not_applicable'
    missing = beam_asymmetry._systematic_inventory([ratio], beam_asymmetry._systematic_covariances([ratio]))
    assert missing['estimator_ratio_vs_likelihood']['status'] == 'unavailable'
    archived = replace(ratio, sample='raw_bdt_fit', point=replace(ratio.point, sigma=.4))
    assert 'raw_vs_kinematic_fit' not in beam_asymmetry._systematic_covariances([ratio, archived])


def test_diagnostic_bootstrap_requires_explicit_universe_before_reading_inputs(tmp_path):
    args = beam_asymmetry.build_parser().parse_args([
        '--bootstrap-diagnostics-replicas', '5', '--output-dir', str(tmp_path)])
    with pytest.raises(ValueError, match='universe'):
        beam_asymmetry.run(args)


@pytest.mark.parametrize("best_binning", [False, True])
def test_paired_diagnostic_reextracts_both_samples_with_shared_run_draws(best_binning):
    from dataclasses import replace
    from observable_extraction.io.root_output import ordered_point_keys, point_key_label

    events = _synthetic_events()
    events = replace(events, run_number=811 + np.arange(len(events)) % 2)
    exposures = {(run, 17): FluxExposure(run, 17, 1.15, .6, .45, .1, .6, .55) for run in (811, 812)}
    samples = {'raw': events, 'raw_bdt': events}
    points = tuple(item for name in samples for item in beam_asymmetry._extract_sample(
        sample_name=name, events=events, exposures=exposures, estimator='ratio',
        retain_ratio_objects=False, energy_edges=ENERGY_EDGES_GEV, best_binning=best_binning).points)
    labels = tuple(point_key_label(key) for key in ordered_point_keys(points, {}))
    result = beam_asymmetry._paired_bootstrap_diagnostics(
        points=points, samples=samples, exposures=exposures,
        run_strata={811: 'uv:1998', 812: 'uv:1998'}, point_keys=labels,
        nominal_sample='raw_bdt', estimator='ratio', replicas=4, seed=8,
        energy_edges=ENERGY_EDGES_GEV, phi_edges=PHI_EDGES_RAD, best_binning=best_binning)
    half = len(points) // 2
    assert not result.failures
    np.testing.assert_array_equal(result.replicas[:, :half], result.replicas[:, half:])


def test_cli_persists_paired_diagnostic_without_combining_it(tmp_path, monkeypatch):
    # This test mocks input ROOT I/O; real energy-domain guards have dedicated tests.
    monkeypatch.setattr(beam_asymmetry, "_validate_energy_inputs", lambda args: None)
    from dataclasses import replace
    from calibration.run_manifest import RunRecord, write_manifest
    from observable_extraction.io.root_input import read_output_uncertainties, read_bootstrap_diagnostics

    events = _synthetic_events(beam_energy_gev=1.)
    events = replace(events, run_number=811 + np.arange(len(events)) % 2)
    exposures = {(run, 17): FluxExposure(run, 17, 1., .6, .45, .1, .6, .55) for run in (811, 812, 813)}
    nominal, flux, manifest = [tmp_path / name for name in ('nominal.root', 'flux.root', 'runs.csv')]
    nominal.write_bytes(b'synthetic input read by test adapter')
    flux.write_bytes(b'synthetic exposures read by test adapter')
    write_manifest([RunRecord(run, '1999_vis', 'P', 'VIS', 'P_VIS', 'automatic', f'1999_vis/run{run}.root')
                    for run, _ in exposures], manifest)
    monkeypatch.setattr(beam_asymmetry, 'read_reconstructed', lambda *args, **kwargs: events)
    monkeypatch.setattr(beam_asymmetry, 'load_exposures',
                        lambda *args, **kwargs: {key: value for key, value in exposures.items()
                                                 if key[0] in set(kwargs['run_numbers'])})
    output = tmp_path / 'output'
    args = beam_asymmetry.build_parser().parse_args([
        '--raw-bdt', str(nominal), '--raw', str(tmp_path / 'absent.root'),
        '--flux-file', str(flux), '--run-manifest', str(manifest), '--profile', 'vis',
        '--estimator', 'ratio', '--output-dir', str(output),
        '--bootstrap-diagnostics-replicas', '4', '--bootstrap-universe-manifest', str(manifest)])
    assert beam_asymmetry.run(args) == 0
    path = output / 'beam_asymmetry.root'
    result, diagnostic = read_output_uncertainties(path), read_bootstrap_diagnostics(path)
    assert diagnostic.replicas.shape == (4, 3)
    assert diagnostic.zero_event_runs['raw_bdt'] == (813,)
    assert result.metadata['final_inference'] == 'suspended'
    assert result.metadata['sources']['raw_vs_kinematic_fit']['status'] == 'not_applicable'
    assert result.metadata['bootstrap_diagnostic_status'] == 'failed_replicas'
    assert diagnostic.failures  # seeded draw contains only the exposed zero-yield run
    assert diagnostic.covariance is None
    assert result.metadata['bootstrap_inputs'][0]['sha256']
    assert 'bootstrap_run' not in result.matrices
    assert np.count_nonzero(result.matrices['statistical'] - np.diag(np.diag(result.matrices['statistical']))) == 0


def test_paired_diagnostic_retains_expected_optimizer_failures(monkeypatch):
    from types import SimpleNamespace
    from observable_extraction.core import conditional_likelihood
    from observable_extraction.io.root_output import ordered_point_keys, point_key_label

    events = _synthetic_events()
    exposures = {(811, 17): FluxExposure(811, 17, 1.15, 1.2, .9, .2, .6, .55)}
    points = beam_asymmetry._extract_sample(sample_name='raw_bdt', events=events,
        exposures=exposures, estimator='both', retain_ratio_objects=False,
        energy_edges=ENERGY_EDGES_GEV).points
    monkeypatch.setattr(conditional_likelihood, 'minimize_scalar',
        lambda *args, **kwargs: SimpleNamespace(success=False, fun=float('inf'), message='forced optimizer failure'))
    result = beam_asymmetry._paired_bootstrap_diagnostics(
        points=points, samples={'raw_bdt': events}, exposures=exposures,
        run_strata={811: 'uv:1998'}, point_keys=tuple(point_key_label(key) for key in ordered_point_keys(points, {})),
        nominal_sample='raw_bdt', estimator='both', replicas=3, seed=8,
        energy_edges=ENERGY_EDGES_GEV, phi_edges=PHI_EDGES_RAD)
    assert len(result.failures) == 3
    assert result.covariance is None
    assert all('forced optimizer failure' in reason for reason in result.failures.values())


def test_diagnostic_universe_cannot_drop_previously_selected_runs():
    from observable_extraction.tests.test_systematics import _run_events

    with pytest.raises(ValueError, match='omits selected runs'):
        beam_asymmetry._validate_diagnostic_universe(
            {'nominal': _run_events([811, 812]), 'sideband': _run_events([813])},
            {811: 'uv:1998', 812: 'uv:1998'})
