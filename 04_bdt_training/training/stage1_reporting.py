"""Text and plot reporting for stage-1 training results."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from sklearn.metrics import roc_curve

from bdt_training.training.stage1_training import TrainingResult

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    HAVE_MATPLOTLIB = True
except ImportError:
    HAVE_MATPLOTLIB = False


def format_metrics_text(result: TrainingResult) -> str:
    """Format the established stage-1 metrics report."""
    metadata = result.feature_metadata
    metrics = result.metrics
    return (
        f"Signal:    {metadata.signal_channel}\n"
        f"Hypothesis:{metadata.hypothesis}\n"
        f"Prior:     {metadata.signal_prior}  (a training choice, not a cross-section)\n"
        f"Beam rewt: {metadata.beam_reweighted}\n"
        f"AUC:       {metrics['auc']:.4f}\n"
        f"Threshold: {result.threshold:.4f}\n"
        f"Precision: {metrics['precision']:.4f}\n"
        f"Recall:    {metrics['recall']:.4f}\n"
        f"F1:        {metrics['f1']:.4f}\n"
        f"N_train:   {result.n_train}\n"
        f"N_val:     {result.n_val}\n"
    )


def render_stage1_plots(result: TrainingResult, out_dir: str | Path) -> None:
    """Render the established stage-1 validation plots."""
    if not HAVE_MATPLOTLIB:
        raise RuntimeError("Matplotlib is required to render stage-1 plots")

    out = Path(out_dir)
    metrics = result.metrics
    y_val = result.y_val
    w_val = result.w_val
    scores_val = result.scores_val

    fpr, tpr, _ = roc_curve(y_val, scores_val, sample_weight=w_val)
    fig, ax = plt.subplots()
    ax.plot(fpr, tpr, label=f"AUC={metrics['auc']:.3f}")
    ax.plot([0, 1], [0, 1], "k--")
    ax.set_xlabel("FPR")
    ax.set_ylabel("TPR")
    ax.set_title("Stage-1 BDT ROC")
    ax.legend()
    fig.savefig(str(out / "stage1_roc.png"), dpi=150)
    plt.close(fig)

    feature_names = result.feature_metadata.feature_names
    feature_importances = result.model.feature_importances_
    order = np.argsort(feature_importances)[::-1]
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.barh(
        [feature_names[i] for i in order[:20]][::-1],
        feature_importances[order[:20]][::-1],
    )
    ax.set_xlabel("Importance (gain)")
    ax.set_title("Stage-1 feature importance (top 20)")
    fig.tight_layout()
    fig.savefig(str(out / "stage1_feature_importance.png"), dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots()
    ax.hist(scores_val[y_val == 1], bins=50, alpha=0.6, label="signal", density=True)
    ax.hist(
        scores_val[y_val == 0],
        bins=50,
        alpha=0.6,
        label="background",
        density=True,
    )
    ax.axvline(
        result.threshold,
        color="red",
        linestyle="--",
        label=f"threshold={result.threshold:.2f}",
    )
    ax.set_xlabel("BDT score")
    ax.set_ylabel("Density")
    ax.set_title("Stage-1 score distribution")
    ax.legend()
    fig.savefig(str(out / "stage1_score_dist.png"), dpi=150)
    plt.close(fig)
