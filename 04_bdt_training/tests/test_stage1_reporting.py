"""Stage-1 reporting contracts."""

import numpy as np
import pytest

from bdt_training.dataset.stage1_dataset import Stage1DatasetMetadata
from bdt_training.training.stage1_reporting import (
    HAVE_MATPLOTLIB,
    format_metrics_text,
    render_stage1_plots,
)
from bdt_training.training.stage1_training import TrainingResult
from graal_common.stage1.features import FEATURE_NAMES_S1


class _Model:
    feature_importances_ = np.arange(26, dtype=np.float32)


def _result() -> TrainingResult:
    return TrainingResult(
        model=_Model(),
        y_val=np.array([0.0, 1.0, 0.0, 1.0], dtype=np.float32),
        w_val=np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32),
        scores_val=np.array([0.1, 0.9, 0.2, 0.8], dtype=np.float32),
        threshold=0.4,
        metrics={"auc": 1.0, "precision": 0.8, "recall": 0.75, "f1": 0.7742},
        feature_metadata=Stage1DatasetMetadata(
            feature_names=tuple(FEATURE_NAMES_S1),
            signal_channel="eta_pi0",
            hypothesis="eta_pi0",
            signal_prior=0.5,
            beam_reweighted=True,
        ),
        n_train=16,
        n_val=4,
    )


def test_metrics_text_preserves_publication_format():
    assert format_metrics_text(_result()) == (
        "Signal:    eta_pi0\n"
        "Hypothesis:eta_pi0\n"
        "Prior:     0.5  (a training choice, not a cross-section)\n"
        "Beam rewt: True\n"
        "AUC:       1.0000\n"
        "Threshold: 0.4000\n"
        "Precision: 0.8000\n"
        "Recall:    0.7500\n"
        "F1:        0.7742\n"
        "N_train:   16\n"
        "N_val:     4\n"
    )


@pytest.mark.skipif(not HAVE_MATPLOTLIB, reason="Matplotlib not installed")
def test_plot_renderer_preserves_output_filenames(tmp_path):
    render_stage1_plots(_result(), tmp_path)

    expected = {
        "stage1_roc.png",
        "stage1_feature_importance.png",
        "stage1_score_dist.png",
    }
    assert {path.name for path in tmp_path.iterdir()} == expected
    assert all((tmp_path / name).stat().st_size > 0 for name in expected)
