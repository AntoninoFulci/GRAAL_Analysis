# Coherent gamma p -> eta pi0 p production: design

## Purpose and milestone boundary

Implement the complete complex production amplitude used by Döring, Oset,
and Strottman for `gamma p -> eta pi0 p`, combining the already implemented
Eq. (43) tree with the production and rescattering families in Figs. 6--10 of
*Phys. Rev. C* **73**, 045209 (2006). This is Increment A of the remaining
path to Ajaka et al. Figure 4:

1. coherent production amplitude (this increment);
2. twelve publication-binned Ajaka curves and their validation;
3. native-bin overlay and covariance-aware fit to our experimental
   asymmetries.

This increment produces a polarized full-model API and validates its
unpolarized components and coherent sum. It does not yet generate the twelve
Ajaka curves or fit experimental data. Stage 07/08 code and outputs remain
untouched. Work continues directly on `main`, as explicitly requested, while
preserving all pre-existing dirty and untracked files.

The scientific objective remains a predictive and eventually fittable model,
not an interpolation of published curves. Published traces are independent
validation datasets and are never inputs to parameter estimation during this
increment.

## Primary sources and adopted baseline conventions

The principal amplitude source is Döring, Oset, and Strottman, *Phys. Rev. C*
**73**, 045209 (2006), local PDF
`tmp/pdfs/10.1103@PhysRevC.73.045209.pdf`, SHA-256
`19a2fbce10ed8201a29bdfbcfb9f3690a280d943c1e83db01aa1b2057d20eccb`.
Supporting inputs come from:

- Nacher et al., *Nucl. Phys. A* **695**, 295 (2001), local PDF
  `tmp/pdfs/nucl-th-0012065.pdf`, for two-pion resonance production,
  widths, and pion form-factor conventions;
- Sarkar et al., *Nucl. Phys. A* **750**, 294 (2005), local PDF
  `tmp/pdfs/nucl-th-0407025.pdf`, for dynamically generated
  `Delta*(1700)` couplings;
- Inoue et al., *Phys. Rev. C* **65**, 035204 (2002), local PDF
  `tmp/pdfs/PhysRevC.65.035204.pdf`, for the six-channel strong amplitude;
- Butler, Savage, and Springer, *Nucl. Phys. B* **399**, 69 (1993), author
  preprint `tmp/pdfs/9211247v1.pdf`, for the decuplet-state phase convention.

The previously implemented `reconstructed_full_tmatrix` is the baseline
strong amplitude. Its documented rho/K* assignment and sourced modern mass
set are accepted for this milestone despite incomplete historical convention
information. They no longer block production-amplitude work.

Where the papers leave conventions unprinted, use one inspectable baseline:

- the decuplet phases attributed to Butler et al. in PRC 73 Sec. IV D;
- the quoted signs of `g_eta = 1.7 - 1.4 i` and
  `g_K = 3.3 + 0.7 i`;
- the charge factors and empirical `1.15` correction printed in
  PRC 73 Eqs. (39)--(42);
- sourced masses and the `Lambda = 1.4 GeV` first-loop cutoff used by the
  principal paper.

These are baseline reconstruction choices, not newly inferred paper results.
Their values and provenance must appear in generated metadata. Later work may
treat alternative signs or mass conventions as discrete model variants or
nuisance choices; this increment does not tune them to published curves or to
our data.

## Coherent amplitude architecture

Every production family exposes a function returning the same object:

```text
amplitude(sample, photon_polarization, parameters, strong_amplitude)
    -> complex array [event, final nucleon spin, initial nucleon spin]
```

Concrete functions are used directly. No abstract plugin layer or generic
reaction framework is introduced for this single channel. Each family owns
its source equation, channel coefficients, loop integration, and propagators.
All families receive identical event kinematics and polarization conventions.

For each event and photon polarization,

```text
M_full = M_chiral + M_external_pi0 + M_internal_pi0
       + M_explicit_resonances + M_eta_delta_rescattering
       + M_k_sigma_star_rescattering + M_Eq43_tree
```

The complex spin matrices are summed before spin sums or squaring. The
polarized observable is then

```text
|M_epsilon|^2 = (1/2) sum_initial,final |M_full|^2.
```

An incoherent sum of family cross sections is forbidden. Diagnostic family
selection is allowed only through an explicit diagnostic API; the physical
full-model entry point always includes every implemented family and cannot
silently omit one.

The seven contributions are:

1. chiral magnetic/contact production with rescattering, Fig. 6 and
   Eq. (21);
2. external `pi0` emission around `gamma p -> eta p`, Fig. 7 and Eq. (24),
   using the coherent Kroll--Ruderman plus meson-pole subamplitude of
   Eqs. (8)--(9);
3. `pi0` emission inside the first meson--baryon loop, Fig. 8(c,d) and
   Eq. (25), retaining both terms required by the paper's gauge argument;
4. explicit `Delta*(1700) pi Delta`, `N*(1520) pi Delta`, and Delta
   Kroll--Ruderman plus pole kernels, Fig. 9 and Eqs. (26)--(37);
5. `Delta*(1700) -> eta Delta` followed by `eta p` rescattering, Fig. 10
   and Eq. (39) inserted into Eq. (26);
6. `Delta*(1700) -> K Sigma*` rescattering plus the `Sigma*`
   Kroll--Ruderman term, Fig. 10 and Eqs. (40)--(42) inserted into Eq. (26);
7. the isolated `Delta*(1700) -> eta Delta -> eta pi0 p` tree,
   Fig. 11 and Eq. (43), which already exists and remains separately callable.

Kroll--Ruderman and related meson-pole partners that the source treats as a
gauge pair are indivisible in the physical API. Tests may inspect them
separately, but configuration cannot ship a physical model containing only
one member of a required pair.

## Files and ownership

Create `theory/references/eta_pi0_p_full_parameters.json` for new production
inputs. It uses the existing source registry and the same strict
value/unit/source-key/locator schema as other parameter records. No fallback
constants are permitted.

Create focused implementation units:

- `theory/src/graal_theory/amplitudes/production_loops.py` owns the direct
  numerical loop integrations used by Eqs. (8), (21), and (24)--(27), plus
  any validated value-keyed cache;
- `theory/src/graal_theory/amplitudes/chiral_photoproduction.py` owns the
  Fig. 6--8 families;
- `theory/src/graal_theory/amplitudes/resonance_photoproduction.py` owns the
  Fig. 9 kernels and the resonance widths not already provided by
  `propagators.py`;
- `theory/src/graal_theory/amplitudes/decuplet_rescattering.py` owns the
  Fig. 10 `eta Delta` and `K Sigma*` families;
- `theory/src/graal_theory/models/eta_pi0_p_full.py` owns parameter
  composition, strong-T injection, the coherent family sum, polarized spin
  sums, and the unpolarized average.

Existing `delta1700.py`, `propagators.py`, `nstar1535_full.py`, and the Eq. (43)
`EtaPi0PModel` remain separately callable. Common helpers are extended only
where their existing responsibility already owns the operation. Stage 07/08
is not imported.

Add corresponding focused test modules and integration tests. Independently
digitized Fig. 12--14 and Fig. 19 references live as source-audited CSV/JSON
records under `theory/references/`; digitization code and checksums remain
separate from model calculation.

## Parameters and future fit boundary

Parameter ownership is compositional:

- `TreeParameters`: existing Eq. (43) inputs;
- `StrongTParameters`: final-fit subtractions, channel masses, pion correction,
  and VMD masses/conventions;
- `ProductionParameters`: new cutoff, magnetic coefficients, resonance
  couplings, form-factor parameters, and additional resonance inputs;
- `FullModelParameters`: immutable composition of those three blocks.

There are no hidden module-level physical parameters. Public constructors
load the sourced baseline, while internal calculations accept validated
replacement dataclasses. Caches are keyed by every immutable input that can
alter their result; callers cannot mutate cached state or affect later
predictions.

This increment does not create an optimizer or a generic parameter registry.
It preserves later fittability through explicit dataclass replacement. The
native-bin fitting milestone will define only identifiable continuous
parameters, physical bounds or priors, and discrete model variants. A global
amplitude normalization cannot be determined from beam asymmetry alone because
it cancels in `Sigma`; it must not be presented as an asymmetry-fit degree of
freedom. Experimental nuisance parameters remain separate from physical
couplings.

## Numerical evaluation and data flow

For a photon energy, three-body sample, and transverse polarization:

1. build one common `eta pi0 p` kinematic sample;
2. evaluate each family on that sample;
3. evaluate the strong transition matrix at the family-specific invariant
   energy where required;
4. sum complex spin matrices event by event;
5. perform the final-spin sum and initial-spin average once;
6. pass nonnegative polarized weights to the observable layer.

Direct quadrature is the authoritative loop calculation. Begin with direct
evaluation and existing SciPy integration tools. Add interpolation only when a
measured runtime bottleneck prevents publication-grid calculation, and only
with tests against direct evaluation throughout the physical domain. An
interpolator is an acceleration layer, never a second physics prescription.

No nonfinite value, complex-to-real cast, clipped singularity, failed
quadrature, or unsupported kinematic point is silently accepted. Errors name
the family, energy, event or channel, and failing invariant when available.
Ordinary closed channels use their sourced analytic continuation; only a true
invalid branch or singularity raises.

## Verification and acceptance

### Source and structural tests

- Every new numeric input has unit, source key, and page/equation locator.
- Exact channel ordering and printed charge/SU(3) coefficients are tested.
- Every family returns a finite complex array with the common spin shape.
- Zero source coefficients remain exactly zero.
- Required Kroll--Ruderman/pole pairs are both present and cannot be separated
  in the physical full-model configuration.
- Invalid scalar types, nonfinite inputs, malformed polarization, singular
  denominators, and failed integration produce explicit errors.

### Preservation tests

- The Eq. (43) amplitude and its isolated predictions remain unchanged within
  `rtol = 1e-12`.
- Reduced, pion-corrected, and reconstructed-full strong T variants remain
  numerically unchanged.
- Existing standalone prediction and convergence tests remain green.

### Numerical convergence

- Direct loop quadrature is checked with tighter tolerances or higher order at
  representative thresholds, resonance regions, and high-energy endpoints.
- For integrated predictions, consecutive resolutions must change total cross
  section by less than `1%` and every populated non-negligible histogram bin by
  less than `3%`, matching the existing convergence gate.
- Edge or threshold values that fail convergence are masked and reported, not
  joined by a plotted line.
- Any acceleration table must reproduce direct complex amplitudes at held-out
  physical points within a tolerance chosen to keep the resulting observable
  change below the same convergence budget.

### Primary-source comparisons

- Validate each family against the isolated or grouped component curves exposed
  in Figs. 12--14 before judging the coherent sum.
- Preserve the already validated Fig. 14 dotted Eq. (43) component.
- Compare the reconstructed full and reduced coherent sums with Fig. 14 solid
  and dashed curves, and compare the total cross section/invariant-mass spectra
  with Figs. 18--20 and Fig. 19.
- Reference readings carry PDF hash, page, axis calibration, line mapping, and
  conservative reading uncertainty.
- A discrepancy is recorded with numerical uncertainty and component identity.
  It does not trigger automatic parameter tuning and does not stop later curve
  generation merely because a historical convention was unprinted.

Implementation completion means every listed family is present, source-linked,
coherently combined, numerically converged, and compared with available
component/full-model evidence. Agreement and discrepancy counts are reported
separately from code-completeness status.

## Outputs and handoff

Increment A produces:

- a source-linked full polarized model API;
- per-family diagnostic amplitudes and integrated component predictions;
- coherent full/reduced comparison tables and figures;
- machine-readable numerical settings, parameter provenance, and convention
  choices;
- an updated amplitude inventory with status for every family;
- a clear validation report listing passes, discrepancies, and masked points.

Increment B will reuse this API to integrate all three pair definitions over
the four Ajaka energy ranges, handle partially accessible mass bins, and
produce the twelve publication curves. Increment C will read
`test_data/beam_asymmetry/beam_asymmetry.root`, initially selecting the nominal
`raw_bdt`/`ratio` points, exact native bin edges, systematic/statistical
covariances, fluxes, and polarizations. It will generate baseline and fitted
overlays without importing Stage 07 implementation code.
