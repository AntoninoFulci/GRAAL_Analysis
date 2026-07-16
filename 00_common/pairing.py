"""Assigning four observed photons to two mesons, and scoring the assignment.

The one chi2 in the project. The reconstruction uses it to pick a pairing; the
stage-1 features use it as a discriminant. Those were two separate
implementations of the same formula — a table-driven loop there, a vectorised
expression here — agreeing by inspection and free to drift. That is the shape of
the bug that once had the gate scoring its model on a feature vector built by a
second, drifted copy of the feature builder.

The enumeration used to live in `05_reconstruction/data/combinations_*.txt`, a file
per channel listing rows like

    0 1 2 3 0.547862 0.134977      # photons (0,1) are the eta, (2,3) the pi0
    0 1 2 3 0.134977 0.547862      # ...or the other way round

Those files carried no information: they were exactly the three ways to split
four photons into two pairs, times the two ways to assign the mesons to them
(times one, not two, when the mesons are the same particle). Every row was
derivable from the hypothesis, and the meson masses were copied into the table
where they were free to disagree with the registry. `pairings()` derives them
instead — which is also what lets a new hypothesis be reconstructed without
anyone writing it a table first.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from graal_common.channels import CHI2_RESOLUTION, Hypothesis

# The C(4,2)=6 photon pairs, and the slot each occupies in a pair-mass array.
PAIR_IDX: list[tuple[int, int]] = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]
_PAIR_SLOT: dict[tuple[int, int], int] = {pair: k for k, pair in enumerate(PAIR_IDX)}

# The 3 ways to split 4 photons into two disjoint pairs.
PARTITIONS: list[tuple[tuple[int, int], tuple[int, int]]] = [
    ((0, 1), (2, 3)),
    ((0, 2), (1, 3)),
    ((0, 3), (1, 2)),
]


@dataclass(frozen=True)
class Pairing:
    """One hypothesis about which photons made which meson."""

    heavy: tuple[int, int]
    light: tuple[int, int]


def pair_slot(i: int, j: int) -> int:
    """Where the (i, j) photon pair sits in a pair_masses array."""
    return _PAIR_SLOT[(min(i, j), max(i, j))]


def pairings(hypothesis: Hypothesis) -> list[Pairing]:
    """Every way the four photons could be this hypothesis's two mesons.

    Six for two different mesons, three when they are the same particle: with a
    degenerate hypothesis, swapping "heavy" and "light" relabels the pairs
    without asking a different question, and scoring both would be the same chi2
    twice.
    """
    out: list[Pairing] = []
    for a, b in PARTITIONS:
        out.append(Pairing(heavy=a, light=b))
        if not hypothesis.is_degenerate:
            out.append(Pairing(heavy=b, light=a))
    return out


def pair_masses(photons: np.ndarray) -> np.ndarray:
    """Invariant masses of the 6 photon pairs.

    photons: (..., 4, 4), last axis [px, py, pz, E]. Returns (..., 6) in
    PAIR_IDX order. Broadcasts, so one event (4,4) -> (6,) and a whole chunk
    (N,4,4) -> (N,6) go through the same code.
    """
    out = []
    for i, j in PAIR_IDX:
        s = photons[..., i, :] + photons[..., j, :]
        m2 = s[..., 3] ** 2 - (s[..., 0] ** 2 + s[..., 1] ** 2 + s[..., 2] ** 2)
        # Resolution can push m^2 marginally negative on a genuinely light
        # system; report 0 rather than NaN.
        out.append(np.sqrt(np.clip(m2, 0.0, None)))
    return np.stack(out, axis=-1)


def chi2(
    m_heavy_measured: np.ndarray | float,
    m_light_measured: np.ndarray | float,
    hypothesis: Hypothesis,
) -> np.ndarray | float:
    """How badly two measured masses miss the hypothesis's two poles.

    Each term is the miss in units of the mass resolution, which the analysis
    takes as a fixed fraction (CHI2_RESOLUTION) of the target mass. Broadcasts.
    """
    d_heavy = (m_heavy_measured - hypothesis.heavy_mass) / (
        CHI2_RESOLUTION * hypothesis.heavy_mass
    )
    d_light = (m_light_measured - hypothesis.light_mass) / (
        CHI2_RESOLUTION * hypothesis.light_mass
    )
    return d_heavy**2 + d_light**2


def chi2_per_pairing(pair_m: np.ndarray, hypothesis: Hypothesis) -> np.ndarray:
    """chi2 of every pairing, given the 6 pair masses.

    pair_m: (..., 6) from pair_masses. Returns (..., n_pairings), in the order
    pairings() gives them.
    """
    return np.stack(
        [
            chi2(
                pair_m[..., pair_slot(*p.heavy)],
                pair_m[..., pair_slot(*p.light)],
                hypothesis,
            )
            for p in pairings(hypothesis)
        ],
        axis=-1,
    )


def best_pairing(photons: np.ndarray, hypothesis: Hypothesis) -> tuple[Pairing, float]:
    """The pairing that best fits the hypothesis, and its chi2. One event."""
    scores = chi2_per_pairing(pair_masses(photons), hypothesis)
    idx = int(np.argmin(scores))
    return pairings(hypothesis)[idx], float(scores[idx])


def best_chi2(photons: np.ndarray, hypothesis: Hypothesis) -> np.ndarray:
    """The best pairing's chi2 for each of N events. photons: (N, 4, 4)."""
    return chi2_per_pairing(pair_masses(photons), hypothesis).min(axis=-1)
