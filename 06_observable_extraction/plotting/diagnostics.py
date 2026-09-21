"""Headless PDF diagnostics for beam-asymmetry extraction."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from observable_extraction.io.root_output import OutputPoint


PAIR_ORDER = ("p_pi0", "p_eta", "eta_pi0")
PAIR_LABELS = {
    "p_pi0": r"$p\pi^0$",
    "p_eta": r"$p\eta$",
    "eta_pi0": r"$\eta\pi^0$",
}


def _save(path: Path, figure) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, format="pdf", bbox_inches="tight")
    plt.close(figure)


def write_point_comparison_pdf(
    path: Path,
    points: Sequence[OutputPoint],
    *,
    group_by: str,
) -> None:
    """Compare samples or estimators without changing fitted values."""
    if group_by not in {"sample", "estimator"}:
        raise ValueError("group_by must be 'sample' or 'estimator'")
    groups = sorted({getattr(item, group_by) for item in points})
    figure, axes = plt.subplots(1, 3, figsize=(12.5, 3.8), sharey=True)
    for axis, pair in zip(axes, PAIR_ORDER):
        for group in groups:
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
            axis.errorbar(x, y, yerr=yerr, marker="o", linestyle="none", label=group)
        axis.axhline(0.0, color="0.65", linewidth=0.8)
        axis.set_title(PAIR_LABELS[pair])
        axis.set_xlabel(r"$M$ [GeV/$c^2$]")
        axis.set_ylim(-1.0, 1.0)
        axis.grid(alpha=0.2)
    axes[0].set_ylabel(r"Beam asymmetry $\Sigma$")
    handles, labels = axes[-1].get_legend_handles_labels()
    if handles:
        figure.legend(handles, labels, loc="upper center", ncol=max(1, len(groups)))
        figure.subplots_adjust(top=0.80)
    figure.suptitle(f"Comparison by {group_by}")
    _save(path, figure)


def write_fit_diagnostics_pdf(
    path: Path,
    points: Sequence[OutputPoint],
) -> None:
    """Write compact convergence, fit-quality, and fallback diagnostics."""
    figure, axes = plt.subplots(1, 2, figsize=(10.5, 4.0))
    for pair in PAIR_ORDER:
        selected = [item for item in points if item.point.pair == pair]
        if not selected:
            continue
        index = np.arange(len(selected))
        p_values = [item.point.diagnostics.p_value for item in selected]
        reduced = [
            item.point.diagnostics.chi2 / item.point.diagnostics.ndf
            if item.point.diagnostics.ndf > 0
            else np.nan
            for item in selected
        ]
        axes[0].plot(index, p_values, marker=".", linestyle="none", label=PAIR_LABELS[pair])
        axes[1].plot(index, reduced, marker=".", linestyle="none", label=PAIR_LABELS[pair])
    axes[0].axhline(0.01, color="tab:red", linestyle="--", linewidth=0.8)
    axes[0].set_ylabel("fit p-value")
    axes[0].set_ylim(0.0, 1.0)
    axes[1].set_ylabel(r"$\chi^2/\mathrm{ndf}$")
    for axis in axes:
        axis.set_xlabel("fitted-bin index")
        axis.grid(alpha=0.2)
        axis.legend()
    fallback = sum(item.point.diagnostics.used_fallback for item in points)
    failed = sum(not item.point.diagnostics.converged for item in points)
    figure.suptitle(
        f"Fit diagnostics: {fallback} fallback fits, {failed} non-converged fits"
    )
    _save(path, figure)


def write_systematic_summary_pdf(
    path: Path,
    covariances: Mapping[str, np.ndarray],
) -> None:
    """Plot per-point uncertainty from each systematic covariance diagonal."""
    figure, axis = plt.subplots(figsize=(10.5, 4.5))
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
        axis.legend(fontsize="small")
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
    figure, axis = plt.subplots(figsize=(7.0, 4.2))
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
) -> None:
    """Store BREM azimuth controls; no BREM event enters Sigma extraction."""
    figure, axes = plt.subplots(1, 3, figsize=(12.0, 3.7), sharey=True)
    for axis, pair in zip(axes, PAIR_ORDER):
        phi = np.asarray(brem_phi_by_pair.get(pair, []), dtype=np.float64)
        if phi.size:
            axis.hist(phi, bins=np.linspace(0.0, 2.0 * np.pi, 13), histtype="step")
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
    figure, axis = plt.subplots(figsize=(9.0, 4.2))
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
