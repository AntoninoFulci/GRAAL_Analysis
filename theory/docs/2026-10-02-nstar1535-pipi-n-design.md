# N*(1535) ππN correction: design

## Purpose and boundary

Add the source-defined, energy-dependent `ππN` correction to the charge-`+1`
six-channel strong transition matrix in standalone `theory/`. This is one
bounded scientific milestone toward the coherent `γp → ηπ⁰p` amplitude, twelve
calculated Ajaka Figure 4 curves, and the later fit of our native-bin data.
It does **not** produce any of those curves by itself. The publication goal and
claim gate remain in [the Figure 4 design](2026-10-01-figure4-theory-design.md).

The existing reduced calculation must remain available and unchanged. A matrix
with `ππN` but without vector-meson exchange (VMD) is an **intermediate
variant**, neither P73's reduced nor full model. No result from this milestone
may be labeled the published full prediction. No parameter may be tuned to
Ajaka's digitized curves or to our measurements.

Primary sources: Inoue, Oset, Vicente Vacas, *Phys. Rev. C* **65**, 035204
(2002), Eqs. (25)–(30), PDF `tmp/pdfs/PhysRevC.65.035204.pdf` (SHA-256
`e8861394ef3fb86c005694d3cb82d8c2b905e39dbe384903f58392d644cff6ac`);
Döring, Oset, Strottman, *Phys. Rev. C* **73**, 045209 (2006), Eqs. (5)–(6),
PDF `tmp/pdfs/10.1103@PhysRevC.73.045209.pdf` (SHA-256
`19a2fbce10ed8201a29bdfbcfb9f3690a280d943c1e83db01aa1b2057d20eccb`).
The [equation-level source map](../references/nstar_1535_tmatrix_source_map.md)
records the transcription and known ambiguities.

## Approach

Use direct, deterministic integration of the physical three-body domain for
`Im G̃(W)` from P65 Eq. (26), set `Re G̃(W)=0` as in its final fit, and add
P73 Eq. (6) **once** to the pion–nucleon `2×2` block of the existing WT
kernel. Solve `(I−VG)T=V` with the existing six-channel meson–baryon loops.
The correction is kept separate from the reduced-kernel function, and the
linear-system validation/solve is shared rather than duplicated.

Alternatives considered: a pretabulated/interpolated loop could accelerate
large event integrations but would add interpolation and error-control
questions before the normalization is verified. An explicit eight-channel
`ππN` system would be a different representation and would double-count if
combined with P73 Eq. (6). Neither is part of this increment. If later panel
integration needs acceleration, benchmark a tabulation against this direct
reference implementation in a separate step.

Use GeV throughout. P65 Eqs. (29)–(30) determine real `v₁₁(W)` and
`v₃₁(W)` in `GeV⁻³`; Eq. (26) yields `G̃` in `GeV⁵`; P73 Eq. (6) therefore
adds a complex `GeV⁻¹` matrix. Its ordinary products/squares are **not**
absolute squares. Only indices `(π⁰p, π⁺n)` receive this correction.

For stable integration, parameterize the physical domain by the energy
`ω₁` of one pion and the allowed `ω₂` interval from the decay of the
remaining `πN` system. Require positive pion energies and an on-shell,
positive-energy nucleon. This is equivalent to Eq. (26)'s `θ(1−A²)` inside
the physical Dalitz domain; it excludes unphysical energy configurations
that satisfy the angular inequality alone. The integrand is finite and
nonnegative before P65's negative prefactor. At and below
`W=M_N+2m_π`, return zero. Compare 48- and 96-point Gauss–Legendre rules
in each integration dimension; accept the 96-point value only when their
difference is at most `max(10⁻¹² GeV⁵, 10⁻³ |G̃₉₆|)`, and fail explicitly
otherwise. Real energies use
the existing reduced matrix's domain, through `1.70 GeV`; no second-sheet
continuation or pole search is introduced.

P65 does not itemize the common `m_π` and `M_N` values in this loop. Fix the
baseline to the already sourced PDG-2024 charged-pion mass and isospin-average
nucleon mass `(M_p+M_n)/2`; mark this as an **implementation convention**, not
an author-specified value. Report sensitivity to neutral-pion and individual
proton/neutron choices. Keep these choices explicit and distinct from the
physical channel masses in the six two-body loops.

Load P65's final-fit subtraction constants from a separate, source-linked
record: `μ=1.2 GeV`, `(a_πN,a_ηN,a_KΛ,a_KΣ)=(2.0,0.1,1.5,−2.8)` (Eq. 28).
Never mutate or overwrite the basic/reduced record with `(2.0,0.2,1.6,−2.8)`.
The intermediate variant uses the final-fit record to prepare for eventual
VMD integration; without VMD this is not a published standalone fit.

## Verification and exit

Focused tests must establish: exact threshold zero; nonpositive `Im G̃`
above threshold; GeV↔MeV normalization; agreement of the mapped-domain
quadrature with an independently bounded integration at `W=1.25`, `1.45`,
and `1.65 GeV`; 48/96-point convergence; correct P65 polynomials;
P73's symmetric, pion-block-only correction and its negative-semidefinite
absorptive part; finite, symmetric `T`; and the defining matrix equation.
Six-channel *closed* two-body unitarity must **not** be imposed after the
absorptive `ππN` term is added. Existing reduced-model frozen-grid and Eq.
(43) tests remain unchanged and pass.

As an external check, compare the sign, scale, and energy shape of the loop
with P65 Fig. 11, preserving its `10⁸ MeV⁵` axis units and recording any
digitization uncertainty. Do not use that plot to fit a missing factor.
P73 Fig. 15 is a **full-model** target, deferred until VMD is included; a
discrepancy there must not be repaired by retuning this isolated term.

Exit this milestone when the sourced `ππN` kernel, direct loop, provenance,
tests, and comparison note are complete. Next: resolve and implement P65's
VMD assignments/switching conventions, then assemble photoproduction terms
coherently. Only after those checks may the twelve-panel comparison and
native-bin fit proceed. Stage 07/08 and their outputs remain untouched.
