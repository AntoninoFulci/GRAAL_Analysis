from dataclasses import replace

import pytest

from observable_extraction.core.models import FitDiagnostics
from observable_extraction.core import ratio_fit


def test_best_binning_reuses_projections_and_keeps_all_corrected_candidates(monkeypatch):
    import numpy as np
    from observable_extraction import beam_asymmetry as beam
    from observable_extraction.core.models import FluxExposure
    from observable_extraction.tests.test_beam_asymmetry_cli import _synthetic_events

    calls = []
    project = beam.project_all_pairs
    def project_once(*args):
        calls.append(1)
        return project(*args)
    monkeypatch.setattr(beam, "project_all_pairs", project_once)
    events = _synthetic_events(beam_energy_gev=1.0, phi_bins=48)
    bundle = beam._extract_sample(
        sample_name="raw_bdt", events=events,
        exposures={(811, 17): FluxExposure(811, 17, 1.0, 1.2, 0.9, 0.2, 0.6, 0.55)},
        estimator="both", retain_ratio_objects=True,
        energy_edges=np.array([0.9313, 1.10]), best_binning=True,
    )
    assert len(calls) == 1
    assert len(bundle.points) == 6
    assert len(bundle.binning_candidates) == 9
    assert {p.phi_bins for p in bundle.binning_candidates} == {8, 12, 16}
    divisors = {8: 0.9003, 12: 0.9549, 16: 0.9745}
    for point in bundle.binning_candidates:
        graph = next(g for g in bundle.candidate_ratio_objects
                     if g.pair == point.point.pair and g.phi_bins == point.phi_bins)
        assert point.point.sigma == pytest.approx(graph.sigma / divisors[point.phi_bins])
    for point in bundle.points:
        if point.estimator == "likelihood":
            assert point.phi_bins == 0
            continue
        candidates = [p for p in bundle.binning_candidates if p.point.pair == point.point.pair]
        expected = min(candidates, key=lambda p: (
            p.point.diagnostics.p_value < 0.01, p.point.diagnostics.used_fallback,
            abs(p.point.diagnostics.chi2 / p.point.diagnostics.ndf - 1),
            {12: 0, 8: 1, 16: 2}[p.phi_bins]))
        assert point == expected


def test_cli_best_binning_is_opt_in():
    from observable_extraction.beam_asymmetry import build_parser
    assert not build_parser().parse_args([]).best_binning
    assert build_parser().parse_args(["--best-binning"]).best_binning


def test_best_binning_workflow_persists_choice_candidates_and_matching_controls(tmp_path, monkeypatch):
    import ROOT
    from observable_extraction import beam_asymmetry as beam
    from observable_extraction.core.models import FluxExposure
    from observable_extraction.io.root_input import read_output_contract, read_output_points
    from observable_extraction.tests.test_beam_asymmetry_cli import _synthetic_events

    events = _synthetic_events(beam_energy_gev=1.0, phi_bins=48)
    reads = []
    def read(*args, **kwargs):
        reads.append(args[0])
        return events
    monkeypatch.setattr(beam, "read_reconstructed", read)
    monkeypatch.setattr(beam, "load_exposures", lambda *a, **k: {
        (811, 17): FluxExposure(811, 17, 1.0, 1.2, 0.9, 0.2, 0.6, 0.55)})
    out = tmp_path / "best"
    beam.main(["--raw-bdt", str(tmp_path / "nominal.root"),
               "--raw", str(tmp_path / "absent.root"), "--profile", "vis",
               "--best-binning", "--output-dir", str(out)])
    assert len(reads) == 1
    points = read_output_points(out / "beam_asymmetry.root")
    contract = read_output_contract(out / "beam_asymmetry.root")
    assert contract.best_binning
    assert contract.phi_bin_divisor is None
    assert len(points) == 6
    assert (out / "figure4_experimental.pdf").is_file()
    source = ROOT.TFile.Open(str(out / "beam_asymmetry.root"))
    try:
        for bins in (8, 12, 16):
            assert source.Get(f"binning_candidates/{bins}/sigma_points").GetEntries() == 3
        for p in points:
            if p.estimator != "ratio":
                assert p.phi_bins == 0
                continue
            prefix = f"{p.point.pair}/e{p.point.energy_bin}/m{p.point.mass_bin}"
            graph = source.Get(f"ratio_objects/{prefix}/ratio")
            assert graph.GetN() == p.phi_bins
            fit = source.Get(f"binning_candidates/{p.phi_bins}/ratio_objects/{prefix}/fit")
            divisor = {8: 0.9003, 12: 0.9549, 16: 0.9745}[p.phi_bins]
            assert p.point.sigma == pytest.approx(fit.GetParameter(0) / divisor)
        matrix = source.Get("covariance/systematic/photon_multiplicity")
        for index in range(1, matrix.GetNbinsX() + 1):
            assert matrix.GetBinContent(index, index) == pytest.approx(0, abs=1e-15)
    finally:
        source.Close()


def test_best_binning_uses_distance_from_one_not_smallest_chi2():
    rank = ratio_fit.binning_quality_key
    low = FitDiagnostics(True, 0.7, 7, 0.99, False)
    close = FitDiagnostics(True, 10.8, 11, 0.46, False)
    assert rank(close, 12) < rank(low, 8)


def test_best_binning_prefers_valid_nominal_and_has_stable_tie_break():
    rank = ratio_fit.binning_quality_key
    nominal = FitDiagnostics(True, 9, 7, 0.25, False)
    fallback = FitDiagnostics(True, 5, 5, 0.4, True)
    assert rank(nominal, 8) < rank(fallback, 8)
    assert rank(nominal, 8) < rank(replace(nominal, p_value=0.001), 8)
    perfect = FitDiagnostics(True, 11, 11, 0.4, False)
    assert rank(perfect, 12) < rank(perfect, 8)
    assert rank(perfect, 8) < rank(perfect, 16)
    for invalid in [replace(perfect, converged=False), replace(perfect, ndf=0)]:
        with pytest.raises(ValueError, match="valid"):
            rank(invalid, 12)


def test_each_mass_point_selects_independently_and_missing_fixed_fit_stays_missing(monkeypatch):
    import numpy as np
    from observable_extraction import beam_asymmetry as beam
    from observable_extraction.core.models import FluxExposure
    from observable_extraction.tests.test_beam_asymmetry_cli import _synthetic_events

    events = _synthetic_events(beam_energy_gev=1.0, phi_bins=48)
    exposures = {(811, 17): FluxExposure(811, 17, 1.0, 1.2, 0.9, 0.2, 0.6, 0.55)}
    masses, phis = beam.project_all_pairs(events.proton, events.eta, events.pi0)["p_pi0"]
    real = beam.extract_ratio_grid(pair="p_pi0", mass_gev=masses, phi_rad=phis,
        beam_energy_gev=events.beam_energy_gev, polarization=events.polarization,
        exposures=exposures, energy_edges=np.array([0.9313, 1.10]))[0]

    def grid(*, pair, phi_edges, **kwargs):
        n = len(phi_edges) - 1
        if pair != "p_pi0" or n == 16:
            return ()
        results = []
        for mass_bin in (0, 1):
            # Point 0 prefers 8 bins; point 1 prefers 12 bins.
            chi2 = n - 1 if (mass_bin == 0) == (n == 8) else 0.1
            diag = FitDiagnostics(True, chi2, n - 1, 0.5, False)
            results.append(replace(real, point=replace(real.point, mass_bin=mass_bin, diagnostics=diag),
                fit=replace(real.fit, diagnostics=diag), counts_vertical=np.ones(n), counts_horizontal=np.ones(n)))
        return tuple(results)

    monkeypatch.setattr(beam, "extract_ratio_grid", grid)
    options = dict(sample_name="raw_bdt", events=events, exposures=exposures,
                   estimator="ratio", retain_ratio_objects=False, energy_edges=np.array([0.9313, 1.10]))
    bundle = beam._extract_sample(**options, best_binning=True)
    assert [(p.point.mass_bin, p.phi_bins) for p in bundle.points] == [(0, 8), (1, 12)]
    fixed = beam._extract_sample(**options, selected_phi_bins={
        ("p_pi0", 0, 0): 12, ("p_pi0", 0, 1): 16})
    assert [(p.point.mass_bin, p.phi_bins) for p in fixed.points] == [(0, 12)]
    monkeypatch.setattr(beam, "extract_ratio_grid", lambda **kwargs: ())
    assert beam._extract_sample(**options, best_binning=True).points == ()
