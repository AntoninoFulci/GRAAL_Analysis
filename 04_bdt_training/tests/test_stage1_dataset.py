"""Stage-1 feature-dataset storage and validation contracts."""

from dataclasses import replace
import json
from pathlib import Path

import numpy as np
import pytest

import bdt_training.grid_search_stage1 as grid_search
import bdt_training.dataset.stage1_dataset as stage1_dataset
import bdt_training.train_bdt_stage1 as trainer
from graal_common.stage1.features import FEATURE_NAMES_S1


DATASET_KEYS = {
    "X",
    "y",
    "w",
    "feature_names",
    "signal_channel",
    "hypothesis",
    "signal_prior",
    "beam_reweighted",
}


def _arrays(n: int = 20) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    y = np.tile(np.array([0, 1], dtype=np.int8), n // 2)
    X = np.zeros((n, 26), dtype=np.float32)
    X[:, 0] = y
    w = np.linspace(0.5, 1.5, n, dtype=np.float32)
    return X, y, w


def _dataset():
    X, y, w = _arrays()
    metadata = stage1_dataset.Stage1DatasetMetadata(
        feature_names=tuple(FEATURE_NAMES_S1),
        signal_channel="eta_pi0",
        hypothesis="eta_pi0",
        signal_prior=0.5,
        beam_reweighted=True,
    )
    return stage1_dataset.Stage1Dataset(X=X, y=y, w=w, metadata=metadata)


def _write_old_format(path: Path, **overrides) -> None:
    X, y, w = _arrays()
    values = {
        "X": X,
        "y": y,
        "w": w,
        "feature_names": np.array(FEATURE_NAMES_S1),
        "signal_channel": np.array("eta_pi0"),
        "hypothesis": np.array("eta_pi0"),
    }
    values.update(overrides)
    np.savez(path, **values)


def test_save_load_round_trip_preserves_arrays_metadata_and_exact_keys(tmp_path):
    expected = _dataset()
    path = tmp_path / "features_stage1.npz"

    stage1_dataset.save_stage1_dataset(path, expected)
    actual = stage1_dataset.load_stage1_dataset(path)

    np.testing.assert_array_equal(actual.X, expected.X)
    np.testing.assert_array_equal(actual.y, expected.y)
    np.testing.assert_array_equal(actual.w, expected.w)
    assert actual.metadata == expected.metadata
    with np.load(path) as stored:
        assert set(stored.files) == DATASET_KEYS


def test_loader_accepts_old_format_without_optional_metadata(tmp_path):
    path = tmp_path / "old_features_stage1.npz"
    _write_old_format(path)

    dataset = stage1_dataset.load_stage1_dataset(path)

    assert dataset.metadata.signal_prior is None
    assert dataset.metadata.beam_reweighted is None


@pytest.mark.parametrize("missing", ["signal_channel", "hypothesis"])
def test_missing_identity_metadata_keeps_explicit_failure(tmp_path, missing):
    path = tmp_path / "missing_metadata.npz"
    X, y, w = _arrays()
    values = {
        "X": X,
        "y": y,
        "w": w,
        "feature_names": np.array(FEATURE_NAMES_S1),
        "signal_channel": np.array("eta_pi0"),
        "hypothesis": np.array("eta_pi0"),
    }
    del values[missing]
    np.savez(path, **values)

    with pytest.raises(KeyError, match=missing):
        stage1_dataset.load_stage1_dataset(path)


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"X": np.zeros(26)}, "X must be a 2D array"),
        ({"y": np.zeros((20, 1))}, "y must be a 1D array"),
        ({"w": np.zeros((20, 1))}, "w must be a 1D array"),
        ({"y": np.zeros(19)}, "same number of events"),
        ({"X": np.zeros((20, 25))}, "26 feature columns"),
        (
            {"feature_names": np.array([FEATURE_NAMES_S1])},
            "feature_names must be a 1D array",
        ),
        ({"feature_names": np.array(FEATURE_NAMES_S1[:-1])}, "26 feature names"),
        ({"w": np.full(20, np.nan)}, "weights must be finite"),
        (
            {"signal_channel": np.array(["eta_pi0"])},
            "signal_channel must be a scalar",
        ),
        ({"hypothesis": np.array(["eta_pi0"])}, "hypothesis must be a scalar"),
        ({"signal_channel": np.array("not_a_channel")}, "unknown signal channel"),
        ({"hypothesis": np.array("not_a_hypothesis")}, "unknown hypothesis"),
    ],
)
def test_loader_rejects_malformed_dataset(tmp_path, override, message):
    path = tmp_path / "malformed.npz"
    _write_old_format(path, **override)

    with pytest.raises(ValueError, match=message):
        stage1_dataset.load_stage1_dataset(path)


def test_saver_rejects_non_finite_weights(tmp_path):
    dataset = _dataset()
    bad = replace(dataset, w=np.full(len(dataset.w), np.inf))

    with pytest.raises(ValueError, match="weights must be finite"):
        stage1_dataset.save_stage1_dataset(tmp_path / "bad.npz", bad)


@pytest.mark.parametrize("field", ["signal_prior", "beam_reweighted"])
def test_saver_requires_complete_metadata(tmp_path, field):
    dataset = _dataset()
    metadata = replace(dataset.metadata, **{field: None})

    with pytest.raises(ValueError, match=field):
        stage1_dataset.save_stage1_dataset(
            tmp_path / "incomplete.npz",
            replace(dataset, metadata=metadata),
        )


class _FakeClassifier:
    feature_importances_ = np.zeros(26)

    def __init__(self, **_kwargs):
        pass

    def fit(self, *_args, **_kwargs):
        return self

    def predict_proba(self, X):
        scores = np.where(X[:, 0] > 0.5, 0.9, 0.1)
        return np.column_stack([1.0 - scores, scores])

    def save_model(self, path):
        Path(path).write_text("{}\n")


def test_trainer_accepts_old_format_valid_fixture(tmp_path, monkeypatch):
    features = tmp_path / "old_features_stage1.npz"
    _write_old_format(features)
    monkeypatch.setattr(trainer.xgb, "XGBClassifier", _FakeClassifier)
    monkeypatch.setattr(trainer, "_HAVE_MPL", False)

    output = tmp_path / "model"
    trainer.train(str(features), str(output), n_estimators=1, verbose=False)

    provenance = json.loads((output / "stage1_provenance.json").read_text())
    assert provenance["signal_prior"] is None
    assert provenance["beam_reweighted"] is None


def test_grid_search_accepts_old_format_valid_fixture(tmp_path, monkeypatch):
    features = tmp_path / "old_features_stage1.npz"
    _write_old_format(features)

    def fake_train(*_args, **_kwargs):
        return 0.8, 5

    monkeypatch.setattr(grid_search, "_train_single", fake_train)

    output = tmp_path / "model"
    grid_search.run_search(str(features), str(output), n_iter=1)

    best = json.loads((output / "best_hyperparams.json").read_text())
    assert best["auc"] == 0.8
    assert best["n_estimators"] == 5
