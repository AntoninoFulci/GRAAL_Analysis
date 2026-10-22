"""Detector response from unique generated identities, including undetected events.

Rows are reconstructed cells, columns true cells. Unweighted, independent MC
only: training weights are not detector efficiencies. Cell -1 on the selected
side denotes migration out of the analysis domain. Truth outside the domain
must be modelled with explicit guard cells, not silently discarded.
"""

from __future__ import annotations

import numpy as np


def _integers(values, name):
    values = np.asarray(values)
    if values.ndim != 1 or (values.size and values.dtype.kind not in "iu"):
        raise ValueError(f"{name} must be a one-dimensional integer array")
    if np.any(values > np.iinfo(np.int64).max):
        raise ValueError(f"{name} exceeds int64")
    return values.astype(np.int64)


def count_response(generated_ids, generated_bins, selected_ids, selected_bins, n_bins):
    """Count a complete generated sample and its uniquely matched selected subset."""
    if type(n_bins) is not int or n_bins < 1:
        raise ValueError("n_bins must be a positive integer")
    ids = _integers(generated_ids, "generated_ids")
    bins = _integers(generated_bins, "generated_bins")
    selected = _integers(selected_ids, "selected_ids")
    reco = _integers(selected_bins, "selected_bins")
    if len(ids) != len(bins) or len(selected) != len(reco) or not len(ids):
        raise ValueError(
            "identity and cell arrays must match and generation must be nonempty"
        )
    if np.any(ids < 0) or np.any(selected < 0):
        raise ValueError("event identities must be non-negative")
    if len(np.unique(ids)) != len(ids) or len(np.unique(selected)) != len(selected):
        raise ValueError("duplicate event identities")
    if np.any((bins < 0) | (bins >= n_bins)) or np.any((reco < -1) | (reco >= n_bins)):
        raise ValueError("cell outside declared grid; use explicit truth guard cells")
    order = np.argsort(ids)
    positions = np.searchsorted(ids[order], selected)
    if np.any(positions >= len(ids)) or not np.array_equal(
        ids[order][positions], selected
    ):
        raise ValueError("selected identity absent from generated denominator")
    counts = np.zeros((n_bins, n_bins), dtype=np.int64)
    accepted = reco >= 0
    np.add.at(counts, (reco[accepted], bins[order][positions[accepted]]), 1)
    return np.bincount(bins, minlength=n_bins), counts


def response_probabilities(generated, selected):
    """Return R and conditional multinomial covariance for each true column.

    Covariance shape is (truth, reconstructed, reconstructed). The unobserved
    category (all losses) is included through 1 - sum(R[:, truth]). A cell
    without generated or accepted support cannot establish a total.
    """
    n = np.asarray(generated, dtype=float)
    counts = np.asarray(selected, dtype=float)
    if n.ndim != 1 or not len(n) or counts.shape != (len(n), len(n)):
        raise ValueError(
            "response counts must be square with one denominator per true cell"
        )
    if (
        not np.all(np.isfinite(n))
        or not np.all(np.isfinite(counts))
        or np.any(n <= 0)
        or np.any(counts < 0)
        or np.any(n != np.floor(n))
        or np.any(counts != np.floor(counts))
    ):
        raise ValueError(
            "response requires positive integer generated and non-negative integer selected counts"
        )
    if np.any(counts.sum(axis=0) > n):
        raise ValueError("selected counts exceed generated denominator")
    if np.any(counts.sum(axis=0) == 0):
        raise ValueError(
            "zero acceptance: cannot infer a total without an extrapolation model"
        )
    response = counts / n
    covariance = np.array(
        [(np.diag(p) - np.outer(p, p)) / total for p, total in zip(response.T, n)]
    )
    return response, covariance
