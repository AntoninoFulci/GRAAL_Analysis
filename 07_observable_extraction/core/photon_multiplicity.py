"""Quantify current first-four-photon selection against exactly-four subset."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from observable_extraction.io.reconstructed_events import EventArrays


@dataclass(frozen=True)
class PhotonMultiplicityStudy:
    inclusive_count: int
    exactly_four_count: int
    exactly_four_fraction: float
    sigma_inclusive: np.ndarray
    sigma_exactly_four: np.ndarray
    sigma_shift: np.ndarray
    best_quartet_resolved: bool = False


def compare_multiplicity_selections(
    events: EventArrays,
    estimator: Callable[[EventArrays], np.ndarray],
) -> PhotonMultiplicityStudy:
    if len(events) == 0:
        raise ValueError("inclusive sample is empty")
    exactly_four_mask = events.n_photons_input == 4
    exactly_four_count = int(np.count_nonzero(exactly_four_mask))
    if exactly_four_count == 0:
        raise ValueError("exactly-four sample is empty")
    sigma_inclusive = np.asarray(estimator(events), dtype=np.float64)
    sigma_exactly_four = np.asarray(
        estimator(events.take(exactly_four_mask)), dtype=np.float64
    )
    if sigma_inclusive.shape != sigma_exactly_four.shape:
        raise ValueError("multiplicity estimators returned incompatible shapes")
    if np.any(~np.isfinite(sigma_inclusive)) or np.any(
        ~np.isfinite(sigma_exactly_four)
    ):
        raise ValueError("multiplicity estimates must be finite")
    return PhotonMultiplicityStudy(
        inclusive_count=len(events),
        exactly_four_count=exactly_four_count,
        exactly_four_fraction=exactly_four_count / len(events),
        sigma_inclusive=sigma_inclusive,
        sigma_exactly_four=sigma_exactly_four,
        sigma_shift=sigma_exactly_four - sigma_inclusive,
    )
