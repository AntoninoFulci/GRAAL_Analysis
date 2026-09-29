import numpy as np

from observable_extraction.core.models import FitDiagnostics, SigmaPoint
from observable_extraction.io.root_output import OutputPoint
from observable_extraction.plotting.figure4 import build_figure4, write_figure4_pdf


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
