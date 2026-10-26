"""Diagnostics for the raw eta/pi0 core-versus-tail candle test."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np

from graal_common.physics.channels import M_ETA, M_PI0
from observable_extraction.io.root_output import OutputPoint
from observable_extraction.plotting.figure4 import EnergyRow


PAIR_ORDER = ("p_pi0", "p_eta", "eta_pi0")
PAIR_LABELS = {
    "p_pi0": r"$p\pi^0$",
    "p_eta": r"$p\eta$",
    "eta_pi0": r"$\eta\pi^0$",
}
ESTIMATOR_ORDER = ("ratio", "likelihood")


def _validated_width(half_width_gev: float) -> float:
    width = float(half_width_gev)
    if not np.isfinite(width) or width <= 0.0:
        raise ValueError("half_width_gev must be finite and positive")
    return width


def _save(path: Path, figure) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, format="pdf", bbox_inches="tight")
    plt.close(figure)


def build_candle_mass_plane(
    eta_mass_gev,
    pi0_mass_gev,
    *,
    half_width_gev: float,
    full_core_count: int,
    tail_count: int,
    balanced_core_count: int,
    excluded_nonfinite_count: int,
):
    """Build the full raw candidate-mass plane and candle rectangle."""
    eta_mass = np.asarray(eta_mass_gev, dtype=np.float64)
    pi0_mass = np.asarray(pi0_mass_gev, dtype=np.float64)
    if eta_mass.ndim != 1 or pi0_mass.ndim != 1:
        raise ValueError("mass arrays must be one-dimensional")
    if eta_mass.shape != pi0_mass.shape:
        raise ValueError("mass arrays must have the same length")
    if eta_mass.size == 0:
        raise ValueError("mass arrays must be non-empty")
    width = _validated_width(half_width_gev)
    raw_counts = (
        full_core_count,
        tail_count,
        balanced_core_count,
        excluded_nonfinite_count,
    )
    counts = tuple(int(value) for value in raw_counts)
    if any(value != raw or value < 0 for value, raw in zip(counts, raw_counts)):
        raise ValueError("candle counts must be non-negative integers")
    full_core, tails, balanced_core, excluded_nonfinite = counts
    if balanced_core != tails or balanced_core > full_core:
        raise ValueError("balanced core count must equal tails and fit in core")
    if full_core + tails + excluded_nonfinite != eta_mass.size:
        raise ValueError("candle counts do not match baseline")

    finite = np.isfinite(eta_mass) & np.isfinite(pi0_mass)
    if int(np.count_nonzero(~finite)) != excluded_nonfinite:
        raise ValueError("non-finite mass count does not match candle counts")
    figure, axis = plt.subplots(figsize=(7.2, 6.0), constrained_layout=True)
    histogram = axis.hist2d(
        eta_mass[finite], pi0_mass[finite], bins=80, cmap="viridis"
    )
    figure.colorbar(histogram[3], ax=axis, label="Eventi")
    axis.add_patch(Rectangle(
        (M_ETA - width, M_PI0 - width),
        2.0 * width,
        2.0 * width,
        fill=False,
        edgecolor="tab:red",
        linewidth=1.8,
        label="Candle window",
    ))
    axis.autoscale(enable=True, axis="both", tight=False)
    axis.text(
        0.02,
        0.98,
        f"Baseline: {eta_mass.size}\n"
        f"Core completo: {full_core}\n"
        f"Code: {tails}\n"
        f"Campioni bilanciati: {balanced_core} + {tails}\n"
        f"Masse non finite escluse: {excluded_nonfinite}",
        transform=axis.transAxes,
        va="top",
        ha="left",
        bbox={"facecolor": "white", "alpha": 0.85, "edgecolor": "0.7"},
    )
    axis.set_xlabel(r"Raw $M(\eta)$ [GeV]")
    axis.set_ylabel(r"Raw $M(\pi^0)$ [GeV]")
    axis.set_title(r"Post-BDT raw $\eta$/$\pi^0$ candidate masses")
    axis.legend(loc="upper right")
    return figure, axis


def write_candle_mass_plane_pdf(
    path: Path,
    eta_mass_gev,
    pi0_mass_gev,
    *,
    half_width_gev: float,
    full_core_count: int,
    tail_count: int,
    balanced_core_count: int,
    excluded_nonfinite_count: int,
) -> None:
    figure, _ = build_candle_mass_plane(
        eta_mass_gev,
        pi0_mass_gev,
        half_width_gev=half_width_gev,
        full_core_count=full_core_count,
        tail_count=tail_count,
        balanced_core_count=balanced_core_count,
        excluded_nonfinite_count=excluded_nonfinite_count,
    )
    _save(path, figure)


def _key(item: OutputPoint) -> tuple[str, int, int]:
    return item.point.pair, item.point.energy_bin, item.point.mass_bin


def _sample_map(
    points: Sequence[OutputPoint], *, sample: str, estimator: str
) -> dict[tuple[str, int, int], OutputPoint]:
    selected: dict[tuple[str, int, int], OutputPoint] = {}
    for item in points:
        if item.sample != sample or item.estimator != estimator:
            continue
        key = _key(item)
        if key in selected:
            raise ValueError(f"duplicate {sample} {estimator} point for {key}")
        selected[key] = item
    return selected


def available_candle_estimators(
    points_by_profile: Mapping[str, Sequence[OutputPoint]],
) -> tuple[str, ...]:
    """Return estimators with both candle samples in at least one profile."""
    available = []
    for estimator in ESTIMATOR_ORDER:
        for points in points_by_profile.values():
            samples = {
                item.sample for item in points if item.estimator == estimator
            }
            if {"raw_bdt_core", "raw_bdt_tails"} <= samples:
                available.append(estimator)
                break
    return tuple(available)


def _plot_points(axis, points: Sequence[OutputPoint], *, sample: str) -> None:
    if not points:
        return
    marker, color, label = {
        "raw_bdt_core": ("o", "tab:blue", "Core"),
        "raw_bdt_tails": ("s", "tab:orange", "Code"),
    }[sample]
    axis.errorbar(
        [0.5 * (item.point.mass_low_gev + item.point.mass_high_gev) for item in points],
        [item.point.sigma for item in points],
        yerr=np.array([
            [item.point.stat_low for item in points],
            [item.point.stat_high for item in points],
        ]),
        fmt=marker,
        color=color,
        capsize=2,
        linestyle="none",
        label=label,
    )


def build_candle_comparison(
    points_by_profile: Mapping[str, Sequence[OutputPoint]],
    rows: Sequence[EnergyRow],
    *,
    estimator: str,
):
    """Compare disjoint equal-count core and tail points on the physical grid."""
    if estimator not in {"ratio", "likelihood"}:
        raise ValueError(f"unknown estimator: {estimator}")
    if not rows:
        raise ValueError("at least one energy row is required")

    sample_maps = {}
    paired_profile = False
    for profile, points in points_by_profile.items():
        core = _sample_map(points, sample="raw_bdt_core", estimator=estimator)
        tails = _sample_map(points, sample="raw_bdt_tails", estimator=estimator)
        sample_maps[profile] = (core, tails)
        paired_profile = paired_profile or bool(core and tails)
    if not paired_profile:
        raise ValueError(
            f"core and tails {estimator} samples must both contain points"
        )

    figure, axes = plt.subplots(
        len(rows), 3,
        figsize=(11.0, 2.8 * len(rows) + 0.8),
        sharey=True,
        constrained_layout=True,
        squeeze=False,
    )
    for row_index, row in enumerate(rows):
        core_map, tail_map = sample_maps.get(row.profile, ({}, {}))
        for column, pair in enumerate(PAIR_ORDER):
            axis = axes[row_index, column]
            core = sorted(
                (item for key, item in core_map.items()
                 if key[0] == pair and key[1] == row.energy_bin),
                key=lambda item: item.point.mass_bin,
            )
            tails = sorted(
                (item for key, item in tail_map.items()
                 if key[0] == pair and key[1] == row.energy_bin),
                key=lambda item: item.point.mass_bin,
            )
            _plot_points(axis, core, sample="raw_bdt_core")
            _plot_points(axis, tails, sample="raw_bdt_tails")
            axis.axhline(0.0, color="0.65", linewidth=0.8)
            axis.set_ylim(-1.0, 1.0)
            axis.grid(alpha=0.2)
            if row_index == 0:
                axis.set_title(PAIR_LABELS[pair])
            if column == 0:
                axis.set_ylabel(
                    "$\\Sigma$\n"
                    f"{row.profile.upper()} {row.low_gev:.4g}–{row.high_gev:.4g} GeV"
                )
            if row_index == len(rows) - 1:
                axis.set_xlabel(r"$M$ [GeV]")

    handles_by_label = {}
    for axis in axes.flat:
        handles, labels = axis.get_legend_handles_labels()
        for handle, label in zip(handles, labels):
            handles_by_label.setdefault(label, handle)
    ordered_labels = [
        label for label in ("Core", "Code") if label in handles_by_label
    ]
    if ordered_labels:
        figure.legend(
            [handles_by_label[label] for label in ordered_labels],
            ordered_labels,
            loc="outside upper center",
            ncol=2,
        )
    return figure, axes


def write_candle_comparison_pdf(
    path: Path,
    points_by_profile: Mapping[str, Sequence[OutputPoint]],
    rows: Sequence[EnergyRow],
    *,
    estimator: str,
) -> None:
    figure, _ = build_candle_comparison(
        points_by_profile, rows, estimator=estimator
    )
    _save(path, figure)
