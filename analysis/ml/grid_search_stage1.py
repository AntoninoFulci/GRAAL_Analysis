"""Hyperparameter grid search for the stage-1 BDT.

Uses a fixed train/val split and XGBoost early stopping to find the best
combination of tree depth, learning rate, and regularisation.  Saves the best
configuration to a JSON file alongside a summary CSV.

Usage:
    python -m analysis.ml.grid_search_stage1 \\
        --features features_stage1.npz \\
        --out-dir analysis/ml/model \\
        [--n-iter 30] [--seed 42]

By default runs a randomised search (n_iter samples from the grid) because
full grid search (3×4×3×3 = 108 combos × training time) is prohibitive.
Pass --full-grid to enumerate all combinations.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import random
import time
from pathlib import Path
from typing import Any

import numpy as np

try:
    import xgboost as xgb
except ImportError as exc:
    raise ImportError("xgboost required: pip install xgboost") from exc

from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split


_PARAM_GRID: dict[str, list] = {
    "max_depth":        [3, 4, 5, 6],
    "learning_rate":    [0.05, 0.10, 0.15, 0.20],
    "subsample":        [0.7, 0.8, 1.0],
    "colsample_bytree": [0.7, 0.8, 1.0],
    "min_child_weight": [1, 5, 20],
    "gamma":            [0.0, 0.1, 0.3],
}

# Cap at 400 trees; early stopping at 20 rounds keeps configs fast.
# lr=0.01 excluded: it needs 500+ trees to converge → prohibitively slow.
_N_ESTIMATORS_MAX = 400
_EARLY_STOPPING_ROUNDS = 20


def _train_single(
    X_tr: np.ndarray,
    y_tr: np.ndarray,
    w_tr: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    w_val: np.ndarray,
    params: dict[str, Any],
    seed: int,
) -> tuple[float, int]:
    """Train one XGBoost config; return (val_auc, best_n_estimators)."""
    model = xgb.XGBClassifier(
        n_estimators=_N_ESTIMATORS_MAX,
        eval_metric="auc",
        random_state=seed,
        tree_method="hist",
        early_stopping_rounds=_EARLY_STOPPING_ROUNDS,
        **params,
    )
    model.fit(
        X_tr, y_tr,
        sample_weight=w_tr,
        eval_set=[(X_val, y_val)],
        sample_weight_eval_set=[w_val],
        verbose=False,
    )
    scores = model.predict_proba(X_val)[:, 1]
    auc = float(roc_auc_score(y_val, scores, sample_weight=w_val))
    best_n = int(model.best_iteration) + 1
    return auc, best_n


def run_search(
    features_path: str,
    out_dir: str = "analysis/ml/model",
    n_iter: int = 30,
    full_grid: bool = False,
    val_fraction: float = 0.20,
    seed: int = 42,
) -> None:
    rng_py = random.Random(seed)

    print(f"Loading features from {features_path} …")
    data = np.load(features_path)
    X: np.ndarray = data["X"].astype(np.float32)
    y: np.ndarray = data["y"].astype(np.float32)
    w: np.ndarray = data["w"].astype(np.float32)
    print(f"  {len(X)} events  ({(y==1).sum()} signal, {(y==0).sum()} background)")

    X_tr, X_val, y_tr, y_val, w_tr, w_val = train_test_split(
        X, y, w, test_size=val_fraction, random_state=seed, stratify=y
    )
    print(f"  Train: {len(X_tr)}  Val: {len(X_val)}")

    all_keys = list(_PARAM_GRID.keys())
    all_combos = list(itertools.product(*[_PARAM_GRID[k] for k in all_keys]))
    candidates = [dict(zip(all_keys, combo)) for combo in all_combos]
    if not full_grid:
        rng_py.shuffle(candidates)
        candidates = candidates[:n_iter]

    print(f"\nSearching {len(candidates)} configurations …\n")

    results: list[dict] = []
    best_auc = -1.0
    best_cfg: dict = {}

    for i, cfg in enumerate(candidates):
        t0 = time.time()
        try:
            auc, n_est = _train_single(X_tr, y_tr, w_tr, X_val, y_val, w_val, cfg, seed)
        except Exception as exc:
            print(f"  [{i+1}/{len(candidates)}] FAILED: {exc}")
            continue
        elapsed = time.time() - t0
        row = {"auc": auc, "n_estimators": n_est, "time_s": round(elapsed, 1), **cfg}
        results.append(row)

        marker = " *" if auc > best_auc else ""
        print(
            f"  [{i+1:3d}/{len(candidates)}] AUC={auc:.4f}  n_est={n_est:4d}"
            f"  depth={cfg['max_depth']}  lr={cfg['learning_rate']:.3f}"
            f"  sub={cfg['subsample']}  col={cfg['colsample_bytree']}"
            f"  mcw={cfg['min_child_weight']}  gam={cfg['gamma']}"
            f"  ({elapsed:.0f}s){marker}",
            flush=True,
        )
        if auc > best_auc:
            best_auc = auc
            best_cfg = dict(row)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    results.sort(key=lambda r: r["auc"], reverse=True)

    csv_path = out / "grid_search_results.csv"
    if results:
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
            writer.writeheader()
            writer.writerows(results)
        print(f"\nResults saved to {csv_path}")

    best_json_path = out / "best_hyperparams.json"
    if best_cfg:
        with open(best_json_path, "w") as f:
            json.dump(best_cfg, f, indent=2)
        print(f"Best config saved to {best_json_path}")

    print(f"\n=== Best configuration ===")
    print(f"  AUC:            {best_auc:.4f}")
    if best_cfg:
        for k in all_keys + ["n_estimators"]:
            if k in best_cfg:
                print(f"  {k:<20s}: {best_cfg[k]}")


def _cli() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--features",     default="features_stage1.npz")
    parser.add_argument("--out-dir",      default="analysis/ml/model")
    parser.add_argument("--n-iter",       type=int, default=30,
                        help="Random configs to try (ignored with --full-grid)")
    parser.add_argument("--full-grid",    action="store_true",
                        help="Enumerate all combinations (slow)")
    parser.add_argument("--val-fraction", type=float, default=0.20)
    parser.add_argument("--seed",         type=int, default=42)
    args = parser.parse_args()

    run_search(
        features_path=args.features,
        out_dir=args.out_dir,
        n_iter=args.n_iter,
        full_grid=args.full_grid,
        val_fraction=args.val_fraction,
        seed=args.seed,
    )


if __name__ == "__main__":
    _cli()
