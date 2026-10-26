# Commands and configuration

Run from the checkout root with the PyROOT-compatible environment active. These launch commands perform computations and require valid inputs:

```bash
python scripts/run_pipeline.py --mode test_data --phi-bins 12
python scripts/run_pipeline.py --mode production --output-dir results/my-campaign --cpus 4 --extraction-workers 2 --seed 42
```

`--phi-bins` accepts 8, 12 or 16 (default 12); `--best-binning` selects each ratio point among all three fits and overrides that fixed choice. `--energy-config` reads explicit UV/VIS grids. The default grids remain UV `[1.10,1.20,1.30,1.40,1.50]` GeV and VIS `[0.9313,1.10]` GeV. The planner also enables the [core-versus-tail candle test](core-tail-candle-test) for both profiles with a `0.05 GeV` half-width and seed `20261024`. The [common input manifest](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/config/common_inputs.json) and [run quality policy](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/config/run_quality_exclusions.json) are validated, not inferred from selected event counts.

Inspect supported interfaces without starting jobs:

```bash
python scripts/run_preanalysis.py --help
python -m event_selector.select_events --help
python -m bdt_training.build_background_features --help
python 05_reconstruction/reconstruct_eta_pi0_chi2.py --help
python 06_calibration/build_run_manifest.py --help
python 06_calibration/build_strip_energy_flux.py --help
python -m flux_studies.audit_flux --help
python 08_observable_extraction/beam_asymmetry.py --help
python scripts/plot_campaign.py --help
graal-theory --help
```

To change azimuth binning without rebuilding earlier stages, give stage 08 a completed, compatible campaign's reconstruction and calibrated flux. The following VIS example assumes `results/my-campaign` already contains UV and VIS products, and writes a new diagnostic extraction:

```bash
python 08_observable_extraction/beam_asymmetry.py   \
  --raw results/my-campaign/vis/reco/reco_eta_pi0_chi2.root   \
  --raw-bdt results/my-campaign/vis/reco/reco_eta_pi0_bdt.root   \
  --profile vis   \
  --flux-file results/my-campaign/common/flux_calibrated.root   \
  --run-manifest config/run_manifest.csv   \
  --run-quality config/run_quality_exclusions.json   \
  --output-dir results_test/vis-phi16/beam_asymmetry   \
  --estimator both \
  --phi-bins 16 \
  --bootstrap-replicas 0
```

Combine that exact output with the existing UV result:

```bash
python -m observable_extraction.combine_profiles   \
  --uv-root results/my-campaign/uv/beam_asymmetry/beam_asymmetry.root   \
  --vis-root results_test/vis-phi16/beam_asymmetry/beam_asymmetry.root   \
  --published-csv 08_observable_extraction/references/ajaka2008_figure4_digitized.csv   \
  --output-dir results_test/vis-phi16/combined
```

Composition validates profile and finite-bin conventions; historical incompatible files must be regenerated from compatible inputs. `--by-period` produces exact catalog-period and pooled extractions using inclusive run accounting. [Stage 09](09-theory) documents the explicit theory handoff.
