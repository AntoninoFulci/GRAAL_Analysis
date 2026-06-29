"""Train the stage-1 binary BDT (signal vs background).

Reads a features_stage1.npz produced by build_background_features.py,
trains an XGBoost binary:logistic classifier with cross-section sample_weights,
tunes the operating threshold on a validation set via F1-maximisation, and
saves the model + threshold so reconstruct_eta_pi0.py can load them.

Outputs (all in model/ by default):
    bdt_stage1.json       — XGBoost booster
    stage1_threshold.txt  — scalar operating threshold
    stage1_roc.png        — ROC curve (train vs val)
    stage1_feature_importance.png
    stage1_score_dist.png — score distribution signal vs background
    stage1_metrics.txt    — AUC, threshold, precision, recall, F1

Usage:
    python -m analysis.ml.train_bdt_stage1 \\
        --features features_stage1.npz \\
        --out-dir analysis/ml/model
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

try:
    import xgboost as xgb
except ImportError as exc:
    raise ImportError("xgboost required: pip install xgboost") from exc

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    _HAVE_MPL = True
except ImportError:
    _HAVE_MPL = False

from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, precision_recall_fscore_support

from analysis.ml.callbacks import TqdmCallback


def _find_best_threshold(y_true: np.ndarray, scores: np.ndarray) -> float:
    """Find threshold maximising F1 on the provided set."""
    thresholds = np.linspace(0.01, 0.99, 200)
    best_f1, best_thr = -1.0, 0.5
    for thr in thresholds:
        pred = (scores >= thr).astype(int)
        _, _, f1, _ = precision_recall_fscore_support(y_true, pred,
                                                       average="binary",
                                                       zero_division=0)
        if f1 > best_f1:
            best_f1, best_thr = f1, float(thr)
    return best_thr


def train(
    features_path: str,
    out_dir: str = "analysis/ml/model",
    val_fraction: float = 0.2,
    seed: int = 42,
    n_estimators: int = 300,
    max_depth: int = 5,
    learning_rate: float = 0.05,
    subsample: float = 0.8,
    colsample_bytree: float = 0.8,
    min_child_weight: int = 1,
    gamma: float = 0.0,
    device: str = "cpu",
    nthread: int = -1,
    verbose: bool = True,
) -> None:
    data = np.load(features_path)
    X: np.ndarray = data["X"].astype(np.float32)
    y: np.ndarray = data["y"].astype(np.float32)
    w: np.ndarray = data["w"].astype(np.float32)
    feature_names: list[str] = list(data["feature_names"])

    X_tr, X_val, y_tr, y_val, w_tr, w_val = train_test_split(
        X, y, w, test_size=val_fraction, random_state=seed, stratify=y
    )

    callbacks = []
    if verbose:
        callbacks.append(
            TqdmCallback(n_estimators=n_estimators, desc="training", val_metric="auc")
        )

    model = xgb.XGBClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        subsample=subsample,
        colsample_bytree=colsample_bytree,
        min_child_weight=min_child_weight,
        gamma=gamma,
        eval_metric="auc",
        random_state=seed,
        tree_method="hist",
        device=device,
        nthread=nthread,
        callbacks=callbacks,
    )
    model.fit(
        X_tr, y_tr,
        sample_weight=w_tr,
        eval_set=[(X_val, y_val)],
        sample_weight_eval_set=[w_val],
        verbose=False,
    )

    scores_val = model.predict_proba(X_val)[:, 1]
    auc = roc_auc_score(y_val, scores_val, sample_weight=w_val)
    threshold = _find_best_threshold(y_val, scores_val)
    pred_val = (scores_val >= threshold).astype(int)
    p, r, f1, _ = precision_recall_fscore_support(y_val, pred_val,
                                                   average="binary",
                                                   zero_division=0)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    model.save_model(str(out / "bdt_stage1.json"))
    (out / "stage1_threshold.txt").write_text(f"{threshold:.6f}\n")

    metrics_text = (
        f"AUC:       {auc:.4f}\n"
        f"Threshold: {threshold:.4f}\n"
        f"Precision: {p:.4f}\n"
        f"Recall:    {r:.4f}\n"
        f"F1:        {f1:.4f}\n"
        f"N_train:   {len(X_tr)}\n"
        f"N_val:     {len(X_val)}\n"
    )
    (out / "stage1_metrics.txt").write_text(metrics_text)
    print(metrics_text)

    if _HAVE_MPL:
        from sklearn.metrics import roc_curve

        # ROC
        fpr, tpr, _ = roc_curve(y_val, scores_val, sample_weight=w_val)
        fig, ax = plt.subplots()
        ax.plot(fpr, tpr, label=f"AUC={auc:.3f}")
        ax.plot([0, 1], [0, 1], "k--")
        ax.set_xlabel("FPR"); ax.set_ylabel("TPR")
        ax.set_title("Stage-1 BDT ROC")
        ax.legend()
        fig.savefig(str(out / "stage1_roc.png"), dpi=150)
        plt.close(fig)

        # feature importance
        fi = model.feature_importances_
        order = np.argsort(fi)[::-1]
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.barh([feature_names[i] for i in order[:20]][::-1], fi[order[:20]][::-1])
        ax.set_xlabel("Importance (gain)")
        ax.set_title("Stage-1 feature importance (top 20)")
        fig.tight_layout()
        fig.savefig(str(out / "stage1_feature_importance.png"), dpi=150)
        plt.close(fig)

        # score distribution
        fig, ax = plt.subplots()
        ax.hist(scores_val[y_val == 1], bins=50, alpha=0.6, label="signal", density=True)
        ax.hist(scores_val[y_val == 0], bins=50, alpha=0.6, label="background", density=True)
        ax.axvline(threshold, color="red", linestyle="--", label=f"threshold={threshold:.2f}")
        ax.set_xlabel("BDT score"); ax.set_ylabel("Density")
        ax.set_title("Stage-1 score distribution")
        ax.legend()
        fig.savefig(str(out / "stage1_score_dist.png"), dpi=150)
        plt.close(fig)

    print(f"Saved model to {out}/bdt_stage1.json")
    print(f"Operating threshold: {threshold:.4f}")


def _cli() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--features",     default="features_stage1.npz")
    parser.add_argument("--out-dir",      default="analysis/ml/model")
    parser.add_argument("--val-fraction", type=float, default=0.2)
    parser.add_argument("--n-estimators", type=int,   default=300)
    parser.add_argument("--max-depth",    type=int,   default=5)
    parser.add_argument("--lr",           type=float, default=0.05)
    parser.add_argument("--seed",         type=int,   default=42)
    parser.add_argument(
        "--hyperparams", default=None,
        help="JSON from grid_search_stage1.py; overrides --n-estimators, --max-depth, --lr.",
    )
    parser.add_argument("--device",     default="cpu",
                        help="XGBoost device: cpu (default), cuda, mps (future)")
    parser.add_argument("--nthread",    type=int, default=-1,
                        help="XGBoost nthread; -1 = all cores")
    parser.add_argument("--no-verbose", action="store_true",
                        help="Disable per-tree progress bar")
    args = parser.parse_args()

    n_est   = args.n_estimators
    depth   = args.max_depth
    lr      = args.lr
    sub     = 0.8
    col     = 0.8
    mcw     = 1
    gam     = 0.0

    if args.hyperparams:
        import json
        cfg = json.loads(Path(args.hyperparams).read_text())
        n_est = int(cfg.get("n_estimators",    n_est))
        depth = int(cfg.get("max_depth",        depth))
        lr    = float(cfg.get("learning_rate",  lr))
        sub   = float(cfg.get("subsample",      sub))
        col   = float(cfg.get("colsample_bytree", col))
        mcw   = int(cfg.get("min_child_weight", mcw))
        gam   = float(cfg.get("gamma",          gam))
        print(f"Hyperparams from {args.hyperparams}:")
        for k in ("max_depth", "learning_rate", "n_estimators",
                  "subsample", "colsample_bytree", "min_child_weight", "gamma"):
            if k in cfg:
                print(f"  {k}: {cfg[k]}")

    train(
        features_path=args.features,
        out_dir=args.out_dir,
        val_fraction=args.val_fraction,
        seed=args.seed,
        n_estimators=n_est,
        max_depth=depth,
        learning_rate=lr,
        subsample=sub,
        colsample_bytree=col,
        min_child_weight=mcw,
        gamma=gam,
        device=args.device,
        nthread=args.nthread,
        verbose=not args.no_verbose,
    )


if __name__ == "__main__":
    _cli()
