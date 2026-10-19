# Figure 4: local event-level variance diagnosis, 19 October 2026

## Scope and corrected starting state

The active theory work is in `.work/figure4-fit` (branch `feat/figure4-fit`,
HEAD `56302c8`, with existing uncommitted work), not only in the root `theory/`
copy. The first conversational status summary used the latter and missed the
October 7–12 fit infrastructure, deterministic p5–p8 scan, adaptive selection,
and rejected endpoint-map experiment. Existing work was preserved.

The two historical control bins passed the **former** resolution policy.
The lower control subsequently failed p6/p7 and p7/p8; the upper control lacks
p8/p9 and p7/p9 confirmation. Neither is certified under the stronger current
policy (two refinements and their span). No complete Figure 4 panel is certified.
See the worktree's `theory/docs/2026-10-05-figure4-converged-production-tdd-plan.md`,
Tasks 3G and 3I. Its October 10 scan and October 12 rejected map were reused;
no expensive scan was repeated.

## Instrumentation

Added only these files inside that worktree:

- `theory/scripts/figure4_variance_diagnostic.py`
- `theory/tests/test_figure4_variance_diagnostic.py`

The diagnostic wraps the seven-family model and calls the existing
`predict_figure4_bin`. It records complete H/V complex family matrices,
four-momenta, integration measures, per-event numerator/denominator,
pair masses, and the four Sobol coordinates in `events.npz`.

For each whole family, allocating half of every cross-family interference
term gives signed contributions that sum to the coherent N and D. These
allocations are **not** separate physical cross sections. Their sums are checked
against the original production projection. No physical parameters, sampler,
quadrature tolerances, or production convergence gates were changed.

One highest-resolution amplitude evaluation supplies lower nested prefixes.
Actual prefix momenta and phase-space weights are checked against the existing
sampler at each power; the sample-count normalization is rescaled. Tests compare
the result to independently executed lower-resolution integrals, including
scrambled seeds and a partially accessible energy/mass window.

Reports retain signed family and coordinate-quartile changes between powers.
Each coordinate's four quartiles partition the total; different coordinate
partitions must not be summed together. Neither prefix variation nor weight
concentration is an independent-replica uncertainty estimate.

## Local measurements

MacBook Pro M4 Pro, 14 cores (10 performance, 4 efficiency), 24 GB RAM.
Each diagnostic uses one process with BLAS/OpenMP/Accelerate threads capped
at one, direct strong T, production quadrature 64/48, and unchanged parameters.
The following is a **one-energy-node probe**, not the n=4 publication-bin check:
eta_pi0, E_gamma=[1.10,1.20] GeV, M(eta pi0)=[0.72,0.76] GeV,
one Gauss–Legendre node at E_gamma=1.15 GeV.

The p5 run took 43.3 s including model construction. Its nested estimates:

| Power | Numerator | Denominator | Sigma | Constant-amplitude denominator |
| --- | ---: | ---: | ---: | ---: |
| p4 | -0.2227248953655 | 0.7146484499563 | -0.3116565849672 | 0.0007976050025973 |
| p5 | -0.2404431431602 | 0.8522078010233 | -0.2821414482143 | 0.0007981698410840 |
| p6 | -0.2213113461624 | 0.7827804825835 | -0.2827246604719 | 0.0007984291360080 |

Constant-amplitude normalization changes by about 0.0708%, versus 16.14%
for the coherent denominator, using the code's max-magnitude relative metric.
The three largest events (indices 17, 13, 18) contribute 57.09% of D;
the ten largest contribute 91.55%. Their M(eta p) values are approximately
1.50592, 1.50194, 1.50196 GeV. This is concentration in a coarse sample,
not evidence that a finite physical region can be discarded.

Reevaluating both complex H/V matrices for those three events at orders
96/72 and 128/96 gives a relative Frobenius norm of the matrix difference
of at most 3.52e-10. The spot check took 21.1 s. This rules against
inner quadrature instability as the cause of those three large contributions;
it does not validate every event or diagnose every bin.

The independent p6 run took **87.3 s** including construction. Its p4/p5
prefixes reproduce the independent p5 run within 1e-12. From p5 to p6,
Sigma changes only **0.0005832**, but D changes **8.1468%**; the constant-
amplitude normalization changes **0.03248%**. This directly exhibits
cancellation in the ratio while the denominator remains unstable.
At p6 the ten largest contributions still supply **73.15%** of D.
The signed family allocation associates about 75.7% of the p5/p6 D drift
with the tree family, **including its interference**. This does not imply
that removing the pure tree intensity would remove 75.7% of the drift.

A cheap candidate was evaluated by postprocessing the captured samples:
`I(full) = I(full - pure_tree) + I(pure_tree)`, separately for N and D,
with fixed coefficient one and all interference retained in the residual.
The pure tree used the same source parameters, exact global-azimuth reduction,
and one-node integration at p12/p13/p14 (0.71 s total). Its denominator
changed by 0.0131% at p13/p14. Replacing the coarse pure-tree contribution
with the p14 estimate reduced p5/p6 full-denominator drift from 8.15% to
6.12%, while Sigma drift increased from 0.000583 to 0.004479. This candidate
is insufficient for the fixed 1% normalization requirement even on this
probe; it was **not adopted**. The three tree resolutions are diagnostic
checks, not a certificate for an exact known integral.

Artifacts, relative to `.work/figure4-fit`:

- `theory/outputs/variance-20261019-eta-pi0-p5-n1/report.json`
- `theory/outputs/variance-20261019-eta-pi0-p5-n1/events.npz`
- `theory/outputs/variance-20261019-eta-pi0-p5-n1/inner_quadrature_spot_check.json`
- `theory/outputs/variance-20261019-eta-pi0-p6-n1/report.json`
- `theory/outputs/variance-20261019-eta-pi0-p6-n1/events.npz`
- `theory/outputs/variance-20261019-eta-pi0-p6-n1/tree_control_variate_probe.json`

## Verification and provenance

Focused command, run from `.work/figure4-fit/theory`:

```bash
python3 -m pytest -q tests/test_figure4_variance_diagnostic.py \
  tests/test_figure4_integration.py tests/test_phase_space.py \
  tests/test_figure4_adaptive_pilot.py tests/test_figure4_resolution_scan.py
```

Result: **55 passed in 1.26 s**. New tests were first observed failing before
implementation. Independent review identified a checkout/provenance mismatch
risk; a failing regression then verified the fix. The final CLI rejects imports
from another checkout before writing artifacts. Review of the fix found no
remaining issue. Full theory suite and full numerical certification were not
run; this is diagnostic-only work.

Each run saves code/reference SHA-256 hashes, package versions, command,
HEAD, raw-array checksum, and a completion marker. Source hashes include dirty
code. An existing output directory is refused; failed runs have no `COMPLETE`.
The initial p5 run preceded the package-location guard, but explicitly used
`PYTHONPATH=theory/src` and recorded the then-current script hash.

## Next numerical step

Use the captured contributions to assess joint mass/angular sampling; a
mass-only or generic endpoint map is not justified by these data. Before any
new production mapping, extend the event diagnostic to n=4 and the frozen
p_eta controls, then compare candidate and baseline on identical settings.
All original Jacobian, support, interference and convergence checks remain
mandatory. The one-node probe does not certify the energy integral.

Reproduce the completed p6 probe from `.work/figure4-fit`, using a fresh
output directory (the command deliberately refuses replacement):

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
PYTHONPATH=theory/src python3 theory/scripts/figure4_variance_diagnostic.py \
  --pair eta_pi0 --energy 1.1 1.2 --mass 0.72 0.76 \
  --power 6 --energy-order 1 --mode direct \
  --output theory/outputs/variance-eta-pi0-p6-n1-rerun
```

The next n=4, p7 diagnostic can be run with the same command, replacing
`--power 6 --energy-order 1` by `--power 7 --energy-order 4` and choosing
another output directory. Approximate elapsed time **12 minutes**, obtained
by scaling this 87.3 s one-node p6 run by eight; this estimate is unmeasured
and inner-loop difficulty varies with energy. One process, one numerical-library
thread; compressed raw arrays measured 32 KB at p5, but peak
process memory was not measured. Inputs are source-linked local reference JSONs;
no experimental ROOT files are required. Exit 0 plus `COMPLETE` means the
diagnostic finished, not that convergence passed. Failures preserve
`failure.json` and omit `COMPLETE`. The user subsequently authorized this
n=4 probe; its measured result follows.

## Authorized four-node run: completed

The authorized n=4/p7 direct-mode diagnostic completed with exit 0 and
`COMPLETE` in **727.19 s (12 min 7 s)**, versus the approximately 12-minute
estimate. It evaluated 128 events at each of four energy nodes, with one
process and all numerical-library thread limits set to one. Code and reference
hashes exactly match the preceding n=1/p6 probe. No production source was
changed in this follow-up.

Run directory relative to `.work/figure4-fit`:
`theory/outputs/variance-20261019-eta-pi0-p7-n4/`.

| Power | Numerator | Denominator | Sigma | D drift from preceding power |
| --- | ---: | ---: | ---: | ---: |
| p4 | -0.2094957121192 | 0.7068043604008 | -0.2963984432700 | — |
| p5 | -0.2291734179872 | 0.8413873303337 | -0.2723756464176 | 15.9954% |
| p6 | -0.2113953671560 | 0.7703014005591 | -0.2744320171333 | 8.4487% |
| p7 | -0.1957074422190 | 0.7285280999476 | -0.2686340337910 | **5.4230%** |

The p5/p6 results reproduce the historical October 6 **direct** calculation
exactly; p7 D differs by only 1.11e-16 and Sigma is identical. Thus the new
recorder preserves the known result while exposing its event contributions.
This comparison uses direct-mode references; the October 10 scan used grid
mode and is not claimed bitwise identical.

The last refinement changes Sigma by 0.005798 (below its 0.01 threshold),
but D by 5.4230% (above its strict 1% threshold). Constant-amplitude D changes
only 0.00977%. The bin therefore **fails the Sobol normalization gate**.
No claim of numerical certification follows from command success.

All four nodes contribute negative p6/p7 D drift, after energy weights:

| E_gamma [GeV] | Contribution to D change [microbarn] |
| ---: | ---: |
| 1.1069431844 | -0.0012148553 |
| 1.1330009478 | -0.0087890938 |
| 1.1669990522 | -0.0189606748 |
| 1.1930568156 | -0.0128086767 |

The upper two nodes supply 76.05% of the net drift. Signed family allocation
associates 59.87% with the tree family **including interference**; every other
family also contributes. Angular and mass quartiles show substantial opposing
contributions. These marginal partitions are not independent attribution
percentages and do not establish a unique variable or cause.

At the same p6 resolution, replacing the earlier one-node energy rule by
four nodes changes Sigma by **0.008293** and D by **1.5942%**. The one-node
probe was useful for diagnosis but insufficient as the production energy rule.
Four-node convergence itself still requires an n4/n8 check; none ran here.

The fixed-unit pure-tree control variate was also checked at n=4 using the
captured full-model amplitudes. Only the cheap pure tree was newly integrated,
at p12/p13/p14, taking 2.74 s. It reduces p6/p7 D drift to **4.3674%** and
Sigma drift to 0.002767, still failing normalization. No production adoption.

### Verification and artifacts

`analyze_capture.py` independently verifies the NPZ checksum, finite arrays,
recomposed N/D for every nested prefix, signed family sums, and coordinate
quartile sums. All checks passed. `analysis.json` records their results,
historical comparison, and the script's SHA-256. `events.npz` is 436,345 bytes.
No full integration was rerun for postprocessing; no production/test code
changed in this follow-up, so the earlier software suite was not repeated.

Files inside the run directory:

- `report.json`, `provenance.json`, `events.npz`, `COMPLETE`: original run.
- `analyze_capture.py`, `analysis.json`: reproducible postprocessing.
- `drift_decomposition.png`: visually inspected six-panel drift decomposition.
- `tree_control_variate_probe.py`, `tree_control_variate_probe.json`: cheap
  control-variate check, preserving interference in the residual.

![Four-node drift decomposition](../../.work/figure4-fit/theory/outputs/variance-20261019-eta-pi0-p7-n4/drift_decomposition.png)

Next candidate should address correlated mass/angular structure. It must be
tested on this bin and the frozen p_eta controls before changing production.
Increasing the energy order or isolating the pure tree alone has not solved
the outer-sampling problem. No p8/p9, scrambled-replica, n4/n8, or full-panel
campaign was launched in this follow-up.

## Joint mass/helicity candidate: implementation and preflight

Following authorization to continue locally, a diagnostic-only candidate was
added in `.work/figure4-fit/theory/scripts/figure4_joint_map_probe.py`.
It retains the conditional pair-mass window and rotates the pair-rest-frame
daughter direction onto helicity coordinates relative to the spectator.
This rotation preserves solid angle. For a secondary proton-pion pair,
its invariant is `s_p_pi = A +/- B*cos(chi)`, where

```
A = m_r^2 + m_spectator^2 + 2 E_r E_spectator
B = sqrt(lambda(s_pair,m1^2,m2^2)*lambda(S,s_pair,m_spectator^2))/(2*s_pair)
```

The invariant is sampled from a truncated Cauchy proposal with center
`m_Delta^2` and scale `m_Delta*Gamma_Delta`, using the existing sourced
1.232 GeV mass and 0.117 GeV width. The weight is multiplied by
`(ds/du)/(s_max-s_min)`. If the primary pair is proton-pion, the same
proposal instead acts on its primary invariant. Physical amplitudes and
running widths are untouched. No Ajaka trace enters candidate selection.

Review found cancellation when recovering the helicity cosine by subtracting
nearly equal invariants near threshold. A regression reproduced the failure.
The fix computes the normalized quantile directly using the trigonometric
tangent-difference identity and constructs `cos(chi)=sign*(2*fraction-1)`.
This preserves exact endpoints and the zero-width limit. Review confirmed
the original finding resolved, with no further concrete findings.

The diagnostic CLI now accepts `--sampler delta-helicity`; the default stays
`standard`. Candidate injection is scoped to the diagnostic call and restores
the original sampler even on exceptions. Provenance includes the candidate
source hash and actual proposal parameters; prefix checks use the selected
sampler. No production source was changed for this candidate.

Focused verification: **63 tests passed in 1.63 s** across joint-map,
variance-diagnostic, phase-space and Figure 4 integration tests. Checks cover
finite-difference Jacobians, independent phase-space quadrature and first
two proton-pion invariant moments for all six ordered pair choices,
isotropy, conservation, window support, nested samples, independent seeds,
the secondary invariant CDF, and threshold regression.

Cheap pure-tree preflight took **15.10 s**, using four energy nodes and
p5/p6/p7/p8 plus p12/p13/p14 for both maps. These are deterministic checks,
not independent-replica variance estimates. Results and reproducible script:
`.work/figure4-fit/theory/outputs/joint-map-20261019-tree-preflight/`.

| Bin | Sampler | p5/p6 D drift | p6/p7 D drift | p7/p8 D drift |
| --- | --- | ---: | ---: | ---: |
| Lower p_eta | Standard | 0.40658% | 0.85133% | 0.53639% |
| Lower p_eta | Delta-helicity | 1.24065% | 0.65394% | 0.29766% |
| Upper p_eta | Standard | 1.52052% | 0.27520% | 0.29818% |
| Upper p_eta | Delta-helicity | 0.48204% | 0.35922% | 0.13435% |
| eta_pi0 | Standard | 3.46741% | 1.92140% | 0.37423% |
| eta_pi0 | Delta-helicity | 2.42593% | 0.72777% | 0.33899% |

At p14, cross-map D differences are 0.00250%, 0.00356% and 0.00482%,
respectively; Sigma differences are below 2.64e-5. This supports measure
consistency but does not establish complete-model convergence. Low-power
performance is mixed, so the same lower physical control is the next gate.

The bounded full-model screen uses the frozen lower `p_eta` control,
`E_gamma=[1.1,1.2]`, `M(p eta)=[1.52,1.56]`, four energy nodes and
q/angle orders 64/48 in grid mode, matching the historical lower-bin scan.
It captures p4/p5/p6 from one p6 run (64 events per node). This is an
early screen, not the two-refinement/full-span certification procedure.
The command, from `.work/figure4-fit`, is:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
VECLIB_MAXIMUM_THREADS=1 PYTHONPATH=theory/src /opt/local/bin/python3 \
  theory/scripts/figure4_variance_diagnostic.py \
  --pair p_eta --energy 1.1 1.2 --mass 1.52 1.56 \
  --power 6 --energy-order 4 --mode grid --sampler delta-helicity \
  --output theory/outputs/joint-map-lower-p6-n4-rerun
```

Choose a new output directory for each run. The actual saved run uses
`theory/outputs/joint-map-20261019-lower-p6-n4/`. Its `analyze.py` checks
matching baseline settings, the NPZ checksum, finite arrays, and independent
N/D reconstruction from summed H/V matrices for every prefix. Baseline is
`figure4-resolution-scan-p5-p8/e0-p_eta-b3.json`. Historical and current wall
times cannot establish throughput improvement because execution conditions
differed.

### Lower physical screen: completed, candidate rejected for production

The run completed in **366.75 s (6 min 7 s)**, exit 0, with `COMPLETE`.
Independent capture verification passed, including every p4/p5/p6 prefix.
`comparison.json` records the matching frozen baseline, raw moments, gates
and hashes. The predeclared early screen gives:

| Sampler | Power | Numerator | Denominator | Sigma |
| --- | ---: | ---: | ---: | ---: |
| Standard | 5 | -0.178520207353397 | 0.543222993556722 | -0.328631537086724 |
| Standard | 6 | -0.180179989511444 | 0.538503267353495 | -0.334594050648844 |
| Delta-helicity | 5 | -0.170830157565343 | 0.558532714119508 | -0.305855240430538 |
| Delta-helicity | 6 | -0.171671929194381 | 0.536376930960691 | -0.320058375528761 |

For p5/p6, standard D drift is **0.86884%**, versus **3.96678%** for the
candidate (gate strictly below 1%). Standard Sigma drift is **0.00596251**,
versus **0.01420314** for the candidate (gate at most 0.01). The candidate
fails both tests and worsens the normalization drift by about 4.57 times.
These are differences between nested deterministic resolutions, not estimates
of independent sampling variance. The standard map passing this one step
does not supersede its known failures at later refinements.

**Decision:** retain the candidate and its tests as diagnostic evidence;
do not adopt it in production. Stop this candidate at the lower physical
control. No full-model upper control, eta_pi0 comparison, p7/p8 continuation,
replica campaign or panel scan was launched. The cheap tree results do not
justify overriding the failed complete-model screen. No new bin is certified.

The tested proposal targets the Delta mass structure and helicity angle,
but that alone does not improve this coherent physical control at the tested
resolution. This result does not rule out all joint maps or their behavior
at higher resolution. Future candidates must address the remaining coherent
angular structure and pass the same lower-bin screen before wider runs.

## Exact angular factorization of the current p_eta model

The next authorized investigation traced the angular dependence through the
implemented kernels instead of trying another sampling density. At fixed
total CM energy `W` and `z=M(eta p)`, the pion energy and momentum magnitude
are fixed. The six non-tree families depend on the pion four-vector, not on
the separate eta/proton orientation inside their rest frame:

- `chiral_contact` is independent of the pion direction.
- `internal_pi0`, `explicit_resonances`, `eta_delta_rescattering` and
  `k_sigma_star_rescattering` are linear in its spatial vector, with scalar
  loop coefficients depending only on `W,z` and the fixed pion magnitude.
- `external_pi0` is linear after removing its signed recoil factor
  `h=1/[E_out*(E_in-E_pi-E_out)]`, where
  `E_out=sqrt(m_p^2+k^2+p_pi^2+2*k*p_pi,z)`.

For each polarization, evaluate the six complete families at three physical
Cartesian pion directions. At any new unit direction `n`, reconstruct a
linear family as `sum_i n_i A_i`. For external emission, divide each anchor
by its recoil factor before summing and multiply by the target recoil
factor afterwards. Copy the contact term. This uses no fit and no mass
interpolation. The Eq. 43 tree is evaluated directly at every target event.
All seven complex matrices are summed before the spin sum, preserving
interference and each family's gauge partners.

For the p_eta projection, the selected pair momentum is opposite the pion.
With pion azimuth zero, its azimuth is pi. The existing exact global-azimuth
projection therefore gives `N=int(v-h)dmu`, `D=int(v+h)dmu`, where H/V
spin weights include the usual factor 1/2. The remaining internal helicity
azimuth drops out exactly: for ordering `(p,eta)`,
`M(p pi)^2=m_p^2+m_pi^2+2E_p*E_pi*-2q*r*cos(chi)`, independent of that
azimuth. This identity is specific to the currently implemented kernels
and this projection; it is not assumed for a general production model.

After both azimuth integrations, the phase-space measure is
`dPhi3 = p_pi*q/(64*pi^3*W) dz dcos(theta_pi) dcos(chi)`.
Equivalently, the existing sampler's integrated-angle density times
`ds_pair * dc/2 * dt/2` can be used. Apply the unchanged flux/unit factor
and normalized photon-energy weights, with no extra azimuth or Monte Carlo
normalization. The new diagnostic uses that equivalent measure and preserves
accessible energy/mass clipping and the 1.80 GeV support ceiling.

Implementation: `.work/figure4-fit/theory/scripts/figure4_angular_reduction_probe.py`.
It computes expensive Cartesian anchors at each energy/mass quadrature node
and reuses them for 8/16/32-point angular quadratures. Production sampling,
model functions, physics parameters and certification gates remain unchanged.
Independent code/mathematical review found no concrete issues in the
factorization, signs, measure, clipping or coherent projection.

### Off-axis validation and tests

Full direct-mode checks at `(E_gamma,z)=(1.15,1.54)`, `(1.45,1.62)` and
`(1.45,1.609361)` GeV used q/angle orders 64/48, both H/V polarizations,
and four target directions/helicity configurations per point. The last
point is near the KLambda threshold. Every reconstructed family agrees with
the direct family; the largest absolute discrepancy divided by that family's
largest direct matrix entry is **6.16e-13**. Changing only internal helicity
azimuth also preserves all seven directly calculated families. Checks took
**34.92 s**. These finite probes support the source-derived identity; they
do not guarantee arbitrary eventwise quadrature success near every threshold.

Evidence: `theory/outputs/angular-reduction-20261019-validation/`, including
`probe.py`, `results.json`, complex matrices and an archived copy of the
validated helper source. The source was subsequently extended with the
bin integrator; the validated reconstruction helpers were unchanged.

**68 focused tests passed in 2.80 s**, covering the new angular diagnostic
plus the existing joint map, variance recorder, phase space and Figure 4
integrator. New tests verify independent invariant/helicity relations,
phase-space volume, signed external recoil reconstruction, and a complete
bin against independent quadrature with destructive interference and
energy-onset clipping. No claim that the entire repository suite was run.

A separate pure-tree comparison used the unchanged production Sobol
integrator at p16/p17/p18 (up to 262,144 events per energy node), against
the reduced quadrature with 16 mass nodes and 32 nodes for each angle.
With four energy nodes, reduced `D=0.4382290100466612` and
`Sigma=-0.5668641369403509`; Sobol p18 gives
`D=0.4382295890773993`, `Sigma=-0.5668648770962972`.
Differences are **0.00013213%** in D and **7.40e-7** in Sigma. This
independent coordinate/measure comparison took 38.59 s and is saved as
`angular-reduction-20261019-lower/tree_check.py` and `tree_check.json`.

### Bounded complete-model lower-bin screen

The complete seven-family lower control uses the same energy/mass window
as before, direct mode and q/angle orders 64/48. First, energy order 4 and
mass orders 4/8 were evaluated, each with angular orders 8/16/32 reusing
the same expensive anchors. Timings were **72.34 s** and **139.48 s**.
At angular order 32:

| Mass nodes | Energy nodes | Numerator | Denominator | Sigma |
| ---: | ---: | ---: | ---: | ---: |
| 4 | 4 | -0.1711515262787370 | 0.5173808808456447 | -0.3308037320571154 |
| 8 | 4 | -0.1711692038781700 | 0.5174149769122045 | -0.3308160983272314 |

Mass refinement 4 to 8 changes D by **0.00658969%** and Sigma by
**1.23663e-5**. Angular 8-to-32 differences at these mass orders are below
2.1e-10 relative in D and 1.8e-10 absolute in Sigma. This is promising local
stability, not yet a certificate or a proven whole-panel runtime gain.
The subsequent checks increase mass order to 16 at energy order 4 and
energy order to 8 at mass order 8. They use separate processes with one
numerical-library thread each; their outcomes are recorded below.

Artifacts live in `theory/outputs/angular-reduction-20261019-lower/`.
`run.py` accepts `--mass-orders` and `--energy-order`; each combination
gets a separate directory and refuses to overwrite it. Each result saves
the exact source snapshot, source/reference hashes, complex Cartesian
anchor matrices, raw N/D, and `COMPLETE` only on successful completion.
`compare.py` checks provenance and NPZ integrity before recording mass,
angular and energy differences separately.

Both final checks completed successfully: mass16/energy4 in **299.48 s**,
mass8/energy8 in **299.16 s**, running concurrently as two single-thread
processes. At angular order 32:

| Mass nodes | Energy nodes | Numerator | Denominator | Sigma |
| ---: | ---: | ---: | ---: | ---: |
| 16 | 4 | -0.1711690590940232 | 0.5174139698896212 | -0.3308164623590242 |
| 8 | 8 | -0.1711722413759809 | 0.5174209956295855 | -0.3308181206827578 |

| Refinement | Relative D difference | Absolute Sigma difference |
| --- | ---: | ---: |
| Mass 4 to 8, energy4 | 0.00658969% | 1.23663e-5 |
| Mass 8 to 16, energy4 | 0.000194626% | 3.64032e-7 |
| Full mass span 4 to 16, energy4 | 0.00639508% | 1.27303e-5 |
| Energy 4 to 8, mass8 | 0.00116321% | 2.02236e-6 |

Across all runs and angular comparisons (8/16, 16/32 and full span 8/32),
the largest D difference is 2.06e-10 relative and the largest Sigma
difference is 2.45e-10. These deterministic differences are all below
the existing raw normalization/Sigma tolerances. `compare.py` verified
all saved source/reference fingerprints, source snapshots, NPZ checksums
and finite matrices before producing `comparison.json`.

**Decision:** this angular-factorization candidate passes the bounded lower
physical screen and warrants an upper-control investigation. Keep it
diagnostic for now. No full upper bin or panel was integrated this turn;
upper and threshold checks above were pointwise matrix checks only.
No new bin is marked certified. The Gauss rules are not nested Sobol
refinements, and these results have not been integrated into the production
certification policy; independent-replica, panel/cross-projection and
remaining production validation gates are not claimed complete.

The result is a source-derived reduction plus measured lower-bin stability,
not proof that every panel is solved or a universal runtime speedup.
The next bounded step is the frozen upper p_eta bin, including its strong
threshold structure, before extending the projection geometry to other pairs.

## Authorized upper p_eta control

The next local run uses the frozen upper control:
`E_gamma=[1.4,1.5]` GeV and `M(p eta)=[1.60,1.64]` GeV. The only
strong-channel threshold inside this mass window is K+Lambda at
**1.60936 GeV**, computed from the unchanged sourced meson/baryon masses.
The angular integrator, production model and reference SHA-256 values
match those used for the lower control. No implementation change or new
physics parameter was introduced for this follow-up.

The initial unsplit quadratures use mass orders 4 and 8, energy order 4,
angular orders 8/16/32, and direct q/angle orders 64/48. They completed
without typed numerical failures in **84.30 s** and **162.71 s**. At
angular order 32:

| Mass nodes | Energy nodes | Numerator | Denominator | Sigma |
| ---: | ---: | ---: | ---: | ---: |
| 4 | 4 | -0.6136579654295950 | 1.2079752886437278 | -0.5080053964668338 |
| 8 | 4 | -0.6187308276385007 | 1.2179975443111837 | -0.5079902094453012 |

The 4-to-8 mass refinement changes D by **0.82284695%** and Sigma by
**1.51870e-5**. The D margin is substantially narrower than in the lower
bin, motivating both higher mass order and an independent threshold
partition. In the unsplit mass8 rule, the nearest node above KLambda is
1.609579292808348 GeV; Gauss nodes are nonnested, so increasing their count
does not move the nearest point monotonically towards the threshold.

For the independent partition, the same unchanged integrator was run on
`[1.60,1.60936]` and `[1.60936,1.64]`, with four mass nodes per subinterval
and the same four energy nodes. Both windows are fully accessible at all
energy nodes. Raw N and D were added; Sigma was formed only after summation.
This preserves the measure and does not average the two asymmetries.
Gauss nodes are interior, so no event lies exactly on the threshold.

This eight-total-mass-node partition completed in **164.08 s**, with
`N=-0.6172396796353472`, `D=1.2146961136425090`, and
`Sigma=-0.5081432900813609` at angular order 32. Below/above-threshold
contributions to D are 0.3382460052597490 and 0.8764501083827599.
Its difference from the unsplit mass8 result is approximately **0.271%**
in D. This is a cross-check on threshold sensitivity, not a separate
certification or an adoption of the previously rejected Sobol split map.

Artifacts: `theory/outputs/angular-reduction-20261019-upper/` and
`theory/outputs/angular-reduction-20261019-upper-threshold-split/` in the
advanced worktree. Both runners preserve independent outputs, source
snapshots, source/reference hashes and complex anchors. Failures omit
`COMPLETE` and retain diagnostics. The next comparisons are unsplit mass16
at energy4 and energy8 at mass8, with at most two single-thread processes.

### Upper control completed: bounded checks pass

Both final runs completed without typed failures: mass16/energy4 in
**330.94 s** and mass8/energy8 in **335.54 s**. At angular order 32:

| Mass nodes | Energy nodes | Numerator | Denominator | Sigma |
| ---: | ---: | ---: | ---: | ---: |
| 16 | 4 | -0.6169788268183689 | 1.2141576344105964 | -0.5081538091368808 |
| 8 | 8 | -0.6187455614321339 | 1.2180251141602040 | -0.5079908076105167 |

| Comparison | Relative D difference | Absolute Sigma difference |
| --- | ---: | ---: |
| Mass 4 to 8, energy4 | 0.822847% | 1.51870e-5 |
| Mass 8 to 16, energy4 | 0.315264% | 1.63600e-4 |
| Full mass span 4 to 16, energy4 | 0.509188% | 1.48413e-4 |
| Energy 4 to 8, mass8 | 0.00226349% | 5.98165e-7 |
| Unsplit mass8 versus split4 per side | 0.271054% | 1.53081e-4 |
| Unsplit mass16 versus split4 per side | 0.0443304% | 1.05191e-5 |

All comparisons satisfy the existing strict 1% normalization tolerance;
Sigma differences are below the existing spatial/energy tolerances. Among
the unsplit angular refinements and full angular spans, the largest D
difference is **0.000306821%**, and the largest absolute Sigma difference
is **1.57791e-7**. The 16-to-32 angular differences are below 2.23e-9
relative in D. The remaining sensitivity in this control is primarily
the mass rule across the threshold, rather than angular resolution.

`angular-reduction-20261019-upper/compare.py` completed with exit 0. It
verified source/reference hashes, every source snapshot, NPZ checksums,
finite anchor matrices and exact raw-moment recomposition of the threshold
partition before writing `comparison.json`. No production/test source
changed in this follow-up. Runner and comparison scripts compiled and
executed successfully; the previously passing 68-test suite was not rerun
merely to repeat verification of unchanged code.

**Decision:** the angular-factorization candidate now passes the bounded
lower and upper p_eta physical controls at the tested resolutions. Preserve
the diagnostic implementation and results. Do not label these as newly
certified bins: Gauss refinements are nonnested; integration with the
production certification policy, independent checks required by that policy,
other pair projections, panel covariance and cross-projection totals remain
open. No physical parameter or numerical tolerance was adjusted, and no
universal speedup is claimed from historical timing comparisons.

The next concrete target is the failing eta_pi0 bin at
`E_gamma=[1.1,1.2]`, `M(eta pi0)=[0.72,0.76]`. Extending to that projection
requires its mass-window geometry and selected-pair azimuthal weight;
the p_eta observable formula must not be reused unchanged. Its previously
measured direct p6/p7 normalization drift was 5.4230%.


## Eta-pion projection: exact azimuth preflight

The separate diagnostic `scripts/figure4_pair_projection_probe.py` reuses
`figure4_angular_reduction_probe.py` without changing that archived helper.
It retains fixed W and z=M(eta p) as amplitude coordinates, but clips the
proton helicity cosine t to the selected eta-pion window. At fixed z,
`M(eta pi)^2 = K + b*t`, where b is the positive product of the two
Kallen square roots divided by `2*z^2`. The outer z integration is split
at exact Dalitz crossings of both selected mass edges and at sourced
strong-channel thresholds. Each segment uses a sine-squared change of
s=z^2 with its exact Jacobian; angular measures are `dt/2` and `dc/2`.

For pion polar cosine c, the boosted proton cone has longitudinal and
transverse components `A=gamma*(q*t-beta*Ep*)`, `B=q*sqrt(1-t^2)`.
Let `r=abs(A)/hypot(A,B)`, `u=abs(c)`. The exact internal-azimuth average is

```
<cos(2 phi_eta_pi)> = -(1-u)/(1+u)                 for u >= r
                    = 1 - 2*(1-r)/(1-c*c)        for u < r
<sin(2 phi_eta_pi)> = 0
```

The selected pair momentum is minus the proton momentum, which leaves
the double angle unchanged. Evaluate `1-r` as
`B^2/[hypot(A,B)*(hypot(A,B)+abs(A))]` to avoid cancellation, and split
polar rules at `c=+-r`. Thus N uses `(V-H)*<cos(2 phi)>`, D uses `V+H`;
V/H are coherent seven-family squared matrix norms including spin average.
There is no additional azimuth factor or Monte Carlo event-count divisor.
The full upper-energy support is checked before amplitude calls; a bin
extending beyond M(eta p)=1.80 GeV is rejected, never truncated silently.

Independent mathematical review found no critical or important issue.
**80 focused tests pass** in 8.16 s, including explicit uniform-azimuth
averages on actual boosted four-vectors, exact mass-edge crossings,
independent eta-pion phase-space integration across energy onset,
destructive family interference, a nonzero polarized dipole numerator
checked against the existing eta-pion Sobol sampler, and rejection of
unsupported bins before amplitude evaluation.

A cheap Eq.43-only physical check used energy4, mass12 per segment,
angular orders 8/16/32 and standard eta-pion Sobol p16/p17/p18. At angle32:
reduced N=-0.1053883917885702, D=0.43508398684192334,
Sigma=-0.24222539779856428. Sobol p18 gives
N=-0.10538836135019027, D=0.43508365128628357,
Sigma=-0.24222551465360642. D differs by **0.00007712%**, Sigma by
**1.16855e-7**. Combined preflight time: 49.79 s. This validates projection
geometry and normalization, not full-model convergence.

Artifacts: `theory/outputs/angular-reduction-20261019-eta-pi0/`.
The frozen full-model target is E_gamma=[1.1,1.2], M(eta pi)=[0.72,0.76],
direct 64/48. At energy4 the support has 3,3,4,4 mass segments;
the last two energy nodes cross the sourced KLambda threshold at
1.60936 GeV. Initial mass2 and mass4 runs therefore use 28 and 56 expensive
anchor nodes, respectively, each shared across angular orders 8/16/32.


### Full eta-pion model: coarse mass rules fail, energy and angles stable

The direct 64/48 runs completed at angular order 32 as follows:

| Mass nodes per segment | Energy nodes | Numerator | Denominator | Sigma | Seconds |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 2 | 4 | -0.1493866781971856 | 0.6363778272830625 | -0.2347452594867640 | 126.07 |
| 4 | 4 | -0.1902491723406704 | 0.7174117169107355 | -0.2651882703559778 | 251.22 |
| 8 | 4 | -0.1927318859765875 | 0.7248672390424603 | -0.2658857727260287 | 501.92 |
| 4 | 8 | -0.1902493920222666 | 0.7173988353027179 | -0.2651933382941552 | 486.67 |

Mass2/4 changes D by **11.2953%** and Sigma by **0.0304430**: both fail.
Mass4/8 changes D by **1.02854%** and Sigma by **0.000697502**: the
normalization still fails the unchanged strict 1% tolerance. The full
mass2/8 span also fails. These coarse rules cannot be called converged.
Energy4/8 at mass4 changes D by **0.00179557%**, Sigma by **5.06794e-6**;
this supports only the tested energy refinement at mass4, not a combined
uncomputed mass16/energy8 result. Angular8/16/32 changes D by at most
approximately 5.2e-11 relative in these runs.

The mass8 D differs from the historical direct p7 result by **0.502501%**,
Sigma by **0.00274826**. The historical p6/p7 D difference remains
**5.42298%**, so p7 is not an independently certified reference.
`compare.py` verifies target bounds, direct 64/48 settings, shared
source/reference fingerprints, both source snapshots, NPZ checksums,
finite complex matrices, capture dimensions, angular orders and N/D
ratios before comparing records. Initial comparison completed with exit 0;
its explicit failing-gate booleans are scientific results, not runtime errors.

A final mass16/energy4 run was started to determine whether the residual
mass error keeps decreasing. This bounded follow-up does not authorize a
claim that all diagnostic checks pass if a prior or full-span gate fails.


### Final eta-pion mass confirmation: latest refinement stable, full gate incomplete

Mass16/energy4 completed in **1001.79 s (16 min 42 s)** with 224 anchor
nodes (448 H/V calls). At angular32:

- N = **-0.19272765841862727**
- D = **0.7248671655110299**
- Sigma = **-0.2658799675148131**

| Comparison | Relative D difference | Absolute Sigma difference | Fixed D gate |
| --- | ---: | ---: | --- |
| Mass4 to 8 | 1.02853622% | 0.000697502370 | fail |
| Mass8 to 16 | 0.0000101441% | 0.000005805211 | pass |
| Full mass4 to 16 | 1.02852618% | 0.000691697159 | fail |
| Energy4 to 8 at mass4 | 0.00179557% | 0.000005067938 | pass |

The largest angular8/16/32 D difference over all five runs is
**5.13885e-11 relative**, largest Sigma difference **3.28431e-11**.
The latest result differs from the historical uncertified direct p7 by
0.502511% in D and 0.00275407 in Sigma. That comparison is contextual,
not a convergence certificate or an estimate of the true numerical error.

The final `compare.py` completed with exit 0 and verified all five
runs' source/reference fingerprints, source snapshots, capture checksums,
finite matrices, expected dimensions and raw-moment ratios. Historical
support/settings and all shared source/reference hashes match. Final
`comparison.json` explicitly retains the failed coarse and full-span
gates. No physics source, production sampler, parameter or tolerance was
changed in this eta-pion extension. Focused proof remains **80 passing
tests**; no unrelated broad suite was rerun after unchanged source.

**Decision:** retain this candidate as a promising diagnostic. Exact
angular averaging and the independent physical tree check are validated;
the last mass refinement is highly stable, but the tested mass4/8/16
sequence does **not** pass every unchanged gate. Do not call the eta-pion
bin certified or the entire bounded screen passed. Mass4 is underresolved;
a fresh three-level confirmation beginning at mass8 (8/16/32), with energy
refinement at an adequately resolved mass order, remains to be measured.
Neither a formal quadrature error bound nor production certification-policy
integration has been supplied. Inner-loop, independent production-policy,
p_pi0, covariance and panel/cross-projection gates also remain open.

The bounded local campaign is complete; no further physics job remains
running. This outcome is additional evidence for the factorization route,
not reproduction of the twelve panels or a change to existing certificates.
