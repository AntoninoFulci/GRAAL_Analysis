"""Stage-1 BDT gate: rejects background-like events before the chi2 pairing.

The feature vector comes from compute_stage1_features — the same function that
built the training set. There is deliberately no second implementation here:
the previous inline one had drifted out of the layout the model was trained on,
and was scoring the model on noise.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from analysis_bdt.build_background_features import compute_stage1_features

DEFAULT_MODEL_DIR = Path(__file__).parent.parent / "05_analysis_bdt" / "model"

MODEL_FILE = "bdt_stage1.json"
THRESHOLD_FILE = "stage1_threshold.txt"


class Stage1Gate:
    """Accept an event if the stage-1 BDT scores it at or above the threshold."""

    def __init__(self, model, threshold: float):
        self.model = model
        self.threshold = float(threshold)

    @classmethod
    def load(cls, model_dir: Path = DEFAULT_MODEL_DIR) -> "Stage1Gate":
        model_dir = Path(model_dir)
        model_path = model_dir / MODEL_FILE
        threshold_path = model_dir / THRESHOLD_FILE

        if not model_path.exists():
            raise FileNotFoundError(
                f"stage-1 model not found: {model_path}. "
                "Train it with run_pipeline.sh, or use reconstruct_eta_pi0_chi2.py "
                "for the analysis without the BDT gate."
            )
        if not threshold_path.exists():
            raise FileNotFoundError(f"stage-1 threshold not found: {threshold_path}")

        import xgboost as xgb

        model = xgb.XGBClassifier()
        model.load_model(str(model_path))
        threshold = float(threshold_path.read_text().strip())

        print(f"[stage1] loaded {model_path}, threshold={threshold:.4f}")
        return cls(model, threshold)

    def accepts(self, photons: np.ndarray, proton: np.ndarray, beam: np.ndarray) -> bool:
        """photons: (4,4); proton, beam: (4,) — all [px, py, pz, E]."""
        X = compute_stage1_features(photons[None], proton[None], beam[None])
        score = float(self.model.predict_proba(X)[0, 1])
        return score >= self.threshold
