"""Typed storage contract for Stage-1 feature datasets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from graal_common.physics.beam_profiles import get_beam_profile
from graal_common.physics.energy_binning import EnergyBinning
from graal_common.physics.channels import CHANNELS, HYPOTHESES
from graal_common.stage1.features import N_FEATURES_S1


@dataclass(frozen=True)
class Stage1DatasetMetadata:
    """Physics identity and assumptions carried with a feature matrix."""

    feature_names: tuple[str, ...]
    signal_channel: str
    hypothesis: str
    signal_prior: float | None = None
    beam_reweighted: bool | None = None
    beam_profile: str | None = None
    energy_min_gev: float | None = None
    energy_max_gev: float | None = None
    loss_seed: int | None = None
    loss_seed_policy: str | None = None


@dataclass(frozen=True)
class Stage1Rows:
    """Row provenance. Origin is the parent MC file SHA-256 plus original entry.

    Profile and detector variants deliberately do not form part of the origin.
    A stored split is train=0, validation=1, test=2, assigned across profiles.
    """

    origin_id: np.ndarray
    channel: np.ndarray
    profile: np.ndarray
    detector_variant: np.ndarray
    split: np.ndarray | None = None


@dataclass(frozen=True)
class Stage1Dataset:
    """Arrays and metadata consumed by Stage-1 training commands."""

    X: np.ndarray
    y: np.ndarray
    w: np.ndarray
    metadata: Stage1DatasetMetadata
    rows: Stage1Rows | None = None


def _validate_dataset(dataset: Stage1Dataset) -> None:
    X, y, w = dataset.X, dataset.y, dataset.w
    metadata = dataset.metadata

    if X.ndim != 2:
        raise ValueError(f"X must be a 2D array, got shape {X.shape}")
    if y.ndim != 1:
        raise ValueError(f"y must be a 1D array, got shape {y.shape}")
    if w.ndim != 1:
        raise ValueError(f"w must be a 1D array, got shape {w.shape}")
    if len(X) != len(y) or len(X) != len(w):
        raise ValueError(
            "X, y, and w must contain the same number of events, got "
            f"{len(X)}, {len(y)}, and {len(w)}"
        )
    if X.shape[1] != N_FEATURES_S1:
        raise ValueError(
            f"X must contain {N_FEATURES_S1} feature columns, got {X.shape[1]}"
        )
    if len(metadata.feature_names) != N_FEATURES_S1:
        raise ValueError(
            f"dataset must contain {N_FEATURES_S1} feature names, got "
            f"{len(metadata.feature_names)}"
        )
    try:
        weights_are_finite = bool(np.isfinite(w).all())
    except TypeError as exc:
        raise ValueError("weights must be finite numeric values") from exc
    if not weights_are_finite:
        raise ValueError("weights must be finite numeric values")
    if metadata.signal_channel not in CHANNELS:
        raise ValueError(f"unknown signal channel {metadata.signal_channel!r}")
    if metadata.hypothesis not in HYPOTHESES:
        raise ValueError(f"unknown hypothesis {metadata.hypothesis!r}")
    try:
        labels = np.unique(y)
    except TypeError as exc:
        raise ValueError("labels must be exactly 0 and 1") from exc
    if not np.isin(labels, (0, 1)).all():
        raise ValueError("labels must be exactly 0 and 1")
    if not np.array_equal(labels, np.array([0, 1])):
        raise ValueError("dataset must contain both signal and background labels")
    _validate_profile_metadata(metadata)
    if metadata.loss_seed is not None or metadata.loss_seed_policy is not None:
        if metadata.loss_seed is None or metadata.loss_seed_policy is None:
            raise ValueError("loss seed and seed policy must be complete or entirely absent")
        if type(metadata.loss_seed) is not int or not 0 <= metadata.loss_seed < 2**64:
            raise ValueError("loss_seed must be an integer in [0, 2**64)")
        if metadata.loss_seed_policy not in ("legacy", "channel-v1"):
            raise ValueError("unsupported loss seed policy")
    if dataset.rows is not None:
        rows = dataset.rows
        for key in ("origin_id", "channel", "profile", "detector_variant"):
            value = np.asarray(getattr(rows, key))
            if value.shape != y.shape or value.dtype.kind not in "US" or np.any(value == ""):
                raise ValueError(f"{key} must be a nonempty string for every row")
        if not np.isin(rows.channel, tuple(CHANNELS)).all():
            raise ValueError("unknown row channel")
        _, first, inverse = np.unique(rows.origin_id, return_index=True, return_inverse=True)
        if np.any(rows.channel != rows.channel[first][inverse]):
            raise ValueError("origin cannot belong to multiple channels")
        if not np.array_equal(rows.channel == metadata.signal_channel, y == 1):
            raise ValueError("row channel conflicts with class label")
        if not np.isin(rows.profile, ("uv", "vis")).all():
            raise ValueError("unsupported row profile")
        if metadata.beam_profile is not None and np.any(rows.profile != metadata.beam_profile):
            raise ValueError("row profile conflicts with dataset profile")
        if np.any(w < 0) or not np.any(w > 0):
            raise ValueError("weights must be nonnegative with positive total")
        if not np.isfinite(X).all():
            raise ValueError("identified dataset features must be finite")
        if rows.split is not None:
            from bdt_training.dataset.grouped_split import audit_group_splits
            audit_group_splits(rows.origin_id, rows.split)


def _validate_profile_metadata(metadata: Stage1DatasetMetadata) -> None:
    values = (
        metadata.beam_profile,
        metadata.energy_min_gev,
        metadata.energy_max_gev,
    )
    if all(value is None for value in values):
        return
    if any(value is None for value in values):
        raise ValueError(
            "profile energy metadata must be complete or entirely absent"
        )
    profile = get_beam_profile(metadata.beam_profile)
    bounds = np.asarray(
        [metadata.energy_min_gev, metadata.energy_max_gev], dtype=np.float64
    )
    if not np.isfinite(bounds).all():
        raise ValueError("profile energy bounds must be finite")
    if bounds[1] <= bounds[0]:
        raise ValueError("profile energy bounds must be increasing")
    EnergyBinning(tuple(bounds)).validate_profile(profile)


def _scalar(stored, key: str):
    value = np.asarray(stored[key])
    if value.ndim != 0:
        raise ValueError(f"{key} must be a scalar, got shape {value.shape}")
    return value.item()


def load_stage1_dataset(path: str | Path) -> Stage1Dataset:
    """Load a Stage-1 NPZ dataset."""
    with np.load(path, allow_pickle=False) as stored:
        for key in ("signal_channel", "hypothesis"):
            if key not in stored:
                raise KeyError(
                    f"{path} has no {key!r}. It predates the channel registry, "
                    "so which channel it treats as signal is recorded nowhere. "
                    "Rebuild it with bdt_training.build_background_features."
                )

        for key in ("X", "y", "w", "feature_names"):
            if key not in stored:
                raise KeyError(f"{path} has no {key!r}")

        stored_feature_names = np.asarray(stored["feature_names"])
        if stored_feature_names.ndim != 1:
            raise ValueError(
                "feature_names must be a 1D array, got shape "
                f"{stored_feature_names.shape}"
            )

        metadata = Stage1DatasetMetadata(
            feature_names=tuple(str(name) for name in stored_feature_names),
            signal_channel=str(_scalar(stored, "signal_channel")),
            hypothesis=str(_scalar(stored, "hypothesis")),
            signal_prior=(
                float(_scalar(stored, "signal_prior"))
                if "signal_prior" in stored
                else None
            ),
            beam_reweighted=(
                bool(_scalar(stored, "beam_reweighted"))
                if "beam_reweighted" in stored
                else None
            ),
            beam_profile=(
                str(_scalar(stored, "beam_profile"))
                if "beam_profile" in stored
                else None
            ),
            energy_min_gev=(
                float(_scalar(stored, "energy_min_gev"))
                if "energy_min_gev" in stored
                else None
            ),
            energy_max_gev=(
                float(_scalar(stored, "energy_max_gev"))
                if "energy_max_gev" in stored
                else None
            ),
            loss_seed=_scalar(stored, "loss_seed") if "loss_seed" in stored else None,
            loss_seed_policy=(
                _scalar(stored, "loss_seed_policy") if "loss_seed_policy" in stored else None
            ),
        )
        dataset = Stage1Dataset(
            X=np.array(stored["X"], copy=True),
            y=np.array(stored["y"], copy=True),
            w=np.array(stored["w"], copy=True),
            metadata=metadata,
            rows=_load_rows(stored),
        )
    _validate_dataset(dataset)
    return dataset


def _load_rows(stored) -> Stage1Rows | None:
    keys = {"origin_id", "channel", "profile", "detector_variant"}
    present = keys & set(stored.files)
    if not present and "dataset_schema_version" not in stored:
        if "split" in stored:
            raise ValueError("split without origin identity cannot certify independence")
        return None
    if present != keys or "dataset_schema_version" not in stored or _scalar(stored, "dataset_schema_version") != 2:
        raise ValueError("incomplete or unsupported identified dataset schema")
    return Stage1Rows(**{key: np.array(stored[key], copy=True) for key in keys},
                      split=np.array(stored["split"], copy=True) if "split" in stored else None)


def save_stage1_dataset(path: str | Path, dataset: Stage1Dataset) -> None:
    """Write a Stage-1 dataset, adding profile keys only when available."""
    _validate_dataset(dataset)
    metadata = dataset.metadata
    if metadata.signal_prior is None:
        raise ValueError("signal_prior is required when saving a Stage-1 dataset")
    if metadata.beam_reweighted is None:
        raise ValueError("beam_reweighted is required when saving a Stage-1 dataset")
    values = {
        "X": dataset.X,
        "y": dataset.y,
        "w": dataset.w,
        "feature_names": np.array(metadata.feature_names),
        "signal_channel": np.array(metadata.signal_channel),
        "hypothesis": np.array(metadata.hypothesis),
        "signal_prior": np.array(metadata.signal_prior),
        "beam_reweighted": np.array(metadata.beam_reweighted),
    }
    if metadata.beam_profile is not None:
        values.update(
            beam_profile=np.array(metadata.beam_profile),
            energy_min_gev=np.array(metadata.energy_min_gev),
            energy_max_gev=np.array(metadata.energy_max_gev),
        )
    if metadata.loss_seed is not None:
        values.update(
            loss_seed=np.array(metadata.loss_seed, dtype=np.uint64),
            loss_seed_policy=np.array(metadata.loss_seed_policy),
        )
    if dataset.rows is not None:
        values["dataset_schema_version"] = np.array(2)
        for key in ("origin_id", "channel", "profile", "detector_variant"):
            values[key] = getattr(dataset.rows, key)
        if dataset.rows.split is not None:
            values["split"] = dataset.rows.split
    np.savez(path, **values)
