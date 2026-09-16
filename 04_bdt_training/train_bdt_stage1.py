"""Train the stage-1 binary BDT (signal vs background).

Reads a features_stage1.npz produced by build_background_features.py,
trains an XGBoost binary:logistic classifier with cross-section sample_weights,
tunes the operating threshold on a validation set via F1-maximisation, and
saves the model + threshold so reconstruct_eta_pi0.py can load them.

Outputs (all in artifacts/stage1/ by default):
    bdt_stage1.json       — XGBoost booster
    stage1_threshold.txt  — scalar operating threshold
    stage1_roc.png        — ROC curve (train vs val)
    stage1_feature_importance.png
    stage1_score_dist.png — score distribution signal vs background
    stage1_metrics.txt    — AUC, threshold, precision, recall, F1

Usage:
    python -m bdt_training.train_bdt_stage1 \\
        --features features_stage1.npz \\
        --out-dir 04_bdt_training/artifacts/stage1
"""

from __future__ import annotations

import argparse
from pathlib import Path

from graal_common.physics.channels import TAGGER_FWHM_GEV, TAGGER_SIGMA_GEV
from graal_common.stage1.artifacts import (
    MODEL_FILE,
    Stage1ArtifactPaths,
    Stage1Provenance,
)

from bdt_training.dataset.stage1_dataset import load_stage1_dataset
from bdt_training.training.stage1_reporting import (
    HAVE_MATPLOTLIB as _HAVE_MPL,
    format_metrics_text,
    render_stage1_plots,
)
from bdt_training.training.stage1_training import (
    TrainingConfig,
    _find_best_threshold,
    fit_stage1,
    xgb,
)


def train(
    features_path: str,
    out_dir: str = "04_bdt_training/artifacts/stage1",
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
    dataset = load_stage1_dataset(features_path)

    # Which channel these features were built to find, and around which two
    # mesons. Refuse features that do not say: the gate has to know, and a
    # default guess here would be a guess about physics.
    signal_channel = dataset.metadata.signal_channel
    hypothesis = dataset.metadata.hypothesis
    # Assumptions, not settings: what prior the classes were mixed at, and
    # whether the MC was shown the beam the experiment actually had. Older
    # feature files predate both; say so rather than implying a value.
    signal_prior = dataset.metadata.signal_prior
    beam_reweighted = dataset.metadata.beam_reweighted
    print(f"signal channel: {signal_channel}   hypothesis: {hypothesis}")
    print(f"signal prior: {signal_prior}   beam reweighted: {beam_reweighted}")

    config = TrainingConfig(
        val_fraction=val_fraction,
        seed=seed,
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        subsample=subsample,
        colsample_bytree=colsample_bytree,
        min_child_weight=min_child_weight,
        gamma=gamma,
        device=device,
        nthread=nthread,
        verbose=verbose,
    )
    result = fit_stage1(dataset, config)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    artifacts = Stage1ArtifactPaths.from_directory(out)

    result.model.save_model(str(artifacts.model))
    artifacts.threshold.write_text(f"{result.threshold:.6f}\n")

    # Travels with the model so the gate can build its features around the same
    # mesons, and refuse when asked to gate something else. A .json booster on
    # its own does not remember what it was taught to look for.
    provenance = Stage1Provenance(
        signal_channel=signal_channel,
        hypothesis=hypothesis,
        signal_prior=signal_prior,
        beam_reweighted=beam_reweighted,
        phase_space_sampling="accept-reject-unweighted",
        tagger_resolution_fwhm_gev=TAGGER_FWHM_GEV,
        tagger_resolution_sigma_gev=TAGGER_SIGMA_GEV,
        detector_covariance_status="legacy-uncalibrated",
        feature_names=result.feature_metadata.feature_names,
    )
    artifacts.provenance.write_text(provenance.to_json())

    metrics_text = format_metrics_text(result)
    artifacts.metrics.write_text(metrics_text)
    print(metrics_text)

    if _HAVE_MPL:
        render_stage1_plots(result, out)

    print(f"Saved model to {out}/{MODEL_FILE}")
    print(f"Operating threshold: {result.threshold:.4f}")


def _cli() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--features",     default="features_stage1.npz")
    parser.add_argument(
        "--out-dir", default="04_bdt_training/artifacts/stage1"
    )
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
