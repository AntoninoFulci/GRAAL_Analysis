# Coherent production validation and historical Increment A exit gate

This document retains the **historical Increment A** audit and its measured
results. Its `W <= 1.70 GeV` guard and upper-energy masks describe that
baseline, not current code. The current direct strong amplitude is bounded
at `W <= 1.80 GeV`: PRC65 describes qualitative scattering agreement only
through about `1.60 GeV`, while PRC73 uses the model through `1.80 GeV` in
Fig. 18. The extension is source use, with no quantified model uncertainty.
Ajaka Figure 4 still has **not** been reproduced or validated: numerical
publication-bin convergence and comparison remain open.

Current 2026-10-06 status: stable Eq. (25)/(26) recoil endpoints and
four-coordinate conditional integration pass the unchanged strict inner
checks in two real `p_eta` pilot bins. At `E_gamma=[1.10,1.20]`,
`M(p eta)=[1.52,1.56]`, base `p5` passes energy `n/2n`, deterministic
`p5/p6`, eight-replica `SE(Sigma)=0.00912`, and direct/grid gates. At
`E_gamma=[1.40,1.50]`, `M(p eta)=[1.60,1.64]`, base `p7` passes the same
gates with `SE(Sigma)=0.001603`. These are **individual-bin** results;
cross-bin covariance, three pair-mass total comparisons, 76 other
accessible bins, and all twelve Ajaka residual panels remain open.
The source-equivalent two-stratum `K+Lambda` sampler was removed after
real `p5/p6` and `p6/p7` normalization drifts of `2.236%` and `2.640%`.
The CLI now schedules by bin, but complete-bin 14-worker scaling and its
`<=24 h` launch gate remain unmeasured.
One interior nominal bin from each of the twelve Ajaka panels was screened
at direct `n=4`, `64/48`: only `2/12` pass deterministic `p5/p6` `Sigma`
and denominator gates. The ten failures were extended to `p6/p7`;
`0/10` pass both gates. An old-code `eta_pi0` worker encountered Eq. (26)
`log(0)` when a positive mapped distance below one ULP rounded onto a
recoil root. A frozen-event RED/GREEN repair preserves that distance; the
corrected full bin computes at `p7`, but its denominator still drifts
`5.423%` versus `p6`. For low-energy `p_eta`, `M=[1.56,1.60]`, a coherent
family/coordinate audit reproduces the `p6→p7` denominator change to
`5e-12` absolute. All seven interference-allocated families and all four
Sobol coordinate partitions contribute. No full-panel launch follows from
these screens.

One independent PRC73 Fig. 18 source guard has passed at `E_gamma=1.7 GeV`:
direct seven-family `M(eta p)=[1.645,1.655]` density at Sobol `p7/p8`
is `14.32913/14.22723 microbarn/GeV` (relative drift `0.711%`). Eight
fixed scrambled `p7` replicas average `14.20144` with `SE=0.07828`;
deterministic `p7` differs by `1.63 SE`. The numerical bound
`0.10190` plus source reading bound `2.0` covers the `1.79856` residual
to the independent `M(eta p)=1.65` trace value `16.0`. This is a
compatible **single finite mass window**, not verification of the full
Fig. 18 spectrum or a Figure 4 reproduction claim.
Machine-readable pilot values and exact individual gate components are in
the ignored local artifact `theory/outputs/figure4-pilot-audit-2026-10-06.json`.

Current full-production pilot: analytic recoil-angle treatment resolves the
historical Eq. (25) tangent-cut event at `E_gamma=1.4069431844202973 GeV`,
`M(eta p)=1.61009316501 GeV`, using unchanged `64/48` and `1e-5/1e-10`
inner checks. Analytic global-azimuth integration reduces conditional Sobol
to four coordinates. In the real `p_eta` energy `[1.40,1.50]`, mass
`[1.60,1.64]` pilot, `p5/p6` gives `Sigma=-0.506392405/-0.512297890`
but denominators `1.184199708/1.204879559`; the latter changes about
`1.72%` and fails the fixed `<1%` gate. At `p7`, a new near-tangent
`K+Lambda` event (`M(eta p)=1.60914962014 GeV`, event 104 at the first
energy node) fails the default `64/48` inner check by `1.5179e-6`; isolated
`96/72` and `128/96` agree. The subsequent full `p7` bin at `96/72`
passes every strict inner check, but its
denominator `1.217629483` differs from a fresh same-order `p6/96:72`
denominator `1.204877915` by `1.047245%`, failing the fixed `<1%`
Sobol gate. The `p6` run took `644.4 s`; its `Sigma=-0.512297379` differs
from `p7` by `0.003429`, within the `0.01` gate.
`Sigma=-0.508868327`. Its measured runtime is
`1288.9 s`. Extrapolating this bin cost to the upper `p_eta` panel's eight
accessible bins and all 14 base-equivalent certification passes gives
`40.1 h` on the historical one-worker-per-panel scheduler. This is a
same-cost estimate, not a measured full-panel runtime; the current CLI
schedules by nominal bin.
Fresh `p5/p6` diagnostic denominator contributions change by `-0.00994`
below the `K+Lambda` threshold at `1.60936 GeV`, `+0.02570` between that
threshold and `1.62 GeV`, and `+0.00492` above `1.62 GeV` in this bin.
The narrow interval immediately above threshold dominates the net
`+0.02068` drift. This is a variance-localization result, not a converged
prediction or permission to tune physical parameters.
An exact `K+Lambda` threshold split was tested and reverted: the Sobol zero
point sampled the threshold exactly and Eq. (25) failed even at `512/384`;
after a fixed digital shift, a nearby `1.60929498643 GeV` event failed at
both `64/48` and `96/72`. Toy phase-space volume and nested-point tests
passed, but no complete physical split-bin result existed at that stage.
The later shared Eq. (25)/(26) endpoint repair allowed a complete split
trial, whose normalization gate failed as recorded above; the unsplit
sampler is the active production path.
At that stage the measured `p6` bin cost was about `355 s`; even perfect four-worker scaling
projects at least `26.9 h` for 78 accessible bins and the mandatory base,
energy doubling, Sobol doubling, eight replicas, and direct check. The
24-hour launch gate failed on the measured four-worker setup. The host reports
14 logical CPUs; a separate warm-event benchmark measured
`6.04/11.62/15.13` evaluations/s at 4/8/14 workers. That suggests about
`10.8 h` for the same `p6` workload at 14 workers, but does not establish
complete-bin scaling or convergence. No twelve-panel
numerical or physical comparison
has been run. The bounded PRC73 Fig. 18 trace now has the one-point
comparison above; its remaining spectrum is open.

## Source comparisons and counts

The Task 7 generated baseline is in the ignored directory
`theory/outputs/task7-full-production-baseline/`. Its JSON/Markdown report is
provenance-bearing evidence for the source mapping and explicitly unsuccessful
low-resolution comparisons, not authoritative convergence evidence. Of 73
source points, 71 lie in the adopted model/reference overlap; the two rounded
Fig. 14 tree endpoints (1.486 and 1.635 GeV) lie outside physical support.

| Compared group | Compatible | Discrepant | Unresolved | Masked nonconverged | Overlap total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Component curves, including indivisible-family/source-kernel mapping gaps | 0 | 0 | 25 | 35 | 60 |
| Coherent reconstructed-full curves, Figs. 14/19 | 0 | 0 | 0 | 6 | 6 |
| Reduced coherent curve, Fig. 14 | 0 | 0 | 5 | 0 | 5 |
| Total | 0 | 0 | 30 | 41 | 71 |

Component masked counts are contact 5, external-pion 5, internal-pion 5,
eta-Delta 5, and tree 15. The 25 unresolved component points are the three
individual Fig. 13 resonance kernels (15), Fig. 12 Eqs. (40)–(41) (5), and
Fig. 13 Eq. (42) (5). Those strokes cannot be represented by the whole-family
diagnostic API. Gauge partners and coherent families were not split to create
source-equivalent-looking output. The physical model hardcodes the final-fit
reconstructed-full strong closure; the source-faithful reduced coherent
closure is unavailable and its five source points remain unresolved.

Task 7 controls were nonscrambled Sobol p4/5 (16/32 events), 8 bins, q/angle
16/16, relative loop tolerance `1e-3` and absolute tolerance `1e-8`. Its
runtime was not recorded in the generated metadata. Its comparison allowance
was additive: 20% of source value plus reading error plus numerical error.
No Task 8 mask or isolated-event result reclassifies these baseline points as
compatible or discrepant.

## Physical convergence measurements

`tests/test_full_production_convergence.py` exercises the real sourced Eq. (43)
model, physical seven-family API, and real strong variants. The end-to-end
criterion is strict: total cross-section relative change `<1%`; every bin
carrying at least `1e-4` of total integrated weight at either resolution has
relative change `<3%`. The rule includes edge bins and uses bin integrals,
not densities or an absolute microbarn cutoff. A vanished previously populated
bin fails the comparison. Direct quadrature remains authoritative; no surrogate,
interpolated loop, fitted parameter, tolerance relaxation, or mocked amplitude
is used.

The threshold is `E_gamma=0.9313108757812466` GeV with the current sourced
masses. Representative energies are threshold+1 MeV, 1.2 GeV, the 1.4 GeV
upper-interval boundary, and the 1.5 GeV publication endpoint. Published Figure 4
intervals are `[1.10,1.20)`, `[1.20,1.30)`, `[1.30,1.40)`, `[1.40,1.50]` GeV.

Routine full-model screens attempt p4/5 at q/angle16 and 32 with unchanged
direct-loop default tolerances `rtol=1e-5`, `atol=1e-10`. Every integral itself
checks configured against doubled orders (16/32 or 32/64); the end-to-end
audit would additionally compare both loop configurations at each power and
both powers at each loop configuration if all predictions existed.

| Full-model energy (GeV) | Measured setting | Exact failed family/event/channel | Status and reason |
| --- | --- | --- | --- |
| 0.9323108757812466 | q/angle16, p4 and p5 | `explicit_resonances`, event 0, `channel=1=pi_plus_n`, `z=1.48664055351` GeV; Eq. (26) intermediate invariant `1.62168956829` GeV | `masked_nonconverged`: checked 16/32 quadrature, max difference `2.62084e-6`; routine runtimes 5.97/8.44 s |
| 1.2 | q/angle16, p4 and p5 | `external_pi0`, event 0, `z=1.61651937683` GeV; Eq. (8)–(9) `pi_plus_n` meson pole | `masked_nonconverged`: checked 16/32 quadrature, max difference `3.65527e-5`; 0.033/0.054 s |
| 1.2 | q/angle32, p4 and p5 | `internal_pi0`, event 15, `channel=4=k_plus_lambda`, `z=1.60842859385` GeV | `masked_nonconverged`: checked 32/64 quadrature, max difference `1.65265e-6`; 10.07/11.75 s |
| 1.4 | q/angle16 and 32, p4 and p5 | `chiral_contact`, event 0, `channel=all`, `z=1.70711932863` GeV | `masked_unsupported_domain`: strong `W outside reduced real-axis domain`; about 0.0004 s per attempt |
| 1.5 | q/angle16 and 32, p4 and p5 | `chiral_contact`, event 0, `channel=all`, `z=1.75066191924` GeV | `masked_unsupported_domain`: strong `W outside reduced real-axis domain`; about 0.0004 s per attempt |

The upper-energy restriction also affects interior phase space: original p5
event 8 at 1.4 GeV has `z=1.7060452129631272` GeV and event 3 at 1.5 GeV has
`z=1.727950305891468` GeV. Their phase-space-volume weight fractions are
0.0335027 and 0.0370344, respectively; these are volume fractions, not calculated
full cross-section fractions. Real whole-contact-family calls at those events
reject the unsupported strong invariants. The blocker is not confined to a
measure-zero Sobol endpoint.

The bounded routine screen has 16 setting slots: 6 numerical masks, 8
unsupported-domain masks, and 2 `not_completed_runtime_bound` slots for the
threshold q/angle32 p4/5 comparison. There are zero accepted full-model
energies. `not_completed_runtime_bound` means unexecuted in the routine screen;
it is neither a computed quadrature failure nor a converged result. Failed or
incomplete audits carry a reason and an all-false convergence mask. Regression
checks query both an exact sample and an interval midpoint: the validation
adapter returns no value/error and never interpolates across the mask.

A separate complete physical exploratory grid returned finite threshold
q/angle32 totals: p4 `sigma=6.611608959162628e-7` microbarn in **505.1697 s**;
p5 `sigma=6.556919313546106e-7` microbarn in **1014.5766 s**. Their total relative
change is `0.00834075`, satisfying the total-only criterion. Histogram bin metrics
were not retained by that exploratory command, and the q/angle16 counterpart
failed, so the combined loop-and-Sobol acceptance gate is not established.
The exploratory grid's 16 actually executed attempts contain 6 numerical masks,
8 unsupported-domain masks and 2 finite-unvalidated results; still zero accepted
full-model energies. Its summed measured evaluation runtime was **1555.4006 s**.
This high cost is why the routine suite records its two high-order threshold
slots explicitly as incomplete instead of repeating a long direct calculation
in every focused/full verification. Finite output and total-only agreement do
not certify populated bins or loop convergence.

The Task 7 internal-pion failure is independently resolved at **one** source
event by higher direct orders: original p4 event 15 at 1.2 GeV, `K+Lambda`,
`z=1.60842859385` GeV, x-polarization. Configured q/angle16 and 32 fail with
max differences `1.73605e-4` and `1.65265e-6`; configured 64 and 128 pass their
internal 64/128 and 128/256 checks. The real-strong complex family matrices
also agree at `rtol=1e-5`, `atol=1e-10`. The measured norms were
1.1969701980820058 and 1.1969701971334, with runtimes 2.0202 and 8.0667 s.
The first sampled passing pair was 64/128; this is not a global optimal-order
claim, a full-spectrum calculation, or a license to count the baseline as
converged.

For the **isolated Eq. (43) tree only**, 8-bin p16/17 (65,536/131,072 events)
spectra pass at all four energies. These are the smallest passing powers among
the measured candidates p10/11, p12/13, p14/15, p16/17; all three lower pairs
fail a populated-bin criterion at each energy.

| Tree energy (GeV) | Total relative change | Maximum populated-bin relative change |
| --- | ---: | ---: |
| 0.9323108757812466 | `8.63648e-6` | `0.00891980` |
| 1.2 | `4.61955e-5` | `0.00851978` |
| 1.4 | `3.15091e-4` | `0.01104839` |
| 1.5 | `5.26339e-5` | `0.01298480` |

No claim is made that the full model passes at p16/17. Running this very
expensive seven-family direct integration at those powers was not attempted.

## Preservation and convention baseline

A fresh interpreter computes current Eq. (43) complex spin matrices for both
transverse polarizations at `W=1.82` GeV, p4, and the 1.2 GeV tree total plus
three 16-bin spectra at p10 **before** importing/constructing the full production
model. It then recomputes them after import and checks `rtol=1e-12`, `atol=0`.
It also checks the selected full-model Eq. (43) amplitude against the original
matrix. No new fitted goldens are stored. The same cold-import comparison
recomputes the reduced, pion-corrected intermediate, and reconstructed-full
complex strong matrices at W=1.1, 1.55, and 1.7 GeV. Measured maximum absolute
differences are zero for amplitude, spectrum, and all three strong variants.
Existing tests for those variants are invoked unchanged in verification.

The physical baseline retains the charge-+1 channel order
`(pi0 p, pi+ n, eta p, K+ Sigma0, K+ Lambda, K0 Sigma+)`; external transition
column 3 (zero-based 2); final momenta `(eta,pi0,proton)` in the overall CM;
photon along +z; two orthonormal transverse polarizations; coherent complex
spin matrices before spin and photon averages; GeV units and the existing
microbarn conversion. The six strong-channel masses use sourced modern values.
The reconstructed full variant uses final-fit subtractions, the pion correction,
and vector exchange, kept separate from basic/reduced subtraction inputs.

Other conventions are the 1.4 GeV production first-loop cutoff, 1.25 GeV pion
monopole cutoff, printed negative `-i*pi` physical cut and principal intermediate
invariant, `g_eta=1.7-1.4i`, `g_K=3.3+0.7i`, Butler decuplet phases, and the
empirical 1.15 factor. Eq. (41)'s `(2D+F)/(10 f_pi)` and Eq. (42)'s
`4 sqrt(3)/25` coefficients follow the paper. Eta-Delta retains Delta(1232);
kaon topologies use Sigma*, with a common Lambda/pi0 running width. Off-real
intermediate widths vanish: this and the common Sigma*/pi0 prescription are
explicit reconstruction conventions, not unique source-prescribed analytic
continuations. No parameters were tuned to experimental points or theory
strokes, and no numerical acceptance threshold was loosened for this audit.

## Historical blockers and exact Increment B handoff

The full-domain blocker first arises at
`graal_theory/amplitudes/_reduced_t_core.py:validated_energy`, which rejects
external W above 1.7 GeV. That trust boundary is consumed by reconstructed-full
T and its pion/vector ingredients. A source-supported extension and associated
numerical/convention validation would be needed before physical upper-panel
integration. Removing the guard alone would not establish a valid strong model.
The smallest numerical surfaces implicated by the low-order masks are
`production_loops.py:eta_photoproduction_amplitude` (meson-pole quadrature),
`chiral_photoproduction.py:internal_pi0_amplitude` (Eq. (25) recoil cuts), and
`production_loops.py:eq26_rescattering_loop` as used by `explicit_resonance_amplitude`.
One internal source event resolves with higher order; this audit has not
established sufficient orders or practical runtime for a full observable.

No new public API is introduced. Increment B receives these exact existing
interfaces:

```python
from dataclasses import replace
from pathlib import Path
from graal_theory.models.eta_pi0_p_full import EtaPi0PFullModel, FullModelParameters
from graal_theory.phase_space import SobolConfig, sample_three_body
from graal_theory.observables import HistogramSpec, predict_energy

model = EtaPi0PFullModel.from_files(Path("references"))
# Replacements are validated immutable records; retain source provenance.
parameters: FullModelParameters = replace(model.parameters, production=replacement_production)
trial = EtaPi0PFullModel(parameters)
amplitude = trial.amplitude(sample, polarization)                 # (N, 2, 2), complex128, all seven
weights = trial.matrix_element_squared(sample)                   # (N,), unpolarized
polarized = trial.polarized_matrix_element_squared(sample, polarization)
families = trial.family_amplitudes(sample, polarization)          # read-only whole-family diagnostics
diagnostic = trial.selected_amplitude(sample, polarization, ("eq43_tree",))
prediction = predict_energy(energy_gev, trial, SobolConfig(power), HistogramSpec(bins))
```

`sample` is a `ThreeBodySample` with on-shell `(eta,pi0,proton)` momenta in the
overall CM; `polarization` is a finite unit transverse real three-vector.
`replacement_production` is a `ProductionParameters` record created with
`dataclasses.replace`; loop settings remain separate from physical parameters.
`selected_matrix_element_squared(sample, families, polarizations=None)` is also
available for whole-family diagnostics; physical methods accept no family
selection. Exceptions must propagate to explicit masks, not invented zeros.

Future Increment B integrates the four published photon intervals and three
mass-pair panels using the coherent polarized API and the established spin/
photon conventions. The API accepts immutable parameter replacement, but
source-supported upper-domain coverage, feasible full loop/Sobol convergence,
and source-equivalent reduced/full comparison capabilities remain prerequisites
for declaring that physical integration ready. This audit does not fit Ajaka
or provide covariance-aware fitting (Increment C).

## Verification record

Initial audit gate RED: one real Eq. (43) p16/17 test failed its assertion before
the populated-bin comparison existed (`1 failed in 4.34s`). The physical audit
RED had four required-energy failures before the setting/outcome records existed
(`4 failed, 5 deselected in 0.47s`). The implemented audit file then passed:
`11 passed in 63.43s`, no warnings. A separate subprocess path setup failure
was corrected by explicitly supplying the local source directory to the fresh
interpreter; it was not a physical-model failure.

The final required focused command passed **552 tests in 402.24 s**, and the
full theory suite passed **975 tests in 434.08 s**, both with no warnings.
Fourteen new audit cases were added; existing test files were not modified by
Task 8. Unchanged reduced/pion-corrected/reconstructed-full strong tests
separately passed **100 tests in 0.56 s**. Fresh independent review is requested
and will be arranged by the controller after the scoped commit; it is not
claimed complete here. Green verification certifies the tested API,
preservation, convergence criteria, and honest masking behavior; it does not
override the failed physical exit gate.
