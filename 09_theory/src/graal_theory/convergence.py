"""Nested Sobol resolution comparisons for partial observables."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .observables import Prediction


@dataclass(frozen=True)
class ConvergenceReport:
    cross_section_relative_change: float
    max_populated_bin_relative_change: float
    passed: bool
    excluded_edge_bins: dict[str, list[int]]


def _relative_change(low: float, high: float) -> float:
    if low == high == 0.0:
        return 0.0
    if high == 0.0:
        return float("inf")
    return abs(high - low) / abs(high)


def compare_resolutions(low: Prediction, high: Prediction) -> ConvergenceReport:
    if low.photon_energy_gev != high.photon_energy_gev:
        raise ValueError("convergence predictions must use the same photon energy")
    if high.sobol_config.power != low.sobol_config.power + 1:
        raise ValueError("convergence requires consecutive Sobol powers")
    if low.histograms.keys() != high.histograms.keys():
        raise ValueError("convergence histograms must have matching keys")
    cross_change = _relative_change(
        low.partial_cross_section_microbarn,
        high.partial_cross_section_microbarn,
    )
    excluded: dict[str, list[int]] = {}
    changes = []
    for name in low.histograms:
        a = low.histograms[name]
        b = high.histograms[name]
        if not np.array_equal(a.edges, b.edges):
            raise ValueError(f"convergence histogram {name!r} has mismatched edges")
        widths = np.diff(a.edges)
        low_yields = a.values * widths
        high_yields = b.values * widths
        excluded[name] = []
        for index, (value_low, value_high) in enumerate(zip(low_yields, high_yields)):
            if index in (0, len(low_yields) - 1) and max(value_low, value_high) < 1e-6:
                excluded[name].append(index)
                continue
            changes.append(_relative_change(float(value_low), float(value_high)))
    max_change = max(changes, default=0.0)
    return ConvergenceReport(
        cross_change,
        max_change,
        bool(cross_change < 0.01 and max_change < 0.03),
        excluded,
    )
