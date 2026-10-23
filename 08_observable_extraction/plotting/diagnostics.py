"""Headless PDF diagnostics for beam-asymmetry extraction."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from observable_extraction.io.root_output import OutputPoint
from observable_extraction.core.binning import PHI_EDGES_RAD, validate_edges
from observable_extraction.plotting.figure4 import EnergyRow, profile_energy_rows, uncertainty_bar_label


PAIR_ORDER = ("p_pi0", "p_eta", "eta_pi0")
PAIR_LABELS = {
    "p_pi0": r"$p\pi^0$",
    "p_eta": r"$p\eta$",
    "eta_pi0": r"$\eta\pi^0$",
}


def _legend_below(figure, axes, *, ncols=4):
    """Collect every panel's labels and reserve space below the axes."""
    entries = {}
    for axis in np.asarray(axes).flat:
        handles, labels = axis.get_legend_handles_labels()
        for handle, label in zip(handles, labels):
            entries.setdefault(label, handle)
    if entries:
        figure.legend(entries.values(), entries.keys(), loc="outside lower center",
                      ncol=min(ncols, len(entries)), fontsize=9)


def _save(path: Path, figure) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, format="pdf", bbox_inches="tight")
    plt.close(figure)


def _mass_center(point: OutputPoint) -> float:
    return 0.5 * (point.point.mass_low_gev + point.point.mass_high_gev)


def write_period_stability_pdf(path, points_by_period, rows, *, sample, estimator):
    """Compare identical bins across disjoint periods; never draw pooled pulls."""
    figure, axes = plt.subplots(len(rows), 3, figsize=(12, 3 * len(rows) + 1),
                                squeeze=False, constrained_layout=True)
    for row_index, row in enumerate(rows):
        for column, pair in enumerate(PAIR_ORDER):
            axis = axes[row_index, column]
            for period_index, (period, points) in enumerate(points_by_period.items()):
                selected = sorted((item for item in points if item.sample == sample
                                   and item.estimator == estimator and item.point.pair == pair
                                   and item.point.energy_bin == row.energy_bin
                                   and item.point.diagnostics.converged), key=lambda x: x.point.mass_bin)
                if selected:
                    axis.errorbar([_mass_center(item) for item in selected],
                                  [item.point.sigma for item in selected],
                                  yerr=np.array([[item.point.stat_low for item in selected],
                                                 [item.point.stat_high for item in selected]]),
                                  fmt='o', capsize=2, color=f'C{period_index % 10}', label=period)
            axis.axhline(0, color='0.7', linewidth=.8)
            axis.set_title(f'{PAIR_LABELS[pair]} | {row.low_gev:g}–{row.high_gev:g} GeV')
            axis.set_xlabel('M [GeV]')
            axis.set_ylabel(r'$\Sigma$')
            axis.grid(alpha=.2)
    _legend_below(figure, axes)
    figure.suptitle('Period stability — conditional/propagated errors; final inference suspended\n'
                    'Shared global nuisances correlated; no pooled comparison or significance test')
    _save(path, figure)


def build_profile_estimator_comparison(
    points_by_profile: Mapping[str, Sequence[OutputPoint]],
    rows: Sequence[EnergyRow],
    *,
    sample: str = "raw_bdt",
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
        for column, pair in enumerate(PAIR_ORDER):
            axis = axes[row_index, column]
            for estimator, marker in (("ratio", "o"), ("likelihood", "s")):
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
                if not selected:
                    continue
                axis.errorbar(
                    [_mass_center(item) for item in selected],
                    [item.point.sigma for item in selected],
                    yerr=np.array(
                        [
                            [item.point.stat_low for item in selected],
                            [item.point.stat_high for item in selected],
                        ]
                    ),
                    marker=marker,
                    linestyle="none",
                    capsize=2,
                    label=estimator,
                )
            axis.axhline(0.0, color="0.65", linewidth=0.8)
            axis.set_ylim(-1.0, 1.0)
            axis.grid(alpha=0.2)
            if row_index == 0:
                axis.set_title(PAIR_LABELS[pair])
            if column == 0:
                axis.set_ylabel(
                    "$\\Sigma$\n" + f"{row.low_gev:.4g}–{row.high_gev:.4g} GeV"
                )
            if row_index == len(rows) - 1:
                axis.set_xlabel(r"$M$ [GeV]")
    _legend_below(figure, axes)
    return figure, axes


def build_profile_fit_diagnostics(
    points_by_profile: Mapping[str, Sequence[OutputPoint]],
    rows: Sequence[EnergyRow],
    *,
    sample: str = "raw_bdt",
):
    if not rows:
        raise ValueError("at least one energy row is required")
    figure, axes = plt.subplots(
        len(rows),
        3,
        figsize=(11.0, 2.8 * len(rows) + 0.8),
        constrained_layout=True,
        squeeze=False,
    )
    for row_index, row in enumerate(rows):
        profile_points = points_by_profile.get(row.profile, ())
        for column, pair in enumerate(PAIR_ORDER):
            axis = axes[row_index, column]
            selected = sorted(
                (
                    item
                    for item in profile_points
                    if item.sample == sample
                    and item.estimator == "ratio"
                    and item.point.pair == pair
                    and item.point.energy_bin == row.energy_bin
                    and item.point.diagnostics.ndf > 0
                ),
                key=lambda item: item.point.mass_bin,
            )
            if selected:
                x = [_mass_center(item) for item in selected]
                axis.plot(
                    x,
                    [item.point.diagnostics.p_value for item in selected],
                    marker="o",
                    linestyle="none",
                    color="tab:blue",
                    label="p-value",
                )
                reduced_axis = axis.twinx()
                reduced_axis.plot(
                    x,
                    [
                        item.point.diagnostics.chi2 / item.point.diagnostics.ndf
                        for item in selected
                    ],
                    marker="s",
                    linestyle="none",
                    color="tab:orange",
                    label=r"$\chi^2/\mathrm{ndf}$",
                )
                reduced_axis.set_ylabel(r"$\chi^2/\mathrm{ndf}$")
            else:
                axis.text(0.5, 0.5, "No fit", ha="center", va="center")
            axis.axhline(0.01, color="tab:red", linestyle="--", linewidth=0.8)
            axis.set_ylim(0.0, 1.0)
            axis.grid(alpha=0.2)
            if row_index == 0:
                axis.set_title(PAIR_LABELS[pair])
            if column == 0:
                axis.set_ylabel(
                    f"fit p-value\n{row.low_gev:.4g}--{row.high_gev:.4g} GeV"
                )
            if row_index == len(rows) - 1:
                axis.set_xlabel(r"$M$ [GeV]")
    return figure, axes


def write_profile_estimator_comparison_pdf(
    path: Path,
    points_by_profile: Mapping[str, Sequence[OutputPoint]],
    rows: Sequence[EnergyRow],
    *,
    sample: str = "raw_bdt",
) -> None:
    figure, _ = build_profile_estimator_comparison(
        points_by_profile, rows, sample=sample
    )
    _save(path, figure)


def write_profile_fit_diagnostics_pdf(
    path: Path,
    points_by_profile: Mapping[str, Sequence[OutputPoint]],
    rows: Sequence[EnergyRow],
    *,
    sample: str = "raw_bdt",
) -> None:
    figure, _ = build_profile_fit_diagnostics(
        points_by_profile, rows, sample=sample
    )
    _save(path, figure)


def write_point_comparison_pdf(
    path: Path,
    points: Sequence[OutputPoint],
    *,
    group_by: str,
) -> None:
    """Compare samples or estimators without changing fitted values."""
    if group_by not in {"sample", "estimator"}:
        raise ValueError("group_by must be 'sample' or 'estimator'")
    if group_by == "estimator":
        write_profile_estimator_comparison_pdf(
            path,
            {"uv": points},
            profile_energy_rows("uv"),
        )
        return
    groups = sorted({getattr(item, group_by) for item in points})
    figure, axes = plt.subplots(1, 3, figsize=(12.5, 4.5), sharey=True,
                                constrained_layout=True)
    for axis, pair in zip(axes, PAIR_ORDER):
        for group_index, group in enumerate(groups):
            selected = [
                item
                for item in points
                if item.point.pair == pair and getattr(item, group_by) == group
            ]
            selected.sort(
                key=lambda item: (
                    item.point.energy_bin,
                    item.point.mass_bin,
                    item.point.mass_mean_gev,
                )
            )
            if not selected:
                continue
            x = np.array([item.point.mass_mean_gev for item in selected])
            y = np.array([item.point.sigma for item in selected])
            yerr = np.array(
                [
                    [item.point.stat_low for item in selected],
                    [item.point.stat_high for item in selected],
                ]
            )
            axis.errorbar(x, y, yerr=yerr, marker="o", linestyle="none", label=group,
                          color=f"C{group_index % 10}")
        axis.axhline(0.0, color="0.65", linewidth=0.8)
        axis.set_title(PAIR_LABELS[pair])
        axis.set_xlabel(r"$M$ [GeV/$c^2$]")
        axis.set_ylim(-1.0, 1.0)
        axis.grid(alpha=0.2)
    axes[0].set_ylabel(r"Beam asymmetry $\Sigma$")
    _legend_below(figure, axes)
    figure.suptitle(f"Comparison by {group_by}\n" + uncertainty_bar_label(points), fontsize=10)
    _save(path, figure)


def write_fit_diagnostics_pdf(
    path: Path,
    points: Sequence[OutputPoint],
) -> None:
    """Write UV physical-grid fit diagnostics for compatibility callers."""
    write_profile_fit_diagnostics_pdf(
        path,
        {"uv": points},
        profile_energy_rows("uv"),
    )


def write_systematic_summary_pdf(
    path: Path,
    covariances: Mapping[str, np.ndarray],
    *,
    inventory: Mapping | None = None,
) -> None:
    """Plot the provisional component sizes and explicit availability ledger."""
    if inventory is None:
        figure, axis = plt.subplots(figsize=(10.5, 4.5), constrained_layout=True)
    else:
        import textwrap
        figure, (axis, table_axis) = plt.subplots(2, 1, figsize=(13, 11), constrained_layout=True)
        table_axis.axis("off")
        rows = [[name, entry["status"], str(sum(entry["measured_points"])),
                 textwrap.fill(entry["reason"] or entry["category"], 48)]
                for name, entry in inventory.items()]
        table = table_axis.table(cellText=rows, colLabels=["Source", "State", "Points", "Reason / interpretation"],
                                 colWidths=[.26, .13, .06, .55], loc="center", cellLoc="left")
        table.auto_set_font_size(False)
        table.set_fontsize(8)
        table.scale(1, 2.5)
    axis.set_title("Available systematic components: partial, provisional; final inference suspended")
    for name, covariance in sorted(covariances.items()):
        matrix = np.asarray(covariance, dtype=np.float64)
        if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
            raise ValueError(f"systematic covariance {name!r} must be square")
        uncertainty = np.sqrt(np.clip(np.diag(matrix), 0.0, None))
        axis.plot(np.arange(len(uncertainty)), uncertainty, label=name)
    axis.set_xlabel("output-point index")
    axis.set_ylabel(r"systematic uncertainty on $\Sigma$")
    axis.grid(alpha=0.2)
    if covariances:
        _legend_below(figure, [axis], ncols=2)
    else:
        axis.text(0.5, 0.5, "No systematic components", ha="center", va="center")
    _save(path, figure)


def write_background_control_pdf(
    path: Path,
    fractions: Mapping[int, object],
    *,
    signal_leakage: float,
) -> None:
    """Plot fitted signal-region background fraction by photon-energy bin."""
    figure, axis = plt.subplots(figsize=(7.0, 4.2), constrained_layout=True)
    bins = sorted(fractions)
    if bins:
        values = [fractions[index].fraction for index in bins]
        errors = [fractions[index].error for index in bins]
        axis.errorbar(bins, values, yerr=errors, marker="o", linestyle="none")
    else:
        axis.text(0.5, 0.5, "No fitted background bins", ha="center", va="center")
    axis.set_xlabel(r"$E_\gamma$ bin")
    axis.set_ylabel("background fraction in signal region")
    axis.set_ylim(bottom=0.0)
    axis.grid(alpha=0.2)
    axis.set_title(f"Signal-MC hard-sideband leakage: {signal_leakage:.2%}")
    _save(path, figure)


def write_false_asymmetry_controls_pdf(
    path: Path,
    brem_phi_by_pair: Mapping[str, np.ndarray],
    *,
    phi_edges: np.ndarray = PHI_EDGES_RAD,
) -> None:
    """Store BREM azimuth controls; no BREM event enters Sigma extraction."""
    phi_edges = validate_edges(phi_edges)
    figure, axes = plt.subplots(1, 3, figsize=(12.0, 3.7), sharey=True,
                                constrained_layout=True)
    for axis, pair in zip(axes, PAIR_ORDER):
        phi = np.asarray(brem_phi_by_pair.get(pair, []), dtype=np.float64)
        if phi.size:
            axis.hist(phi, bins=phi_edges, histtype="step")
            c2 = float(np.mean(np.cos(2.0 * phi)))
            s2 = float(np.mean(np.sin(2.0 * phi)))
            axis.text(0.04, 0.95, f"<c2>={c2:+.3f}\n<s2>={s2:+.3f}",
                      transform=axis.transAxes, va="top")
        else:
            axis.text(0.5, 0.5, "No BREM events", ha="center", va="center")
        axis.set_title(PAIR_LABELS[pair])
        axis.set_xlabel(r"$\phi$ [rad]")
        axis.grid(alpha=0.2)
    axes[0].set_ylabel("BREM events")
    figure.suptitle("Unpolarized BREM azimuth controls")
    _save(path, figure)


def write_photon_multiplicity_pdf(
    path: Path,
    *,
    inclusive_count: int,
    exactly_four_count: int,
    shifts: np.ndarray,
    best_quartet_resolved: bool,
) -> None:
    """Report exactly-four selection shift and unresolved best-quartet state."""
    shifts = np.asarray(shifts, dtype=np.float64)
    figure, axis = plt.subplots(figsize=(9.0, 4.2), constrained_layout=True)
    if shifts.size:
        axis.plot(np.arange(len(shifts)), shifts, marker="o", linestyle="none")
        axis.axhline(0.0, color="0.6", linewidth=0.8)
    else:
        axis.text(0.5, 0.5, "Multiplicity shift unavailable", ha="center", va="center")
    fraction = exactly_four_count / inclusive_count if inclusive_count else 0.0
    state = "resolved" if best_quartet_resolved else "UNRESOLVED"
    axis.set_title(
        f"Exactly four: {exactly_four_count}/{inclusive_count} ({fraction:.1%}); "
        f"best-quartet {state}"
    )
    axis.set_xlabel("nominal output-point index")
    axis.set_ylabel(r"$\Sigma_{N_\gamma=4}-\Sigma_{inclusive}$")
    axis.grid(alpha=0.2)
    _save(path, figure)
