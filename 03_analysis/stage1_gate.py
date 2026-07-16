"""Stage-1 BDT gate: rejects background-like events before the chi2 pairing.

The feature vector comes from compute_stage1_features — the same function that
built the training set. There is deliberately no second implementation here:
the previous inline one had drifted out of the layout the model was trained on,
and was scoring the model on noise.

For the same reason the gate does not assume which mesons the model was trained
against. The trainer stamps the signal channel and the hypothesis next to the
model, and the gate reads them back and builds its features around those. A
model trained to find eta+pi0 and asked to gate a 2pi0 reconstruction would
otherwise score happily and mean nothing.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from graal_common.channels import ETA_PI0_HYP, HYPOTHESES, Hypothesis
from analysis_bdt.build_background_features import compute_stage1_features

DEFAULT_MODEL_DIR = Path(__file__).parent.parent / "05_analysis_bdt" / "model"

MODEL_FILE = "bdt_stage1.json"
THRESHOLD_FILE = "stage1_threshold.txt"
PROVENANCE_FILE = "stage1_provenance.json"


class Stage1Gate:
    """Accept an event if the stage-1 BDT scores it at or above the threshold."""

    def __init__(
        self,
        model,
        threshold: float,
        hypothesis: Hypothesis = ETA_PI0_HYP,
        signal_channel: str = "eta_pi0",
    ):
        self.model = model
        self.threshold = float(threshold)
        self.hypothesis = hypothesis
        self.signal_channel = signal_channel

    @classmethod
    def load(cls, model_dir: Path = DEFAULT_MODEL_DIR) -> "Stage1Gate":
        model_dir = Path(model_dir)
        model_path = model_dir / MODEL_FILE
        threshold_path = model_dir / THRESHOLD_FILE
        provenance_path = model_dir / PROVENANCE_FILE

        if not model_path.exists():
            raise FileNotFoundError(
                f"stage-1 model not found: {model_path}. "
                "Train it with run_pipeline.sh, or use reconstruct_eta_pi0_chi2.py "
                "for the analysis without the BDT gate."
            )
        if not threshold_path.exists():
            raise FileNotFoundError(f"stage-1 threshold not found: {threshold_path}")
        if not provenance_path.exists():
            raise FileNotFoundError(
                f"stage-1 provenance not found: {provenance_path}. It records which "
                "channel the model was trained to find and which mesons its features "
                "were built around; without it the gate cannot know what it is "
                "gating. Retrain with analysis_bdt.train_bdt_stage1 to produce it."
            )

        import xgboost as xgb

        model = xgb.XGBClassifier()
        model.load_model(str(model_path))
        threshold = float(threshold_path.read_text().strip())

        provenance = json.loads(provenance_path.read_text())
        hypothesis = HYPOTHESES[provenance["hypothesis"]]
        signal_channel = str(provenance["signal_channel"])

        print(
            f"[stage1] loaded {model_path}, threshold={threshold:.4f}, "
            f"signal={signal_channel}, hypothesis={hypothesis.name}"
        )
        return cls(model, threshold, hypothesis, signal_channel)

    def check_hypothesis(self, expected: Hypothesis) -> None:
        """Refuse to gate a reconstruction the model was not trained for.

        The gate exists so that the only difference between the chi2 run and the
        BDT run is the gate. A model taught to recognise a different final state
        still returns a score for every event, and that score would quietly
        become the difference instead.
        """
        if self.hypothesis.name != expected.name:
            raise ValueError(
                f"this stage-1 model was trained on the {self.hypothesis.name!r} "
                f"hypothesis (signal channel {self.signal_channel!r}), but the "
                f"reconstruction is asking it about {expected.name!r}. Train a "
                f"model for that channel first: build_background_features "
                f"--signal-channel <ch> --hypothesis {expected.name}"
            )

    def accepts_many(
        self, photons: np.ndarray, protons: np.ndarray, beams: np.ndarray
    ) -> np.ndarray:
        """Score a whole chunk of events at once.

        photons: (N,4,4); protons, beams: (N,4) — all [px, py, pz, E].
        Returns an (N,) bool array; True keeps the event.

        Asked one event at a time this cost 0.335 ms each — 0.098 building the
        features, 0.237 calling the model — and almost none of that was the model
        thinking. It was per-call overhead, and it dominated: on 17M events the
        gate alone was 75 minutes of the 85 the whole chain took. numpy and
        xgboost both amortise that away over a chunk, together by a factor of
        roughly 300.
        """
        X = compute_stage1_features(photons, protons, beams, self.hypothesis)
        scores = self.model.predict_proba(X)[:, 1]
        return scores >= self.threshold
