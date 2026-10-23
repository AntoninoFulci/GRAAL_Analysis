# Reduced N*(1535) coupled-channel T: design

## Purpose and boundary

Build the charge-`+1`, six-channel, real-energy s-wave meson-baryon
transition matrix needed by the standalone `theory/` calculation of
`gamma p -> eta pi0 p`. This milestone implements only the **reduced**
model defined by Döring, Oset, and Strottman, *Phys. Rev. C* **73**,
045209 (2006), Sec. II and Fig. 1: the basic Inoue, Oset, and Vicente
Vacas, *Phys. Rev. C* **65**, 035204 (2002), two-body model **before**
both t-channel vector exchange and `pi pi N` are added. It does not
calculate photoproduction amplitudes or any Ajaka Figure 4 curve.

Success means an independently calculated complex `T^(i3)` with
traceable inputs, correct six-channel ordering and physical-sheet
behavior, numerical consistency checks, and an honest comparison to
the published reduced reference where its normalization and isospin
convention can be established. Published lines are validation data,
never fit targets.

The broader Figure 4 design remains
[`2026-10-01-figure4-theory-design.md`](2026-10-01-figure4-theory-design.md).
The equation/parameter audit is
[`nstar_1535_tmatrix_source_map.md`](../references/nstar_1535_tmatrix_source_map.md).

## Chosen architecture

Keep the strong transition matrix in a reaction-specific module under
`theory/src/graal_theory/amplitudes/`. It owns the fixed P73 Table I
charge coefficient matrix, P65 s-wave Weinberg-Tomozawa kernel, diagonal
dimensionally regularized loop, and on-shell matrix solution. The
existing `EtaPi0PModel`, Eq. (43) tree amplitude, Stage 07/08, and
their outputs remain unchanged. A future coherent-amplitude milestone
may consume this `T`; no integration is part of this one.

Use one explicit, versioned input record under `theory/references/` for
the ten distinct physical meson/baryon masses, `f_pi`, the `f_K/f_pi`
and `f_eta/f_pi` ratios, subtraction scale, and four subtraction
constants. Every value carries a source and locator using the existing
provenance convention. Reuse the existing PDG 2024 citation for masses,
including values already present in `central_parameters.json`; do not
couple the new loader to that tree-model file's exact-key schema. Use
P65 Eqs. (5), (9) for `f_pi=93 MeV`, ratios `1.22`, `1.3`,
`mu=1200 MeV`, and `(a_piN,a_etaN,a_KLambda,a_KSigma)` =
`(2.0,0.2,1.6,-2.8)`. Internal energy unit: GeV. Retain source PDF
hashes and note that PDG 2024 masses are not documented as identical
to the original authors' numerical mass table, which is not printed
in the inspected sections.

Channel indices are one-based in documentation, zero-based in arrays:

| Index | Channel | Subtraction family |
| ---: | --- | --- |
| 1 | `pi0 p` | `pi N` |
| 2 | `pi+ n` | `pi N` |
| 3 | `eta p` | `eta N` |
| 4 | `K+ Sigma0` | `K Sigma` |
| 5 | `K+ Lambda` | `K Lambda` |
| 6 | `K0 Sigma+` | `K Sigma` |

Implement P73 Table I's symmetric `C` exactly as transcribed in the
source map; never derive it by renaming P65's charge-zero matrix.
For finite real `W` from the lightest `pi N` threshold through
`1.70 GeV`, return complex `6x6` matrices. Compute
`V` with P65 Eq. (5), `G` with P65 Eq. (6) and the physical-sheet
`+i0` prescription, then solve `(I-VG)T=V`; avoid explicitly inverting
`I-VG`. Scalar-energy evaluation is sufficient for this milestone.
Reject malformed/nonfinite inputs and a singular solve explicitly.
Do not silently clamp a closed channel's complex momentum to zero.

## Numerical conventions and verification

The loop includes P65's `2M_i` numerator. Above an open threshold it
must satisfy `Im G_i = -M_i Q_i/(4 pi W)` (P65 Eq. (7)); a closed
channel's real-axis imaginary part must vanish within floating-point
tolerance. Test limiting behavior on both sides of each threshold,
complex-log branch signs, finite results, `T^T=T`, and the reduced
six-channel unitarity relation from P65 Eq. (8) where the matrix is
nonsingular. Verify the WT kernel's symmetry, units, source-linked
parameter values, and stable results under an equivalent linear-solve
formulation. A nonzero `pi N -> eta N` transition despite `C_13=C_23=0`
is a useful coupled-channel smoke test, not an external benchmark.

The published reduced comparison is the **dashed** real and imaginary
`pi N -> eta N` S11 line in P73 Fig. 1. P65 Eq. (10) specifies the
dimensionless partial-wave rescaling, while the computed `T` has units
`GeV^-1` (or `MeV^-1` after conversion). First document the charged
channel to isospin-`1/2` combination and its overall phase from the
source conventions; do not infer a sign by matching the plotted line.
Digitize a small independent reference with source-page, axis, PDF
checksum, and reading uncertainty, or report that the phase convention
prevents a defensible signed comparison. Compare a predeclared energy
grid and record residuals; no adjustment of subtraction constants or
masses to improve agreement. Because masses follow PDG 2024, report
their provenance and resulting comparison limitation. P73 Fig. 15
shows the **full** `T`; it is not an acceptance target for this reduced
implementation. P65's `1543-i46 MeV` pole is on a second sheet and is
also not a real-axis acceptance target.

## Deliverables and exclusions

Deliver module, source-linked parameter record, focused tests, and a
short machine-readable or Markdown comparison report with command,
source hashes, plotted/reference normalization, and discrepancy status.
Document the new component as **reduced strong T only**; preserve
the existing Eq. (43) pilot's scope and output. No CLI, new generic
coupled-channel framework, VMD correction, `pi pi N` loop, complex-energy
pole search, photon-production rescattering, 12-panel overlay, or Stage
07/08 integration is included here. Later full-model work must use
P65's distinct final subtraction set, not mutate this reduced record.

If the signed published comparison remains convention-blocked, deliver
the internally verified `T` and an explicit unresolved condition, not a
claim of reproduced reduced curve.
