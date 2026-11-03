# Core-versus-tail candle test

The candle test is a stability check on the nominal post-BDT event sample. It
compares beam asymmetries extracted from two disjoint geometric regions with
the same number of finite events, up to one event when the total is odd. It
does not change the nominal `raw_bdt` result.

For each complete UV or VIS profile, Stage 08 independently fits the raw eta
and pi0 candidate-mass peaks with a Gaussian plus linear background. The
ellipse remains centered on the physical meson masses and is not rotated. For
finite mass pairs it defines

```text
d0_squared = ((eta_mass - M_ETA) / sigma_eta)^2
           + ((pi0_mass - M_PI0) / sigma_pi0)^2
```

The workflow solves a common factor `k` from the empirical median distance.
The core satisfies `d0_squared / k^2 <= 1`; the tail is its finite complement.
Consequently `k` may be smaller or larger than one, but no manual scan and no
random downsampling are used. Non-finite mass pairs enter neither region and
are counted separately. An exact distance tie across the median fails because
a purely geometric threshold cannot split identical points. Candle mode requires
nominal `raw_bdt`, rejects sideband correction and diagnostic bootstrap, and
requires at least one fitted point overall in each candle sample. Without
candle options, standalone extraction retains its existing behavior.

The 50/50 equality is global before physics-bin fits. An energy/mass bin may
therefore be absent in one region, and ratio or likelihood coverage may differ.
The plots retain such unmatched points. With `--by-period`, the candle samples
are produced only for the pooled profile result; historical period outputs
remain nominal-only.

The normal launcher enables a 50% core for UV and VIS:

```bash
python scripts/run_pipeline.py --mode production --output-dir results/my-campaign
```

For a standalone Stage-08 rerun, add the fraction to the normal extraction:

```bash
python 08_observable_extraction/beam_asymmetry.py \
  --raw results/my-campaign/root/vis/reco/reco_eta_pi0_chi2.root \
  --raw-bdt results/my-campaign/root/vis/reco/reco_eta_pi0_bdt.root \
  --profile vis \
  --flux-file results/my-campaign/root/common/flux_calibrated.root \
  --run-manifest config/support/run_manifest.csv \
  --run-quality config/support/run_quality_exclusions.json \
  --output-dir results_test/vis-candle/beam_asymmetry \
  --estimator both \
  --candle-core-fraction 0.5
```

The additional ROOT samples are `raw_bdt_core` and `raw_bdt_tails`. The
extraction writes `candle_mass_plane.pdf` with the fitted ellipse plus
`comparison_candle_ratio.pdf` and/or `comparison_candle_likelihood.pdf` when
both regions have fitted points for that estimator. `beam_asymmetry.root`
records the fit model and ranges, fitted means and sigmas, requested fraction,
distance threshold, `k`, finite/core/tail counts, and excluded non-finite
count. UV/VIS composition requires the same method and fraction while allowing
their data-derived sigmas and scale factors to differ.

Interpret agreement as a selection-stability diagnostic only. It does not turn the tail sample into a background model, and it does not modify or replace the nominal `raw_bdt` asymmetry. The test does not establish detector acceptance or a formal significance.

The completed port specification and implementation plan remain in [PR history](https://github.com/AntoninoFulci/GRAAL_Analysis/tree/e5c586e3b192b9cfe5dac442140668588d3f28e6/docs/plans). The port extends the current Stage-08 owners; it does not import historical campaign outputs. Formal significance and shared-systematic covariance remain outside this diagnostic.
