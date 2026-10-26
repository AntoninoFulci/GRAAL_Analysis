# Core-versus-tail candle test

The candle test is a stability check on the nominal post-BDT event sample. It compares beam asymmetries extracted from two disjoint samples with the same number of events:

- **core:** both raw candidate masses are inside their inclusive windows, `|M(eta)-m_eta| <= 0.05 GeV` and `|M(pi0)-m_pi0| <= 0.05 GeV`;
- **tails:** the finite-mass complement, so at least one candidate mass is outside its window.

If the full core contains more events than the tails, the workflow draws a deterministic random subset of the core without replacement. The default campaign seed is `20261024`. Non-finite candidate masses belong to neither sample and are counted separately in the ROOT provenance.

The equality is global for each complete UV or VIS profile before physics-bin fits. A particular energy/mass bin can therefore be empty in one sample or have different fitted coverage; the plotting code preserves those unmatched points instead of silently pairing or dropping them. With `--by-period`, the candle samples are extracted only for the pooled profile result, not independently for every historical subperiod.

The normal launcher enables the test for UV and VIS:

```bash
python scripts/run_pipeline.py --mode production --output-dir results/my-campaign
```

For a standalone Stage-08 rerun, add both options to the usual extraction command:

```bash
python 08_observable_extraction/beam_asymmetry.py \
  --raw results/my-campaign/vis/reco/reco_eta_pi0_chi2.root \
  --raw-bdt results/my-campaign/vis/reco/reco_eta_pi0_bdt.root \
  --profile vis \
  --flux-file results/my-campaign/common/flux_calibrated.root \
  --run-manifest config/run_manifest.csv \
  --run-quality config/run_quality_exclusions.json \
  --output-dir results_test/vis-candle/beam_asymmetry \
  --estimator both \
  --candle-mass-half-width 0.05 \
  --candle-balance-seed 20261024
```

The additional ROOT samples are `raw_bdt_core` and `raw_bdt_tails`. The extraction writes `candle_mass_plane.pdf` plus `comparison_candle_ratio.pdf` and/or `comparison_candle_likelihood.pdf` when both candle samples have fitted points for that estimator; combined UV/VIS plots use the same comparison names. `beam_asymmetry.root` records the centers, half-width, boundary and selection logic, seed, balance method, full counts and excluded non-finite count. Composition fails closed if UV and VIS use incompatible candle definitions.

Interpret agreement as a selection-stability diagnostic only. It does not turn the tail sample into a background model, and it does not modify or replace the nominal `raw_bdt` asymmetry.
