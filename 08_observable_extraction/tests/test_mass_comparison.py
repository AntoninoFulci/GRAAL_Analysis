from dataclasses import replace
import json

import numpy as np
import pytest

from observable_extraction.compare_gate import (
    _extract, bootstrap_comparison, selected_cutflow, write_comparison_root,
)
from observable_extraction.core.gate_comparison import align_points
from observable_extraction.core.models import FluxExposure
from observable_extraction.io.reconstructed_events import EventArrays


def sample():
    n = 1200
    phi = np.linspace(0, 2*np.pi, n, endpoint=False)
    vector = np.column_stack((.05*np.cos(phi), .05*np.sin(phi), np.zeros(n), np.ones(n)))
    eta, pi0 = vector.copy(), vector.copy()
    eta[:, 3], pi0[:, 3] = .6, .25
    return EventArrays(np.where(np.arange(n) < 600, 1, 2), np.ones(n, dtype=int),
                       np.where(np.arange(n) % 2, 1, 2), np.full(n, 1.2), eta, pi0, vector,
                       np.full(n, .938), np.full(n, .548), np.full(n, .135),
                       np.full(n, np.nan), np.full(n, 4))


def exposures():
    # Run 3 has exposure but no accepted events.
    return {(run, 1): FluxExposure(run, 1, 1.2, 1., 1., 0., .6, .6) for run in (1, 2, 3)}


def test_generic_comparison_keeps_labels_and_zero_delta_with_common_draws(tmp_path):
    events = sample()
    samples = dict(before=events, after=events)
    names = ("before", "after")
    edges = np.array([1.1, 1.3])
    fitted = _extract(samples, exposures(), edges)
    rows = align_points(fitted["before"], fitted["after"], edges, sample_names=names)
    common = [r for r in rows if r["status"] == "both_estimable"]
    assert len(common) == 6
    assert all(r["delta"] == 0 for r in common)
    assert all(r["before"]["point"] == r["after"]["point"] for r in common)
    diagnostics, _, _, draws = bootstrap_comparison(
        samples, exposures(), {1: "p", 2: "p", 3: "zero"},
        [r["key"] for r in common], edges, 3, 12, sample_names=names)
    assert diagnostics["zero_event_runs"] == {"before": (3,), "after": (3,)}
    assert all(3 in draw for draw in draws)
    np.testing.assert_allclose(diagnostics["difference_covariance"], np.zeros((6, 6)), atol=1e-18)
    path = tmp_path / "comparison.root"
    report = dict(sample_names=names, rows=rows, bootstrap=diagnostics)
    write_comparison_root(path, report)
    import ROOT
    source = ROOT.TFile.Open(str(path))
    try:
        tree = source.Get("comparison")
        assert tree.GetBranch("sigma_before")
        assert tree.GetBranch("sigma_after")
        assert not tree.GetBranch("sigma_bdt")
    finally:
        source.Close()


def test_generic_cutflow_keeps_flux_when_polygon_empties_run():
    before = sample()
    after = before.take(before.run_number != 2)
    rows = selected_cutflow(before, after, exposures(), {1: "p", 2: "p", 3: "p"},
                            [1.1, 1.3], sample_names=("before", "after"))
    emptied = [r for r in rows if r["run"] == 2]
    assert all(r["before"] == 300 and r["after"] == 0 and r["flux"] == 1 for r in emptied)


def polygon(vertices=None):
    from observable_extraction.core.mass_selection import MassPolygon
    return MassPolygon("synthetic-v1", "synthetic independent control", "include",
                       vertices or ((.4, .1), (.7, .1), (.7, .2), (.4, .2)))


def test_study_off_and_total_polygon_reproduce_nominal_and_zero_difference():
    from observable_extraction.compare_mass_selection import compare_mass_samples
    for region in (None, polygon()):
        report, arrays = compare_mass_samples(sample(), exposures(), {1: "p", 2: "p", 3: "p"},
                                              [1.1, 1.3], region, replicas=2, seed=12)
        assert report["selection"]["enabled"] is (region is not None)
        assert arrays["selected_mask"].all()
        assert report["event_counts"] == {"before": 1200, "after": 1200}
        common = [r for r in report["rows"] if r["status"] == "both_estimable"]
        assert len(common) == 6
        assert all(r["delta"] == 0 for r in common)
        assert report["exposure"]["vertical"] == 3
        np.testing.assert_allclose(report["bootstrap"]["difference_covariance"], 0, atol=1e-18)


def test_empty_polygon_preserves_universe_and_reports_unestimable_bins():
    from observable_extraction.compare_mass_selection import compare_mass_samples
    region = polygon(((.8, .3), (.9, .3), (.9, .4), (.8, .4)))
    report, arrays = compare_mass_samples(sample(), exposures(), {1: "p", 2: "p", 3: "p"},
                                          [1.1, 1.3], region, replicas=2, seed=12)
    assert not arrays["selected_mask"].any()
    assert report["event_counts"] == {"before": 1200, "after": 0}
    assert report["exposure"]["vertical"] == 3
    assert report["bootstrap"]["status"] == "no_common_estimable_bins"
    assert all(r["delta"] is None for r in report["rows"])
    assert sum(r["status"] == "before_only" for r in report["rows"]) == 6


def test_mass_study_cli_requires_explicit_file_to_enable_cut():
    from observable_extraction.compare_mass_selection import build_parser
    parser = build_parser()
    args = parser.parse_args(["plot", "--input", "input.root", "--profile", "uv", "--output-dir", "study"])
    assert args.mass_polygon is None
    assert args.sample == "raw_bdt"
    with pytest.raises(SystemExit):
        parser.parse_args(["compare", "--input", "input.root", "--profile", "uv", "--output-dir", "study"])


def test_mass_plot_roundtrip_keeps_raw_values_mask_and_exact_polygon(tmp_path):
    from observable_extraction.compare_mass_selection import write_mass_plot
    import ROOT
    events = replace(sample(), eta_mass_gev=np.r_[np.full(600, .548), np.full(600, .8)])
    region = polygon()
    mask = region.mask(events.eta_mass_gev, events.pi0_mass_gev)
    write_mass_plot(tmp_path, events, mask, region)
    source = ROOT.TFile.Open(str(tmp_path / "mass_selection.root"))
    try:
        assert source.Get("masse_2d_before").GetEntries() == 1200
        assert source.Get("masse_2d_after").GetEntries() == 600
        graph = source.Get("mass_polygon")
        assert graph.GetN() == 5
        assert graph.GetPointX(0) == .4
        assert graph.GetPointY(0) == .1
        assert json.loads(source.Get("mass_selection").GetTitle())["polygon"] == region.to_dict()
    finally:
        source.Close()
    assert (tmp_path / "mass_selection.png").stat().st_size > 1000


def plot_args(tmp_path, monkeypatch):
    from observable_extraction import compare_mass_selection as study
    source, region = tmp_path / "input.root", tmp_path / "polygon.json"
    source.touch()
    region.write_text(json.dumps(polygon().to_dict()))
    monkeypatch.setattr(study, "_read", lambda *_: (sample(), {
        "do_fit": False, "selection": {"energy_range_gev": [1.1, 1.5]}}))
    args = study.build_parser().parse_args([
        "plot", "--input", str(source), "--mass-polygon", str(region),
        "--profile", "uv", "--output-dir", str(tmp_path / "output")])
    return study, args


def test_polygon_is_read_after_initial_identity_snapshot(tmp_path, monkeypatch):
    study, args = plot_args(tmp_path, monkeypatch)
    real_identities = study.file_identities
    called = False

    def concurrent_edit(paths):
        nonlocal called
        if not called:
            called = True
            updated = polygon(((.8, .3), (.9, .3), (.9, .4), (.8, .4))).to_dict()
            args.mass_polygon.write_text(json.dumps(updated))
        return real_identities(paths)

    monkeypatch.setattr(study, "file_identities", concurrent_edit)
    report = study.run(args)
    assert report["event_counts"]["after"] == 0
    assert report["selection"]["polygon"]["vertices"][0] == [.8, .3]


def test_changes_during_plotting_abort_publication(tmp_path, monkeypatch):
    study, args = plot_args(tmp_path, monkeypatch)
    real_plot = study.write_mass_plot

    def concurrent_edit(*arguments):
        real_plot(*arguments)
        args.mass_polygon.write_text(args.mass_polygon.read_text() + "\n")

    monkeypatch.setattr(study, "write_mass_plot", concurrent_edit)
    with pytest.raises(RuntimeError, match="changed"):
        study.run(args)
    assert not args.output_dir.exists()
