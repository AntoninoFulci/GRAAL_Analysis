"""Typed storage contract for Stage-1 feature datasets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

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


@dataclass(frozen=True)
class Stage1Dataset:
    """Arrays and metadata consumed by Stage-1 training commands."""

    X: np.ndarray
    y: np.ndarray
    w: np.ndarray
    metadata: Stage1DatasetMetadata


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
        )
        dataset = Stage1Dataset(
            X=np.array(stored["X"], copy=True),
            y=np.array(stored["y"], copy=True),
            w=np.array(stored["w"], copy=True),
            metadata=metadata,
        )
    _validate_dataset(dataset)
    return dataset


def save_stage1_dataset(path: str | Path, dataset: Stage1Dataset) -> None:
    """Write a Stage-1 dataset using the established eight-key NPZ schema."""
    _validate_dataset(dataset)
    metadata = dataset.metadata
    if metadata.signal_prior is None:
        raise ValueError("signal_prior is required when saving a Stage-1 dataset")
    if metadata.beam_reweighted is None:
        raise ValueError("beam_reweighted is required when saving a Stage-1 dataset")
    np.savez(
        path,
        X=dataset.X,
        y=dataset.y,
        w=dataset.w,
        feature_names=np.array(metadata.feature_names),
        signal_channel=np.array(metadata.signal_channel),
        hypothesis=np.array(metadata.hypothesis),
        signal_prior=np.array(metadata.signal_prior),
        beam_reweighted=np.array(metadata.beam_reweighted),
    )
