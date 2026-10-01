"""Publication-style experimental Figure 4 layout."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

from graal_common.physics.beam_profiles import get_beam_profile
from observable_extraction.io.root_output import OutputPoint


PAIR_COLUMNS = (
    ("p_pi0", r"$p\pi^0$"),
    ("p_eta", r"$p\eta$"),
    ("eta_pi0", r"$\eta\pi^0$"),
)


@dataclass(frozen=True)
class PublishedPoint:
    pair: str
    energy_bin: int
    mass_gev: float
    sigma: float
    stat_low: float
    stat_high: float


@dataclass(frozen=True)
class EnergyRow:
    profile: str
    energy_bin: int
    low_gev: float
    high_gev: float


def profile_energy_rows(profile_name: str) -> tuple[EnergyRow, ...]:
    profile = get_beam_profile(profile_name)
    return tuple(
        EnergyRow(profile.name, index, low, high)
        for index, (low, high) in enumerate(
            zip(profile.energy_edges_gev[:-1], profile.energy_edges_gev[1:])
        )
    )


def combined_energy_rows() -> tuple[EnergyRow, ...]:
    return profile_energy_rows("vis") + profile_energy_rows("uv")


def load_published_points(path: Path) -> tuple[PublishedPoint, ...]:
    with Path(path).open(newline="", encoding="utf-8") as source:
        return tuple(
            PublishedPoint(
                pair=row["pair"],
                energy_bin=int(row["energy_bin"]),
                mass_gev=float(row["mass_gev"]),
                sigma=float(row["sigma"]),
                stat_low=float(row["stat_low"]),
                stat_high=float(row["stat_high"]),
            )
            for row in csv.DictReader(source)
        )


def _energy_label(row: EnergyRow) -> str:
    def format_edge(value: float) -> str:
        if abs(value - round(value, 2)) > 1e-12:
            return f"{value:.4f}"
        return f"{value:.2f}"

    return (
        "$\\Sigma$\n"
        + rf"${format_edge(row.low_gev)}\leq E_\gamma\leq "
        + rf"{format_edge(row.high_gev)}$ GeV"
    )


def build_profile_figure4(
    points_by_profile: Mapping[str, Sequence[OutputPoint]],
    rows: Sequence[EnergyRow],
    *,
    sample: str = "raw_bdt",
    estimator: str = "ratio",
):
    if not rows:
        raise ValueError("at least one energy row is required")
    figure, axes = plt.subplots(
        len(rows),
        3,
        figsize=(11.0, 2.8 * len(rows) + 0.8),
        sharey=True,
        constrained_layout=True,
        squeeze=False,
    )
    for row_index, row in enumerate(rows):
        profile_points = points_by_profile.get(row.profile, ())
        for column, (pair, title) in enumerate(PAIR_COLUMNS):
            axis = axes[row_index, column]
            selected = sorted(
                (
                    item
                    for item in profile_points
                    if item.sample == sample
                    and item.estimator == estimator
                    and item.point.pair == pair
                    and item.point.energy_bin == row.energy_bin
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
            if row_index == 0:
                axis.set_title(title)
            if column == 0:
                axis.set_ylabel(_energy_label(row))
            if row_index == len(rows) - 1:
                axis.set_xlabel(r"$M$ [GeV]")
    return figure, axes


def build_figure4(
    points: Sequence[OutputPoint],
    *,
    sample: str = "raw_bdt",
    estimator: str = "ratio",
):
    return build_profile_figure4(
        {"uv": points},
        profile_energy_rows("uv"),
        sample=sample,
        estimator=estimator,
    )


def build_profile_figure4_comparison(
    points_by_profile: Mapping[str, Sequence[OutputPoint]],
    published_points: Sequence[PublishedPoint],
    rows: Sequence[EnergyRow],
    *,
    sample: str = "raw_bdt",
    estimator: str = "ratio",
):
    figure, axes = build_profile_figure4(
        points_by_profile,
        rows,
        sample=sample,
        estimator=estimator,
    )
    for row_index, row in enumerate(rows):
        if row.profile != "uv":
            continue
        for column, (pair, _) in enumerate(PAIR_COLUMNS):
            selected = sorted(
                (
                    point
                    for point in published_points
                    if point.pair == pair and point.energy_bin == row.energy_bin
                ),
                key=lambda point: point.mass_gev,
            )
            if not selected:
                continue
            axes[row_index, column].errorbar(
                [point.mass_gev for point in selected],
                [point.sigma for point in selected],
                yerr=np.array(
                    [
                        [point.stat_low for point in selected],
                        [point.stat_high for point in selected],
                    ]
                ),
                fmt="D",
                color="#d62728",
                markerfacecolor="white",
                markeredgewidth=1.0,
                markersize=4.5,
                capsize=2,
                label="Ajaka et al. (2008)",
            )
    figure.legend(
        handles=(
            Line2D([], [], marker="o", color="black", linestyle="none"),
            Line2D(
                [],
                [],
                marker="D",
                color="#d62728",
                markerfacecolor="white",
                linestyle="none",
            ),
        ),
        labels=("Questa analisi", "Ajaka et al. (2008)"),
        loc="outside upper center",
        ncol=2,
    )
    return figure, axes


def build_figure4_comparison(
    points: Sequence[OutputPoint],
    published_points: Sequence[PublishedPoint],
    *,
    sample: str = "raw_bdt",
    estimator: str = "ratio",
):
    return build_profile_figure4_comparison(
        {"uv": points},
        published_points,
        profile_energy_rows("uv"),
        sample=sample,
        estimator=estimator,
    )


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


def write_profile_figure4_pdf(
    path: Path,
    points_by_profile: Mapping[str, Sequence[OutputPoint]],
    rows: Sequence[EnergyRow],
    *,
    sample: str = "raw_bdt",
    estimator: str = "ratio",
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure, _ = build_profile_figure4(
        points_by_profile,
        rows,
        sample=sample,
        estimator=estimator,
    )
    try:
        figure.savefig(path)
    finally:
        plt.close(figure)


def write_figure4_comparison_pdf(
    path: Path,
    points: Sequence[OutputPoint],
    published_points: Sequence[PublishedPoint],
    *,
    sample: str = "raw_bdt",
    estimator: str = "ratio",
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure, _ = build_figure4_comparison(
        points,
        published_points,
        sample=sample,
        estimator=estimator,
    )
    try:
        figure.savefig(path)
    finally:
        plt.close(figure)


def write_profile_figure4_comparison_pdf(
    path: Path,
    points_by_profile: Mapping[str, Sequence[OutputPoint]],
    published_points: Sequence[PublishedPoint],
    rows: Sequence[EnergyRow],
    *,
    sample: str = "raw_bdt",
    estimator: str = "ratio",
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure, _ = build_profile_figure4_comparison(
        points_by_profile,
        published_points,
        rows,
        sample=sample,
        estimator=estimator,
    )
    try:
        figure.savefig(path)
    finally:
        plt.close(figure)
