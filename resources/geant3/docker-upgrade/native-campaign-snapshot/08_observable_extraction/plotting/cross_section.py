"""Cross-section plots; no fit/rescaling to a publication reference."""

from __future__ import annotations

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def plot_cross_sections(result, path, reference=None):
    synthetic = result["audit"]["analysis_kind"] == "synthetic_closure"
    diagnostic = result["audit"].get("status", "").startswith("diagnostic_")
    label = (
        "Synthetic closure"
        if synthetic
        else ("Diagnostic extraction" if diagnostic else "Analysis (conditional)")
    )
    grid = result["grid"]
    energy = np.asarray(grid["energy_edges_gev"])
    mass = grid.get("mass_edges_gev")
    values = result["values"]
    errors = np.sqrt(np.diag(result["known_covariance"]))
    ne = len(energy) - 1
    fig, axes = plt.subplots(
        1,
        1 if mass is None else ne,
        figsize=(7 if mass is None else 4 * ne, 4),
        squeeze=False,
    )
    if mass is None:
        axes[0, 0].errorbar(
            (energy[:-1] + energy[1:]) / 2,
            values,
            yerr=errors,
            xerr=np.diff(energy) / 2,
            fmt="o",
            label=label,
        )
        axes[0, 0].set(xlabel=r"$E_\gamma$ [GeV]", ylabel=r"$\sigma$ [$\mu$b]")
    else:
        mass = np.asarray(mass)
        nm = len(mass) - 1
        for e, ax in enumerate(axes[0]):
            ax.errorbar(
                (mass[:-1] + mass[1:]) / 2,
                values[e * nm : (e + 1) * nm],
                yerr=errors[e * nm : (e + 1) * nm],
                xerr=np.diff(mass) / 2,
                fmt="o",
                label=label,
            )
            ax.set(
                xlabel=f"M({grid['observable']}) [GeV]",
                ylabel=r"$d\sigma/dM$ [$\mu$b/MeV]",
                title=f"{energy[e]:.3f}–{energy[e + 1]:.3f} GeV",
            )
    if reference is not None:

        def reference_points(ax, x, y, errors, label):
            ax.plot(x, y, "s", mfc="none", label=label)
            available = np.array([error is not None for error in errors])
            if np.any(available):
                ax.errorbar(
                    np.asarray(x)[available],
                    np.asarray(y)[available],
                    yerr=np.asarray([error for error in errors if error is not None]),
                    fmt="none",
                    color="C1",
                )

        if mass is None:
            reference_points(
                axes[0, 0],
                reference["energy_gev"],
                reference["sigma_ub"],
                reference["error_ub"],
                reference["metadata"]["label"],
            )
        else:
            energies = np.asarray(reference["energy_gev"])
            for e, nominal in enumerate(reference["nominal_energies_gev"]):
                keep = np.isclose(energies, nominal, rtol=0, atol=1e-8)
                reference_points(
                    axes[0, e],
                    np.asarray(reference["mass_gev"])[keep],
                    np.asarray(reference["dsigma_ub_per_mev"])[keep],
                    [
                        error
                        for error, selected in zip(reference["error_ub_per_mev"], keep)
                        if selected
                    ],
                    f"Ajaka: nominal {nominal:g} GeV",
                )
            fig.text(
                0.5,
                0.01,
                "Nominal-energy overlay; published energy-window widths unknown",
                ha="center",
                fontsize=8,
            )
    for ax in axes[0]:
        ax.grid(alpha=0.2)
        ax.legend(fontsize=8)
    fig.suptitle(
        (
            "Synthetic closure"
            if synthetic
            else (
                "Diagnostic extraction - model unvalidated"
                if diagnostic
                else "Conditional result"
            )
        )
        + " — known errors only",
        fontsize=10,
    )
    note = result["audit"].get("plot_note") if mass is None else None
    if note:
        fig.text(0.5, 0.01, note, ha="center", fontsize=7)
    fig.tight_layout(
        rect=(
            0,
            0.08
            if note
            else (0.05 if reference is not None and mass is not None else 0),
            1,
            1,
        )
    )
    fig.savefig(path)
    plt.close(fig)
