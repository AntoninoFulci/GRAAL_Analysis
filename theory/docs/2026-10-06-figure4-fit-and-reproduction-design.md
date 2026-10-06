# Ajaka Figure 4: sourced prediction and GRAAL-data fit

## Purpose and scientific outcomes

The final objective is to reproduce, or explicitly fail to reproduce, the
twelve **theoretical** curves in Ajaka et al., Figure 4 with the coherent
seven-family `gamma p -> eta pi0 p` model. Two calculations must remain
separate:

1. **Sourced prediction:** calculate the twelve curves using the published,
   source-linked physical parameters. Compare converged predictions with the
   independently digitized theoretical strokes. Do not fit those strokes.
2. **GRAAL-data fit:** estimate a small, identifiable set of production
   couplings from our Stage 07 binned beam-asymmetry measurements. Compare the
   fitted model with our points and, separately, with the Ajaka theory curves.

Agreement in one comparison does not imply agreement in the other. A complete
calculation that disagrees with Ajaka is a valid, reported scientific result,
not a reproduced curve. Software tests do not certify either result.

This design replaces the **ordering** in
`2026-10-05-figure4-converged-production-design.md` that postponed even the
design of a native-data fit until after all twelve publication panels passed.
The earlier document still governs the sourced seven-family amplitude,
physical-domain limits, Figure 4 conventions, numerical oracle, convergence
gates, masks, and published-curve comparison. Fit infrastructure and numerical
work may advance in parallel. A physical parameter estimate still requires
converged theoretical predictions for every point admitted to that fit.

## Evidence and starting state

- `EtaPi0PFullModel` coherently sums seven complete complex spin-amplitude
  families. Its source-linked strong input ends at `W = 1.80 GeV`; the
  `1.60 < W <= 1.80 GeV` part is a source-used extension, without a quantified
  scattering-model uncertainty.
- Two actual Figure 4 bins pass all *individual-bin* numerical gates. No
  complete panel passes. In a one-interior-bin-per-panel screen, two of twelve
  passed the `p5/p6` gates; none of the ten remaining passed both `p6/p7`
  gates. No twelve-panel reproduction claim is available.
- The full-bin implementation distributes nominal bins across up to fourteen
  processes, but each bin repeats expensive energy, Sobol, replica and
  direct/grid checks. The current speed and convergence do not support
  repeated direct integration inside an optimizer.
- The existing UV production artifact at
  `results/production-20261006-113738/uv/beam_asymmetry/beam_asymmetry.root`
  contains 109 nominal `raw_bdt` points for each estimator. Its provenance
  says `background=uncorrected`; its run used zero bootstrap replicas and
  records `best_quartet_resolved=false`. It is a development dataset, not a
  final physics release.

## Model and fast prediction

Keep direct evaluation of `EtaPi0PFullModel` and the current Figure 4
integrator as numerical authorities. Fit candidates come from source-linked
**production** couplings; strong-scattering parameters, masses and resonance
widths remain fixed in the first fit. Select at most a small set after a
source-level dependency audit and a sensitivity/identifiability study on
converged predictions. Do not add arbitrary multipliers of whole amplitude
families or separate gauge partners. Parameter bounds must follow source
constraints and physical consistency, not agreement with digitized Ajaka
strokes. Do not invent Gaussian priors when source uncertainties are absent.

For each eligible parameterization, prove that the full complex spin matrix
can be written on the selected domain as a small exact basis

```text
M_epsilon(x; theta) = sum_a c_a(theta) B_epsilon,a(x),
```

where `x` is a phase-space event and `epsilon` is photon polarization.
Coefficients may include a small number of exact parameter monomials. A
coupling that changes a width, strong matrix, integration boundary, or hidden
loop integrand in a way this basis cannot represent is ineligible; do not
silently approximate it. Before precomputation, compare reconstructed and
direct **complex** matrices on fixed events for both polarizations, across
multiple parameter vectors and threshold, cut, upper-domain and pole-adjacent
conditions. Retain source parameter provenance in the basis fingerprint.

On common, fixed phase-space samples, integrate all needed Hermitian
interference products of basis matrices for the polarized numerator and
denominator. A small set of per-bin moment matrices then produces
`Sigma(theta) = N(theta)/D(theta)` without repeating production loops for
every optimizer step. Validate these moments against direct full-model bin
integration at source and independent off-source parameter points. Track
numerical covariance and convergence of the moments over the allowed
parameter domain, not only of a cancellation-prone ratio at one parameter
point. Require finite positive denominators. Reuse the same certified
event-amplitude basis definitions, but integrate distinct moments for Ajaka
publication bins and Stage 07 native bins with their respective energy
weighting. Label sourced and fitted parameters and outputs separately. The
direct evaluator remains selectable for audit.

This scheme speeds **parameter scans**. It does not by itself solve the
phase-space variance already seen at fixed parameters. Continue the
source-equivalent variance work, measured throughput checks, conditional
sampling and per-bin power selection from the existing TDD plan before
certifying production moments. Do not relax integration tolerances or infer
convergence from agreement with Ajaka. If the eligible physical couplings do
not yield a compact exact basis, report that result and revise parameter
selection before considering an emulator.

## Experimental data and objective

The first fit targets Stage 07's **binned** `Sigma`, not individual
reconstructed events. Read the UV `raw_bdt/ratio` nominal points and their
matching covariance rows by original ROOT point index; verify ID mapping,
units, energy and mass edges, sample/estimator identity, finiteness and
provenance. Ratio is the primary estimator because it matches the existing
Figure 4 extraction path and owns the current run-bootstrap covariance.
Likelihood points, extracted from the same events, are a sensitivity check;
they are not additional independent observations. The three pair-mass
projections also share events and require cross-projection statistical
covariance for a final joint fit.

Map predictions to the **actual Stage 07 bins** and measured incident-energy
exposure. Keep this native-data weighting separate from the uniform
incident-energy weighting used for the primary Ajaka publication calculation.
Check that flux, polarization, azimuth-sign conventions and selected run set
are compatible with the Stage 07 estimator. Assess acceptance effects with
available simulation/control studies before interpreting fitted couplings;
if acceptance does not cancel sufficiently in the ratio, specify a validated
response treatment before the final fit. Do not equate a generator-level
curve with a detector-level estimator without this check.

For a validated data vector `d`, prediction `mu(theta)` and covariance `C`,
use a documented generalized least-squares objective
`(d-mu)^T C^{-1} (d-mu)` with only justified parameter constraints or
nuisance terms. Check covariance symmetry, positive definiteness, conditioning
and point order. Do not silently invert a singular matrix, double-count
ratio/likelihood points, or treat digitization bounds as Gaussian data errors.
Numerical integration error must be gated against the experimental precision
and reported separately. Fit diagnostics include residuals, parameter
correlations, sensitivity/Jacobian rank, boundary hits, and a direct-model
recheck at the optimum.

The present uncorrected, no-bootstrap ROOT file supports loader, alignment,
plotting and synthetic-objective tests. It may support a clearly labeled
exploratory numerical fit only once enough matching theoretical bins converge;
no final physical coupling estimate follows from it. Two certified individual
Figure 4 bins are presently insufficient to identify a multi-parameter fit.

Final data require a reviewed Stage 07 release with sideband background
correction, a reviewed positive run-bootstrap replica count, and QA of
materialized systematic covariance components. The existing Stage 07
bootstrap resamples nominal ratio points across all three mass projections;
its cross-projection block must be inspected before a joint fit. Missing
input artifacts, lost bins in replicas, unstable covariance, or failed
acceptance checks block a final inference. Stage 07's unresolved best-quartet
limitation remains explicit in the interpretation until resolved or bounded.

## Workflow, tests and acceptance

1. Freeze sourced defaults and baseline numerical evidence. Keep the existing
   direct Figure 4 gates, masks and independent Ajaka digitization unchanged.
2. Diagnose and reduce four-coordinate coherent-integrand variance on
   representative bins. Certify enough bins and measured runtime to justify
   a full campaign; do not launch all panels at a failing setting.
3. Audit candidate production couplings for exact factorization. Test source
   and off-source event matrices, then precomputed bin moments against direct
   results. Measure build and per-iteration cost on available hardware.
4. Build Stage 07 reader and covariance-aligned fit objective. Test with
   synthetic, identifiable data: recover injected couplings and reject
   shuffled indices, duplicate estimators, nonfinite predictions and invalid
   covariance. Use current ROOT output only for development and QA.
5. Run final Stage 07 extraction and all expensive numerical campaigns only
   after their inputs, commands and outputs are checked. Certify each
   physical bin and the parameter-domain basis. Fit the full supported native
   dataset; perform direct-model and estimator-sensitivity checks.
6. Calculate the sourced and fitted twelve-panel predictions separately.
   Apply the existing Ajaka comparison statuses and mask rules to both,
   clearly identifying which result is the sourced reproduction test.

The sourced result may claim `reproduced` only under the existing
panel-by-panel physical-support, convergence and compatibility criteria. A
fit result may claim a successful description of GRAAL data only with a
validated covariance, identifiable parameters, converged predictions and
reported fit diagnostics. If either gate fails, publish the failing status
and cause rather than an interpolated line through unresolved bins.

## Long-running execution and artifacts

The assistant writes code, documentation and runs short focused checks.
Before any fit, bootstrap, full test suite or integration expected to take
substantial time, it provides the user with the exact command, estimated
duration, CPU/memory assumptions, input paths, output paths and success/fail
signals. The user launches long work and returns its logs or artifacts for
analysis. Estimates come from measured pilots; unmeasured campaigns are
labeled as such. No long job starts silently.

Long campaigns use deterministic seeds and a dedicated output directory with
parameter, source, code, data, binning and numerical-setting fingerprints.
Save completed per-bin work with completion markers so interruption does not
erase certified results and resumption cannot mix incompatible settings.
Never use an incomplete directory as a completed curve or fit. Preserve
production data; generated outputs are ignored by Git and need their own
retention and provenance.

## Handoff to implementation planning

After review of this design, update the Figure 4 TDD plan to reflect this
ordering and add bounded tasks for exact-basis proof, moment convergence,
Stage 07 ROOT/covariance ingestion, synthetic fit recovery, source-versus-fit
reporting, and user-run production commands. Keep the existing physical
oracle and source checks. Do not introduce a fit optimizer before the
prediction and covariance contracts have focused tests.
