# Mass-input audit for the reduced N*(1535) two-body model

Scope: the dashed `pi N -> eta N` S11 curve in Döring, Oset and Strottman, *Phys. Rev. C* **73**, 045209 (2006), Fig. 1, printed p. 045209-3 (**P73**). Its caption and Sec. II define the reduced curve as the Inoue, Oset and Vicente Vacas, *Phys. Rev. C* **65**, 035204 (2002) (**P65**) model before both t-channel vector exchange and the `pi pi N` channel. The relevant fit is therefore P65 Sec. II A, Eq. (9), printed p. 035204-3: `mu=1200 MeV`, `(a_piN,a_etaN,a_KLambda,a_KSigma)=(2.0,0.2,1.6,-2.8)`. These are printed inputs, not values inferred from Fig. 1.

## What the papers fix, and what they do not

| Finding | Evidence and status |
| --- | --- |
| The six **charge +1** states are `pi0 p, pi+ n, eta p, K+ Sigma0, K+ Lambda, K0 Sigma+`; their symmetric `C_ij` is printed. | **Explicit:** P73 Sec. II, Eq. (1) and Table I, p. 045209-2. P65 instead treats six charge-zero states, Sec. II A, p. 035204-2. |
| P65 uses masses `m_i,M_i` in its on-shell kernel and loop; it prints `f_pi=93 MeV`, `f_K=1.22 f_pi`, `f_eta=1.3 f_pi`. | **Explicit:** P65 Eqs. (4)-(6) and text after Eq. (5), p. 035204-2. Neither paper prints a ten-species numerical mass table for the P73 charge +1 calculation. |
| P65's reported charge-zero `K0 Lambda`, `K0 Sigma0`, `K+ Sigma-` thresholds are **1613, 1690, 1691 MeV**, respectively. | **Explicit:** P65 text below Fig. 16, p. 035204-12, in the later/full-model discussion. Distinct 1690/1691 thresholds **rule out a uniformly isospin-averaged kaon/Sigma mass assignment** there. They constrain sums only, at integer-MeV precision; P65 does not separately tabulate the basic-model masses. |
| Subtractions are shared *within* each isospin multiplet. | **Explicit:** P65 text before Eq. (9), p. 035204-3. Its wording is conditional: “for the case in which the masses of the particles in the same multiplet are equal.” Sharing `a_i` is therefore **not** a declaration that the calculation used equal masses. |
| P73 supplies neither the numerical charge +1 masses nor tabulated dashed-curve values, nor a statement that every P65 mass choice was reused unchanged. | **Source-coverage finding:** P73 Sec. II, pp. 045209-2–3, points to P65 for the s-wave projection and `G`; Fig. 1 is graphical. P65 Sec. II A likewise gives mass symbols and fit constants, not a numerical mass list. |
| Whether P73 Fig. 1 was recomputed in its charge +1 basis or reproduced from P65's charge-zero calculation is unstated. | **Source-coverage finding:** P73 Sec. II introduces its charge +1 basis on p. 045209-2 but calls Fig. 1 the “model from Ref. [8]” on p. 045209-3; the caption identifies full/reduced stages, not the charge basis used to draw them. |

Thus P65 gives strong evidence for charge-dependent **strange-channel thresholds** in its later calculation; carrying that assignment into its basic stage or P73 Fig. 1 is an **inference**. The exact charged/neutral pion, nucleon, eta, kaon and hyperon inputs behind P73 Fig. 1 remain unidentified. The ten PDG 2024 values in [`nstar1535_reduced_parameters.json`](nstar1535_reduced_parameters.json) are a documented modern choice, **not** a claimed transcription of the 2002/2006 runs. Rounded threshold sums and a digitized line cannot supply missing individual masses or establish their precision.

## Normalization and phase checks before interpreting a residual

P65 Eq. (5), p. 035204-2, includes the baryon spinor factors `sqrt((M_i+E_i)/(2M_i))` in `V_ij`; Eq. (4) has a `2M_i` loop numerator. P65 Eqs. (7) and (10), p. 035204-3, fix `Im G_i=-M_i Q_i/(4 pi W)` and compare a **dimensionless** partial wave `-sqrt(rho_i rho_j) T_ij`, where `rho_i=M_i Q_i/(4 pi W)`, with the partial-wave analysis. P73 Eq. (5), p. 045209-2, uses the unitarized strong `T`, whereas its Fig. 1 labels `Re S11`/`Im S11`; comparing unscaled `T` to that plot would change both units and shape. Applying P65 Eq. (10) to the off-diagonal `pi N -> eta N` element is the natural extension, but P73 does not separately write an explicit Fig. 1 projection formula.

P65 Sec. III B, after Eq. (24), p. 035204-8, explicitly sets the charged-pion state `|pi+> = -|I=1,I_z=1>`; P73 Eq. (6), p. 045209-2, says it follows P65's isospin conventions. P73 Table I's `pi0 p, pi+ n` block has an `I=1/2` eigenvector proportional to `(1,sqrt(2))` in that **physical charge basis**. The overall sign of this eigenvector and the relative phase chosen for the `eta N` state affect a signed transition amplitude. The papers do not print a complete charge-to-isospin projection for Fig. 1, so a sign convention must be fixed and documented when comparing its real and imaginary curves; a magnitude-only check would miss this issue. P65's `pi+` convention applies even though the reduced model omits the `pi pi N` dynamics where P65 spells it out.

## Next bounded experiment

Keep P65 Eq. (9), P73 Table I, and the current signed Eq. (10) projection fixed. In the current [`nstar1535_reduced.py`](../src/graal_theory/amplitudes/nstar1535_reduced.py) workflow, compare the existing PDG 2024 charge-specific masses with a **clearly labeled diagnostic** isospin-averaged variant derived from the same PDG inputs; report each channel threshold and the Re/Im residuals on the already frozen Fig. 1 grid in [`p73_fig1_reduced_comparison.md`](p73_fig1_reduced_comparison.md). This isolates sensitivity to mass splitting without fitting to the curve or presenting the averaged set as the authors' inputs. If an era-appropriate primary mass table or authors' numerical inputs become available, add that independently sourced scenario with its exact provenance. A remaining mismatch cannot be assigned to masses alone until the signed projection and normalization are checked separately.

## PDF provenance and visual checks

The printed equations/tables and Fig. 1 were checked on rendered pages, alongside text extraction: P65 PDF pp. 2, 3, 8, 12 (printed 035204-2, -3, -8, -12); P73 PDF pp. 2, 3 (printed 045209-2, -3). SHA-256 of the exact local PDFs:

```text
e8861394ef3fb86c005694d3cb82d8c2b905e39dbe384903f58392d644cff6ac  tmp/pdfs/PhysRevC.65.035204.pdf
19a2fbce10ed8201a29bdfbcfb9f3690a280d943c1e83db01aa1b2057d20eccb  tmp/pdfs/10.1103@PhysRevC.73.045209.pdf
```

**Unresolved reproduction inputs:** the ten exact mass values (and their historical source), whether the basic P65 stage reused the later charge-split masses, which charge basis generated P73 Fig. 1, and the complete signed Fig. 1 isospin projection. The sources support a sensitivity test, but not an exact numerical reproduction claim or a mass-only explanation of the current residual.
