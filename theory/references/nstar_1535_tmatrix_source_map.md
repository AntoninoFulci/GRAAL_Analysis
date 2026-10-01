# N*(1535) six-channel T: primary-source map

Scope: the charge +1, strangeness-zero, s-wave meson-octet/baryon-octet amplitude used in PRC 73, 045209 (2006) for `gamma p -> pi0 eta p`. This is a source audit, not a numerical implementation. No T matrix, pole search, fit, or numerical regression test was run for this document. Equations and table entries below are transcriptions; identified implementation choices are not paper results.

## Source identities and citation keys

All paths are relative to the repository root. A citation to a key below identifies both the paper and its exact local PDF; page numbers such as `035204-13` are the printed article pages.

| Key | Primary source and local PDF | Role |
| --- | --- | --- |
| **P73** | M. Döring, E. Oset, D. Strottman, *Chiral dynamics in the gamma p -> pi0 eta p and gamma p -> pi0 K0 Sigma+ reactions*, Phys. Rev. C **73**, 045209 (2006), [PDF](../../tmp/pdfs/10.1103@PhysRevC.73.045209.pdf) | Target: channel order, charge +1 coefficients, effective pi-pi-N correction, full/reduced definitions. |
| **P65** | T. Inoue, E. Oset, M. J. Vicente Vacas, *Chiral unitary approach to S-wave meson baryon scattering in the strangeness S=0 sector*, Phys. Rev. C **65**, 035204 (2002), [PDF](../../tmp/pdfs/PhysRevC.65.035204.pdf) | P73 Ref. [8]: two-body kernel/loops and fitted pi-pi-N model. |
| **P70** | M. Döring, E. Oset, M. J. Vicente Vacas, *s-wave pion nucleon scattering lengths from pi N, pionic hydrogen, and deuteron data*, Phys. Rev. C **70**, 045203 (2004), [PDF](../../tmp/pdfs/PhysRevC.70.045203.pdf) | P73 Ref. [25]: incorporation of pi-pi-N into an effective pi-N kernel, specialized there to low energies. |
| **BSS-v1** | M. N. Butler, M. J. Savage, R. P. Springer, *Strong and Electromagnetic Decays of the Baryon Decuplet*, **hep-ph/9211247v1**, 14 Nov 1992, [PDF](../../tmp/pdfs/9211247v1.pdf) | Local preprint associated with P73 Ref. [40], which cites Nucl. Phys. B **399**, 69 (1993). Journal-final equivalence has **not** been verified. |
| **SOV-v2** | S. Sarkar, E. Oset, M. J. Vicente Vacas, *Baryonic Resonances from Baryon Decuplet-Meson Octet Interaction*, **nucl-th/0407025v2**, 4 Jan 2005, [PDF](../../tmp/pdfs/nucl-th-0407025.pdf) | Local preprint associated with P73 Ref. [21], Nucl. Phys. A **750**, 294 (2005); a separate decuplet-baryon model. The PDF also carries an internal date of October 23, 2018. |
| **PLB639** | M. Döring, E. Oset, D. Strottman, *Clues to the nature of the Delta*(1700) resonance from pion- and photon-induced reactions*, Phys. Lett. B **639**, 59-67 (2006), [PDF](../../tmp/pdfs/10.1016@j.physletb.2006.06.022.pdf) | Later production-model update; its Ref. [25] is **P73**, not P70. |

Reference numbers are local to each paper: P73 [8] = P65; P73 [25] = P70; P70 [25] = P65; PLB639 [25] = P73. Sources: each paper's reference list; P70 Sec. II explicitly describes its use of P65.

SHA-256 of the audited bytes:

```text
e8861394ef3fb86c005694d3cb82d8c2b905e39dbe384903f58392d644cff6ac  tmp/pdfs/PhysRevC.65.035204.pdf
7d07d8510fa19546e9d73824826306babc9cb0b88c06277b5d326303c713854f  tmp/pdfs/PhysRevC.70.045203.pdf
a1ad108ede40ddfa29bd8147296c2c8fe10f4a167f741b2a5aaea6b2d2ee4e29  tmp/pdfs/9211247v1.pdf
19a2fbce10ed8201a29bdfbcfb9f3690a280d943c1e83db01aa1b2057d20eccb  tmp/pdfs/10.1103@PhysRevC.73.045209.pdf
c1def91b01ee5750aca4124ae2469178b204d99649075d7d4f4277facab9d430  tmp/pdfs/10.1016@j.physletb.2006.06.022.pdf
1b67f036787bc1085d1ae0491f64e14b8970ffe4f2377607da51dc5a2fc077af  tmp/pdfs/nucl-th-0407025.pdf
```

## 1. Channel basis and charge coefficients

The **one-based** ordering is fixed by P73 Sec. II, Eq. (1), p. 045209-2:

| Index | State | Subtraction family | Decay constant |
| --- | --- | --- | --- |
| 1 | pi0 p | pi N | f_pi |
| 2 | pi+ n | pi N | f_pi |
| 3 | eta p | eta N | f_eta |
| 4 | K+ Sigma0 | K Sigma | f_K |
| 5 | K+ Lambda | K Lambda | f_K |
| 6 | K0 Sigma+ | K Sigma | f_K |

Family sharing of subtraction constants is specified in P65 Sec. II A, following Eq. (8); decay constants are specified following P65 Eq. (5). P73 uses `T^(i3)` for the transition from channel i to eta p (Sec. III, below Eq. (8)); the K0 Sigma+ final state uses `T^(i6)` (Sec. V C, p. 045209-15).

The following **symmetric** charge +1 matrix is P73 Table I, visually checked against p. 045209-2. It should be taken from that table rather than obtained by relabeling the charge-zero table of P65:

\[
C=\begin{pmatrix}
0&\sqrt2&0&-\tfrac12&-\tfrac{\sqrt3}{2}&\tfrac1{\sqrt2}\\
\sqrt2&1&0&\tfrac1{\sqrt2}&-\sqrt{\tfrac32}&0\\
0&0&0&-\tfrac{\sqrt3}{2}&-\tfrac32&-\sqrt{\tfrac32}\\
-\tfrac12&\tfrac1{\sqrt2}&-\tfrac{\sqrt3}{2}&0&0&\sqrt2\\
-\tfrac{\sqrt3}{2}&-\sqrt{\tfrac32}&-\tfrac32&0&0&0\\
\tfrac1{\sqrt2}&0&-\sqrt{\tfrac32}&\sqrt2&0&1
\end{pmatrix}.
\]

P73 derives C from its octet chiral Lagrangian, Eqs. (2)-(4), and explicitly adopts the isospin classification/conventions of P65 for its Eq. (6). P65 Sec. III B, immediately after Eq. (24), fixes `|pi+> = -|I=1, Iz=1>`. Its `v_11` and `v_31` mean total isospin 1/2 and 3/2, respectively, with two-pion isospin 1; these are **potentials**, whereas `a_11`, `a_31` denote amplitudes after unitarization (P65 Sec. III A, Eq. (14), and Sec. III B, after Eq. (24)). A complete octet charge-to-isospin transformation matrix is not printed in these cited passages; no additional transformation is supplied here.

## 2. Two-body V, G, T and normalization

Write `W = sqrt(s)`. P73 Eq. (4) gives the covariant Weinberg-Tomozawa kernel; its s-wave reduction is P65 Eq. (5):

\[
V_{ij}(W)=-\frac{C_{ij}}{4f_i f_j}(2W-M_i-M_j)
\sqrt{\frac{M_i+E_i(W)}{2M_i}}
\sqrt{\frac{M_j+E_j(W)}{2M_j}}.
\]

The paper defines `E_i` as the on-shell baryon energy. P65, text after Eq. (5), explicitly uses

\[
f_\pi=93\ {\rm MeV},\qquad f_K=1.22f_\pi,\qquad f_\eta=1.3f_\pi.
\]

The diagonal meson-baryon loop includes the **2M_i numerator**, P65 Eq. (4):

\[
G_i(P)=i\int\frac{d^4q}{(2\pi)^4}
\frac{2M_i}{(P-q)^2-M_i^2+i\epsilon}
\frac1{q^2-m_i^2+i\epsilon}.
\]

Its dimensional-regularization expression is P65 Eq. (6), with `Q_i` the on-shell c.m. momentum and `Delta_i=M_i^2-m_i^2` used here only as an abbreviation:

\[
\begin{aligned}
G_i(W)=\frac{2M_i}{(4\pi)^2}\Bigg\{&a_i(\mu)+\log\frac{m_i^2}{\mu^2}
+\frac{M_i^2-m_i^2+s}{2s}\log\frac{M_i^2}{m_i^2}\\
+\frac{Q_i}{W}\Big[&\log(s-\Delta_i+2WQ_i)+\log(s+\Delta_i+2WQ_i)\\
&-\log(-s+\Delta_i+2WQ_i)-\log(-s-\Delta_i+2WQ_i)\Big]\Bigg\}.
\end{aligned}
\]

The physical-sheet prescription must reproduce

\[
\operatorname{Im}G_i(W)=-\frac{M_iQ_i(W)}{4\pi W}
\]

above the channel threshold (P65 Eq. (7)). P73 Eq. (5) specifies

\[
T(W)=[1-V(W)G(W)]^{-1}V(W),
\]

equivalent, where the inverses exist, to P65 Eq. (3), `T^{-1}=V^{-1}-G`. P65 Eq. (10) compares the dimensionless partial-wave quantity

\[
-\sqrt{\frac{M_iQ_i}{4\pi W}}\sqrt{\frac{M_jQ_j}{4\pi W}}\,T_{ij}(W)
\]

with the partial-wave analysis. P73 Fig. 15 labels the unrescaled `|T^(i3)|` and `|T^(i1)|` in **MeV^-1**. Thus the plotted strong T and a dimensionless S11 partial-wave amplitude must not be equated numerically. P65 Eq. (8) is the two-body unitarity relation in this normalization; after eliminating pi-pi-N into an absorptive V, a check of the six-channel submatrix must account for that extra channel rather than imposing a closed six-channel two-body relation.

## 3. Full versus reduced: separate parameter sets

P73 Sec. II, p. 045209-3 and Fig. 1, defines **reduced** as P65 *before both t-channel vector exchange and pi N -> pi pi N are introduced*. Full/reduced differences are used there as a model uncertainty estimate. Turning off only the pi-pi-N correction does not implement that definition.

The two explicitly printed P65 fits are:

| Source/model stage | mu [MeV] | a_piN | a_etaN | a_KLambda | a_KSigma |
| --- | ---: | ---: | ---: | ---: | ---: |
| Basic two-body, Sec. II A, Eq. (9) | 1200 | 2.0 | 0.2 | 1.6 | -2.8 |
| Final model with VMD and pi-pi-N, Sec. III C, Eq. (28) | 1200 | 2.0 | 0.1 | 1.5 | -2.8 |

These correspond to the source stages identified by P73's reduced/full description. P73 does **not** reprint the numerical subtraction sets. P65 Sec. II B says that the intermediate VMD-only calculation retunes the subtraction constants but does not print a separate numerical set there. Do not silently reuse the full fit as a documented VMD-only fit.

### 3a. Vector-exchange correction

P65 Sec. II B, Eqs. (12)-(13), replaces C by

\[
\widetilde C_{ij}=C_{ij}\int\frac{d\widehat k'}{4\pi}
\frac{-m_v^2}{(k'-k)^2-m_v^2},\qquad W>W^0_{ij},
\]

where `W^0_ij` is defined as the energy at which the integral equals one, lying between the two channel thresholds. Below that switching energy the replacement is not applied. The printed example for pi- p -> pi- p is

\[
\frac{m_\rho^2}{4kk'}
\log\frac{m_\rho^2+2k^0k'^0+2kk'-m_\pi^2-m_\pi^2}
{m_\rho^2+2k^0k'^0-2kk'-m_\pi^2-m_\pi^2}.
\]

P65 explicitly gives `m_rho = 770 MeV`, and uses `m_K* = 892 MeV` for strangeness exchange, with pi- p -> K0 Lambda as its example (Sec. II B, p. 035204-5; Fig. 5). The text reports a reduction of about 25% for the pi-N example around W=1500 MeV. The integral is specified, but an exhaustive six-by-six vector-species assignment, numerical switching energies, and a prescription for all subthreshold/complex-energy branches are **not** tabulated there. They must be documented as implementation choices or resolved with further evidence; this map does not invent them.

### 3b. Effective pi-pi-N correction in charge +1

For compact transcription of P73 Eq. (6), define

\[
A=-\frac{\sqrt2}{3}v_{31}-\frac1{3\sqrt2}v_{11},\qquad
B=\frac{v_{31}-v_{11}}3,\qquad
D=-\frac1{3\sqrt2}v_{31}-\frac{\sqrt2}{3}v_{11}.
\]

Then add only in the pion-nucleon block of the kernel:

\[
\delta V_{11}=(A^2+B^2)G_{\pi\pi N},\quad
\delta V_{12}=\delta V_{21}=(AB+BD)G_{\pi\pi N},\quad
\delta V_{22}=(B^2+D^2)G_{\pi\pi N}.
\]

These are ordinary products/squares, as printed, not absolute squares. This is P73's six-channel representation. P65 instead introduces an eight-channel charge-zero system with pi0 pi- p and pi+ pi- n; it omits direct couplings of `{K Sigma, K Lambda, eta n, pi pi N}` to pi-pi-N and excludes pi0 pi0 n because it does not couple to the s-wave pi-N state (Sec. III introduction and Sec. III B). Do not add an explicit pi-pi-N channel on top of P73 Eq. (6) and count the same process twice.

The required energy-dependent potentials **are printed**, in P65 Sec. III C, Eqs. (29)-(30), p. 035204-11. With `x=(W-1470 MeV)/m_pi`,

\[
v_{11}(W)=\left[4.0+1.0\frac{W-1213\ {\rm MeV}}{m_\pi}\right]m_\pi^{-3},
\]

\[
v_{31}(W)=\left[-5.60x-1.05x^2+1.77x^3+0.66x^4-0.17x^5-0.07x^6\right]m_\pi^{-3}.
\]

The loop is `G_pi pi N = G_tilde`, including the relative **three-momentum squared** already in its definition (P65 Eqs. (25)-(27); P73 text below Eq. (6)):

\[
\widetilde G(P)=i^2\!\int\!\frac{d^4q_1d^4q_2}{(2\pi)^8}
(\mathbf q_1-\mathbf q_2)^2
\frac{2M_N}{(P-q_1-q_2)^2-M_N^2+i\epsilon}
\frac1{q_1^2-m_\pi^2+i\epsilon}\frac1{q_2^2-m_\pi^2+i\epsilon},
\]

\[
\operatorname{Im}\widetilde G(W)=-\frac{M_N}{4(2\pi)^3}
\int d\omega_1d\omega_2\,
\left[M_N^2+2q_1^2+2q_2^2-(W-\omega_1-\omega_2)^2\right]
\theta(1-\mathcal A^2),
\]

\[
\mathcal A=\frac{(W-\omega_1-\omega_2)^2-M_N^2-q_1^2-q_2^2}{2q_1q_2},
\qquad q_i=\sqrt{\omega_i^2-m_\pi^2}.
\]

P65 Sec. III C, p. 035204-10, explicitly adopts `Re G_tilde(W)=0` in the final fit. Fig. 11 labels `Im G_tilde` in `10^8 MeV^5`. Eq. (26) does not print explicit integration bounds: an implementation must use the physical positive-energy three-body phase-space domain, not integrate arbitrary omega values merely because the angular theta function is satisfied. The exact charge/average choice for `m_pi` and `M_N` in this common loop is not numerically itemized in that section.

P73 Sec. II reports that including pi-pi-N changes the N*(1535) position by about **10 MeV** and increases its width by about **10%**; these are paper estimates, not changes measured in this repository.

## 4. Why the unexpectedly titled Ref. [25] is relevant

P73's citation to P70 is legitimate but narrowly scoped: P70 Sec. II B, Eq. (8), folds a pi-pi-N propagator and its two adjacent vertices into `delta V`, directly added to the Bethe-Salpeter kernel. That is the method used in P73 Eq. (6), after changing to charge +1. P70's title, *s-wave pion nucleon scattering lengths from pi N, pionic hydrogen, and deuteron data*, does not describe a new resonance-region six-channel N*(1535) parameterization.

P70 explicitly restricts its practical coupled-channel model to pi- p/pi0 n and the separate pi+ p sector near threshold through approximately 1250 MeV (Sec. II, p. 045203-2). In Sec. II B it uses low-energy constants `a_11=2.6 m_pi^-3`, `a_31=5.0 m_pi^-3`, and a constant real-loop parameter **gamma**, observing that the imaginary part is small at its energies. It also adds isoscalar terms and studies damping of their quadratic energy dependence (Sec. II A, Eqs. (6)-(7)). Those numbers and additional low-energy fit terms are **not** substitutions for P65 Eqs. (28)-(30), `Re G_tilde=0`, and P73's energy-dependent loop. P73 explicitly refers back to P65 for the analytic `v_11`, `v_31` functions. [P70 Secs. II A-B; P73 Sec. II, Eq. (6).]

## 5. Ref. [40] and the separate Delta*(1700) inputs

P73 invokes Ref. [40] in **Sec. IV D, Eq. (38)** for the decuplet-baryon/octet-baryon/meson vertex `L=C(bar T^mu A_mu B + bar B A_mu T^mu)` and the corresponding Kroll-Ruderman term. It says its decuplet phase convention is the same as that reference and Ref. [21]. This is a production-vertex dependency, **not** the source of the six-channel octet C matrix or N*(1535) subtraction constants. [P73 p. 045209-10.]

The available BSS-v1 provides the meson matrix in Eq. (2.3), octet-baryon matrix in Eq. (2.9), interaction in Eq. (2.10), and positive tensor-state identifications in Eq. (2.11), including `T^111=Delta++`, `T^112=Delta+/sqrt(3)`, `T^122=Delta0/sqrt(3)`, `T^113=Sigma*+/sqrt(3)`, `T^123=Sigma*0/sqrt(6)`. Its convention has `f_pi approximately 135 MeV` (Sec. 2, p. 3); this must not overwrite P65's explicitly different `f_pi=93 MeV` normalization. BSS-v1 Sec. 3 says the sign of its C cannot be extracted from its decay rates. The local file establishes these **preprint** conventions, not identity with the unavailable journal-final text.

For the adjacent Delta* model, P73 Sec. IV D quotes `g_eta=1.7-i1.4`, `g_K=3.3+i0.7`, `g_Delta=0.5+i0.8`, up to a common sign. These agree with SOV-v2 Sec. 4.3, Table 10, for the pole `1827-i108 MeV` identified there with Delta(1700). SOV-v2 uses `mu=q_max=700 MeV`, `a=-2` in its **decuplet** scattering model (Sec. 2, following Eqs. (16)-(18)); these are not the octet N*(1535) loop parameters. Its Appendix II explicitly gives `|pi+>=-|1,1>` and `|K->=-|1/2,-1/2>`. [P73 p. 045209-10; SOV-v2 pp. 8, 15 and Appendix II.]

PLB639 is a later reaction-level update. Its Sec. 4, Fig. 5 and pp. 65-66 retain the full model of its Ref. [25] (=P73) for the eta pi0 p and K0 pi0 Sigma+ channels and describe about a **30% reduction** in their cross sections from a more realistic, larger Delta(1700) width and a small d-wave rho-N fraction. That is not evidence for a new N*(1535) subtraction fit. Its Sec. 3, Eqs. (13)-(19), and P73 Sec. IV D concern production vertices separately from the six-channel rescattering T.

## 6. Published regression targets, not tests already passed

| Target | Printed result / evidence | Appropriate use and limitation |
| --- | --- | --- |
| Two-body imaginary loop | `Im G_i=-M_i Q_i/(4 pi W)`; P65 Eq. (7) | Real-axis normalization/branch check before dressing with pi-pi-N. |
| Full charge +1 T curves | P73 Fig. 15: `|T^(i3)|` and `|T^(i1)|`, in MeV^-1, W=1400-1700 MeV | Direct target for the desired basis. Curves, not tabulated numerical samples; none digitized here. Line-to-channel mapping is in the caption. |
| Full/reduced S11 comparison | P73 Fig. 1: real and imaginary pi N -> eta N partial wave, W=1500-1640 MeV; full solid, reduced dashed | Tests shape and normalization after the required isospin/partial-wave conversion. No numerical array is printed. |
| Full charge-zero scattering lengths | P65 Table II: pi0 n `-0.023`; pi- p `0.080+i0.003`; eta n `0.264+i0.245`; K0 Lambda `-0.148+i0.165`; K0 Sigma0 `-0.205+i0.068`; K+ Sigma- `-0.284+i0.090`, all fm | Regression for the P65 charge-zero reference, not literal charge +1 values when physical masses split multiplets. P65 p. 035204-12 cautions that strange-channel thresholds are outside the best-described region. |
| Isospin pi-N lengths | `a_3=-0.0875 m_pi^-1`, `a_1=0.1272 m_pi^-1`; P65 p. 035204-13 | Paper predictions; distinct from the experimental numbers alongside them. |
| N*(1535) pole | `P_R^0=1543-i46 MeV`; P65 Eq. (34), Fig. 19 | **Second-sheet** target requiring analytic continuation, not a direct test of a real-axis peak or a charge +1 calculation with unspecified masses. |
| Pole-residue coupling magnitudes | P65 Table III upper block: `|g|=(2.12,1.50,0.92,0.56,0.39,1.84)` in the table order `(K+ Sigma-, K0 Sigma0, K0 Lambda, pi- p, pi0 n, eta n)` | Charge-zero pole residues; no phases can be recovered from these magnitudes alone. |
| Partial widths | P65 Table III upper block: pi- p `14.1`, pi0 n `7.0`, eta n `65.7`, pi0 pi- p `4.6`, pi+ pi- n `2.4` MeV; Eq. (37) | Requires pole residues and open-channel phase space. Not fit parameters for a Breit-Wigner replacement of T. |
| Two-body shapes and pi-pi-N amplitude | P65 Figs. 2-3 (basic), 6-7 (VMD-only), 11-14 (pi-pi-N/full), 17 (pi- p -> eta n cross section) | Figure comparisons only unless explicitly digitized. P65 describes good pi- p -> eta n agreement up to about 1550 MeV; P73 Sec. II notes the model is too narrow at higher energies. |

P65 Table III's **lower** block gives real signed couplings from a Breit-Wigner-plus-background fit over 1450-1650 MeV, Eq. (38), with signs relative to `g_eta n`; these are a different extraction from the upper pole-residue magnitudes and are not a replacement for the energy-dependent T. P65 Eq. (34) and the accompanying text describe a width about 93 MeV, whereas its Sec. V conclusion says “about 80 MeV”; retain this textual discrepancy rather than treating all quoted widths as interchangeable exact targets.

For the pole calculation, P65 Sec. IV, Eq. (32), specifies a sheet continuation of each G across an open-channel cut and Eq. (33) prints

\[
\operatorname{Im}\widetilde G(W)=-0.638y+1.124y^2-0.882y^3,
\qquad y=(W-1213\ {\rm MeV})/m_\pi.
\]

**Unresolved normalization:** Eq. (33) prints no overall unit for these polynomial coefficients, while Fig. 11 uses `10^8 MeV^5`. No missing scale has been inferred or fitted here. For real-axis work, Eqs. (25)-(27) provide the dimensionful loop definition. The polynomial is introduced specifically to enable continuation above the pi-pi-N threshold; it is not an explicitly documented replacement for the physical phase-space integral at all energies. [P65 p. 035204-13; Fig. 11 visually checked on p. 035204-8.]

## 7. Implementation dependency order and remaining gaps

1. Freeze P73's channel order, Table I, and phase convention; record an explicit mass dataset and units. The inspected N*(1535) sections do not provide a complete numerical table of charged meson and octet-baryon masses or a fully specified common pi-pi-N mass choice. [P73 Sec. II; P65 Secs. II-III.]
2. Implement the basic WT kernel and diagonal dimensional-regularization G with the P65 Eq. (9) fit; verify Eq. (7), units, thresholds and the partial-wave rescaling of Eq. (10). This is the source-defined reduced starting point. [P65 Eqs. (5)-(10); P73 Fig. 1.]
3. Resolve/document all vector-exchange assignments and branch/switching prescriptions, then implement P65 Eqs. (12)-(13). Keep its intermediate VMD-only stage distinct from a documented fit, since a numerical VMD-only subtraction set is not printed. [P65 Sec. II B.]
4. Implement `v_11`, `v_31` and the physical pi-pi-N loop; add P73 Eq. (6) once, use `Re G_tilde=0`, and switch to the full subtraction set, P65 Eq. (28). Check dimensions and compare the real-axis charge +1 curves of P73 Fig. 15. [P65 Eqs. (25)-(30); P73 Eqs. (5)-(6).]
5. Only after the strong amplitude is checked, connect `T^(i3)` to the production loops. The **1400 MeV cutoff** in P73 Sec. III, Eq. (8), and Sec. IV, Eq. (26), belongs to those production-loop integrals; it does not replace `mu=1200 MeV` in the strong dimensional-regularization loop. Decuplet phase/coupling inputs from Sec. IV D remain a separate dependency. [P73 pp. 045209-4, 045209-9 to 045209-11.]
6. Treat a pole/residue check as a later, separate task requiring documented complex-energy prescriptions, the Eq. (33) unit issue to be resolved, and a charge-zero reference if comparing literally to P65 Tables II-III. No such calculation has been performed in this audit. [P65 Sec. IV.]

Audit checks actually completed: source SHA-256 hashes; text inspection of the cited primary-source sections; visual checks of P73 Table I/Eq. (6)/Fig. 15 and P65 Eqs. (25)-(27), Eq. (33), Table II and Fig. 11. No absent numerical input was derived from a plotted peak or fitted to a benchmark.
