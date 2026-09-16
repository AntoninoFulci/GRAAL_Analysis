"""Pure stage-1 fitting contracts."""

import numpy as np
import pytest

import bdt_training.training.stage1_training as stage1_training
import bdt_training.train_bdt_stage1 as trainer
from bdt_training.dataset.stage1_dataset import Stage1Dataset, Stage1DatasetMetadata
from graal_common.stage1.features import FEATURE_NAMES_S1


class _FakeClassifier:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.fit_args = None
        self.fit_kwargs = None

    def fit(self, *args, **kwargs):
        self.fit_args = args
        self.fit_kwargs = kwargs
        return self

    def predict_proba(self, X):
        scores = 0.1 + 0.8 * X[:, 0]
        return np.column_stack([1.0 - scores, scores])


class _DirectScoreClassifier(_FakeClassifier):
    def predict_proba(self, X):
        scores = X[:, 0]
        return np.column_stack([1.0 - scores, scores])


def _dataset() -> Stage1Dataset:
    n_events = 20
    X = np.zeros((n_events, 26), dtype=np.float32)
    X[:, 0] = np.arange(n_events, dtype=np.float32) / (n_events - 1)
    y = np.tile(np.array([0, 1], dtype=np.float32), n_events // 2)
    w = np.arange(1, n_events + 1, dtype=np.float32)
    metadata = Stage1DatasetMetadata(
        feature_names=tuple(FEATURE_NAMES_S1),
        signal_channel="eta_pi0",
        hypothesis="eta_pi0",
        signal_prior=0.5,
        beam_reweighted=True,
    )
    return Stage1Dataset(X=X, y=y, w=w, metadata=metadata)


def test_fit_stage1_preserves_split_parameters_threshold_and_weighted_metrics(
    monkeypatch,
):
    monkeypatch.setattr(stage1_training.xgb, "XGBClassifier", _FakeClassifier)
    config = stage1_training.TrainingConfig(
        val_fraction=0.25,
        seed=7,
        n_estimators=11,
        max_depth=3,
        learning_rate=0.2,
        subsample=0.7,
        colsample_bytree=0.6,
        min_child_weight=2,
        gamma=0.1,
        device="cpu",
        nthread=2,
        verbose=False,
    )

    result = stage1_training.fit_stage1(_dataset(), config)

    np.testing.assert_array_equal(
        result.w_val,
        np.array([13.0, 16.0, 9.0, 14.0, 18.0], dtype=np.float32),
    )
    np.testing.assert_array_equal(
        result.y_val,
        np.array([0.0, 1.0, 0.0, 1.0, 1.0], dtype=np.float32),
    )
    np.testing.assert_allclose(
        result.scores_val,
        np.array(
            [0.60526317, 0.731579, 0.4368421, 0.6473685, 0.8157895],
            dtype=np.float32,
        ),
        rtol=0.0,
        atol=1e-7,
    )
    assert result.threshold == pytest.approx(0.6058793969849247)
    assert result.metrics == {
        "auc": pytest.approx(1.0),
        "precision": pytest.approx(1.0),
        "recall": pytest.approx(1.0),
        "f1": pytest.approx(1.0),
    }
    assert result.n_train == 15
    assert result.n_val == 5
    assert result.feature_metadata == _dataset().metadata

    assert result.model.kwargs == {
        "n_estimators": 11,
        "max_depth": 3,
        "learning_rate": 0.2,
        "subsample": 0.7,
        "colsample_bytree": 0.6,
        "min_child_weight": 2,
        "gamma": 0.1,
        "eval_metric": "auc",
        "random_state": 7,
        "tree_method": "hist",
        "device": "cpu",
        "nthread": 2,
        "callbacks": [],
    }
    assert result.model.fit_kwargs["verbose"] is False
    np.testing.assert_array_equal(
        result.model.fit_kwargs["sample_weight_eval_set"][0],
        result.w_val,
    )


def test_old_training_module_reexports_threshold_helper():
    assert trainer._find_best_threshold is stage1_training._find_best_threshold


def test_fit_stage1_metrics_respect_validation_weights(monkeypatch):
    monkeypatch.setattr(
        stage1_training.xgb,
        "XGBClassifier",
        _DirectScoreClassifier,
    )
    dataset = _dataset()
    dataset.X[:, 0] = 0.1
    dataset.X[[12, 15, 8, 13, 17], 0] = [0.8, 0.9, 0.2, 0.4, 0.7]

    result = stage1_training.fit_stage1(
        dataset,
        stage1_training.TrainingConfig(
            val_fraction=0.25,
            seed=7,
            verbose=False,
        ),
    )

    assert result.threshold == pytest.approx(0.2020603015075377)
    assert result.metrics == {
        "auc": pytest.approx(0.606060606060606),
        "precision": pytest.approx(0.7868852459016393),
        "recall": pytest.approx(1.0),
        "f1": pytest.approx(0.8807339449541285),
    }


def test_verbose_training_keeps_progress_callback(monkeypatch):
    monkeypatch.setattr(stage1_training.xgb, "XGBClassifier", _FakeClassifier)

    result = stage1_training.fit_stage1(
        _dataset(),
        stage1_training.TrainingConfig(n_estimators=17, verbose=True),
    )

    callbacks = result.model.kwargs["callbacks"]
    assert len(callbacks) == 1
    assert callbacks[0]._n == 17
    assert callbacks[0]._desc == "training"
    assert callbacks[0]._metric == "auc"
