# GRAAL Analysis

GRAAL Analysis is a batch analysis pipeline for GRAAL photoproduction data.
Its primary implemented analysis is **γp → pηπ⁰**, with η and π⁰ reconstructed
from four detected photons and a recoil proton.

Two reconstruction paths are produced from the same selected events:

- standard χ² photon pairing;
- the same reconstruction after a Stage-1 BDT rejects background-like events.

Both paths share event guards, pairing, cuts, and the default 6C kinematic fit.
This makes the BDT gate the intended difference between their output samples.

## Pipeline

`run_pipeline.sh` is the main entry point.

| Stage | Responsibility | Primary output |
|---:|---|---|
| 1 | Detector pre-analysis | ROOT tree `h80` |
| 2 | Event preselection | ROOT tree `h85` |
| 3 | Monte Carlo generation | Nine channel files with tree `mc` |
| 4 | Beam measurement and Stage-1 features | `features_stage1.npz` |
| 5 | Hyperparameter search | `best_hyperparams.json` |
| 6 | Stage-1 BDT training | Model, threshold, metrics, provenance |
| 7 | χ² and BDT-gated reconstruction | Reconstructed ROOT trees |
| 8 | Physics plots | PDF and ROOT plot artifacts |

## Documentation map

- [Architecture](architecture)
- [Repository structure](repository-structure)
- [Pipeline and entry points](pipeline)
- [Data and storage](data-and-storage)
- [Configuration](configuration)
- [Development setup](development)
- [Testing](testing)
- [Architectural decisions](architecture-decisions)
- [Extension points](extension-points)

Detailed pages cover each numbered stage, detector cuts, Stage-1 features,
photon pairing, the BDT gate, the kinematic fit, calibration, and plotting.
