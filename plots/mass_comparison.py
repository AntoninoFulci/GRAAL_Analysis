"""Raw and 6C-fit mass shapes from the same BDT-gated reconstruction events."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


MASS_FIELDS = {
    "eta": (r"$M(\eta)$", (0.3, 0.8), "6C constrained meson mass"),
    "pi0": (r"$M(\pi^0)$", (0.05, 0.25), "6C constrained meson mass"),
    "p_eta": (r"$M(p\eta)$", (1.0, 2.8), ""),
    "p_pi0": (r"$M(p\pi^0)$", (1.0, 2.8), ""),
    "eta_pi0": (r"$M(\eta\pi^0)$", (0.6, 2.0), ""),
}


def mass_pair(arrays, name: str) -> tuple[np.ndarray, np.ndarray]:
    if not arrays.has_fit:
        raise ValueError("BDT reconstruction has no kinematic-fit branches")
    if name == "eta":
        raw, fit = arrays.eta_mass_raw, arrays.eta_mass
    elif name == "pi0":
        raw, fit = arrays.pi0_mass_raw, arrays.pi0_mass
    else:
        raw, fit = arrays.pair_masses_raw[name], arrays.pair_masses_fit[name]
    raw, fit = np.asarray(raw), np.asarray(fit)
    if len(raw) == 0 or raw.shape != fit.shape or not np.isfinite(raw).all() or not np.isfinite(fit).all():
        raise ValueError(f"invalid same-event raw/fit mass arrays for {name}")
    return raw, fit


def _draw(axis, arrays, name: str, profile: str) -> None:
    raw, fit = mass_pair(arrays, name)
    label, bounds, note = MASS_FIELDS[name]
    bins = np.linspace(*bounds, 61)
    weights = np.full(len(raw), 1.0 / len(raw))
    axis.hist(raw, bins=bins, weights=weights, histtype="step", linewidth=1.7, label="raw")
    axis.hist(fit, bins=bins, weights=weights, histtype="step", linewidth=1.7, label="6C fit")
    axis.set_xlim(*bounds)
    axis.set_xlabel(label + " [GeV]")
    axis.set_ylabel("Fraction of BDT events / bin")
    axis.set_title(profile.upper() + (f" — {note}" if note else ""))
    axis.legend()


def write_profile_masses(arrays, output_dir: Path, profile: str) -> None:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in MASS_FIELDS:
        figure, axis = plt.subplots(figsize=(7, 5), constrained_layout=True)
        try:
            _draw(axis, arrays, name, profile)
            figure.savefig(output_dir / f"mass_raw_fit_{name}.pdf")
        finally:
            plt.close(figure)


def write_common_masses(arrays_by_profile: Mapping[str, object], output_dir: Path) -> None:
    if set(arrays_by_profile) != {"uv", "vis"}:
        raise ValueError("common mass comparison requires UV and VIS")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in MASS_FIELDS:
        figure, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharex=True, sharey=True, constrained_layout=True)
        try:
            for axis, profile in zip(axes, ("vis", "uv")):
                _draw(axis, arrays_by_profile[profile], name, profile)
            figure.savefig(output_dir / f"mass_uv_vis_{name}.pdf")
        finally:
            plt.close(figure)
