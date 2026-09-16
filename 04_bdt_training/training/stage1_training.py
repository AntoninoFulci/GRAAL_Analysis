"""Pure fitting and evaluation engine for the stage-1 BDT."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from sklearn.metrics import precision_recall_fscore_support, roc_auc_score
from sklearn.model_selection import train_test_split

from bdt_training.dataset.stage1_dataset import Stage1Dataset, Stage1DatasetMetadata

try:
    import xgboost as xgb
except ImportError as exc:
    raise ImportError("xgboost required: pip install xgboost") from exc

from bdt_training.training.callbacks import TqdmCallback


@dataclass(frozen=True)
class TrainingConfig:
    """Configuration previously exposed as arguments to ``train``."""

    val_fraction: float = 0.2
    seed: int = 42
    n_estimators: int = 300
    max_depth: int = 5
    learning_rate: float = 0.05
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    min_child_weight: int = 1
    gamma: float = 0.0
    device: str = "cpu"
    nthread: int = -1
    verbose: bool = True


@dataclass(frozen=True)
class TrainingResult:
    """Model and validation outputs needed for publication and reporting."""

    model: Any
    y_val: np.ndarray
    w_val: np.ndarray
    scores_val: np.ndarray
    threshold: float
    metrics: dict[str, float]
    feature_metadata: Stage1DatasetMetadata
    n_train: int
    n_val: int


def _find_best_threshold(
    y_true: np.ndarray,
    scores: np.ndarray,
    sample_weight: np.ndarray | None = None,
) -> float:
    """Find threshold maximising F1 on the provided set."""
    thresholds = np.linspace(0.01, 0.99, 200)
    best_f1, best_thr = -1.0, 0.5
    for thr in thresholds:
        pred = (scores >= thr).astype(int)
        _, _, f1, _ = precision_recall_fscore_support(
            y_true,
            pred,
            average="binary",
            sample_weight=sample_weight,
            zero_division=0,
        )
        if f1 > best_f1:
            best_f1, best_thr = f1, float(thr)
    return best_thr


def fit_stage1(dataset: Stage1Dataset, config: TrainingConfig) -> TrainingResult:
    """Fit and evaluate stage-1 without filesystem or plotting side effects."""
    X = dataset.X.astype(np.float32)
    y = dataset.y.astype(np.float32)
    w = dataset.w.astype(np.float32)

    X_tr, X_val, y_tr, y_val, w_tr, w_val = train_test_split(
        X,
        y,
        w,
        test_size=config.val_fraction,
        random_state=config.seed,
        stratify=y,
    )

    callbacks = []
    if config.verbose:
        callbacks.append(
            TqdmCallback(
                n_estimators=config.n_estimators,
                desc="training",
                val_metric="auc",
            )
        )

    model = xgb.XGBClassifier(
        n_estimators=config.n_estimators,
        max_depth=config.max_depth,
        learning_rate=config.learning_rate,
        subsample=config.subsample,
        colsample_bytree=config.colsample_bytree,
        min_child_weight=config.min_child_weight,
        gamma=config.gamma,
        eval_metric="auc",
        random_state=config.seed,
        tree_method="hist",
        device=config.device,
        nthread=config.nthread,
        callbacks=callbacks,
    )
    model.fit(
        X_tr,
        y_tr,
        sample_weight=w_tr,
        eval_set=[(X_val, y_val)],
        sample_weight_eval_set=[w_val],
        verbose=False,
    )

    scores_val = model.predict_proba(X_val)[:, 1]
    auc = roc_auc_score(y_val, scores_val, sample_weight=w_val)
    threshold = _find_best_threshold(y_val, scores_val, sample_weight=w_val)
    pred_val = (scores_val >= threshold).astype(int)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_val,
        pred_val,
        average="binary",
        sample_weight=w_val,
        zero_division=0,
    )

    return TrainingResult(
        model=model,
        y_val=y_val,
        w_val=w_val,
        scores_val=scores_val,
        threshold=threshold,
        metrics={
            "auc": float(auc),
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
        },
        feature_metadata=dataset.metadata,
        n_train=len(X_tr),
        n_val=len(X_val),
    )
