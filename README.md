# GRAAL Analysis

Analysis pipeline for GRAAL photoproduction data, focused on
**γp → pηπ⁰** with η → γγ and π⁰ → γγ. It compares standard photon pairing
by χ² with the same reconstruction preceded by a Stage-1 BDT background gate,
then applies a 6C kinematic fit.

## Requirements

- Python 3.10 or newer, using the interpreter compatible with PyROOT
- CERN ROOT with PyROOT
- Python dependencies from `04_bdt_training/requirements.txt`

```bash
python -m pip install -r 04_bdt_training/requirements.txt
python -m pip install -e .
```

## Run

```bash
./run_pipeline.sh --help
./run_pipeline.sh
```

`run_pipeline.sh` orchestrates eight stages: detector pre-analysis, event
selection, Monte Carlo generation, feature construction, hyperparameter
search, BDT training, reconstruction, and plotting.

## Test

```bash
pytest -q
```

Architecture, data formats, configuration, component guides, and operational
details live in the [project wiki](https://github.com/AntoninoFulci/GRAAL_Analysis/wiki).
