"""XGBoost training callbacks."""
from __future__ import annotations

import xgboost as xgb
from tqdm import tqdm


class TqdmCallback(xgb.callback.TrainingCallback):
    """Displays a tqdm progress bar during XGBoost training.

    Usage::

        cb = TqdmCallback(n_estimators=600, desc="training", val_metric="auc")
        model.fit(..., callbacks=[cb], verbose=False)
    """

    def __init__(
        self,
        n_estimators: int,
        desc: str = "training",
        val_metric: str = "auc",
    ) -> None:
        self._n = n_estimators
        self._desc = desc
        self._metric = val_metric
        self._bar: tqdm | None = None

    def before_training(self, model):
        self._bar = tqdm(total=self._n, desc=self._desc, unit="tree")
        return model

    def after_iteration(self, model, epoch: int, evals_log: dict) -> bool:
        if self._bar is not None:
            self._bar.update(1)
            for _dataset, metrics in evals_log.items():
                if self._metric in metrics:
                    val = metrics[self._metric][-1]
                    self._bar.set_postfix({self._metric: f"{val:.4f}"})
                    break
        return False

    def after_training(self, model):
        if self._bar is not None:
            self._bar.close()
        return model
