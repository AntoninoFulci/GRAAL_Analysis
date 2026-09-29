"""Publication-style experimental Figure 4 layout."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from observable_extraction.io.root_output import OutputPoint


PAIR_COLUMNS = (
    ("p_pi0", r"$p\pi^0$"),
    ("p_eta", r"$p\eta$"),
    ("eta_pi0", r"$\eta\pi^0$"),
)


def build_figure4(
    points: Sequence[OutputPoint],
    *,
    sample: str = "raw_bdt",
    estimator: str = "ratio",
):
    figure, axes = plt.subplots(
        4,
        3,
        figsize=(11.0, 12.0),
        sharey=True,
        constrained_layout=True,
    )
    for row in range(4):
        for column, (pair, title) in enumerate(PAIR_COLUMNS):
            axis = axes[row, column]
            selected = sorted(
                (
                    item
                    for item in points
                    if item.sample == sample
                    and item.estimator == estimator
                    and item.point.pair == pair
                    and item.point.energy_bin == row
                ),
                key=lambda item: item.point.mass_bin,
            )
            if selected:
                x = np.array(
                    [
                        0.5 * (item.point.mass_low_gev + item.point.mass_high_gev)
                        for item in selected
                    ]
                )
                y = np.array([item.point.sigma for item in selected])
                yerr = np.array(
                    [
                        [item.point.stat_low for item in selected],
                        [item.point.stat_high for item in selected],
                    ]
                )
                markers = [
                    "s" if item.point.diagnostics.used_fallback else "o"
                    for item in selected
                ]
                for index, marker in enumerate(markers):
                    axis.errorbar(
                        x[index],
                        y[index],
                        yerr=yerr[:, index:index + 1],
                        fmt=marker,
                        color="black",
                        capsize=2,
                    )
            axis.axhline(0.0, color="0.75", linewidth=0.8)
            axis.set_ylim(-1.0, 1.0)
            axis.grid(alpha=0.15)
            if row == 0:
                axis.set_title(title)
            if column == 0:
                low = 1.1 + 0.1 * row
                high = low + 0.1
                axis.set_ylabel(
                    "$\\Sigma$\n"
                    + rf"${low:.1f}\leq E_\gamma\leq {high:.1f}$ GeV"
                )
            if row == 3:
                axis.set_xlabel(r"$M$ [GeV]")
    return figure, axes


def write_figure4_pdf(
    path: Path,
    points: Sequence[OutputPoint],
    *,
    sample: str = "raw_bdt",
    estimator: str = "ratio",
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure, _ = build_figure4(points, sample=sample, estimator=estimator)
    try:
        figure.savefig(path)
    finally:
        plt.close(figure)
