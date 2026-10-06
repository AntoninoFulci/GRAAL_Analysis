# Full UV/VIS pipeline

## Scope

Starts from `pre_analisi_*.root` files containing `h80`. Runs shared flux
calibration, isolated UV/VIS training and reconstruction, separate asymmetry
extraction, then final plot composition. Raw `h70`, resume, grid search,
bootstrap, and sideband correction are outside version one.

## Server setup

```bash
./scripts/setup.sh --mode farm \
  --python /path/to/pyroot-compatible-python \
  --raw-target /path/to/graal_data \
  --pre-target /path/to/pre_analysis
source .venv/bin/activate
```

`--raw-target` remains required by current setup although launcher begins from
pre-analysis. Server needs no queue service or administrator-only daemon.

## Test-data campaign

```bash
python scripts/run_pipeline.py --mode test_data
```

Reads one local UV and one local VIS period, generates 100000 attempted MC
events per required channel, and writes `results/test_data/`.

## Production campaign

```bash
python scripts/run_pipeline.py --mode production
```

Reads all matching UV/VIS pre-analysis periods, generates 1000000 attempted MC
events per required channel, and writes `results/production/`. Calibration
selects every manifest run with target `P`, including multiple proton periods
from the same year. Deuterium runs remain in the shared manifest but do not
enter this proton campaign; target selection uses manifest metadata, not file
names.

## Alternate output root

```bash
python scripts/run_pipeline.py --mode production \
  --output-dir /data/graal/results/campaign-01
```

Destination must be absent or empty. Launcher never deletes previous results.

## Output layout

```text
results/<mode>/
|-- common/
|   `-- flux_calibrated.root
|-- uv/
|   |-- selected/
|   |-- mc/
|   |-- bdt/
|   |   |-- beam_spectrum.npz
|   |   |-- features_stage1.npz
|   |   `-- artifacts/stage1/
|   |-- reco/
|   |   |-- reco_eta_pi0_chi2.root
|   |   `-- reco_eta_pi0_bdt.root
|   `-- beam_asymmetry/
|-- vis/
|   |-- selected/
|   |-- mc/
|   |-- bdt/
|   |   |-- beam_spectrum.npz
|   |   |-- features_stage1.npz
|   |   `-- artifacts/stage1/
|   |-- reco/
|   |   |-- reco_eta_pi0_chi2.root
|   |   `-- reco_eta_pi0_bdt.root
|   `-- beam_asymmetry/
|-- combined/
|   |-- figure4_experimental.pdf
|   |-- figure4_comparison_ajaka2008.pdf
|   |-- comparison_estimators.pdf
|   `-- fit_diagnostics.pdf
`-- pipeline_commands.log
```

## Failure behavior

Preflight checks runtime and required inputs without creating output. Pipeline
stops on first nonzero child exit. Existing warnings remain warnings. Earlier
completed artifacts remain for diagnosis but are not resume checkpoints.

## Acceptance checks

Run `pytest -q`, inspect command log, confirm both Stage-07 ROOT files carry
matching profile metadata/energy edges, and inspect all four combined PDFs.
