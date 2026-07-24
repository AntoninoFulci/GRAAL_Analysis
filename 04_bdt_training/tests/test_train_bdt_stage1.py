"""Operating-point metrics must respect physical event weights."""

import numpy as np

from bdt_training.train_bdt_stage1 import _find_best_threshold


def test_best_threshold_uses_sample_weight():
    y = np.array([1, 1, 0, 0])
    scores = np.array([0.90, 0.40, 0.80, 0.30])
    weights = np.array([1.0, 20.0, 1.0, 1.0])

    threshold = _find_best_threshold(y, scores, sample_weight=weights)

    assert threshold <= 0.40
