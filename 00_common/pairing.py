"""Enumerate photon pairings and score them against a meson hypothesis."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from graal_common.channels import CHI2_RESOLUTION, Hypothesis

# Photon pairs and their positions in a pair-mass array.
PAIR_IDX: list[tuple[int, int]] = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]
_PAIR_SLOT: dict[tuple[int, int], int] = {pair: k for k, pair in enumerate(PAIR_IDX)}

# The three partitions of four photons into disjoint pairs.
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
    """Return the pair-mass index for photons ``i`` and ``j``."""
    return _PAIR_SLOT[(min(i, j), max(i, j))]


def pairings(hypothesis: Hypothesis) -> list[Pairing]:
    """Generate all photon pairings for ``hypothesis``."""
    out: list[Pairing] = []
    for a, b in PARTITIONS:
        out.append(Pairing(heavy=a, light=b))
        # Swapping identical mesons would duplicate the same score.
        if not hypothesis.is_degenerate:
            out.append(Pairing(heavy=b, light=a))
    return out


def pair_masses(photons: np.ndarray) -> np.ndarray:
    """Compute the six photon-pair invariant masses.

    Accepts ``(..., 4, 4)`` with the last axis ordered as ``[px, py, pz, E]``;
    returns ``(..., 6)`` in ``PAIR_IDX`` order.
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
    """Compute the mass-pole chi2 for a hypothesis."""
    d_heavy = (m_heavy_measured - hypothesis.heavy_mass) / (
        CHI2_RESOLUTION * hypothesis.heavy_mass
    )
    d_light = (m_light_measured - hypothesis.light_mass) / (
        CHI2_RESOLUTION * hypothesis.light_mass
    )
    return d_heavy**2 + d_light**2


def chi2_per_pairing(pair_m: np.ndarray, hypothesis: Hypothesis) -> np.ndarray:
    """Score every pairing from pair masses shaped ``(..., 6)``."""
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
    """Select the best pairing for one event."""
    scores = chi2_per_pairing(pair_masses(photons), hypothesis)
    idx = int(np.argmin(scores))
    return pairings(hypothesis)[idx], float(scores[idx])


def best_chi2(photons: np.ndarray, hypothesis: Hypothesis) -> np.ndarray:
    """Compute the minimum pairing chi2 for each event."""
    return chi2_per_pairing(pair_masses(photons), hypothesis).min(axis=-1)


def best_pairing_indices(
    pair_m: np.ndarray, hypothesis: Hypothesis
) -> tuple[np.ndarray, np.ndarray]:
    """Select best-pairing photon indices for a batch of pair masses."""
    ps = pairings(hypothesis)
    heavy_table = np.array([p.heavy for p in ps], dtype=np.intp)  # (n_pairings, 2)
    light_table = np.array([p.light for p in ps], dtype=np.intp)
    chosen = np.argmin(chi2_per_pairing(pair_m, hypothesis), axis=-1)  # (N,)
    return heavy_table[chosen], light_table[chosen]
