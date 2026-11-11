# Calibrated flux recovery on a common energy grid

The November 2026 implementation adds an explicit offline study. It does not
qualify an estimated-flux recovery policy, activate estimates in the workflow, overwrite
`flux_calibrated.root`, or supersede the historical `selected_policy=null` result.
The [design](../docs/plans/2026-11-10-flux-recovery-design.md) defines the scientific
work still required. Software tests establish contracts, not physical validity.

## Measured polarized baseline

On 11 November 2026 the owner accepted the measured-only first step and adopted
it as the default **for beam asymmetries only**. Stage 08 admits valid measured
POL1/POL2 exposures independently of BREM availability. The local pilot recovered
289 selected events (+2.21%); evidence: `results_test/flux-baseline-20261111/report.md`.
This does not qualify estimated POL flux or cross sections. Cross-section
eligibility and absolute normalization remain an explicit future scientific review.
`FluxExposure.flux_brem=None` means unavailable; measured zero remains zero.
`brem_status` distinguishes measured valid, estimated, missing, duplicate and
defective controls. Selectors and diagnostics use measured-valid BREM only and
report their run/stratum/event denominator. Complete measured triplets retain
the established energy, polarization and estimator conventions. Legacy CSV rows
whose aggregate status is invalid remain excluded because they lack per-state
evidence sufficient to reclassify their polarized exposures.

Standalone, pipeline, period, comparison and bootstrap consumers share this
policy. New ROOT provenance, period indices and exposure summaries identify it
as `paired_pol_independent_brem`; UV/VIS composition requires matching declared
policies (legacy pairs remain readable). Shared raw-flux calibration and its
cross-section-binned diagnostic products retain their existing requirements.

The campaign inventory counts missing and defective BREM separately, records
unique selected event rows before/after the measured-only change, and never
counts BREM reconstruction as additional Sigma events. Without declared
reconstructed inputs, selected event counts are unavailable, not zero.

The older `recovery_budget` diagnostic now separates full-state support from
additional Sigma candidates. `potential_sigma_*` counts only runs with missing
POL states whose POL gaps all have candidate support; unsupported BREM cannot
block that count. BREM-only gaps are reported as `pol_pair_present_*`, never as
additional ML Sigma recovery. These are counts before strip acceptance, not
certified measured yields or accepted recovery. Historical budget files are
preserved unchanged.

## Explicit campaign commands

Use the installed package from the checkout under test. Set
`PYTHONDONTWRITEBYTECODE=1`, absolute `TMPDIR` and `MPLCONFIGDIR` inside the
campaign. All output destinations must be new paths under
`results_test/<campaign>/`; publication refuses overwrites and input overlap.

```sh
python -m flux_studies.energy_campaign inventory --config campaign.json --output results_test/flux-study/inventory
python -m flux_studies.energy_campaign baseline --config campaign.json --output results_test/flux-study/measured-baseline
python -m flux_studies.energy_campaign develop --config campaign.json --output results_test/flux-study/development-01
python -m flux_studies.energy_campaign freeze --config approved-protocol.json --output results_test/flux-study/protocol.json
python -m flux_studies.energy_campaign verify --protocol results_test/flux-study/protocol.json --output results_test/flux-study/verification
python -m flux_studies.energy_campaign apply --protocol results_test/flux-study/protocol.json --verification results_test/flux-study/verification/report.json --output results_test/flux-study/application
```

`baseline` publishes the before/after measured-only Sigma extraction and cutflow;
it does not train a model. These commands are intentionally separate. Development evaluates one declared
mask/rule configuration per output; compare bounded candidate configurations on
development data and record the selection rationale. `development_config.json`
preserves fitted parameters and input hashes for the subsequent protocol.
Changing input identities cannot silently rebind those parameters during freeze.
`verify` consumes an exclusive final-attempt receipt before calculation. Failure
remains a consumed attempt. A completed report is bound to its exact path and
hash by a separate exclusive completion receipt; `apply` rechecks it and the
numerical qualification. A failed final sample can only become development data
for a newly declared protocol and genuinely separate verification cohort.

## Campaign JSON contract

Inventory needs the following fields; paths identify actual local inputs, not
assumed full-campaign availability:

| Field | Content |
| --- | --- |
| `inputs.manifest`, `inputs.run_quality` | Maintained run manifest and shared quality policy |
| `inputs.calibrated_flux` | Measured calibrated ROOT |
| `inputs.h80` | Distinct inclusive h80 ROOT paths |
| `inputs.reco` | Explicit profile-to-reconstruction paths, such as `uv` and `vis`; empty only for inventory without event counts |
| `inputs.counts_cache` | Optional authenticated inclusive count cache for exactly those h80 files |
| `inputs.axes_product`, `inputs.axes_provenance` | Optional pair: stage-06 calibrated ROOT containing `calibration/runN_STATE_fit` and matching QA; necessary for recovered strip exposures |
| `cohort_runs` | Distinct proton manifest run IDs actually in scope |
| `energy_edges` | Finite strictly increasing common-grid edges in GeV; arbitrary bin count |

Development/freeze additionally declare these fields:

| Field | Content |
| --- | --- |
| `assignments` | One `{run, period, block, role}` per cohort run; roles `train`, `calibration`, `development`, `final`; whole acquisition blocks cannot cross roles |
| `masks` | Explicit `[run, state]` pairs reproducing actual missing-state/gap patterns; evaluation masks cannot be training runs |
| `seed`, `replicas`, `coverage_resamples`, `min_groups` | Explicit numerical simulation/support controls; no inherited farm/core allocation |
| `parameters` | Optional during development; frozen list of `{group, parameters}` from model fits, required for final verification/application |
| `normalization_domains` | `{period, state, qualified, evidence}` declarations from independent stability checks; no inferred prescale/dead-time/trigger qualification |
| `rule` | `max_gap`, `min_count`, `min_replicas`, `min_groups`, `max_relative_integral_std`, `min_valid_replica_fraction` |
| `selection` | Bounded `candidate_rules` containing the selected `rule`, explicit `objective` and `stopping_rule`, and authenticated `development_reports` entries `{path, sha256}` |
| `limits` | `max_abs_shift_stat`, `max_representation_shift_stat`, `max_model_shift_stat`, `max_shift_std_stat`, `max_combined_precision_ratio`, `max_missing_fraction`, `min_complete_replicas`, `min_coverage_groups`, `min_coverage68`, `min_coverage95`, `max_coverage_interval_width` |
| `point_universe` | Frozen `[period, estimator, pair, energy_bin, mass_bin]` keys; missing/failed points remain explicit |
| `history` | `previously_used_runs` and `final_interpretation`; previously inspected runs cannot be relabeled final |
| `systematics` | Explicit `scope`, `status`, `evidence`; absent/unqualified measured-reference and common-systematic evidence prevents qualification |
| `input_sha256` | Complete absolute-path-to-hash snapshot, produced by inventory/development and authenticated at freeze/load |

No example numerical acceptance thresholds are supplied: these are scientific
development products, not software defaults. Historical 0.05/0.10/0.30 thresholds
and Kernel Ridge policies are not reused. Model fitting uses one worker; a short
benchmark and explicitly declared resources precede a real campaign.

## Representation and leakage boundaries

The new `state_wise=True` loader inventories every proton manifest run and each
state, including absent inclusive counts and excluded runs. Valid measured states
can supply their own models even when another state is missing. Known all-zero
histograms stay measured; a zero-integral prediction is unavailable.

Bin values are integrated fluxes. Transfers integrate piecewise-constant source
densities, account for tails and ROOT flow, and retain coverage fractions.
Padding an enclosing common grid is a representation of finite histogram
support, not evidence of measured energy coverage beyond it. Predictions carry
the intersection of their donors' measured supports; acceptance requires the
independent target axis to lie inside that support and the common grid.

Independent axes come from authenticated inclusive h80 calibration fits and
coverage QA. Loading them reads calibration TF1 objects, not target flux
contents. Mapping yields authentic strip IDs 1–128; stage 08 computes per-state
polarizations and the established mean POL energy. An insufficient independent
axis leaves an energetic candidate, not an admitted Sigma exposure. Existing
measured states are protected; replacing them requires explicit masked-closure
mode and defective measurements cannot be silently substituted.

`energy_validation.py` trains only Extra Trees hybrid, with linear interpolation
as integral provider and diagnostic. Features have `3K+3` entries. Tuning uses
inner training blocks, donors bracket each target in the same period/state,
and all states of a masked run are withheld. Distances use complete manifest
positions including excluded runs; 15 minutes per position remains an assumption.
The historical native study entry points remain separate and inactive by default.

## Uncertainty and comparisons

Calibration-only residuals separate log-integral and normalized shape. Aligned
replicas preserve shared run/block/donor dependencies. Model/donor bootstrap
draws are retained separately; calibrated total residuals are not added to them
again. This dependence model itself requires scientific qualification.
Coverage for qualification uses exactly the accepted run/state cohort; full-mask
coverage stays a separate diagnostic. Coverage reports marginal energy-bin, integral and shape diagnostics, with
dependency-group intervals and independent period/state support; marginal
95% coverage is not a simultaneous 95% spectrum band.

The new closure extracts A (without POL recovery), B (recovery), C (same accepted
sample with known measured flux), and D (known energy-grid flux mapped through
independent axes). BREM-only masks preserve A's POL sample. Rejected POL runs
stay out of C/D. A separate original-axis roundtrip control distinguishes
rebinning from changing the independent axis. Projection failure never falls
back to hidden measured truth.

Poisson event replicas are synchronized across scenarios and combined with
aligned flux replicas; shared A/B events remain correlated. Reports retain
failed replicas and fixed comparison points, paired shifts/covariance, ratio
fallback changes, and joint B/A precision. No incomplete uncertainty sum is
called a total error. Real missing-flux comparisons have no measured oracle and
measure stability/benefit only. Experimental candidates and exposures remain
separate products and require this explicit path to be consumed.

## Evidence and remaining scientific work

Implementation verification logs are retained in
`results_test/flux-recovery-20261110/` as dated software evidence. Disposable
test outputs are removed after verification. No scientific extraction, farm
campaign, production replacement, BDT retraining or theory stage was launched
for this implementation.

Verification on 11 November: 925 combined stage 06/07/08 tests passed; after the
final study refinements, all 284 stage 07 tests passed again. Five workflow
boundary checks and one installed-extraction integration check also passed.
The counts overlap and must not be summed. The combined run retained one
pre-existing empty-legend plotting warning. Exact commands and retained-log
purposes are recorded in `results_test/flux-recovery-20261110/verification.md`.

Next scientific work: declare exact h80/reconstructed cohort and calibration QA;
quantify the measured POL-only recovery; benchmark; develop and freeze grid,
mask/rule candidates and numerical protocol; qualify representation, normalization,
coverage and systematic treatment per domain; perform one separate verification;
only then apply to genuine absences. Previously inspected campaign data provide
internal confirmation, not a claim of never-observed external validation.
