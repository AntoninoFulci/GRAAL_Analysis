# N*(1535) vector-exchange correction: design

## Purpose and scientific boundary

Reconstruct the real-axis, charge-`+1` six-channel strong transition matrix
used by Döring, Oset, and Strottman for `γp → ηπ⁰p`, adding the vector-meson
exchange (VMD) correction to the already implemented `ππN` variant. This is
the next prerequisite for a **coherent photoproduction amplitude** and the
twelve calculated curves in Ajaka et al. Figure 4. It produces no Figure 4
curve itself. After publication-binning validation, the eventual model must
also support fitting our higher-statistics asymmetries in their native bins.
The [Figure 4 design](2026-10-01-figure4-theory-design.md) remains the claim
gate for that final objective.

The reduced strong matrix (no VMD, no `ππN`) and the `ππN`-only intermediate
matrix remain separately callable and numerically unchanged. Stage 07/08,
their outputs, and the existing Eq. (43) pilot are outside this increment.
No vector mass, switching energy, subtraction constant, or normalization is
fitted to P65/P73 plots, Ajaka lines, or our data during reconstruction.

Primary sources: Inoue, Oset, Vicente Vacas, *Phys. Rev. C* **65**, 035204
(2002), Sec. II B, Eqs. (12)–(13), Fig. 5 and Sec. III C, Eq. (28), local PDF
`tmp/pdfs/PhysRevC.65.035204.pdf` (SHA-256
`e8861394ef3fb86c005694d3cb82d8c2b905e39dbe384903f58392d644cff6ac`);
Döring, Oset, Strottman, *Phys. Rev. C* **73**, 045209 (2006), Sec. II,
Table I and Fig. 15, local PDF `tmp/pdfs/10.1103@PhysRevC.73.045209.pdf`
(SHA-256 `19a2fbce10ed8201a29bdfbcfb9f3690a280d943c1e83db01aa1b2057d20eccb`).
The [source map](../references/nstar_1535_tmatrix_source_map.md) distinguishes
paper statements from implementation conventions.

## Reconstructed VMD prescription

Use P73 Table I's existing channel order and coefficients. P65 prescribes
`C_ij → C_ij F_ij(W)` only above `W⁰_ij`, where the angular integral equals
one. For real center-of-mass energy `W`, meson mass `m_i`, baryon mass `M_i`,
meson energy `ω_i=(W²+m_i²−M_i²)/(2W)`, and `q_i²=ω_i²−m_i²`, define

```
A = m_v² − m_i² − m_j² + 2 ω_i ω_j
B = 2 q_i q_j
F_ij(W) = (m_v²/2) ∫[-1,1] dz / (A − B z)
        = m_v²/(2B) log[(A+B)/(A−B)]
```

The `B→0` limit is `m_v²/A`. Use the real-valued physical-sheet continuation
of this angular average when exactly one channel is closed; direct angular
quadrature provides an independent check. The factor is dimensionless,
symmetric in `i,j`, and real on the specified real-energy domain. Reject a
singular propagator, nonfinite factor, or branch that cannot be reconciled
with the angular integral; do not silently take a real part or clip a result.

P65 explicitly uses `m_ρ=0.770 GeV` for `π⁻p→π⁻p` and `m_K*=0.892 GeV` for
the strangeness-changing `π⁻p→K⁰Λ` example. It does **not** tabulate a
vector species for every P73 charge-`+1` matrix element. The user-approved
reconstruction therefore assigns `ρ` to nonzero elements whose meson
channels have equal strangeness and `K*` to nonzero elements changing
strangeness. In this basis, channels 1–3 (`πN,ηN`) have meson strangeness
zero, and channels 4–6 (`KΣ,KΛ`) have meson strangeness `+1`. This rule is an
**implementation convention**, not an additional assertion about P65's
unprinted assignments or a unique SU(3) vector-exchange decomposition. Make
the resulting 6×6 assignment inspectable, and leave zero `C_ij` entries zero.
Store both quoted masses and P65 source locators in
`theory/references/nstar1535_vmd_masses.json`, separate from subtraction
constants. Reject invalid units, nonpositive or nonfinite values, and missing
source keys. Do
not introduce a fitted species or scale parameter.

For each nonzero `C_ij`, solve `F_ij(W⁰_ij)=1` in the closed interval between
the two channel thresholds `m_i+M_i` and `m_j+M_j`. Equal-threshold diagonal
entries switch at their threshold. The physical-mass probe found a crossing
for every nonzero entry in the existing P73 matrix; implementation must
verify the bracket and fail explicitly if another mass set has no crossing.
Use `C_ij` at and below `W⁰_ij` and `C_ij F_ij(W)` above it. Equality ensures
continuity. Compute only on the existing real-axis domain, from the lowest
channel threshold through `1.70 GeV`; no complex-energy continuation or
pole/residue claim is part of this step.

The formula, not P65's informal “about 25%” sentence, fixes normalization.
For example, Eq. (13) with the already sourced charged-pion/proton masses
gives `F(π⁻p→π⁻p, W=1.500 GeV)≈0.6383`; the left panel of P65 Fig. 5 is
visually near that scale. Do not force `0.75` by changing inputs.

## Ownership and data flow

A focused VMD module owns the angular factor, vector-species assignment,
switching energies, and corrected coefficient/kernel construction. Reuse the
existing WT kinematic normalization and `C` matrix rather than copying the
full WT formula. A separate strong-amplitude entry point constructs

```
V_full(W) = V_WT(W; C → C̃(W)) + δV_ππN(W)
T_full(W) = [I − V_full(W) G(W)]⁻¹ V_full(W)
```

The VMD step replaces `C` within the WT expression; it is **not** an
additional diagram added to the original WT kernel. Add P73 Eq. (6)'s
`δV_ππN` once, in the pion block only. Reuse the existing two-body loops and
linear solver. The baseline calculation loads the separate final-fit
subtractions `μ=1.2 GeV`, `(a_πN,a_ηN,a_KΛ,a_KΣ)=(2.0,0.1,1.5,−2.8)` from
P65 Eq. (28), plus the already documented physical channel masses and the
common `ππN` mass convention. Preserve ability to pass other validated
numeric inputs later for the **native-bin fit**, while labeling the sourced
baseline distinctly from a fitted variant.

All energies/masses use GeV; `V`, `δV`, and `T` use `GeV⁻¹`, and `G` uses
`GeV`. Public naming and documentation must say “full-model
reconstruction”; agreement with Fig. 15 cannot prove the unprinted vector
assignments unique. Such agreement validates this strong submodel, **not**
the coherent photoproduction prediction or Ajaka Figure 4.

## Verification and exit

Focused tests must establish P65 Eq. (13) for elastic `πN` and its
`B→0` limit; agreement with independent angular quadrature for elastic,
open/closed, and two-open-channel cases; all nonzero species assignments;
zero-pattern preservation; source masses and units; symmetric, real finite
corrected coefficients; one crossing between each pair of thresholds;
continuity at every switch; and explicit failure for malformed inputs or
missing crossings. Verify that VMD-only changes the expected kernel entries,
that `ππN` is added exactly once, and that the full `T` satisfies its matrix
equation. Frozen reduced, `ππN`-only, and Eq. (43) regressions must pass.

Document numerical/visual comparison with P65 Fig. 5, including PDF hash,
axis-reading uncertainty, and mass convention. Compare full charge-`+1`
`|T^(i3)|` and `|T^(i1)|` with P73 Fig. 15, distinguishing plot-reading
uncertainty from the known difference between sourced PDG-2024 masses and
the papers' unprinted complete mass set. Record residuals or a clear qualitative
discrepancy; **do not** retune missing information until a primary source
justifies it. If comparison fails, keep implementation as a tested candidate
and explicitly withhold the published-full-model label. The full solid S11
line in P73 Fig. 1 is an optional secondary diagnostic only after its
charge-to-isospin and partial-wave conventions are documented; it is not an
acceptance gate for this increment.

Exit when source-linked VMD code, preservation/physics tests, and comparison
note are complete. Next milestone connects verified `T^(i3)` and other strong
transitions to all reaction-level production terms and their relative
complex phases. Only after component and coherent cross-section checks may
we calculate and overlay all twelve Ajaka Figure 4 curves; only after that
validation may we fit our higher-statistics native-bin asymmetries.
