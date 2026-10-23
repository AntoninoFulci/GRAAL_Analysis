# Stage 04: BDT training

The training chain measures the selected beam spectrum, builds weighted MC features, optionally searches hyperparameters, and trains the Stage-1 gate. Public entry points are `bdt_training.beam_spectrum`, `bdt_training.build_background_features`, `bdt_training.grid_search_stage1`, and `bdt_training.train_bdt_stage1`; each supports `--help`.

[00_common/stage1/features.py](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/00_common/stage1/features.py) owns the exact 26-feature order used for training and inference. Features include six two-photon masses, pairing hypotheses, missing quantities, photon-energy/angular summaries and proton kinematics. The feature missing mass uses beam + target − measured proton; reconstruction's recoil missing mass uses beam + target − mesons. They are distinct quantities.

Only four surviving photons enter the feature sample; photon order is randomized by the established seed convention. Channel/beam/acceptance weights and photon-loss handling are shared with the existing dataset contract. The UV and VIS training domains remain explicit. [Bundled hyperparameters](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/04_bdt_training/artifacts/stage1/best_hyperparams.json) are versioned inputs, not permission to bypass provenance validation.

The runtime bundle includes the model, operating threshold, hypothesis, feature names and order, beam coverage and provenance. Stage 05 rejects incompatible bundles. Validation-derived threshold/metrics are not an untouched final physics test. Weighted ROC, score and feature diagnostics do not certify signal efficiencies or unknown channel normalizations.

[Scientific status](status) records the unresolved VIS central-proton topology, extended/shared-domain validation, background efficiencies and correlated inference.
