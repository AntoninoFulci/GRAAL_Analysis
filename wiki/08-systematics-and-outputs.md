# 08 — Systematics and Outputs

Stage 08 stores uncertainty over an ordered list of `OutputPoint` objects.
The October 13, 2026 update adds explicit identity, availability, and paired
run diagnostics. **Final physical inference is suspended:** the existing
numerical uncertainty model remains provisional. See the
[implementation and artifact audit](../docs/research/2026-10-13-systematics-infrastructure.md).

## What the bars mean

| Product | Quantity drawn | Interpretation |
|---|---|---|
| Figure 4 bars | `stat_low`, `stat_high` | Conditional fit errors; uncorrected likelihood intervals remain asymmetric |
| Figure 4 shaded rectangles | `syst_total = sqrt(sum(diag(Csyst)))` | Available legacy components only; partial and provisional |
| Reconstruction/estimator comparisons | `stat_low`, `stat_high` | Shared-event comparisons; not independent-error significance tests |
| ROOT `ratio_objects/.../ratio` | propagated Poisson error of the observed ratio | Flux and polarization fixed; physical finite-bin correction applies to Sigma, not this curve |
| ROOT `covariance/total` | `Cstat + sum(Csyst)` | Symmetrized covariance summary; not the Figure 4 error bar |

When background correction runs, the existing CLI replaces the `stat_*`
branches with a symmetric propagated uncertainty containing observed Sigma,
background Sigma, and fraction uncertainty. It is explicitly labelled
`background_propagated_unclassified`; it is **not certified as purely
statistical**. Original asymmetric conditional likelihood intervals are not
preserved by that legacy correction. New Jacobian propagation does not claim
to replace a profile likelihood interval.

The `point_uncertainty_kinds` ROOT object preserves that interpretation across
reading/replotting. Older files without it are labelled
`legacy_stat_branches_unclassified`, never silently certified as statistical.

## Systematic Components

`core/systematics.py:REQUIRED_SYSTEMATICS` is an inventory, not proof that every
source was measured. `covariance/uncertainty_metadata` records every source as
`executed`, `not_applicable`, or `unavailable`, together with input/variation,
dimensionless Sigma units, signed shifts, per-point measured masks, omission
reasons, classification, and the assumed correlation model. A measured zero
shift retains its zero matrix; an unavailable point has a null shift in the
inventory. Embedded numerical zeros outside a measured mask are not evidence
of independence.

| Source | Current execution |
|---|---|
| `polarization_scale_3pct` | `-0.03 Sigma`, common rank-one legacy model |
| `estimator_ratio_vs_likelihood` | Half counterpart difference where both points exist, including zero differences |
| `raw_vs_kinematic_fit` | Retired from operational covariance; retained as `not_applicable` in inventory; archival comparison plots remain available |
| `background_template` | Legacy corrected-minus-uncorrected shift; **not independent evidence for fraction uncertainty** |
| `angular_offset_sine_leakage` | Diagnostic fallback `s2`, when fitted |
| `photon_multiplicity` | Exactly-four minus inclusive result for the nominal sample, if all required bins survive; comparison-sample entries unmeasured |
| `flux_balance`, `bdt_threshold`, `sideband_definition`, `fit_fallback`, `mass_phi_binning`, `run_period_stability` | Unavailable until the required variations and physical choices exist |

The current rank-one construction is `Csyst = Delta Delta^T`: a single common
nuisance per component. Independence between different sources and physical
scope (global or period-specific) remain unvalidated. Estimator and cut shifts
contain statistical noise. The legacy correction shift can overlap fraction
uncertainty already present in `stat_*`; this is recorded as unresolved rather
than silently redefining the physical result.

`systematic_summary.pdf` includes the availability table. Figure 4 labels its
band as partial/provisional even if every materialized matrix is nonzero.

## Covariance Combination

`validate_covariance` rejects nonfinite, nonsquare, asymmetric, or non-PSD
matrices with numerical tolerance. `difference_covariance(CA, CB, CAB)` checks
the joint block covariance and returns `CA + CB - CAB - CAB.T`. Cross covariance
is required explicitly; no inverse or diagonal chi-square is inferred.

`correct_sigma_with_covariance(obs, bkg, f, Cin)` implements

```math
\Sigma_s=(\Sigma_{obs}-f\Sigma_b)/(1-f),\quad
J=(1/(1-f),\,-f/(1-f),\,(\Sigma_{obs}-\Sigma_b)/(1-f)^2),\quad C_{out}=JC_{in}J^T.
```

Input order is **all observed bins, all background bins, all fraction bins**.
A fraction shared across bins must have its corresponding covariance supplied
in the fraction block; cross blocks are retained. This API requires an
explicit joint covariance and does not invent the classification of `f`.
It is not automatically substituted into final CLI inference.

## Bootstrap by Run

The existing `--bootstrap-replicas` remains the legacy nominal-only option:
it derives runs from selected nominal events and combines its covariance with
the fit diagonal using `max(fit variance, bootstrap variance)`. It is disabled
by default and is not the new paired diagnostic.

The independent diagnostic entry point is:

```bash
python3 -m observable_extraction.beam_asymmetry \
  --raw-bdt <no-fit-reconstruction.root> --raw <comparison.root> \
  --flux-file <calibrated.root> --run-manifest <calibration-manifest.csv> \
  --profile uv --estimator both \
  --bootstrap-universe-manifest <inclusive-campaign-runs.csv> \
  --bootstrap-diagnostics-replicas <reviewed-diagnostic-count> \
  --bootstrap-seed <seed> --output-dir results/<campaign>/systematics-diagnostic
```

The universe uses the standard run-manifest schema. It must cover selected
runs and contain only the chosen target/profile. Every listed run needs valid
exposure: a missing exposure is an error, not a zero count. Additional exposed
runs with zero selected events are included. Its completeness relative to the
acquisition campaign must be established by the analyst; selected events
alone cannot prove it.

Within each explicit profile/period stratum, draw the original number of runs
with replacement. The same draws repeat event blocks in all samples and scale
all matching exposures. All requested estimators are rerun; when the nominal
result is background-corrected, sideband fractions and background asymmetries
are rerun with those draws. Signal MC remains fixed; finite-MC uncertainty is
excluded and recorded. A compared result retains its original correction
status. An omitted fitted bin or expected optimizer failure is retained, never
redrawn. **Any failed replica makes the joint covariance unavailable.** Other
software exceptions remain fatal.

ROOT retains every replica, repeated run identities, failed point/reason
information, seed, exposure-weighted Kish effective run count, covariance
rank, and approximate Monte Carlo standard error from centered outer products.
The latter measures replica precision, not physical error. Diagnostics never
enter `Cstat`, `Csyst`, `Ctot`, or figure bars automatically. The two bootstrap
CLI modes cannot be enabled together.

`paired_bootstrap_by_run` is also usable with an explicit estimator callback.
That callback can select paired alternatives before returning the common
ordered vector. Event/Poisson bootstrap at fixed exposure needs shared event
identities across input files and an agreed ensemble; it is not implemented.
No production replica count or policy allowing incomplete replicas is chosen.

## ROOT and Figure Outputs

```text
sigma_points                          existing TTree, asymmetric branches retained
point_uncertainty_kinds                TNamed JSON, one interpretation per point
provenance                            includes final_inference=suspended
covariance/
  point_keys                          ordered JSON key map
  uncertainty_metadata                source inventory and unresolved assumptions
  total, statistical                  TH2D
  correlation_total, correlation_statistical
  systematic/<source>                 TH2D, including measured-zero sources
  correlation_systematic/<source>     TH2D
  bootstrap_run, correlation_bootstrap_run  optional legacy matrices
diagnostics/paired_bootstrap/         optional, separate from published covariance
  metadata                            keys, seed, failures, rank, effective runs
  replicas                            replica/point_index/sigma TTree, including NaN
  run_draws                           replica/draw_index/run_number TTree
  covariance, correlation             present only if all replicas estimable
  covariance_mc_error                 approximate elementwise Monte Carlo SE
```

Every square matrix carries the **same ordered keys on both axes**. Keys contain
campaign, selection, profile, period, sample, estimator, pair, energy bin, and
mass bin. CLI campaign identity is the resolved output directory; selection is
`no-fit` or `archived-fit-selected`, and period is explicitly `pooled`.
Generic callers must supply context or receive `unspecified`, never guessed
metadata. Duplicate keys, dimension mismatch, invalid covariance, and failed
`Ctot=Cstat+sum(Csyst)` closure are rejected before replacing an existing file.
The writer remains atomic.

`read_output_uncertainties` verifies matrix axes against the point table,
dimensions, symmetry/PSD and closure. Legacy files remain readable with no key
map and explicitly unknown availability/correlations. `read_bootstrap_diagnostics`
restores replica values and full draw history, including failures. Absent
legacy diagnostics return `None`.

## Period extraction

`--by-period` reuses the same Stage-08 engine for the pooled input and each exact
`RunRecord.source_period`. The launcher enables it. The inclusive run universe
comes from reconstruction cutflow, or an explicit `--run-universe-manifest`
when that cutflow is absent. Raw, BDT and sideband inputs must share the universe.
Zero-yield exposure strata remain in the normalization; unknown runs, conflicting
CSV/manifest classification, ambiguous run identity and unsafe labels are errors.

`periods/index.json` records available and absent periods, missing-flux runs,
V/H/BREM selection accounting, exposure strata, all bin statuses, closure,
input/source hashes, commands and versions. Each available period gets
`periods/<source_period>/beam_asymmetry.root` with the normal schema and
`extraction_metadata`. A non-estimable period stores an empty point tree, no
covariance and no fabricated zero Sigma. Nonconverged fits remain identifiable
in metadata, outside the published point vector.

Pooled Sigma is extracted from the disjoint union, never averaged from period
Sigmas. Closure independently reconstructs that union and checks counts,
exposures, estimable bins and uncorrected fits within 1e-8. Period stability
plots compare exact bins with conditional/propagated error bars. Stored period
differences carry no significance claim. Polarization-scale signed responses
represent one shared nuisance across periods; other cross-period covariances
remain unknown. `run_period_stability` is still not promoted to a systematic
covariance: final inference remains suspended.

## Verification and remaining decisions

Tests cover shared/opposite-sign nuisances, identical versus disjoint
comparisons, zero-yield runs, lost bins, optimizer failures, seed reproducibility,
ROOT roundtrips, point permutations, rejection without overwriting, legacy
unknowns, and different statistical/systematic plot widths. The reproducible
[Gaussian run toy](../docs/research/2026-10-13-systematics-toy.py) checks stability
at multiple replica counts/seeds and coverage in its own model.

Still required before final inference: user-identified figure/result,
classification and covariance of `f`, global/per-period nuisance scope,
statistical versus stability interpretation of run dispersion, event identities
for Poisson/event replicas, precision target and non-estimable-bin policy.
No new physical campaign was generated by this infrastructure update.
