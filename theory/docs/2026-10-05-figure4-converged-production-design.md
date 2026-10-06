# Converged full-production curves for Ajaka Figure 4

## Purpose and success criterion

This increment must turn the existing seven-family coherent
`gamma p -> eta pi0 p` amplitude into numerically converged beam-asymmetry
curves for all twelve panels of Ajaka et al., Figure 4. It follows the model
of Ajaka Refs. [11,12], not a fit to the digitized strokes. The digitized
strokes remain validation data only.

The order is fixed:

1. make the sourced strong amplitude evaluable over the complete invariant-
   mass domain required by the four published photon-energy bins;
2. make direct full-production integration practical without replacing direct
   quadrature as the numerical authority;
3. establish convergence in every physically populated publication bin;
4. generate and compare all twelve calculated curves;
5. only after this gate, design the fit to the higher-statistics native data.

Success requires finite and converged predictions over every physically
accessible portion of the twelve panels, explicit masks elsewhere, and a
panel-by-panel comparison against the independently digitized Ajaka theory
strokes. A fast but unconverged curve, a line drawn through a mask, or a curve
made by fitting the digitized stroke does not satisfy the milestone.

Work remains inside `theory/`. Stage 07/08 code and outputs, native-data
fitting, new reaction channels, parameter tuning, and second-sheet pole work
are outside this increment.

## Starting point

The full model already computes seven complete spin-amplitude families and
sums them as complex matrices before the spin sum:

```text
M_full = sum_f M_f
|M_epsilon|^2 = 1/2 sum_spin |M_full|^2
```

The software audit passes, but the physical gate does not. The current audit
accepts zero of four representative energies: upper-bin events request a
strong invariant above the hard `W <= 1.70 GeV` limit, while brute-force
loop-plus-Sobol refinement is too expensive to certify full spectra. Existing
statuses `compatible`, `discrepant`, `unresolved`, and `masked` must remain
distinct.

The earlier broad design remains authoritative for Figure 4 conventions:
`theory/docs/2026-10-01-figure4-theory-design.md`. This document specifies the
missing physical-domain and numerical architecture needed to execute it.

## Source boundary for the strong amplitude

Three local primary-source facts constrain the extension:

- Doring, Oset, and Strottman, *Phys. Rev. C* **73**, 045209 (2006),
  Sec. V A and Fig. 18, explicitly apply the full and reduced `N*(1535)`
  models at photon energies from `1.2` through `1.7 GeV`; the plotted
  `M(eta p)` range reaches about `1.8 GeV`.
- Inoue, Oset, and Vicente Vacas, *Phys. Rev. C* **65**, 035204 (2002),
  state that their scattering amplitudes agree qualitatively with data from
  threshold to `1.6 GeV` and differ qualitatively above that energy. Their
  fitted high-energy numbers are described as indicative.
- Ajaka et al., *Phys. Rev. Lett.* **100**, 052003 (2008), use four bins from
  `[1.10,1.20)` through `[1.40,1.50] GeV`. With the repository proton and
  neutral-pion masses, the last bin has the exact kinematic limit
  `max M(eta p) = sqrt(m_p^2 + 2 m_p E_gamma) - m_pi0 = 1.7873058993 GeV`.

Ajaka Ref. [12], Doring, Oset, and Strottman, *Phys. Lett. B* **639**, 59
(2006), remains the later reaction-level source for the implemented
`Delta*(1700)` coupling/width conventions. This increment preserves those
conventions; the strong-domain extension does not substitute a new resonance
fit or revert to PRC73-only production parameters.

Therefore `1.80 GeV` is a **source-use ceiling**, because PRC73 actually uses
the model there. It is not a claim that PRC65 validated the strong amplitude
against scattering data up to `1.80 GeV`. Reports must distinguish:

- `validated_scattering_region`: `W <= 1.60 GeV`;
- `source_used_extension`: `1.60 < W <= 1.80 GeV`;
- unsupported: `W > 1.80 GeV`, which remains an error or mask.

The first label records the source's **qualitative** scattering-data agreement;
it does not imply a quantified model uncertainty or exact data reproduction.

No polynomial, loop, or amplitude may be extrapolated past `1.80 GeV`. Every
reported bin records the fraction of its unpolarized denominator produced by
events in the source-used extension. This is a limitation indicator, not an
invented numerical systematic uncertainty.

Source files and immutable identities:

- `tmp/pdfs/10.1103@PhysRevC.73.045209.pdf`, SHA-256
  `19a2fbce10ed8201a29bdfbcfb9f3690a280d943c1e83db01aa1b2057d20eccb`;
- `tmp/pdfs/PhysRevC.65.035204.pdf`, SHA-256
  `e8861394ef3fb86c005694d3cb82d8c2b905e39dbe384903f58392d644cff6ac`;
- `tmp/pdfs/10.1016@j.physletb.2006.06.022.pdf`, SHA-256
  `c1def91b01ee5750aca4124ae2469178b204d99649075d7d4f4277facab9d430`;
- `tmp/pdfs/PhysRevLett.100.052003.pdf`, SHA-256
  `7fdf85fe56fa8b0e232d070269e3e58d4d7ca542dcd9ac2287291abaa6b4f1cb`.

The local PDF structural preflight was unavailable because `pypdf` is absent.
Consequently this design uses article sections, figure numbers, equations, and
file hashes as locators; it does not claim independently verified PDF page
anchors.

## Architecture

### 1. Direct strong-T authority and bounded domain extension

The existing `reconstructed_full_tmatrix` remains the reference evaluator.
Extend the shared real-axis validation and the `pi pi N` loop ceiling from
`1.70` to exactly `1.80 GeV`; do not remove their upper bound. Preserve the
same equations, masses, subtraction constants, VMD switching prescription,
quadrature checks, condition-number guard, and finite/symmetry checks.

Required direct checks include all channel thresholds, all VMD switching
landmarks, `W = 1.60`, `1.70`, `1.75`, and `1.80 GeV`, plus points one floating-
point step to either side of each internal landmark. Existing values at and
below `1.70 GeV` must remain unchanged to their current regression tolerance.
At every new point require a finite complex symmetric matrix and a small
residual of `(I - V G) T = V`.

Add one bounded high-energy production comparison from PRC73 Fig. 18. It need
not digitize all six Fig. 18 panels: the `E_gamma = 1.7 GeV` full-model
`M(eta p)` curve is sufficient to exercise the strong input through the new
ceiling. Compare only source points with `M(eta p) <= 1.80 GeV`; the published
panel continues beyond that mass, but its tail cannot authorize extrapolating
this reconstruction. Record digitization uncertainty and do not use this
curve for tuning. This is an additional high-energy source check, not a
substitute for the Ajaka Figure 4 gate.

### 2. Validated strong-T grid

Brute-force reevaluation of the same one-dimensional strong matrix inside
nested event and loop integrations is unnecessary. Introduce one concrete,
immutable `StrongTGrid` value owned by the strong-amplitude layer. It is an
acceleration of `reconstructed_full_tmatrix`, not a new physical model and not
a generic plugin framework.

The grid is a correctness-preserving cache, but it is **not** sufficient as
the main throughput solution. A measured `W=1.62 GeV` direct strong-T call
took about `0.0013 s`, whereas one seven-family event at `E_gamma=1.2 GeV`,
q/angle order `32`, one polarization took about `16.9 s`. Roughly `13.1 s`
was in `explicit_resonances`; profiling traced repeated scalar Eq. (26)
quadrature and per-node source validation. These measurements are local
performance evidence, not extrapolated physics acceptance.

Construction rules:

- sample the direct evaluator over its physical domain;
- split intervals at every meson-baryon threshold and VMD switching landmark;
- interpolate real and imaginary parts separately with adaptive piecewise
  linear segments, avoiding cubic overshoot and never interpolating across a
  threshold or switch;
- recursively refine an interval until direct midpoint and quarter-point
  checks satisfy combined absolute/relative matrix tolerances;
- return fresh or read-only `complex128 (6,6)` matrices;
- reject parameter or vector-mass fingerprints that differ from those used to
  build the grid.

The cache key contains every immutable input that can change a value:
strong parameters, vector masses, domain endpoints, landmark set, direct
quadrature settings, interpolation tolerances, and implementation version.
An in-memory bounded cache is enough for this increment; no persistent cache
format is required.

Direct quadrature remains selectable in validation runs. Grid acceptance
requires both:

1. matrix agreement at deterministic off-grid points, using absolute tolerance
   near zeros and relative tolerance elsewhere;
2. agreement of polarized full-model event weights and final publication-bin
   asymmetries on fixed samples.

Target bounds are `max(1e-8 GeV^-1, 1e-4 |T_direct|)` elementwise matrix
error, `0.25%` relative error for non-negligible polarized event weights, and
`0.002` absolute error in final `Sigma`. If these bounds require too many
nodes, keep direct evaluation for the failing interval rather than loosening
the gate.

`EtaPi0PFullModel` may consume a matching `StrongTGrid`; omitted grid means the
direct evaluator. This is dependency injection for a validated numerical
representation, not injection of an arbitrary strong model. Physical
parameters and the grid fingerprint must match before any family evaluation.

### 2b. Direct production-loop throughput gate

Before running the full twelve-panel calculation, retain the current scalar
production quadrature as an independent oracle and make the same direct
integrals practical. Profile representative low- and upper-energy events by
family. First hoist event-constant source parameters, spin factors, and width
values out of radial/angle node loops; then batch node evaluation in the
existing Eq. (8)/(26) quadrature path where numerical branches allow it.
Preserve principal-value subtraction, `+i0` cut, radial landmarks, endpoint
rules, and configured/doubled-order checks. No surrogate or interpolation of
production loops is authorized by this throughput work.

For each optimized family, compare complete complex spin matrices with the
scalar oracle on fixed threshold, cut, pole-adjacent, and upper-domain events
for both polarizations and both quadrature orders. Record a measured
per-event throughput and project the cost of the required energy nodes,
conditional Sobol points, scrambled replicates, and refinements. Full-panel
execution starts only if the measured projection is at most `24 h` on
available hardware. This is a planning threshold, not a physics tolerance;
otherwise retain typed `not_completed_runtime_bound` masks and revise the
computational plan, never infer convergence from a fast partial run.

### 3. Mass- and energy-stratified phase space

Whole-space Sobol sampling poorly resolves narrow or partially accessible
publication bins. Add a conditional three-body sampler that integrates one
requested pair-mass window directly. It reuses the existing factorized
Lorentz-invariant phase-space map, permutes daughters only internally, restores
canonical `(eta, pi0, proton)` ordering, and carries the exact restricted
`ds_pair` Jacobian. Existing `sample_three_body` behavior and fingerprints stay
unchanged.

For each nominal mass bin and photon energy:

1. intersect the nominal interval with exact kinematic support;
2. mark an empty intersection `masked_kinematic`, never as zero asymmetry;
3. sample the accessible interval directly using a deterministic Sobol block;
4. compute both photon polarizations on identical events;
5. accumulate polarized numerator, unpolarized denominator, their covariance,
   accessible support, and weighted mass position.

Photon-energy integration uses fixed Gauss-Legendre nodes inside each published
energy interval. For each mass bin, split the interval at the exact incident-
energy onset where its lower mass edge first becomes accessible, then integrate
only the accessible energy subinterval. This removes a step in the integrand
that would otherwise make a fixed-order edge-bin check misleading. Compare
order `n` with `2n` on the same subinterval. The primary publication
calculation uses uniform incident-photon weighting because Ajaka specifies the
intervals but not the theory-line photon spectrum. A measured-flux-weighted
calculation is a separately labeled sensitivity result when a provenance-
complete spectrum is available. It cannot replace the primary result merely
because it agrees better with the digitized stroke.

Independent scrambled Sobol replicates provide numerical covariance across
mass bins. Use the same replicate identifiers across bins to estimate their
joint covariance, even though each conditional mass-bin sample is distinct.
Fixed seeds and identical events for horizontal/vertical polarizations
preserve correlations and reduce asymmetry noise. The older
nonscrambled `p` versus `p+1` comparison remains an independent bias check.

### 4. Beam-asymmetry observable

For each pair (`p_pi0`, `p_eta`, `eta_pi0`), use the azimuth of the pair-momentum
sum around the photon axis, measured from the horizontal plane. Preserve the
Ajaka/Ref. [14] vertical-minus-horizontal sign convention.

The primary model line is formed from integrated polarized cross sections,
not from separately averaged eventwise ratios. For fully polarized horizontal
and vertical basis states, the tested sign convention gives:

```text
Sigma_b = 2 integral_b dPhi cos(2 phi)
              [w_vertical - w_horizontal]
          / integral_b dPhi [w_vertical + w_horizontal]
```

For the full coherent model, the redundant global azimuth is integrated
analytically using its horizontal and vertical complex spin matrices. If
`C=Re Tr(M_H^† M_V)/2`, `D=w_V-w_H`, and the sampled pair azimuth is `phi`,
the exact global-angle contribution to the numerator is
`D cos(2phi)-2 C sin(2phi)`; its denominator is `w_V+w_H`. Each separately
integrated H/V normalization equals half that denominator. The model's
rotation covariance was checked on a real seven-family event. Conditional
Sobol sampling therefore fixes the spectator global azimuth to zero and uses
four coordinates (pair mass, two polar cosines, relative azimuth). This is a
variance reduction of the same continuous-phi observable, not a change of
polarization sign or a fit to the published line. The old five-coordinate
sampler remains the direct Monte Carlo diagnostic.

The implementation must verify this normalization with synthetic amplitudes.
It must not introduce a second sign convention to match Figure 4. Twelve-bin
finite-phi center fitting remains a diagnostic reproduction of the experimental
estimator; the continuous polarized-cross-section projection is the primary
theory observable. Their difference is reported.

Data flow:

```text
Ajaka energy interval
    -> Gauss-Legendre energy node
    -> nominal pair-mass bin intersected with kinematic support
    -> conditional Sobol phase space
    -> direct or validated-grid strong T
    -> coherent sum of seven complex spin-amplitude families
    -> horizontal and vertical event weights
    -> correlated numerator/denominator accumulation
    -> Sigma, numerical covariance, support metadata, status
    -> twelve-panel comparison and report
```

### 5. Figure 4 comparison and outputs

Generate machine-readable predictions for all four energy intervals and all
three pair definitions. Each bin carries:

- nominal and accessible mass ranges;
- weighted mass position;
- `Sigma` and numerical uncertainty;
- covariance row identifier;
- direct/grid mode and numerical settings;
- strong-domain extension fraction;
- status and mask reason, distinguishing `masked_kinematic`,
  `masked_unsupported_domain`, and `masked_nonconverged`;
- source, parameter, and code fingerprints.

Generate a 4-by-3 comparison figure containing experimental points only where
requested by the existing comparison workflow, digitized published theory
strokes, and newly calculated curves. Calculated line segments stop at every
masked bin. Never connect across a missing, unsupported, or unconverged value.

Compare predictions with
`theory/references/ajaka2008_figure4_theory.csv`. At each overlapping mass,
interpolate only between adjacent accepted calculated bins and combine the
`0.020` digitization **bound** conservatively with the numerical error bound;
do not treat it as a Gaussian standard deviation. Never interpolate
through a mask or beyond the calculated support. Do not add an invented
quantitative allowance for PRC65 high-energy limitations. Preserve point
statuses `compatible`, `discrepant`, `unresolved`, and `masked`; a panel passes
reproduction only when all resolved published points within exact physical
support are compatible and every physically populated nominal bin is
converged. Expected `masked_kinematic` bins outside that support do not fail
the panel; an accessible bin masked for nonconvergence does.
Published points outside exact kinematic support or the calculated interval
are recorded as `masked` with their reason; they cannot silently disappear
from the comparison or count as agreement. A complete, converged calculation
with one or more `discrepant` panels is a valid negative scientific result,
reported as `calculated_discrepant`, never `reproduced`. Tests passing means
software gates pass, not that the physical reproduction claim passes.
Sensitivity weightings cannot upgrade the primary uniform-weight status.

Outputs live under a dedicated ignored `theory/outputs/` run directory and
include CSV/JSON predictions, covariance, comparison PDF, residual table, and a
Markdown validation report. The report states clearly whether all twelve
panels pass. A scientifically complete negative result is allowed; it must name
the discrepant panels and cannot be relabeled as reproduction.

## Numerical and scientific gates

A bin is publishable only if all applicable checks pass:

- the scalar-oracle and accelerated production quadratures agree on fixed
  physical events, and measured throughput supports a complete run (a
  practical planning gate, never a substitute for any physics gate);
- inner production-loop configured/doubled quadratures pass on representative
  high-impact events, including upper-domain events;
- strong-grid and direct evaluations meet the bounds above;
- energy order `n/2n` changes `Sigma` by at most `0.005` and each non-negligible
  polarized normalization by less than `1%`;
- nonscrambled Sobol `p/p+1` changes `Sigma` by at most `0.01`, total weight by
  less than `1%`, and every populated normalization bin carrying at least
  `1e-4` of total weight by less than `3%`;
- independent scrambled replicates yield finite covariance and numerical
  standard error no larger than `0.01` in `Sigma`;
- `|Sigma| <= 1` within roundoff;
- the three invariant-mass integrations agree with the same total polarized
  cross sections within numerical tolerances;
- direct Eq. (43), reduced strong-T, pion-corrected strong-T, VMD, and existing
  full-model regression fingerprints remain unchanged where their domains
  overlap.

Failure produces a typed mask or discrepancy, never relaxed tolerances or
parameter adjustment. Expensive convergence settings are selected from measured
refinement, not from agreement with Ajaka.

## Required corner-case repair

The explicit-resonance preflight currently rejects a dormant source when
`f_delta_n_pi = 0`, both `N* Delta pi` couplings are zero, the Delta width is
zero, and an unrelated strong transition is nonzero. Repair the ownership rule:
pole and width validation applies only to an active source term. Dormant terms
return exact zero, while any active term retains the strict hidden-pole guard.
This repair is regression-scoped and does not change nominal parameters.

## Verification structure

Implementation follows test-driven development and independent review. Tests
are grouped by responsibility:

1. source-domain tests for the `1.80 GeV` ceiling and unchanged lower-domain
   fingerprints;
2. direct/grid tests at landmarks and off-grid points;
3. source-equivalent direct-production throughput tests and runtime projection;
4. conditional phase-space tests against independent one-dimensional phase-
   space integrals and whole-space sums for constant amplitudes;
5. analytic toy-amplitude tests for sign, finite-phi attenuation, covariance,
   partial support, and energy weighting;
6. real seven-family direct-versus-grid and convergence tests;
7. twelve-panel output/schema/reference comparison tests;
8. dormant/active explicit-resonance pole regressions;
9. full standalone theory suite.

The final review must separately assess software correctness, numerical
convergence, and physics claims. Passing tests alone cannot upgrade a masked or
source-limited scientific result.

## Execution audit, 2026-10-05 to 2026-10-06

Source-equivalent vectorization of Eqs. (26) and (25) now reduces one warm
seven-family event/polarization at `E_gamma=1.5` from roughly `9.9 s` to
`0.28 s` at q/angle `32/32`, or `0.63 s` at sourced default `64/48` (the first
event also computes the cached resonance width). Exactly 78 of 120 nominal
bins are kinematically accessible. Four measured processes deliver 4.206
event/polarization evaluations per second versus 1.136 for one process.
These measurements make a minimum-setting calculation plausible, but do not
establish that the necessary energy/Sobol refinements will converge within
24 hours. The Task 3C feasibility gate remains open until a real pilot fixes
those settings and includes every mandatory check. No twelve-panel
reproduction claim is currently supported. The physics objective and every
numerical tolerance remain unchanged.

The first real conditional pilot exposed an Eq. (25) tangent recoil cut in
`K+Lambda` at `E_gamma=1.4069431844202973 GeV`,
`M(eta p)=1.61009316501 GeV`. Its original scalar quadrature failed even at
`2048/1536`. Exact analytic recoil-angle integration, including the `+i0`
logarithm, now makes that event pass the unchanged configured/doubled loop
gate at `64/48`; the corresponding radial-source Eq. (26) integral uses the
same treatment. This resolves the specific Task 3D blocker, not all possible
events or the publication-bin convergence gate.

For the first seven-family `p_eta` publication bin, energy `[1.40,1.50]` and
mass `[1.60,1.64]`, exact global-azimuth averaging reduces conditional Sobol
dimension from five to four. At energy order four and loop `64/48`, four-
coordinate `p4/p5/p6` gave approximately
`Sigma=-0.508793605/-0.506391888/-0.512297379` and unpolarized
denominators `1.163684060/1.184197284/1.204877917`. The `p5/p6`
values are from the latest source-equivalent diagnostic run; differences
of a few parts per million from earlier pilot output do not affect gates.
The `p5/p6` Sigma difference passes `0.01`, but denominator change is about
`1.72%`, failing the strict `<1%` gate. No numerical acceptance follows.
At raised inner order `96/72`, all events of the same `p7` bin pass their
unchanged configured/doubled checks, giving `Sigma=-0.508868327` and
denominator `1.217629483` in `1288.9 s`. A fresh same-order `p6` run at
`96/72` gives `Sigma=-0.512297379`, denominator `1.204877915` in
`644.4 s`. The formal `p6/p7` denominator change is `1.047245%`, again
failing `<1%`, while `Delta Sigma=0.003429` passes `0.01`.
Partitioning the fresh `p5/p6` denominator at the sourced `K+Lambda`
threshold (`1.60936 GeV`) gives changes `-0.00994` below threshold,
`+0.02570` in `[1.60936,1.62)`, and `+0.00492` in `[1.62,1.64)`.
The narrow interval immediately above threshold drives more than the net
`+0.02068` drift, with partial cancellation below. This identifies a
specific mass region for source-equivalent stratification, without proving
that stratification will pass the gate.
An exact two-stratum trial at `1.60936 GeV` preserved volume and nested
Sobol points in toy tests, but its deterministic zero point landed exactly
on the new threshold and failed the Eq. (25) cut check even at `512/384`.
A fixed digital shift avoided that endpoint; a nearby sampled event at
`M(eta p)=1.60929498643 GeV` still failed at `64/48` and `96/72`.
The trial was reverted from the production sampler. Subsequent isolated
Eq. (25) regressions now pass below, on, and above this threshold after
stationary-point radial splitting and stable recoil-log evaluation. A
complete stratified publication bin and its variance gate remain untested;
do not use an unverified split for the curves.
The exact recoil-angle branch remains algebraically equivalent to Eq. (25):
`q_on²-q²=(W-omega-E_left)(q0_on+omega)(W-omega+E_left)/(2W)`, and
`(1/A-1/B)/(B-A)=1/(AB)` for the two baryon denominators. Its physical
logarithm has the required negative imaginary cut. The remaining blocker
is full-bin Sobol normalization convergence, not a missing numerator factor.
At measured `p6` runtime about `355 s` per bin, 78 accessible bins and the
required base, doubled-energy, `p+1`, eight replicas, and direct comparison
cost at least `78 * 355 * (1+2+2+8+1) / 4 = 96,915 s`, or `26.9 h`, on four
measured workers. This omits startup, source comparison, and any further
refinement. The 24-hour feasibility gate therefore fails at `p6` on the
measured four-worker setup. The host reports 14 logical CPUs. A separate
56-evaluation warm-event benchmark measured `6.04`, `11.62`, and `15.13`
event/polarization evaluations per second at 4, 8, and 14 workers. Its
14-worker rate is 2.50 times its four-worker rate, implying a rough `10.8 h`
projection for the same `p6` workload. Event mix, process startup,
inner-order failures, and convergence refinements make that an estimate,
not a passed feasibility gate. The `p6` normalization gate already fails.
Do not start the twelve-panel run at this setting. The next throughput task
must confirm representative complete-bin scaling or reduce the
remaining angular/mass variance through source-equivalent integration; it
must remeasure complete certification cost before Task 10.
At the measured `p7`/`96/72` cost, a same-cost estimate for the eight
accessible bins of the upper `p_eta` panel is
`8 * (1+2+2+8+1) * 1288.9 s = 40.1 h` on its single panel worker; the
current CLI parallelizes by panel. Different bins may cost less or more, so
this is a workload projection, not a lower bound. Bin-level parallelism and
shared H/V work would be needed to revisit throughput if `p7` or higher
powers prove numerically necessary. The strict numerical blocker remains
the measured same-order `p5/p6` and `p6/p7` denominator failures.

## Handoff to native-data fitting

This increment ends at converged publication-bin curves and their validation.
The next design reuses the same conditional integrator and coherent model with
native energy/mass bins, measured horizontal/vertical flux and polarization,
the native estimator, and experimental covariance. It may add fitted physics
parameters only after specifying priors, bounds, identifiability, and nuisance
systematics. No fit parameter is introduced here.
