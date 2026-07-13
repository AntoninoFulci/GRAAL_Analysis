import numpy as np
import pytest

from analysis.stage1_gate import Stage1Gate
from analysis_bdt.build_background_features import compute_stage1_features


class FakeModel:
    """Records the feature matrix it was scored on; returns a fixed score."""

    def __init__(self, score):
        self.score = score
        self.seen = None

    def predict_proba(self, X):
        self.seen = X
        return np.array([[1.0 - self.score, self.score]])


def _event():
    """One synthetic event: 4 photons, a proton, a beam. Values are arbitrary."""
    photons = np.array([
        [0.20, 0.10, 0.30, 0.374],
        [-0.15, 0.05, 0.25, 0.297],
        [0.05, -0.20, 0.40, 0.450],
        [-0.10, 0.02, 0.35, 0.365],
    ])
    proton = np.array([0.10, -0.05, 0.30, 0.995])
    beam = np.array([0.0, 0.0, 1.4, 1.4])
    return photons, proton, beam


def test_accepts_when_the_score_is_above_the_threshold():
    gate = Stage1Gate(FakeModel(score=0.9), threshold=0.5)
    assert gate.accepts(*_event()) is True


def test_rejects_when_the_score_is_below_the_threshold():
    gate = Stage1Gate(FakeModel(score=0.1), threshold=0.5)
    assert gate.accepts(*_event()) is False


def test_accepts_exactly_at_the_threshold():
    gate = Stage1Gate(FakeModel(score=0.5), threshold=0.5)
    assert gate.accepts(*_event()) is True


def test_the_model_is_scored_on_the_features_it_was_trained_on():
    # Regression test for the misaligned feature vector: the gate must hand the
    # model exactly what compute_stage1_features produces, in that order.
    model = FakeModel(score=0.9)
    gate = Stage1Gate(model, threshold=0.5)
    photons, proton, beam = _event()

    gate.accepts(photons, proton, beam)

    expected = compute_stage1_features(photons[None], proton[None], beam[None])
    assert model.seen.shape == (1, 24)
    np.testing.assert_allclose(model.seen, expected, rtol=1e-6)


def test_load_raises_when_the_model_is_missing(tmp_path):
    # A missing model must not silently disable the gate: that would turn the
    # BDT run into a chi2 run and make the comparison between them a lie.
    with pytest.raises(FileNotFoundError, match="bdt_stage1.json"):
        Stage1Gate.load(tmp_path)


def test_load_raises_when_the_threshold_is_missing(tmp_path):
    (tmp_path / "bdt_stage1.json").write_text("{}")
    with pytest.raises(FileNotFoundError, match="stage1_threshold.txt"):
        Stage1Gate.load(tmp_path)
