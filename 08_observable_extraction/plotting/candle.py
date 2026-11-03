"""Diagnostics for the raw eta/pi0 core-versus-tail candle test."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse, Rectangle
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
    gaussian_model=None,
):
    """Build the full raw mass plane with the selected rectangle or ellipse."""
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
    if gaussian_model is None and (balanced_core != tails or balanced_core > full_core):
        raise ValueError("balanced core count must equal tails and fit in core")
    if gaussian_model is not None and balanced_core != full_core:
        raise ValueError("Gaussian candle must retain every core event")
    if full_core + tails + excluded_nonfinite != eta_mass.size:
        raise ValueError("candle counts do not match baseline")

    finite = np.isfinite(eta_mass) & np.isfinite(pi0_mass)
    if int(np.count_nonzero(~finite)) != excluded_nonfinite:
        raise ValueError("non-finite mass count does not match candle counts")
    figure, axis = plt.subplots(figsize=(7.2, 6.0), constrained_layout=True)
    histogram = axis.hist2d(
        eta_mass[finite], pi0_mass[finite], bins=80, cmap="viridis", rasterized=True
    )
    figure.colorbar(histogram[3], ax=axis, label="Eventi")
    if gaussian_model is None:
        contour = Rectangle((M_ETA - width, M_PI0 - width), 2.0 * width, 2.0 * width,
                            fill=False, edgecolor='tab:red', linewidth=1.8, label='Candle window')
        annotation = (f"Baseline: {eta_mass.size}\nCore completo: {full_core}\nCode: {tails}\n"
                      f"Campioni bilanciati: {balanced_core} + {tails}\n"
                      f"Masse non finite escluse: {excluded_nonfinite}")
    else:
        eigenvalues, eigenvectors = np.linalg.eigh(gaussian_model.covariance_gev2)
        major = eigenvectors[:, -1]
        diameters = 2. * np.sqrt(gaussian_model.radius_squared * eigenvalues)
        contour = Ellipse((gaussian_model.eta_center_gev, gaussian_model.pi0_center_gev),
                          diameters[-1], diameters[0], angle=np.degrees(np.arctan2(major[1], major[0])),
                          fill=False, edgecolor='tab:red', linewidth=1.8, label='Gaussian 50% contour')
        observed = full_core / (full_core + tails) if full_core + tails else 0.
        annotation = (f"Full: {eta_mass.size}\nCore: {full_core}\nTails: {tails}\n"
                      f"Gaussian probability: 50%\nMeasured core / finite: {observed:.2%}\n"
                      f"Nonfinite masses excluded: {excluded_nonfinite}")
    axis.add_patch(contour)
    axis.autoscale(enable=True, axis="both", tight=False)
    axis.text(
        0.02,
        0.98,
        annotation,
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
    gaussian_model=None,
) -> None:
    figure, _ = build_candle_mass_plane(
        eta_mass_gev,
        pi0_mass_gev,
        half_width_gev=half_width_gev,
        full_core_count=full_core_count,
        tail_count=tail_count,
        balanced_core_count=balanced_core_count,
        excluded_nonfinite_count=excluded_nonfinite_count,
        gaussian_model=gaussian_model,
    )
    _save(path, figure)


def _key(item: OutputPoint) -> tuple[str, int, int]:
    return item.point.pair, item.point.energy_bin, item.point.mass_bin


def _gaussian_projection_counts(model):
    """Integrate the stored joint fit on its own grid; never perform a new fit."""
    audit = model.to_dict()['fit']
    if audit is None:
        raise ValueError('Gaussian projection plots require a fitted model audit')
    bins, order = audit['bins_per_axis'], audit['quadrature_order']
    edges = [np.linspace(*window, bins + 1) for window in audit['fit_window_gev']]
    nodes, weights = np.polynomial.legendre.leggauss(order)
    points = [(edge[:-1, None] + edge[1:, None]) / 2 + np.diff(edge)[:, None] * nodes / 2
              for edge in edges]
    dx = points[0][:, None, :, None] - model.eta_center_gev
    dy = points[1][None, :, None, :] - model.pi0_center_gev
    precision = np.linalg.inv(model.covariance_gev2)
    exponent = precision[0, 0] * dx**2 + 2 * precision[0, 1] * dx * dy + precision[1, 1] * dy**2
    integrated = np.sum(np.exp(-.5 * exponent) * weights[:, None] * weights[None, :], axis=(-2, -1))
    signal = integrated / integrated.sum() * audit['parameters'][5]
    pedestal = np.full((bins, bins), audit['parameters'][6] / bins**2)
    return edges, signal, pedestal


def write_candle_gaussian_projections_pdf(path: Path, eta_mass_gev, pi0_mass_gev, *, gaussian_model) -> None:
    """Raw mass projections and stored Gaussian+pedestal fit in its joint window.

    The window applies only to these fit diagnostics, never to the samples used
    for physical quality controls or asymmetry extraction.
    """
    eta, pi0 = np.asarray(eta_mass_gev, dtype=float), np.asarray(pi0_mass_gev, dtype=float)
    if eta.ndim != 1 or eta.shape != pi0.shape:
        raise ValueError('raw mass arrays must have the same one-dimensional shape')
    edges, signal, pedestal = _gaussian_projection_counts(gaussian_model)
    in_window = (np.isfinite(eta) & np.isfinite(pi0)
                 & (eta >= edges[0][0]) & (eta <= edges[0][-1])
                 & (pi0 >= edges[1][0]) & (pi0 <= edges[1][-1]))
    observed = np.histogram2d(eta[in_window], pi0[in_window], bins=edges)[0]
    figure, axes = plt.subplots(1, 2, figsize=(11., 4.6), constrained_layout=True)
    for index, (axis, label) in enumerate(zip(axes, (r'Raw $M(\eta)$ [GeV]', r'Raw $M(\pi^0)$ [GeV]'))):
        summed_axis = 1 - index
        axis.stairs(observed.sum(axis=summed_axis), edges[index], color='black', label='Observed in joint fit window')
        axis.stairs((signal + pedestal).sum(axis=summed_axis), edges[index], color='tab:red', label='Stored Gaussian + pedestal fit')
        axis.stairs(signal.sum(axis=summed_axis), edges[index], color='tab:blue', linestyle='--', label='Gaussian component')
        axis.stairs(pedestal.sum(axis=summed_axis), edges[index], color='tab:orange', linestyle=':', label='Constant pedestal')
        axis.set(xlabel=label, ylabel='Events / bin')
        axis.legend(fontsize=8)
        axis.grid(alpha=.2)
    figure.suptitle(f'Joint mass-fit projections: {int(in_window.sum())} / {eta.size} input events in declared fit window')
    _save(path, figure)


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
        "raw_bdt": ("D", "black", "Full"),
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
    """Compare full/core/tail points, retaining independently unmatched bins."""
    if estimator not in {"ratio", "likelihood"}:
        raise ValueError(f"unknown estimator: {estimator}")
    if not rows:
        raise ValueError("at least one energy row is required")

    sample_maps = {}
    paired_profile = False
    for profile, points in points_by_profile.items():
        core = _sample_map(points, sample="raw_bdt_core", estimator=estimator)
        tails = _sample_map(points, sample="raw_bdt_tails", estimator=estimator)
        full = _sample_map(points, sample="raw_bdt", estimator=estimator)
        sample_maps[profile] = (core, tails, full)
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
        core_map, tail_map, full_map = sample_maps.get(row.profile, ({}, {}, {}))
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
            full = sorted(
                (item for key, item in full_map.items()
                 if key[0] == pair and key[1] == row.energy_bin),
                key=lambda item: item.point.mass_bin,
            )
            _plot_points(axis, full, sample="raw_bdt")
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
        label for label in ("Full", "Core", "Code") if label in handles_by_label
    ]
    if ordered_labels:
        figure.legend(
            [handles_by_label[label] for label in ordered_labels],
            ordered_labels,
            loc="outside upper center",
            ncol=len(ordered_labels),
        )
    if 'Full' in handles_by_label:
        figure.supxlabel('Full overlaps core/tails; descriptive comparison, no independent-sample significance', fontsize=9)
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
