"""Integration test for TqdmCallback — verifies XGBoost integration without errors."""
from __future__ import annotations

import numpy as np
import xgboost as xgb


def _tiny_dataset(n: int = 200, seed: int = 0):
    rng = np.random.default_rng(seed)
    X = rng.standard_normal((n, 5)).astype(np.float32)
    y = (X[:, 0] + rng.standard_normal(n) * 0.5 > 0).astype(np.float32)
    return X, y


def test_tqdm_callback_completes_training():
    """TqdmCallback should allow XGBoost to train to completion without error."""
    from analysis.ml.callbacks import TqdmCallback

    X, y = _tiny_dataset()
    X_tr, X_val = X[:160], X[160:]
    y_tr, y_val = y[:160], y[160:]

    cb = TqdmCallback(n_estimators=10, desc="test", val_metric="auc")
    # XGBoost >=2.0 requires callbacks to be passed via the constructor, not fit().
    model = xgb.XGBClassifier(
        n_estimators=10,
        eval_metric="auc",
        random_state=42,
        tree_method="hist",
        verbosity=0,
        callbacks=[cb],
    )
    model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)

    assert model.n_estimators == 10


def test_tqdm_callback_after_iteration_returns_false():
    """after_iteration must return False to not stop training early."""
    from analysis.ml.callbacks import TqdmCallback

    cb = TqdmCallback(n_estimators=5, desc="test", val_metric="auc")

    class _FakeModel:
        pass

    cb.before_training(_FakeModel())
    fake_evals_log = {"validation_0": {"auc": [0.95, 0.96]}}
    result = cb.after_iteration(_FakeModel(), epoch=1, evals_log=fake_evals_log)
    assert result is False
    cb.after_training(_FakeModel())


def test_tqdm_callback_no_crash_missing_metric():
    """TqdmCallback should not crash if val_metric is not in evals_log."""
    from analysis.ml.callbacks import TqdmCallback

    cb = TqdmCallback(n_estimators=5, desc="test", val_metric="auc")

    class _FakeModel:
        pass

    cb.before_training(_FakeModel())
    cb.after_iteration(_FakeModel(), epoch=0, evals_log={"validation_0": {"logloss": [0.5]}})
    cb.after_training(_FakeModel())
