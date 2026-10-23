from dataclasses import replace

import numpy as np
import pytest
import matplotlib.pyplot as plt

from observable_extraction.tests.test_figure4 import _points
from observable_extraction.plotting.diagnostics import (
    build_profile_estimator_comparison,
    build_profile_fit_diagnostics,
    write_fit_diagnostics_pdf,
    write_false_asymmetry_controls_pdf,
    write_photon_multiplicity_pdf,
    write_point_comparison_pdf,
    write_systematic_summary_pdf,
)
from observable_extraction.plotting.figure4 import (
    combined_energy_rows,
    profile_energy_rows,
)


def test_diagnostic_writers_create_pdf_artifacts(tmp_path):
    comparison = tmp_path / "comparison.pdf"
    fits = tmp_path / "fits.pdf"
    systematics = tmp_path / "systematics.pdf"
    controls = tmp_path / "controls.pdf"
    multiplicity = tmp_path / "multiplicity.pdf"

    write_point_comparison_pdf(comparison, _points(), group_by="estimator")
    write_fit_diagnostics_pdf(fits, _points())
    write_systematic_summary_pdf(
        systematics,
        {"polarization_scale_3pct": np.eye(len(_points())) * 0.01},
    )
    write_false_asymmetry_controls_pdf(
        controls,
        {"p_pi0": np.linspace(0.0, 2.0 * np.pi, 20, endpoint=False)},
    )
    write_photon_multiplicity_pdf(
        multiplicity,
        inclusive_count=100,
        exactly_four_count=80,
        shifts=np.array([0.01, -0.02]),
        best_quartet_resolved=False,
    )

    for path in (comparison, fits, systematics, controls, multiplicity):
        assert path.read_bytes().startswith(b"%PDF")


def test_estimator_comparison_uses_five_by_three_physical_grid():
    uv_points = _points()
    vis_ratio = replace(
        uv_points[0],
        point=replace(
            uv_points[0].point,
            energy_bin=0,
            energy_low_gev=0.9313,
            energy_high_gev=1.10,
        ),
    )
    vis_likelihood = replace(vis_ratio, estimator="likelihood")

    figure, axes = build_profile_estimator_comparison(
        {"vis": (vis_ratio, vis_likelihood), "uv": uv_points},
        combined_energy_rows(),
    )

    assert axes.shape == (5, 3)
    assert len(axes[0, 0].containers) == 2
    assert '\\n' not in axes[0, 0].get_ylabel()
    assert '\n' in axes[0, 0].get_ylabel()
    figure.clf()


def test_fit_diagnostics_use_ratio_only_and_leave_empty_panels_blank():
    ratio = _points()[0]
    ratio = replace(
        ratio,
        point=replace(
            ratio.point,
            energy_low_gev=0.9313,
            energy_high_gev=1.10,
        ),
    )
    likelihood = replace(
        ratio,
        estimator="likelihood",
        point=replace(
            ratio.point,
            diagnostics=replace(
                ratio.point.diagnostics,
                chi2=0.0,
                ndf=0,
                p_value=1.0,
            ),
        ),
    )

    figure, axes = build_profile_fit_diagnostics(
        {"vis": (ratio, likelihood)},
        profile_energy_rows("vis"),
    )

    assert axes.shape == (1, 3)
    assert axes[0, 0].lines[0].get_xdata().tolist() == [0.75]
    assert [text.get_text() for text in axes[0, 1].texts] == ["No fit"]
    figure.clf()


@pytest.mark.parametrize('kind', ['sample', 'systematics', 'controls', 'periods'])
def test_diagnostic_titles_and_legends_have_separate_space(monkeypatch, tmp_path, kind):
    from observable_extraction.plotting import diagnostics
    captured = []
    monkeypatch.setattr(diagnostics, '_save', lambda path, figure: captured.append(figure))
    path = tmp_path / 'layout.pdf'
    if kind == 'sample':
        # Last panel is empty; both samples must still appear in the legend.
        points = [_points()[0], replace(_points()[0], sample='raw')]
        diagnostics.write_point_comparison_pdf(path, points, group_by='sample')
    elif kind == 'systematics':
        diagnostics.write_systematic_summary_pdf(path, {
            'estimator_ratio_vs_likelihood': np.eye(3),
            'polarization_scale_3pct': np.eye(3) * .1})
    elif kind == 'controls':
        diagnostics.write_false_asymmetry_controls_pdf(path, {'p_pi0': np.array([.1, .5])})
    else:
        diagnostics.write_period_stability_pdf(
            path, {f'2000_uv{index}': _points() for index in range(8)},
            profile_energy_rows('uv')[:1], sample='raw_bdt', estimator='ratio')
    figure = captured[0]
    try:
        figure.canvas.draw()
        renderer = figure.canvas.get_renderer()
        for legend in figure.legends:
            bounds = legend.get_window_extent(renderer)
            assert all(not bounds.overlaps(axis.get_tightbbox(renderer)) for axis in figure.axes)
            if figure._suptitle:
                assert not bounds.overlaps(figure._suptitle.get_window_extent(renderer))
        if figure._suptitle:
            bounds = figure._suptitle.get_window_extent(renderer)
            assert all(not bounds.overlaps(axis.title.get_window_extent(renderer)) for axis in figure.axes)
        if kind == 'sample':
            assert {text.get_text() for text in figure.legends[0].get_texts()} == {'raw', 'raw_bdt'}
    finally:
        plt.close(figure)
