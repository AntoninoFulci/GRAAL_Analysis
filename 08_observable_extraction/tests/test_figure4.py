from dataclasses import replace

import numpy as np
import pytest
import matplotlib.pyplot as plt

from observable_extraction.core.models import FitDiagnostics, SigmaPoint
from observable_extraction.io.root_output import OutputPoint
from observable_extraction.plotting.figure4 import (
    PublishedPoint,
    build_figure4,
    build_figure4_comparison,
    build_profile_figure4,
    build_profile_figure4_comparison,
    combined_energy_rows,
    load_published_points,
    profile_energy_rows,
    write_figure4_comparison_pdf,
    write_figure4_pdf,
)


def _points():
    diagnostics = FitDiagnostics(True, 4.0, 8, 0.85, False)
    points = []
    for pair in ("p_pi0", "p_eta", "eta_pi0"):
        for energy_bin in range(4):
            points.append(
                OutputPoint(
                    sample="raw_bdt",
                    estimator="ratio",
                    point=SigmaPoint(
                        pair=pair,
                        energy_bin=energy_bin,
                        mass_bin=0,
                        energy_low_gev=1.1 + 0.1 * energy_bin,
                        energy_high_gev=1.2 + 0.1 * energy_bin,
                        mass_low_gev=0.7,
                        mass_high_gev=0.8,
                        mass_mean_gev=0.75,
                        sigma=0.1 * (energy_bin - 1),
                        stat_low=0.05,
                        stat_high=0.06,
                        diagnostics=diagnostics,
                    ),
                    sigma_uncorrected=0.1,
                    systematic_total=0.03,
                    background_fraction=0.1,
                    count_vertical=100,
                    count_horizontal=90,
                    flux_vertical=1000.0,
                    flux_horizontal=900.0,
                    polarization_vertical=0.6,
                    polarization_horizontal=0.58,
                )
            )
    return tuple(points)


def test_figure4_layout_has_four_energy_rows_and_three_pair_columns():
    figure, axes = build_figure4(_points())

    assert axes.shape == (4, 3)
    assert len(figure.axes) == 12
    assert [axes[0, column].get_title() for column in range(3)] == [
        r"$p\pi^0$", r"$p\eta$", r"$\eta\pi^0$"
    ]
    assert all(axis.get_ylim() == (-1.0, 1.0) for axis in axes.flat)
    assert "\\n" not in axes[0, 0].get_ylabel()
    assert "\n" in axes[0, 0].get_ylabel()
    assert not any(
        line.get_label() == "theory"
        for axis in axes.flat
        for line in axis.lines
    )
    figure.clf()


def test_figure4_writer_creates_pdf(tmp_path):
    output = tmp_path / "figure4_experimental.pdf"

    write_figure4_pdf(output, _points())

    assert output.read_bytes().startswith(b"%PDF")


def test_combined_rows_put_vis_before_four_uv_bins():
    rows = combined_energy_rows()

    assert [(row.profile, row.energy_bin) for row in rows] == [
        ("vis", 0),
        ("uv", 0),
        ("uv", 1),
        ("uv", 2),
        ("uv", 3),
    ]


def test_profile_figure_has_five_rows_and_uses_geometric_mass_centers():
    uv_points = _points()
    vis_point = replace(
        uv_points[0],
        point=replace(
            uv_points[0].point,
            energy_bin=0,
            energy_low_gev=0.9313,
            energy_high_gev=1.10,
            mass_low_gev=0.70,
            mass_high_gev=0.80,
            mass_mean_gev=0.79,
        ),
    )

    figure, axes = build_profile_figure4(
        {"vis": (vis_point,), "uv": uv_points},
        combined_energy_rows(),
    )

    assert axes.shape == (5, 3)
    assert axes[0, 0].get_ylabel().endswith(
        r"$0.9313\leq E_\gamma\leq 1.10$ GeV"
    )
    plotted_x = axes[0, 0].containers[0].lines[0].get_xdata()
    assert plotted_x.tolist() == [0.75]
    figure.clf()


def test_published_points_loader_preserves_panel_and_asymmetric_errors(tmp_path):
    source = tmp_path / "ajaka2008.csv"
    source.write_text(
        "pair,energy_bin,mass_gev,sigma,stat_low,stat_high\n"
        "p_eta,2,1.61,-0.42,0.07,0.09\n",
        encoding="utf-8",
    )

    points = load_published_points(source)

    assert len(points) == 1
    assert points[0].pair == "p_eta"
    assert points[0].energy_bin == 2
    assert points[0].mass_gev == 1.61
    assert points[0].sigma == -0.42
    assert points[0].stat_low == 0.07
    assert points[0].stat_high == 0.09


def test_figure4_comparison_places_published_point_in_matching_panel():
    published = (
        PublishedPoint(
            pair="p_eta",
            energy_bin=2,
            mass_gev=1.61,
            sigma=-0.42,
            stat_low=0.07,
            stat_high=0.09,
        ),
    )

    figure, axes = build_figure4_comparison(_points(), published)

    assert len(axes[2, 1].containers) == 2
    assert all(
        len(axis.containers) == 1
        for row, columns in enumerate(axes)
        for column, axis in enumerate(columns)
        if (row, column) != (2, 1)
    )
    assert [text.get_text() for text in figure.legends[0].get_texts()] == [
        "Questa analisi",
        "Ajaka et al. (2008)",
    ]
    figure.clf()


def test_combined_comparison_routes_ajaka_uv_bin_zero_to_second_row():
    uv_points = _points()
    vis_point = replace(
        uv_points[4],
        point=replace(
            uv_points[4].point,
            energy_bin=0,
            energy_low_gev=0.9313,
            energy_high_gev=1.10,
        ),
    )
    published = (
        PublishedPoint("p_eta", 0, 1.55, -0.4, 0.08, 0.08),
    )

    figure, axes = build_profile_figure4_comparison(
        {"vis": (vis_point,), "uv": uv_points},
        published,
        combined_energy_rows(),
    )

    assert len(axes[0, 1].containers) == 1
    assert len(axes[1, 1].containers) == 2
    figure.clf()


def test_figure4_comparison_writer_creates_separate_pdf(tmp_path):
    output = tmp_path / "figure4_comparison_ajaka2008.pdf"
    published = (
        PublishedPoint("eta_pi0", 0, 0.75, -0.30, 0.08, 0.10),
    )

    write_figure4_comparison_pdf(output, _points(), published)

    assert output.read_bytes().startswith(b"%PDF")


def test_figure4_comparison_legend_does_not_cover_column_titles():
    published = (
        PublishedPoint("p_eta", 0, 1.55, -0.4, 0.08, 0.08),
    )
    figure, axes = build_figure4_comparison(_points(), published)
    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    legend_bounds = figure.legends[0].get_window_extent(renderer)

    assert all(
        not legend_bounds.overlaps(axis.title.get_window_extent(renderer))
        for axis in axes[0]
    )
    figure.clf()


def test_figure4_separates_asymmetric_bars_from_systematic_band():
    item = replace(_points()[0], systematic_total=.23, background_fraction=0.,
                   point=replace(_points()[0].point, sigma=.2, stat_low=.03, stat_high=.07))
    figure, axes = build_figure4([item])
    axis = axes[0, 0]
    segment = axis.containers[0].lines[2][0].get_segments()[0]
    np.testing.assert_allclose(segment[:, 1], [.17, .27])
    assert len(axis.patches) == 1
    np.testing.assert_allclose(axis.patches[0].get_y(), -.03)
    np.testing.assert_allclose(axis.patches[0].get_height(), .46)
    assert 'conditional statistical' in figure._suptitle.get_text()
    figure.clf()
    corrected = replace(item, uncertainty_kind='background_propagated_unclassified')
    figure, _ = build_figure4([corrected])
    assert 'classification pending' in figure._suptitle.get_text()
    figure.clf()


def test_best_binning_shapes_preserve_points_errors_and_fallback_status():
    base = _points()[0]
    points = [replace(base, phi_bins=count, point=replace(
        base.point, mass_bin=index, mass_low_gev=.7 + index * .1,
        mass_high_gev=.8 + index * .1, mass_mean_gev=.75 + index * .1,
        diagnostics=replace(base.point.diagnostics, used_fallback=index == 1)))
        for index, count in enumerate((8, 12, 16))]
    figure, axes = build_profile_figure4({'uv': points}, profile_energy_rows('uv')[:1])
    try:
        containers = axes[0, 0].containers
        assert [item.lines[0].get_marker() for item in containers] == ['o', 's', '^']
        assert [item.lines[0].get_markerfacecolor() for item in containers] == ['black', 'none', 'black']
        for index, container in enumerate(containers):
            np.testing.assert_allclose(container.lines[0].get_xdata(orig=False), [.75 + index * .1])
            np.testing.assert_allclose(container.lines[2][0].get_segments()[0][:, 1],
                                       [base.point.sigma - .05, base.point.sigma + .06])
        assert [text.get_text() for text in figure.legends[0].get_texts()] == [
            'Questa analisi: 8 bin φ', 'Questa analisi: 12 bin φ',
            'Questa analisi: 16 bin φ', 'Fit fallback (simbolo vuoto)']
    finally:
        plt.close(figure)


@pytest.mark.parametrize('rows', [
    profile_energy_rows('uv')[:1],
    combined_energy_rows(),
    profile_energy_rows('vis', [.9313, 1.01565, 1.1])
    + profile_energy_rows('uv', np.linspace(1.1, 1.5, 9)),
])
def test_binning_and_reference_share_one_legend_clear_of_titles_and_axes(rows):
    points = tuple(replace(item, phi_bins=(8, 12, 16)[index % 3],
                           point=replace(item.point, diagnostics=replace(
                               item.point.diagnostics, used_fallback=True)))
                   for index, item in enumerate(_points()))
    figure, axes = build_profile_figure4_comparison(
        {'uv': points, 'vis': points}, [PublishedPoint('p_pi0', 0, .75, .1, .1, .1)], rows)
    try:
        figure.canvas.draw()
        renderer = figure.canvas.get_renderer()
        assert len(figure.legends) == 1
        legend = figure.legends[0]
        bounds = legend.get_window_extent(renderer)
        assert figure.bbox.contains(bounds.x0, bounds.y0)
        assert figure.bbox.contains(bounds.x1, bounds.y1)
        assert not bounds.overlaps(figure._suptitle.get_window_extent(renderer))
        assert all(not bounds.overlaps(axis.get_tightbbox(renderer)) for axis in axes.flat)
        has_reference = any(row.profile == 'uv' and row.low_gev == 1.1
                            and row.high_gev == 1.2 for row in rows)
        assert ('Ajaka et al. (2008)' in [text.get_text() for text in legend.get_texts()]) == has_reference
    finally:
        plt.close(figure)


@pytest.mark.parametrize('vis_low,expected_rows', [(0.930, 5), (0.9313, 6)])
def test_overlay_matches_intervals_preserves_errors_and_shifts_ajaka(vis_low, expected_rows):
    base = _points()[0]
    uv_rows = profile_energy_rows('uv', [0.930, 1.100, 1.200, 1.300, 1.400, 1.500])
    uv = tuple(replace(base, phi_bins=12, point=replace(
        base.point, energy_bin=row.energy_bin, energy_low_gev=row.low_gev,
        energy_high_gev=row.high_gev)) for row in uv_rows)
    vis = replace(base, phi_bins=12, point=replace(
        base.point, energy_bin=0, energy_low_gev=vis_low, energy_high_gev=1.1,
        sigma=.3, stat_low=.02, stat_high=.08,
        diagnostics=replace(base.point.diagnostics, used_fallback=True)))
    published = [PublishedPoint('p_pi0', 0, .76, -.4, .07, .09)]
    figure, axes = build_profile_figure4_comparison(
        {'uv': uv, 'vis': [vis]}, published,
        profile_energy_rows('vis', [vis_low, 1.1]) + uv_rows,
        overlay_profiles=True)
    try:
        assert axes.shape == (expected_rows, 3)
        low_axis = axes[0 if vis_low == .930 else 1, 0]
        assert len(axes[0, 0].containers) == (2 if vis_low == .930 else 1)
        vis_plot = low_axis.containers[-1]
        assert vis_plot.lines[0].get_color() == 'tab:blue'
        assert vis_plot.lines[0].get_markerfacecolor() == 'none'
        np.testing.assert_allclose(vis_plot.lines[0].get_xdata(orig=False), [.75])
        np.testing.assert_allclose(vis_plot.lines[2][0].get_segments()[0][:, 1], [.28, .38])
        assert len(low_axis.patches) == (2 if vis_low == .930 else 1)
        assert 'nessun dato' in low_axis.texts[0].get_text()
        # Ajaka bin 0 belongs to 1.1–1.2, never the new UV bin 0.
        ajaka_axis = axes[1 if vis_low == .930 else 2, 0]
        assert len(ajaka_axis.containers) == 2
        np.testing.assert_allclose(ajaka_axis.containers[-1].lines[0].get_ydata(orig=False), [-.4])
        labels = [text.get_text() for text in figure.legends[0].get_texts()]
        assert 'UV: 12 bin φ' in labels and 'VIS: 12 bin φ' in labels
        assert 'Ajaka et al. (2008)' in labels
        figure.canvas.draw()
        renderer = figure.canvas.get_renderer()
        bounds = figure.legends[0].get_window_extent(renderer)
        assert all(not bounds.overlaps(axis.get_tightbbox(renderer)) for axis in axes.flat)
    finally:
        plt.close(figure)
