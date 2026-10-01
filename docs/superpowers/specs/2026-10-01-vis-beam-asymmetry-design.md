# VIS beam-asymmetry extension design

Date: 2026-10-01  
Status: approved in sections during design review

## Goal

Extend the existing local `eta pi0 p` analysis with a VIS-specific chain and
use it to add a new `0.9313 <= E_gamma <= 1.10 GeV` row above the four UV rows
of the Ajaka-style Figure 4.

The local run is a complete rehearsal before processing the full farm
statistics:

```text
VIS pre-analysis -> event selection -> VIS Monte Carlo -> VIS BDT training
-> VIS reconstruction -> VIS asymmetry extraction -> combined UV+VIS plots
```

Success means that every stage runs from the supplied VIS pre-analysis file,
all VIS products remain isolated below `test_data/`, the existing UV results
remain unchanged, and the combined figure contains one VIS row followed by the
four established UV rows.

## Fixed analysis decisions

- VIS analysis range: `0.9313--1.10 GeV`.
- UV range and four existing UV bins remain unchanged.
- VIS and UV have independent exposure, polarization, reconstruction, and fit
  paths. They are combined only while plotting final results.
- The reaction threshold is represented by the exact lower edge `0.9313 GeV`,
  not the rounded label `0.9 GeV`.
- The final nominal estimator is the ratio estimator. The likelihood estimator
  is retained as a cross-check.
- A physical bin is fitted only when it contains at least 20 selected
  `POL1 + POL2` events. Twenty is accepted; nineteen is not.
- Existing Ajaka mass ranges, ten mass bins, and twelve azimuthal bins are
  reused without modification.
- Points are drawn at geometric mass-bin centers.
- No run bootstrap, expanded feasibility gate, new background correction, or
  new systematic study is part of this local VIS extension.

## Analysis profiles

A shared profile definition owns beam-specific constants instead of spreading
UV/VIS conditionals through downstream code.

| Profile | Beam identifier | Laser wavelength | Energy edges [GeV] |
|---|---|---:|---|
| `uv` | `P_UV` | 351 nm | `1.10, 1.20, 1.30, 1.40, 1.50` |
| `vis` | `P_VIS` | 514 nm | `0.9313, 1.10` |

Callers pass a profile or explicit profile-derived energy edges to selection,
exposure loading, binning, and extraction. UV remains the compatibility
default where an existing public command needs one, but VIS commands select
`vis` explicitly.

Profile identity and energy bounds travel with the VIS feature dataset and BDT
provenance. Reconstruction rejects a model whose profile or energy interval
does not match the requested analysis. Legacy UV artifacts remain readable;
new metadata must not invalidate the existing UV workflow. Missing profile
metadata is accepted only through the legacy/UV compatibility path and is
never accepted for an explicitly requested VIS reconstruction.

## Selection and exposure rules

The local VIS source is:

```text
test_data/pre_analyzed/pre_analisi_1999_vis.root
```

Selection is rerun from this file. Downstream VIS event selection imposes the
exact reconstructed tagged-photon interval `0.9313 <= E_gamma <= 1.10 GeV`;
the wider energy content present in the source file must not leak into the
analysis.

A run is usable only when calibrated `POL1`, `POL2`, and `BREM` information all
exist. An incomplete run is skipped and reported. This rule applies to local
tests and all later farm processing. For the current VIS file, run 2071 is
known to lack BREM and is therefore skipped.

Within otherwise usable runs, events whose `(run, strip)` has no valid exposure
are excluded and counted. The extraction does not fabricate, interpolate, or
average missing exposure. VIS exposure and polarization use `P_VIS`; no UV/VIS
polarization average is allowed.

## VIS Monte Carlo

Generate a dedicated VIS sample rather than training on the broad legacy
energy interval. Generators accept an analysis lower bound, upper bound, and
output destination while preserving their current defaults for legacy calls.
Each channel samples true beam energy from:

```text
max(channel production threshold, 0.9313 GeV) <= E_gamma <= 1.10 GeV
```

The local rehearsal uses the existing default generation size of one million
attempted events per channel.

Required channels:

- signal: `eta_pi0`;
- ordinary backgrounds: `pi0pi0`, `3pi0`, `eta_via_3pi0`, `4pi0`;
- signal-decay background: `eta_pi0_via_3pi0`.

`eta_2pi0`, `omega_pi0`, and `etaprime` are excluded because their production
thresholds lie above the VIS endpoint.

Stored tagged energy is smeared, so a small reconstructed tail may fall outside
the generation truth interval. Beam reweighting and analysis cuts give such
events zero analysis weight or exclude them; generators must not move a
physical production threshold to compensate for detector smearing.

## VIS beam spectrum and BDT training

Measure the target beam-energy distribution from the newly selected VIS data,
restricted to the VIS interval. Use 17 equal bins across this interval, giving
an approximately 10 MeV width consistent with the legacy spectrum, rather than
applying 150 bins to this much narrower interval.

Build Stage-1 features with the same feature order, photon-loss model,
detector acceptance, photon shuffling, and channel-weight machinery used by
the UV model. Keep the balanced `signal_prior = 0.5`. Ordinary backgrounds are
weighted by flux, energy-dependent cross section, and acceptance;
`eta_pi0_via_3pi0` remains slaved to the signal through its branching-ratio and
acceptance ratio.

Train a fresh VIS booster. The first local model reuses the validated UV
hyperparameter values, but learns all tree parameters and its operating
threshold from the VIS dataset and VIS validation split. A new grid search is
deferred unless diagnostics show a concrete need.

Required training reports are the existing ROC, score distributions, feature
importance, metrics, threshold, and provenance. Also report channel survival,
zero-weight count, finite-weight validation, and Kish effective sample size.
These measurements are diagnostics, not arbitrary feasibility cuts.

## Reconstruction

Run BDT reconstruction on the VIS selected file using only the VIS Stage-1
artifact directory. Model loading validates signal channel, hypothesis,
profile, and energy interval before reading events.

The nominal reconstruction product is the `reco_eta_pi0_bdt` tree consumed by
observable extraction. This extension does not require a new kinematic-fit or
sideband study. Existing reconstruction physics, branch names, and event
definitions remain unchanged.

## Asymmetry extraction

Extraction receives profile energy edges explicitly; no extractor may depend
on the current UV-only global edge array. VIS and UV fits run independently.

For every profile, pair, energy bin, and mass bin:

1. select events in the profile energy interval and Ajaka mass bin;
2. retain `POL1` and `POL2` events having valid exposure;
3. count selected events across both polarization states;
4. skip the bin when the total is below 20;
5. otherwise run the ratio and likelihood estimators using that profile's
   exposures and polarizations.

Existing estimator-level validity requirements still apply, such as both
polarization states being present and enough populated azimuthal information
for a defined fit. These are correctness requirements, not additional
physics-quality gates.

Empty, inaccessible, or underpopulated bins produce no point. They are shown as
empty panels/positions rather than zeros.

## Five-row plotting model

UV ROOT output keeps local energy-bin IDs `0--3`; VIS ROOT output keeps local
energy-bin ID `0`. A plotting row is therefore identified by
`(profile, local_energy_bin)`, preventing a renumbering of existing UV data.

Final row order:

1. VIS `0.9313--1.10 GeV`;
2. UV `1.10--1.20 GeV`;
3. UV `1.20--1.30 GeV`;
4. UV `1.30--1.40 GeV`;
5. UV `1.40--1.50 GeV`.

Columns remain `p pi0`, `p eta`, and `eta pi0`. The experimental and Ajaka
comparison figures both use this 5x3 layout. Published Ajaka points appear only
in the four UV rows because no published VIS row is being imported.

`comparison_estimators.pdf` also uses the physical 5x3 arrangement.
`fit_diagnostics.pdf` displays ratio-estimator diagnostics only, including
`chi2/ndf` and p-value for each fitted physical bin.

## Output layout

Existing UV files are neither moved nor overwritten. New local products are:

```text
test_data/vis/
|-- selected/
|   `-- analisi_1999_vis.root
|-- mc/
|   |-- eta_pi0_mc.root
|   |-- pi0pi0_mc.root
|   |-- 3pi0_mc.root
|   |-- eta_via_3pi0_mc.root
|   |-- 4pi0_mc.root
|   `-- eta_pi0_via_3pi0_mc.root
|-- bdt/
|   |-- beam_spectrum.npz
|   |-- features_stage1.npz
|   `-- artifacts/stage1/
|-- reco/
|   `-- reco_eta_pi0_bdt.root
`-- beam_asymmetry/
    |-- beam_asymmetry.root
    |-- figure4_experimental.pdf
    |-- comparison_estimators.pdf
    `-- fit_diagnostics.pdf

test_data/beam_asymmetry/uv_vis/
|-- figure4_experimental.pdf
|-- figure4_comparison_ajaka2008.pdf
|-- comparison_estimators.pdf
`-- fit_diagnostics.pdf
```

The combined plotter reads the existing UV and new VIS ROOT results explicitly.
It never merges event trees or exposure tables.

## Failure policy and reporting

Stop the relevant stage on:

- unknown profile or invalid interval;
- missing required MC channel;
- empty measured VIS spectrum;
- non-finite training weights or missing training class;
- model/profile/range mismatch;
- missing nominal reconstructed tree;
- complete absence of fittable asymmetry bins.

Continue while recording:

- incomplete runs skipped;
- events dropped for missing exposure;
- inaccessible or sub-20-event bins;
- fit-level failures confined to individual bins;
- weak AUC, low acceptance, or large statistical uncertainties.

Stage summaries report input/output event counts, observed energy bounds, used
and skipped runs, missing-exposure event count, MC survival and weights, BDT
train/validation metrics, per-bin polarization counts, and fit diagnostics.

## Verification

Automated coverage must include:

- exact UV/VIS profile constants and edge routing;
- parameterized generator ranges with unchanged legacy defaults;
- VIS selection boundary behavior at `0.9313` and `1.10 GeV`;
- Stage-1 model/profile/range compatibility;
- 19-event skip and 20-event fit boundaries for both estimators;
- incomplete-run skip and missing-exposure exclusion;
- 5x3 combined figure layout and row labels;
- Ajaka overlay restricted to UV rows;
- unchanged UV binning and plotting regression.

Local end-to-end validation additionally checks every expected artifact,
inspects BDT reports, verifies ROOT tree entry counts and energy bounds, and
renders the final PDFs for visual review.

## Deferred work

- bootstrap covariance by run;
- investigation of statistically anomalous bins at full statistics;
- VIS-specific hyperparameter grid search unless current diagnostics justify it;
- additional background/systematic studies;
- full farm execution.

Farm execution begins only after the local VIS chain and five-row figure are
reviewed. The same profile and run-completeness rules must then be used without
changing analysis definitions.
