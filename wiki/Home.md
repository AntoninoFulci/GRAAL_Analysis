# GRAAL Analysis

GRAAL Analysis is a file-oriented scientific pipeline for the photoproduction
reaction gamma p -> p eta pi0, with eta and pi0 reconstructed from four
photons and a recoil-proton candidate. It compares standard chi-square photon
pairing with the same reconstruction preceded by a Stage-1 BDT background
gate, then makes the calibrated samples available to beam-asymmetry extraction.

The repository contains detector pre-analysis, event selection, Monte Carlo
generation, classifier training, reconstruction, beam calibration, observable
extraction, and diagnostic plots. Stages exchange validated files; there is no
database, long-running service, or central pipeline command.

## Choose Your Path

| If you want to... | Start here | Continue with |
|---|---|---|
| Install the project and validate an environment | [Getting started](getting-started) | [Commands and configuration](commands-and-configuration) |
| Understand the physics objective | [Scientific foundations](scientific-foundations) | [Physics channels](physics-channels), [photon pairing](photon-pairing) |
| Run the analysis in the correct order | [End-to-end workflow](workflow) | Stage pages 01 through 07 |
| Understand package and data boundaries | [Architecture](architecture) | [Repository structure](repository-structure), [data and artifacts](data-and-artifacts) |
| Change or extend code safely | [Development](development) | [Testing](testing), [architectural decisions](architecture-decisions) |
| Diagnose a failed run | [Troubleshooting](troubleshooting) | The relevant stage page |

## Pipeline at a Glance

| Area | Responsibility | Primary boundary |
|---|---|---|
| `00_common/` | Shared physics, I/O, filesystem, and Stage-1 contracts | Imported Python APIs |
| `01_pre_analysis/` | Detector-level pre-analysis and cut dispatch | ROOT tree `h80` |
| `02_event_selector/` | Reconstruction-oriented event preselection | ROOT tree `h85` |
| `03_mc_simulation/` | Registered Monte Carlo channel generation | ROOT tree `mc` |
| `04_bdt_training/` | Beam spectrum, features, weights, search, and classifier | NPZ plus model bundle |
| `05_reconstruction/` | Chi-square and BDT-gated event reconstruction | Reconstructed ROOT trees |
| `06_calibration/` | Run manifest and strip-energy/flux calibration | CSV, JSON, and ROOT calibration products |
| `07_observable_extraction/` | Beam-asymmetry estimation and systematic treatment | ROOT and PDF products |
| `plots/` | Reconstruction diagnostics and publication-oriented figures | PDF and ROOT plot artifacts |

The numbered directories communicate order, not an automatic scheduler. Run
the stage entry points explicitly and validate their outputs before continuing.

## Documentation Map

- [Architecture](architecture) explains package and external boundaries.
- [End-to-end workflow](workflow) traces every major artifact between stages.
- [Data and artifacts](data-and-artifacts) records persisted schemas and owners.
- [Commands and configuration](commands-and-configuration) consolidates CLI usage.
- [Plotting and diagnostics](plotting-and-diagnostics) maps final consumers.
- [Known limitations](known-limitations) separates present constraints from
  supported behavior.

Every component page follows the same pattern where applicable: scientific
role, inputs, processing, invariants, outputs, commands, failures,
implementation map, tests, and limitations.
