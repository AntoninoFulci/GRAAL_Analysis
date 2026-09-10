from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import numpy as np

from figure4_analysis import SigmaPoint
from figure4_plot import plot_sigma_grid


def point(center: float, sigma: float) -> SigmaPoint:
    return SigmaPoint(
        mass_low=center - 0.02,
        mass_high=center + 0.02,
        mass_center=center,
        sigma=sigma,
        stat_uncertainty=0.05,
        valid=True,
        reason=None,
        event_count=100.0,
        fit_deviance=8.0,
        fit_ndof=11,
    )


def test_plot_sigma_grid_writes_original_four_by_three_framework_figure(tmp_path):
    energy_ranges = [(1.1, 1.2), (1.2, 1.3), (1.3, 1.4), (1.4, 1.5)]
    pairs = ("p_pi0", "p_eta", "eta_pi0")
    results = {
        (row, pair): [point(0.8 + 0.1 * column, -0.2 + 0.1 * row)]
        for row in range(4)
        for column, pair in enumerate(pairs)
    }
    output = tmp_path / "framework_sigma_grid.png"
    figure = plot_sigma_grid(
        results,
        energy_ranges=energy_ranges,
        pair_order=pairs,
        output_path=output,
        analysis_label="GRAAL framework validation",
    )
    assert output.is_file()
    assert output.stat().st_size > 1000
    assert len(figure.axes) == 12
    assert [axis.get_title() for axis in figure.axes[:3]] == [
        r"$M(p\pi^0)$",
        r"$M(p\eta)$",
        r"$M(\eta\pi^0)$",
    ]


def test_plot_marks_invalid_bins_without_turning_them_into_sigma_points(tmp_path):
    invalid = SigmaPoint(
        0.7, 0.8, 0.75, np.nan, np.nan, False, "empty mass bin", 0.0, np.nan, 0
    )
    results = {(0, "p_pi0"): [invalid]}
    figure = plot_sigma_grid(
        results,
        energy_ranges=[(1.1, 1.2)],
        pair_order=("p_pi0",),
        output_path=tmp_path / "invalid.png",
        analysis_label="test",
    )
    assert len(figure.axes[0].lines) == 1  # zero reference line only
    assert len(figure.axes[0].collections) == 0
    assert figure.axes[0].get_xlim() == (0.7, 0.8)
