# Architecture

GRAAL Analysis is a file-oriented batch pipeline. ROOT files carry detector,
Monte Carlo, and reconstructed events between stages. NumPy NPZ, JSON, text,
CSV, and PDF files carry training, calibration, provenance, and reporting
artifacts. No server process or database is involved.

## End-to-end flow

```mermaid
flowchart LR
    RAW[Raw detector ROOT files] --> PRE[1. Pre-analysis]
    PRE -->|h80| SEL[2. Event selector]
    SEL -->|h85| BEAM[4. Beam spectrum]
    SEL --> RECO[7. Reconstruction]
    GEN[3. ROOT MC generators] -->|nine mc trees| FEAT[4. Stage-1 feature builder]
    BEAM -->|beam_spectrum.npz| FEAT
    FEAT -->|features_stage1.npz| SEARCH[5. Grid search]
    FEAT --> TRAIN[6. BDT training]
    SEARCH -->|best_hyperparams.json| TRAIN
    TRAIN -->|model + threshold + provenance| GATE[Stage-1 gate]
    GATE --> RECO
    RECO -->|chi2 and BDT ROOT trees| PLOTS[8. Plotting]
    PLOTS --> OUT[PDF and ROOT artifacts]
    PRE --> CAL[Strip-energy and flux calibration]
    MANIFEST[Run manifest] --> CAL
    FLUX[Tagger flux ROOT file] --> CAL
    CAL --> CALOUT[CSV + QA JSON]
```

Stages 4–6 form the training path. Stage 7 consumes its versioned runtime
bundle only for BDT-gated reconstruction; standard χ² reconstruction has no
model dependency.

## Package boundaries

```mermaid
flowchart TD
    COMMON[graal_common\nphysics · I/O · calibration · Stage-1 contracts]
    SELECTOR[event_selector]
    MC[mc_simulation]
    TRAIN[bdt_training\ndataset · training]
    RECOCORE[reconstruction.core\nROOT-free event physics]
    RECORT[reconstruction.runtime\nCLI · ROOT · model adapters]
    PLOTCORE[plots.core\nkinematics · data adapters]
    PLOTS[plots entry points]
    COMMON --> SELECTOR
    COMMON --> MC
    COMMON --> TRAIN
    COMMON --> RECOCORE
    COMMON --> RECORT
    COMMON --> PLOTCORE
    TRAIN --> RECORT
    RECOCORE --> RECORT
    PLOTCORE --> PLOTS
    RECORT --> PLOTS
```

Physical directories remain numbered so pipeline order is visible. Editable
installation maps them to valid Python package names such as `graal_common`,
`bdt_training`, and `reconstruction`.

## Main boundaries

- `00_common/` owns shared physical constants, channel and hypothesis
  registries, photon pairing, ROOT-array helpers, calibration contracts, and
  Stage-1 feature/artifact schemas.
- Numbered stage directories own orchestration and adapters specific to that
  stage.
- `reconstruction/core/` keeps event decisions and fitting independent from
  ROOT; `reconstruction/runtime/` owns ROOT I/O, CLI translation, and model
  loading.
- `plots/core/` separates reusable calculations and ROOT data conversion from
  plot orchestration.
- Tests enforce cross-module schemas where training output becomes runtime
  input.

## External boundaries

ROOT/PyROOT is detector and reconstructed-event storage/runtime boundary.
`uproot` and `awkward` provide array-oriented ROOT access in training and some
plotting paths. XGBoost supplies Stage-1 classifier; NumPy, SciPy,
scikit-learn, and matplotlib support calculation, fitting, evaluation, and
reporting. Pipeline execution calls no remote service or API.

`scripts/sync-wiki.sh` is separate from analysis execution. It uses Git and
GitHub only when a maintainer explicitly publishes in-repository wiki.
