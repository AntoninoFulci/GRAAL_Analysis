import numpy as np
import pytest

from analysis.stage1_gate import Stage1Gate
from analysis_bdt.build_background_features import compute_stage1_features


class FakeModel:
    """Records the feature matrix it was scored on; returns fixed scores.

    One row of scores per input row, the way a real model does — the gate asks
    about a whole chunk at once.
    """

    def __init__(self, *scores):
        self.scores = np.asarray(scores, dtype=float)
        self.seen = None

    def predict_proba(self, X):
        self.seen = X
        assert len(X) == len(self.scores), (
            f"the gate asked about {len(X)} events but this fake was primed "
            f"with {len(self.scores)} scores"
        )
        return np.column_stack([1.0 - self.scores, self.scores])


def _events(n=1):
    """n synthetic events: 4 photons, a proton, a beam each. Values arbitrary."""
    photons = np.array([
        [0.20, 0.10, 0.30, 0.374],
        [-0.15, 0.05, 0.25, 0.297],
        [0.05, -0.20, 0.40, 0.450],
        [-0.10, 0.02, 0.35, 0.365],
    ])
    proton = np.array([0.10, -0.05, 0.30, 0.995])
    beam = np.array([0.0, 0.0, 1.4, 1.4])
    return (
        np.repeat(photons[None], n, axis=0),
        np.repeat(proton[None], n, axis=0),
        np.repeat(beam[None], n, axis=0),
    )


def test_accepts_when_the_score_is_above_the_threshold():
    gate = Stage1Gate(FakeModel(0.9), threshold=0.5)
    assert gate.accepts_many(*_events()).tolist() == [True]


def test_rejects_when_the_score_is_below_the_threshold():
    gate = Stage1Gate(FakeModel(0.1), threshold=0.5)
    assert gate.accepts_many(*_events()).tolist() == [False]


def test_each_event_in_a_chunk_gets_its_own_answer_in_order():
    # The whole point of batching: one call, one verdict per event, in order.
    # A gate that returned a single verdict for the chunk, or shuffled them,
    # would pass every other test in this file.
    gate = Stage1Gate(FakeModel(0.9, 0.1, 0.7, 0.2), threshold=0.5)
    assert gate.accepts_many(*_events(4)).tolist() == [True, False, True, False]


def test_accepts_exactly_at_the_threshold():
    gate = Stage1Gate(FakeModel(0.5), threshold=0.5)
    assert gate.accepts_many(*_events()).tolist() == [True]


def test_the_model_is_scored_on_the_features_it_was_trained_on():
    # Regression test for the misaligned feature vector: the gate must hand the
    # model exactly what compute_stage1_features produces, in that order.
    model = FakeModel(0.9, 0.9, 0.9)
    gate = Stage1Gate(model, threshold=0.5)
    photons, protons, beams = _events(3)

    gate.accepts_many(photons, protons, beams)

    expected = compute_stage1_features(photons, protons, beams)
    assert model.seen.shape == (3, 24)
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
