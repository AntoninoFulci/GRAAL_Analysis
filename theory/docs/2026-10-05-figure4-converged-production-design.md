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
ceiling. Record digitization uncertainty and do not use this curve for tuning.

### 2. Validated strong-T grid

Brute-force reevaluation of the same one-dimensional strong matrix inside
nested event and loop integrations is unnecessary. Introduce one concrete,
immutable `StrongTGrid` value owned by the strong-amplitude layer. It is an
acceleration of `reconstructed_full_tmatrix`, not a new physical model and not
a generic plugin framework.

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
energy interval. Compare order `n` with `2n`. The primary publication
calculation uses uniform incident-photon weighting because Ajaka specifies the
intervals but not the theory-line photon spectrum. A measured-flux-weighted
calculation is a separately labeled sensitivity result when a provenance-
complete spectrum is available. It cannot replace the primary result merely
because it agrees better with the digitized stroke.

Independent scrambled Sobol replicates provide numerical covariance across
mass bins. Fixed seeds and identical events for horizontal/vertical
polarizations preserve correlations and reduce asymmetry noise. The older
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
- status and mask reason;
- source, parameter, and code fingerprints.

Generate a 4-by-3 comparison figure containing experimental points only where
requested by the existing comparison workflow, digitized published theory
strokes, and newly calculated curves. Calculated line segments stop at every
masked bin. Never connect across a missing, unsupported, or unconverged value.

Compare predictions with
`theory/references/ajaka2008_figure4_theory.csv`. At each overlapping mass,
interpolate only between adjacent accepted calculated bins and combine the
`0.020` digitization bound with numerical uncertainty. Never interpolate
through a mask or beyond the calculated support. Do not add an invented
quantitative allowance for PRC65 high-energy limitations. Preserve point
statuses `compatible`, `discrepant`, `unresolved`, and `masked`; a panel passes
reproduction only when all resolved points in its published stroke are
compatible and every physically supported calculated segment is converged.
Sensitivity weightings cannot upgrade the primary uniform-weight status.

Outputs live under a dedicated ignored `theory/outputs/` run directory and
include CSV/JSON predictions, covariance, comparison PDF, residual table, and a
Markdown validation report. The report states clearly whether all twelve
panels pass. A scientifically complete negative result is allowed; it must name
the discrepant panels and cannot be relabeled as reproduction.

## Numerical and scientific gates

A bin is publishable only if all applicable checks pass:

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
3. conditional phase-space tests against independent one-dimensional phase-
   space integrals and whole-space sums for constant amplitudes;
4. analytic toy-amplitude tests for sign, finite-phi attenuation, covariance,
   partial support, and energy weighting;
5. real seven-family direct-versus-grid and convergence tests;
6. twelve-panel output/schema/reference comparison tests;
7. dormant/active explicit-resonance pole regressions;
8. full standalone theory suite.

The final review must separately assess software correctness, numerical
convergence, and physics claims. Passing tests alone cannot upgrade a masked or
source-limited scientific result.

## Handoff to native-data fitting

This increment ends at converged publication-bin curves and their validation.
The next design reuses the same conditional integrator and coherent model with
native energy/mass bins, measured horizontal/vertical flux and polarization,
the native estimator, and experimental covariance. It may add fitted physics
parameters only after specifying priors, bounds, identifiability, and nuisance
systematics. No fit parameter is introduced here.
