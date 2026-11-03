# Gaussian core-versus-tail candle test

The candle test is a selection-stability check in the **eta pi0 channel**. It compares the complete nominal post-BDT `raw_bdt` sample with a Gaussian mass core and its tails. The tight selection is this mass ellipse; there is no separate test channel or additional set of tight cuts. The nominal extraction, detector cuts, flux, polarization and estimator conventions remain unchanged.

## Selection and fit

The Stage-08 launcher enables `candle_enabled: true` and `candle_gaussian: true`. It fits a correlated two-dimensional Gaussian peak plus a constant pedestal to the raw eta/pi0 candidate masses. The default fit window is the fixed rectangle `m_eta +/- 0.05 GeV`, `m_pi0 +/- 0.05 GeV`; `candle_mass_half_width_gev` controls this fit window, not the ellipse radius. The binned Poisson fit uses 40 by 40 cells and integrates the model in each cell with 6 by 6 Gauss-Legendre quadrature. The fitted center and positive-definite covariance define the contour, without using polarization or fitted Sigma to choose it.

For the fitted center `mu` and covariance `C`, the inclusive core is

`(m - mu)^T C^-1 (m - mu) <= 2 ln(2)`.

This encloses **50% of the fitted untruncated Gaussian component**. It is not an empirical median, half of the observed candidates, or a background containment prescription. Every finite-mass event belongs to exactly one of core or tails, including finite events outside the fit window. No random downsampling occurs. Nonfinite candidate masses belong to neither subset and are counted explicitly; the full nominal sample remains intact. The plot reports the measured core fraction among finite candidates separately from the theoretical Gaussian probability.

Insufficient or degenerate fit input, nonconvergence, a peak at the allowed parameter boundary, an unidentifiable peak or unusable covariance fail explicitly. There is no fallback to nominal detector widths. A profile requires a usable fit and nonempty core/tail regions. Candle mode requires nominal `raw_bdt`, rejects sideband correction and the separate `--bootstrap-diagnostics-replicas` mode, and requires fitted points in both subsets overall. With adaptive azimuth binning, the full-sample choice is frozen for the core/tail comparison. Individual physics bins can remain unmatched or non-estimable; comparisons retain that status. With `--by-period`, the candle is applied to the pooled profile extraction, not independently refitted in each historical subperiod.

## Stage-08 rerun from completed inputs

The following command documents a new diagnostic extraction from compatible, completed reconstruction and calibrated-flux inputs; it does not restart reconstruction or change an existing campaign. Set the paths to the intended saved campaign before running it:

```bash
python 08_observable_extraction/beam_asymmetry.py \
  --raw results/my-campaign/root/vis/reco/reco_eta_pi0_chi2.root \
  --raw-bdt results/my-campaign/root/vis/reco/reco_eta_pi0_bdt.root \
  --profile vis \
  --flux-file results/my-campaign/root/common/flux_calibrated.root \
  --run-manifest config/support/run_manifest.csv \
  --run-quality config/support/run_quality_exclusions.json \
  --output-dir results_test/vis-gaussian-candle/beam_asymmetry \
  --estimator both \
  --phi-bins 12 \
  --by-period \
  --bootstrap-replicas 0 \
  --candle-gaussian \
  --candle-mass-half-width 0.05 \
  --candle-comparison-replicas 0
```

`--candle-gaussian` alone uses the default 0.05 GeV fit half-width. Standalone extraction without candle options remains unchanged. The CLI is explicit about Gaussian mode: supplying only `--candle-mass-half-width` preserves the historical rectangular mode described below. Stage configuration defaults to Gaussian mode when candle extraction is enabled.

## Outputs and interpretation

The additional ROOT samples are `raw_bdt_core` and `raw_bdt_tails`; `raw_bdt` remains the full sample. The reporting directory contains:

- `candle_mass_plane.pdf`: full raw mass plane, fitted correlated ellipse, theoretical probability, measured counts and containment;
- `candle_mass_projections.pdf`: data projections within the declared joint fit window and the stored Gaussian-plus-pedestal fit components, without a second fit;
- `comparison_candle_ratio.pdf` and/or `comparison_candle_likelihood.pdf`: full/core/tails on the physical energy/mass grid, preserving unmatched fitted coverage; combined UV/VIS plots retain the same names;
- `candle_quality/`: six PDF controls with raw-count and unit-area views, plus `quality_audit.json`, as specified in [plotting and diagnostics](plotting-and-diagnostics).

`beam_asymmetry.root` records the Gaussian model and fitting audit, contour probability and boundary, counts, measured containment and excluded nonfinite count. The same fitted contour is retained through serialization. Composition validates selection semantics and the [azimuth-bin origin](finite-bin-correction); it rejects mixtures of Gaussian and legacy rectangular definitions or incompatible angular origins. Profiles may have separately fitted Gaussian parameters under the same declared fitting policy.

`candle_comparison.json` records full/core and core/tails differences and estimability. Full and core share events, so an independent-sample error calculation is invalid. With the default `candle_comparison_replicas: 0`, comparison uncertainty remains explicitly unevaluated. Optional `--candle-comparison-replicas N` requires `N >= 2`, Gaussian mode and `--by-period` with an inclusive run universe. It draws shared run blocks and their exposure records for all samples, using `bootstrap_seed`, and writes paired conditional covariance diagnostics plus `candle_comparison_replicas.npz` when estimable. The fitted contour is held fixed. These are conditional run-level diagnostics, not final event errors, contour uncertainty or a completed systematic budget; the ordinary `bootstrap_replicas` setting remains separate.

Agreement is a selection-stability diagnostic. It does not establish signal efficiency, background subtraction or a cross section. Cross-section extraction and comparisons are deferred until a cross-section measurement is available.

## Mass balance: sketch only

For eta pi0 events, the proposed study compares each reconstructed meson mass with its reference and the recoil missing mass with the proton mass. Combine these with the four-momentum closure `beam + target - proton - eta - pi0`, keeping energy and momentum residuals distinct. Compare full/core/tails to identify correlated mass shifts or reconstruction tails. A sum of rest masses is not an event conservation equation. This is a scientific outline only: no balance selection, weights, thresholds or new corrections are implemented.

## Historical rectangular mode

The earlier candle used the inclusive rectangle `|M(eta)-m_eta| <= width`, `|M(pi0)-m_pi0| <= width`, and downsampled its full core without replacement to match the finite tail count. It required nonempty regions and at least as many core events as tails, using seed `20261024` by default. That explicit legacy mode remains available through `candle_gaussian: false` in stage configuration, or standalone `--candle-mass-half-width 0.05 --candle-balance-seed 20261024` without `--candle-gaussian`. `candle_balance_seed` is ignored in Gaussian mode. Existing historical products are readable and are never rewritten to adopt the new contour.

The original rectangular port specification remains in [PR history](https://github.com/AntoninoFulci/GRAAL_Analysis/tree/e5c586e3b192b9cfe5dac442140668588d3f28e6/docs/plans). Current software tests verify containment mathematics, numerical fitting, raw-vector controls and reporting contracts; they do not establish production physics validity.

## Dated diagnostic execution: 3 November 2026

A pooled UV/VIS diagnostic rerun used the completed reconstructions and calibrated flux in `results/production_asymmetries_20261026`, with the current explicit run-quality policy, both estimators, 12 azimuth bins centered at zero, and the 0.05 GeV Gaussian fit window. Reconstruction and original scientific products were not rewritten. Results are retained under `results_test/asymmetry-gaussian-real-20261103/`; `evidence.json` records source hashes, fitted models, counts and flux exclusions, with separate UV/VIS command logs. The common directory contains combined full/core/tails comparisons.

| Profile | Full eligible events | Core | Tails | Observed core fraction |
| --- | ---: | ---: | ---: | ---: |
| UV | 100,293 | 48,922 | 51,371 | 48.779% |
| VIS | 11,675 | 5,647 | 6,028 | 48.368% |

Both profiles had zero nonfinite candidate masses in this selected baseline. “Full” means the nominal post-BDT sample after established energy/run/flux eligibility, not all reconstructed candidates. The loader excluded runs without complete flux triplets, invalid strips and exposures outside the polarization domain, with counts in the logs. Paired replicas were not requested for this diagnostic; differences have no assigned significance or final shared-systematic covariance. This dated execution is neither a live farm-state report nor production validation.

Software verification for this change: 1,821 suite tests passed, one skipped; eight focused Gaussian/entry-point integration checks passed after the direct-script import fix. Independent review checked Gaussian fitting/provenance, paired covariance, azimuth correction and report preservation. Logs are retained under `results_test/asymmetry-gaussian-20261103/` as software evidence, separately from the dated scientific outputs.
