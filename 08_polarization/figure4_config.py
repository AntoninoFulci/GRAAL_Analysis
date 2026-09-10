"""Strict configuration for framework-native Figure-4-style output."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import numpy as np

from contracts import PolarizationContractError, load_json


@dataclass(frozen=True)
class Figure4Config:
    energy_ranges: tuple[tuple[float, float], ...]
    mass_bins: int
    phi_bins: int
    target: str
    tree: str
    vectors: str
    orientation_signs: dict[str, int]


def load_figure4_config(path: Path) -> Figure4Config:
    """Load comparison layout only after sign convention approval."""
    payload = load_json(path)
    sign = payload.get("sign_convention")
    if not isinstance(sign, Mapping) or sign.get("status") != "approved":
        raise PolarizationContractError(
            "sign convention requires two-reviewer approval"
        )
    raw_signs = sign.get("orientation_signs")
    if not isinstance(raw_signs, Mapping) or set(raw_signs) != {
        "parallel", "perpendicular"
    } or any(
        isinstance(value, bool) or not isinstance(value, int)
        for value in raw_signs.values()
    ) or set(raw_signs.values()) != {-1, 1}:
        raise PolarizationContractError(
            "approved sign convention must assign opposite signs -1 and +1"
        )
    section = payload.get("figure4_comparison")
    if not isinstance(section, Mapping):
        raise PolarizationContractError("figure4_comparison must be a JSON object")
    raw_edges = section.get("energy_edges_gev")
    try:
        edges = np.asarray(raw_edges, dtype=float)
    except (TypeError, ValueError) as exc:
        raise PolarizationContractError("Figure 4 energy edges must be numeric") from exc
    if (
        edges.shape != (5,)
        or not np.all(np.isfinite(edges))
        or not np.all(np.diff(edges) > 0.0)
    ):
        raise PolarizationContractError(
            "Figure 4 comparison requires exactly four energy bins"
        )
    mass_bins = section.get("mass_bins")
    phi_bins = section.get("phi_bins")
    if isinstance(mass_bins, bool) or not isinstance(mass_bins, int) or mass_bins < 1:
        raise PolarizationContractError("mass_bins must be a positive integer")
    if isinstance(phi_bins, bool) or not isinstance(phi_bins, int) or phi_bins < 3:
        raise PolarizationContractError("phi_bins must be an integer of at least three")
    target = section.get("target")
    tree = section.get("tree")
    vectors = section.get("vectors")
    if not isinstance(target, str) or not target:
        raise PolarizationContractError("Figure 4 target must be non-empty")
    if not isinstance(tree, str) or not tree:
        raise PolarizationContractError("Figure 4 ROOT tree must be non-empty")
    if vectors not in {"raw", "kinematic_fit"}:
        raise PolarizationContractError("vectors must be raw or kinematic_fit")
    return Figure4Config(
        energy_ranges=tuple(
            (float(low), float(high)) for low, high in zip(edges, edges[1:])
        ),
        mass_bins=mass_bins,
        phi_bins=phi_bins,
        target=target,
        tree=tree,
        vectors=vectors,
        orientation_signs=dict(raw_signs),
    )
