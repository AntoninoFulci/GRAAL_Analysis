"""Auditable 60/20/20 splitting of source events, before fitting any model."""
from __future__ import annotations

import numpy as np

SPLIT_NAMES = ("train", "validation", "test")


def audit_group_splits(origin_id: np.ndarray, split: np.ndarray) -> dict:
    origins = np.asarray(origin_id)
    split = np.asarray(split)
    if origins.ndim != 1 or split.shape != origins.shape or not len(origins):
        raise ValueError("origin and split arrays must be nonempty aligned vectors")
    if not np.issubdtype(split.dtype, np.integer) or not np.isin(split, (0, 1, 2)).all():
        raise ValueError("split must contain integer train=0, validation=1, test=2")
    unique, inverse = np.unique(origins, return_inverse=True)
    low = np.full(len(unique), 3)
    high = np.full(len(unique), -1)
    np.minimum.at(low, inverse, split)
    np.maximum.at(high, inverse, split)
    if np.any(low != high):
        raise ValueError("origin appears in multiple splits (train/validation/test leakage)")
    return {
        "unique_origins": len(unique),
        "rows": {name: int(np.count_nonzero(split == i)) for i, name in enumerate(SPLIT_NAMES)},
        "groups": {name: int(np.count_nonzero(low == i)) for i, name in enumerate(SPLIT_NAMES)},
        "intersections": {"train_validation": 0, "train_test": 0, "validation_test": 0},
    }


def assign_group_splits(origin_id, channel, profile, *, seed: int = 42) -> np.ndarray:
    """Stratify unique origins by channel and set of represented beam profiles.

    Sorting origins makes the assignment invariant to row order or copies of
    detector variants. Very small strata cannot support an intact three-way
    comparison: fail explicitly instead of falling back to a row-wise split.
    """
    origin_id, channel, profile = map(np.asarray, (origin_id, channel, profile))
    if origin_id.ndim != 1 or channel.shape != origin_id.shape or profile.shape != origin_id.shape:
        raise ValueError("origin, channel and profile arrays must be aligned vectors")
    if not np.isin(profile, ("uv", "vis")).all():
        raise ValueError("unsupported profile in grouped split")
    origins, first, inverse = np.unique(origin_id, return_index=True, return_inverse=True)
    group_channel = channel[first]
    if np.any(channel != group_channel[inverse]):
        raise ValueError("one origin cannot belong to multiple channels")
    membership = np.zeros(len(origins), dtype=np.int8)
    np.bitwise_or.at(membership, inverse, np.where(profile == "uv", 1, 2).astype(np.int8))
    strata = np.char.add(np.char.add(group_channel.astype(str), ":"), membership.astype(str))
    rng = np.random.default_rng(seed)
    assigned = np.empty(len(origins), dtype=np.int8)
    for stratum in np.unique(strata):
        indices = np.flatnonzero(strata == stratum)
        if len(indices) < 5:
            raise ValueError(f"insufficient independent groups in {stratum}: {len(indices)}; need >=5 or a separate nested grouped validation study")
        indices = rng.permutation(indices)
        n_hold = len(indices) // 5
        assigned[indices] = 0
        assigned[indices[:n_hold]] = 1
        assigned[indices[n_hold:2 * n_hold]] = 2
    split = assigned[inverse]
    audit_group_splits(origin_id, split)
    return split
