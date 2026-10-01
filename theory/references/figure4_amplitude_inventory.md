# Figure 4 coherent-amplitude source inventory

Scope: `gamma p -> eta pi0 p` model behind Ajaka et al., *Phys. Rev.
Lett.* **100**, 052003 (2008), Fig. 4. This inventory maps the production
and rescattering contributions described by Döring, Oset, and Strottman,
*Phys. Rev. C* **73**, 045209 (2006). It is **not** an implemented coherent
model. Equation numbers and figure numbers below refer to that PRC paper.

## Source availability

| Source | Role | Local PDF | SHA-256 / availability |
| --- | --- | --- | --- |
| Döring, Oset, Strottman, *Phys. Rev. C* **73**, 045209 (2006) | Principal `eta pi0 p` amplitudes and Fig. 14 coherent sum | `tmp/pdfs/10.1103@PhysRevC.73.045209.pdf` | `19a2fbce10ed8201a29bdfbcfb9f3690a280d943c1e83db01aa1b2057d20eccb` |
| Döring, Oset, Strottman, *Phys. Lett. B* **639**, 59 (2006) | Complementary `Delta*(1700)` coupling conventions | `tmp/pdfs/10.1016@j.physletb.2006.06.022.pdf` | `c1def91b01ee5750aca4124ae2469178b204d99649075d7d4f4277facab9d430` |
| J. C. Nacher, E. Oset, M. J. Vicente Vacas, L. Roca, *Nucl. Phys. A* **695**, 295 (2001), PRC Ref. [17] | Two-pion resonance couplings, widths, and pion form factor used in Figs. 8–9 | `tmp/pdfs/nucl-th-0012065.pdf` | `0227c86bdf98deb6a7674df6720d5db80a4242fe56cdff431c507729bd7b144e` |
| S. Sarkar, E. Oset, M. J. Vicente Vacas, *Nucl. Phys. A* **750**, 294 (2005), PRC Ref. [21] | Dynamically generated `Delta*(1700)` couplings to `eta Delta` and `K Sigma*` | `tmp/pdfs/nucl-th-0407025.pdf` | `1b67f036787bc1085d1ae0491f64e14b8970ffe4f2377607da51dc5a2fc077af` |
| T. Inoue, E. Oset, M. J. Vicente Vacas, *Phys. Rev. C* **65**, 035204 (2002), PRC Ref. [8] | `N*(1535)` six-channel `T` matrix, loop `G`, subtraction/regularization, full/reduced variants | Not supplied | **blocked_missing_source** |
| M. Döring, E. Oset, M. J. Vicente Vacas, *Phys. Rev. C* **70**, 045203 (2004), PRC Ref. [25] | `pi pi N` correction to the full `N*(1535)` potential, referenced after Eq. (6) | Not supplied | **blocked_missing_source** for full-model variant |
| M. N. Butler, M. J. Savage, R. P. Springer, *Nucl. Phys. B* **399**, 69 (1993), PRC Ref. [40] | Adopted decuplet effective Lagrangian and state phases in Sec. IV D, Eq. (38) | Not supplied | Phase-convention cross-check pending |
| E. Oset, A. Ramos, *Nucl. Phys. A* **679**, 616 (2001), PRC Ref. [41] | Comparison SU(3) factors, explicitly up to a different phase | Not supplied | Comparison only; not the adopted convention |

The PRC paper prints the charge-`+1` channel order, leading potential,
Bethe–Salpeter expression, and some corrections in Sec. II, Eqs. (1)–(6).
It explicitly sends the s-wave projection, loop `G`, and the `v11`/`v31`
ingredients back to Ref. [8]. Ref. [25] supplies a correction used by the
full (rather than reduced) model. The four supplied papers alone therefore
do not fix the entire numerical `N*(1535)` transition amplitude. No
curve-matched substitute is allowed.
Sec. IV D adopts the effective Lagrangian and decuplet-state phases of
Ref. [40], stating agreement with Ref. [21]. It compares the resulting
SU(3) factors with Ref. [41] **up to a different phase**; [41] is not the
source of the adopted convention. Neither [40] nor [41] is supplied.
Eqs. (39)–(42) print the factors used here, but their relative phase
still needs an explicit cross-check against [40] before coding.

## Amplitude families

Here `sourced_not_implemented` describes a **production kernel only**;
`blocked_missing_source` describes the complete contribution after its
required `T`/`G` rescattering factors are included.

| Family | PRC locator | Needed external source | Phase/coupling evidence | Local PDF | Status |
| --- | --- | --- | --- | --- | --- |
| `N*(1535)` coupled-channel transition matrix `T^(i3)` and loop `G_i` | Sec. II, Eqs. (1)–(6), Table I; Sec. III, Eq. (8) | Ref. [8] for projected `V`, `G`, and full/reduced variants; Ref. [25] for full-model `pi pi N` correction | Channel order `(pi0 p, pi+ n, eta p, K+ Sigma0, K+ Lambda, K0 Sigma+)` fixed by Eq. (1); coherent complex matrix required by Eq. (5) | Ref. [8] and [25] absent | **blocked_missing_source** |
| Chiral magnetic/contact photoproduction with rescattering | Fig. 6, Eq. (21); Sec. IV A | Ref. [8] for `G_j T^(j3)` | `b6D`, `b6F` and `X1j`, `Y1j` appear in Eqs. (16)–(21); minimal versus anomalous magnetic terms must retain paper convention | PRC present; Ref. [8] absent | **blocked_missing_source** |
| External `pi0` emission around `gamma p -> eta p` (KR and meson-pole subamplitudes) | Fig. 7, Eq. (24), using Sec. III Eqs. (8)–(9) | Ref. [8] for the `gamma p -> eta p` rescattering amplitude | Eq. (24) fixes recoil `sigma · p_pi` factor; Eq. (9) is coherent KR + meson pole, not their squared sum | PRC present; Ref. [8] absent | **blocked_missing_source** |
| `pi0` emission inside first meson–baryon loop | Fig. 8(c,d), Eq. (25) | Ref. [8] for `T^(i3)`; Ref. [17] for monopole `F_pi` convention | Diagram (d) and form factor pairing are required by the paper's gauge-invariance argument; nonzero channels 2, 4, 5 are printed after Eq. (25) | PRC and Ref. [17] present; Ref. [8] absent | **blocked_missing_source** |
| Explicit `Delta*(1700) pi Delta`, `N*(1520) pi Delta`, and `Delta` KR/pole production kernels | Fig. 9(e,f), Eqs. (26)–(36); Fig. 13 | Ref. [17] for resonance couplings, width and form-factor conventions; Ref. [8] for final `T^(i3)` | Eqs. (28)–(35) specify charge-channel factors; Eq. (26) sums **complex** amplitudes before squaring; KR pole factor in Eq. (32) cannot be omitted | PRC and Ref. [17] present; Ref. [8] absent | **blocked_missing_source** |
| `Delta*(1700) -> eta Delta` rescattering | Fig. 10, Eq. (39) inserted into Eq. (26); Fig. 14 dash-dot | Ref. [21] for `g_eta`; Ref. [17] for electromagnetic coupling/width; Ref. [8] for `eta p -> eta p` `T^(33)`; Ref. [40] for adopted state phases | PRC Sec. IV D adopts Ref. [40]/[21] phase convention; `g_eta`/`g_K` also share a global sign tied to empirical `Delta pi` analysis; relative complex phase must be preserved | PRC, Ref. [17], Ref. [21] present; Refs. [8], [40] absent | **blocked_missing_source** |
| `Delta*(1700) -> K Sigma*` rescattering and `Sigma*` KR term | Fig. 10, Eqs. (40)–(42) inserted into Eq. (26); Figs. 12–13 | Ref. [21] for `g_K`; Ref. [17] for production couplings; Ref. [8] for `K Sigma/K Lambda -> eta p` transitions; Ref. [40] for adopted state phases | Eqs. (40)–(42) supply charge/SU(3) factors and the 1.15 empirical correction; `Sigma*` propagator replaces `Delta` one in Eq. (26) | PRC, Ref. [17], Ref. [21] present; Refs. [8], [40] absent | **blocked_missing_source** |
| Isolated `Delta*(1700) -> eta Delta -> eta pi0 p` tree | Fig. 11, Eqs. (39), (43)–(44); Fig. 14 dotted | Ref. [17] and [21] as already documented in `parameter_provenance.md` | Existing code uses complete Eq. (39) production spin matrix and polarized Eq. (43) amplitude; does **not** include Eq. (26) rescattering | PRC, Ref. [17], Ref. [21] present | **implemented_partial** |

The PRC Fig. 14 **solid** curve is the coherent sum with the full
`N*(1535)` model; the **dashed** curve uses its reduced variant. The
**dotted** curve is the isolated Fig. 11/Eq. (43) tree; the
**dash-dotted** curve is Eq. (39) followed by `eta p` rescattering. The
current `theory/` code validates only the dotted component and an
approximate tree/full cross-section ratio; it does not validate the solid
line or Ajaka Fig. 4. Figure 12 groups chiral contributions; Figure 13
groups explicit-resonance contributions. Neither group can be added as
incoherent cross sections to obtain the solid curve.

## Gate before the coherent-model plan

1. Obtain and verify PRC Ref. [8] primary source; identify all parameters,
   subtraction constants, channel ordering, and complex-amplitude phase
   conventions actually used for the 2006 full-model curve.
2. Obtain PRC Ref. [25] or prove from an equally primary source that the
   full-model `pi pi N` correction is completely specified in the supplied
   PRC paper. If not, label any calculation **reduced model**, not full.
3. Verify the adopted decuplet-state phase convention against Ref. [40]
   (not the comparison convention in Ref. [41]) before combining its terms.
4. Map each source input to a concrete parameter and regression target
   before implementing its amplitude. Preserve isolated Eq. (43) result.

This audit records source gaps, not a request to fit them away using Ajaka
points or theoretical-line digitization.
