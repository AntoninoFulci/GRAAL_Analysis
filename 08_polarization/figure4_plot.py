"""Original framework visualization compatible with a four-by-three comparison."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from contracts import PolarizationContractError
from figure4_analysis import SigmaPoint


PAIR_LABELS = {
    "p_pi0": r"$M(p\pi^0)$",
    "p_eta": r"$M(p\eta)$",
    "eta_pi0": r"$M(\eta\pi^0)$",
}


def plot_sigma_grid(
    results: Mapping[tuple[int, str], Sequence[SigmaPoint]],
    *,
    energy_ranges: Sequence[tuple[float, float]],
    pair_order: Sequence[str],
    output_path: Path,
    analysis_label: str,
):
    """Render framework Sigma points; never reads or overlays published values."""
    import matplotlib.pyplot as plt

    if not energy_ranges or not pair_order:
        raise PolarizationContractError("plot needs energy ranges and pair columns")
    if any(pair not in PAIR_LABELS for pair in pair_order):
        raise PolarizationContractError("plot contains unknown pair column")
    rows = len(energy_ranges)
    columns = len(pair_order)
    figure, axes = plt.subplots(
        rows,
        columns,
        figsize=(4.2 * columns, 2.7 * rows),
        squeeze=False,
        sharey=True,
        constrained_layout=True,
    )
    for row, energy_range in enumerate(energy_ranges):
        low, high = energy_range
        if not np.isfinite(low) or not np.isfinite(high) or high <= low:
            raise PolarizationContractError("plot energy range must have positive width")
        for column, pair in enumerate(pair_order):
            axis = axes[row, column]
            axis.axhline(0.0, color="0.55", linewidth=0.9, linestyle="--")
            points = results.get((row, pair), ())
            if points:
                axis.set_xlim(
                    min(point.mass_low for point in points),
                    max(point.mass_high for point in points),
                )
            valid = [point for point in points if point.valid]
            invalid = [point for point in points if not point.valid]
            if valid:
                axis.errorbar(
                    [point.mass_center for point in valid],
                    [point.sigma for point in valid],
                    yerr=[point.stat_uncertainty for point in valid],
                    fmt="o",
                    color="#2457A6",
                    ecolor="#2457A6",
                    markersize=4.5,
                    capsize=2.0,
                    linewidth=1.0,
                )
            if invalid:
                axis.scatter(
                    [point.mass_center for point in invalid],
                    [-0.94] * len(invalid),
                    marker="x",
                    color="#A33A2B",
                    s=24,
                    linewidths=1.2,
                    label="invalid fit",
                    zorder=3,
                )
            axis.set_ylim(-1.0, 1.0)
            axis.grid(axis="y", color="0.9", linewidth=0.6)
            axis.text(
                0.03,
                0.93,
                rf"${low:.1f}\leq E_\gamma<{high:.1f}$ GeV",
                transform=axis.transAxes,
                ha="left",
                va="top",
                fontsize=9,
            )
            if row == 0:
                axis.set_title(PAIR_LABELS[pair])
            if column == 0:
                axis.set_ylabel(r"Beam asymmetry $\Sigma$")
            if row == rows - 1:
                axis.set_xlabel("Invariant mass (GeV)")
    figure.suptitle(analysis_label)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(destination, dpi=180)
    return figure
