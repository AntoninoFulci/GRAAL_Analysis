# Fix 2010 solution I: reconstruction register

Execution dated 2026-11-06. **Incomplete dynamics; no cross section or Sigma prediction.**
Baseline: arXiv:1004.5240v1, solution I, laboratory Eγ requested in [1.0,1.4] GeV.
Recovery of rho=A3/2/A1/2 from Fig.6 and public-source research are authorized. No additional dynamic approximation has been authorized. No author code is claimed. No stage-08 inputs, fits, or retired routines are used.

## Ingredient matrix (T0 / G0)

| Ingredient | Symbol / value or formula | Unit | Source/version, page/equation | Dependencies | State | Consequence |
|---|---|---|---|---|---|---|
| Six resonance inputs | First row of each group, Table II | MeV; 10^-3 GeV^-1/2; dimensionless; μb | 2010v1 p.9 Table II, visually checked | none | verified | Preserve fitted masses, signs and marginal errors |
| D33(1700) | M=1701±1, Γ=375, sqrt(beta)A=10.6±0.2, rho_R=.95±.01, r=.70±.03 | original table units | same | rho(W) below | verified | Nominal 1700 is label only |
| P33(1600) | 1657±5,350,-.10±.011,.39±.06,1.78±.32 | same | same | widths | verified | Negative production product |
| P31(1750) | 1832±1,400,8.35±.9, helicity 3/2 forbidden,.22±.11 | same | same | widths | verified | Absence of A3/2 is spin selection, not missing value |
| F35(1905) | 1873±4,330,-25.5±.6,-.70±.03,.0091±.0075 | same | same | widths | verified | Keep both signs |
| P33(1920) | 1894±3,200,11.87±.42,1.15±.06,.14±.09 | same | same | widths | verified | No nominal-mass substitution |
| D33(1940) | 1870±1,450,19.9±1.1,1.65±.02,.22±.03 | same | same | widths | verified | Fitted mass differs by 70 MeV |
| Decay angular momenta | (L_eta,L_pi)=(0,1),(1,2),(1,0),(1,2),(1,2),(0,1) | 1 | 2010v1 p.4 Table I and p.8 text | solution I | verified | D33 d wave excluded in I/II; only III contains it |
| Electromagnetic energy law | A1/2(W)=A1/2(MR) omega(W)/omega(MR) for D1700; other resonances n=0 | GeV^-1/2 | 2010v1 p.3 Eq.(5) and text | rho(Eγ) | verified | Never import 2018 exponent 3/2 |
| Ratio shape | rho, solid curve; lab energy, not rho² | 1 | 2010v1 p.8 Fig.6; fig6.ps | axis calibration | derived | Input reconstructed; not observable benchmark |
| Ratio upper support | last vertex x=1344, axis edge x=1351 | PS units | fig6.ps lines 700–779 | linear calibration | verified | Support ends 1.394805194805 GeV; 1.4 cannot be supplied without new assumption |
| Isospin | CT=2/3 in amplitude | 1 | 2010v1 p.3 Eq.(4) text | both decay routes | verified | Squared factor 4/9 only after amplitude |
| Relative signs | sign of sqrt(beta)A encodes A*f_eta; f_pi/f_eta positive for every R | 1 | 2010v1 p.9 caption | Table II | verified | Coherent interference required |
| Resonance propagator | [W-MR+i Γtot(W)/2]^-1 | GeV^-1 | 2010v1 p.3 Eq.(6) | full Γtot(W) | verified | On-shell widths alone do not fix W dependence |
| Total resonance widths | Per-channel weights and complete Γtot(W) for six solution-I states | GeV | 2010v1 Sec.II/III; 2008v1 p.10 Eq.(51), p.11 Eq.(54); 2005v1 Appendix B | separate branch fractions not given by sqrt(beta)A and r | missing | G0 blocked; 2008 example is not 2010 fit |
| Unstable isobars | Delta:1.232/.120; N*:1.535/.150, beta_eta=.45 | GeV | 2010v1 p.5 Eq.(19), Fig.3 context | continuation below nominal thresholds | verified | Values explicitly supplied for Fig.3; full implementation prescription still needs verification |
| N* branch fractions | eta=.45,pi=.45,pipi=.10 | 1 | 2008v1 p.9 Sec.III | compatibility with 2010, energy laws | ambiguous | Do not silently promote old model choices |
| Isobar widths | ΓDelta(omega), ΓN*(omega), form factors | GeV | 2010 Eqs.(16–19); 2008 Sec.III; 2005 Appendix B Eqs.(B.20–B.29) | channel masses, regulators, branch weights | ambiguous | No complete unique 2010 prescription recovered |
| Finite-width integration | integral from mN+m_pi to W-m_eta, spectral factor Γ/[(omega-M)^2+Γ²/4] omega/(2pi) | per Eq.(16) | 2010v1 p.5 Eqs.(16–18) | Γisobar(omega) | verified | No stable eta+Delta threshold closure |
| etaDelta vertex | f_RetaDelta*f_DeltaPiN G_Delta q_eta^L q_pi*/m_pi^(L+1) | source convention | 2010v1 p.4 Eq.(12), p.3 Eq.(9) | couplings / normalization | verified | Numerical normalization remains unclosed |
| piN* vertex / translation | Eq.(10),(11),(13) | source convention | 2010v1 pp.3–4, visually checked | spherical-harmonic translation identity | ambiguous | Eq.(11) as printed has (2l-1) at l=0: cannot mechanically evaluate for L>0; derive/check before implementation |
| Coupling-product conversion | sqrt(beta_eta) A fixes product only, r defined at MR | GeV^-1/2 | 2010v1 p.4, p.9 caption; 2005v1 B.25–B.29 | normalized decay integrals | ambiguous | Do not choose A and beta separately; normalize after width prescription fixed |
| Born diagrams (a–f) | electromagnetic nucleon/N*, pion vertices and relative normalization | source convention | 2010v1 Fig.1 and Sec.II; 2008v1 Sec.III; refs.[6–8] therein | double-pion formalism and eta adaptation | missing | Small contribution not permission to omit; G0/G2 blocked |
| Born dependency | Fix/Arenhövel EPJA25,115 (2005), nucl-th/0503042v1 | — | Appendix B, pp.11–14 | 2008 ref.[8] | verified | Downloaded/read; double-pion formulas do not uniquely specify 2010 eta adaptation |
| Other Born dependencies | Gomez Tejedor/Oset NPA600,413 (1996); Ochi/Hirata/Takaki PRC56,1472 (1997) | — | 2008 refs.[6–7] | double-pion vertices and widths; checked 1995v3/1997v2 | verified | References recovered and relevant sections read; they do not specify the missing eta-specific 2010 contract |
| Negative helicity / parity | A_-lambda=(-1)^(1/2+J-l) A_lambda | 1 | 2008v1 p.3 Eq.(5) | map lambda to photon/target states | verified | Must derive compatible conventions before amplitudes |
| Cross-section normalization | relation source t ↔ invariant M; initial averages and μb conversion | GeV / μb | 2011v2 Eqs.(19–22); 2005 cross-section conventions | complete amplitude vertices | ambiguous | Covariant phase space alone does not determine absolute cross section |
| Polarization formalism | density matrices and trace of T† T | 1 | 2011v2 Sec.III/V | amplitude convention | verified | 2011 Sec.V explicitly discards Born, cannot complete full baseline |
| Sigma energy averages | Fig.9 bins 1.1–1.2,1.2–1.3,1.3–1.4 | GeV | 2010v1 p.11 Fig.9 | energy weights | missing | Future exact graph comparison inconclusive until weights established |
| Stable masses | mp=.938272, mpi0=.134977, meta=.547862 | GeV | graal_common.physics.channels | shared module hash in manifest | verified | Used only for independent kinematics; no change to historical resonance masses |

## Kinematics and invariant phase space (T3 contract)

Metric (+---), four-vectors (E,px,py,pz), GeV. Beam defines +z.
Use canonical K frame: pair-rest axes parallel to CM, rotation-free boost with pair velocity -q_eta/E_pair. Choose eta in xz plane with **negative x**, so y=eta×beam as Fig.2 caption; x=y×z. Collinear endpoints use the continuous limit of this frame. No Wigner spin rotations are part of this kinematic component.

W²=mp²+2mp Eγ; omegaγ=(W²-mp²)/(2W). Pair mass m ranges [mp+mpi,W-meta]. Define q=sqrt([W²-(m+meta)²][W²-(m-meta)²])/(2W), p*=sqrt([m²-(mp+mpi)²][m²-(mp-mpi)²])/(2m).

Adopt **invariant** measure dΦ_n=(2pi)^4 δ⁴(P-sum p) product[d³p/((2pi)^3 2E)]. This is not a claim about normalization of the papers' nonrelativistic amplitude.
Factorization: dΦ3=dm²/(2pi) dΦ2(W;meta,m) dΦ2(m;mpi,mp), dΦ2=q/(16pi² W)dΩ.
After integrating the overall eta azimuth over 2pi, density in (m,cosTheta_eta,cosTheta_pi*,phi_pi*) is q p*/(128 pi^4 W), unit GeV. Integrated phase volume has unit GeV². Azimuth reduction applies to rotationally invariant integrands; do not use it for a fixed lab polarization without transforming that polarization too.
Independent check: Φ3=int dm² sqrt(lambda(W²,m²,meta²))*sqrt(lambda(m²,mpi²,mp²))/(128pi³ W² m²). For three massless particles Φ3=W²/(256pi³).

Only floating roundoff of 1e-12 GeV at mass boundaries is accepted and recorded in returned coordinates. No energy or helicity extrapolation.

## Source audit and unresolved choices

2010 archive and fig6.ps hashes match plan. Text.tex hash also recorded. Visually inspected 2010 pp.3–4 (Eqs.4–13/Table I), p.8 (Fig.6/solution description), p.9 (Table II). Read 2008 Sec.III and 2011 Sec.V; read 2005 Appendix B after public download. Preprints only; publisher equivalence not certified.
Public searches on 2026-11-06: `"Fix" "035207" erratum Born 2010`, `"Isobar model analysis" "erratum"`, `"1004.5240" width energy Born`, and the 2005 dependency title. No pertinent erratum or implementation supplement identified; this does not prove absence. Earlier APS 401 was not retried. No authors contacted.

G0 remains open. T4–T6 and predictive T7 must not run with guessed widths/Born normalization. T1 can deliver a source-faithful reader on measured support; extending it to 1.4 is a separate model assumption, not rounding reconciliation. No choice has been silently made.


## Follow-up after owner confirmed no additional references

On 6 November 2026 the owner reported having no supplementary source. This does not authorize omitting Born terms, borrowing an older model prescription, changing the requested energy interval or extrapolating rho. Public-source research already authorized by the plan continued.

Recovered the remaining two references cited in 2008 Sec.III:

- **Gómez Tejedor/Oset**, NPA600,413 (1996), `hep-ph/9506209v3` (19 October 1995). Sec.2, pp.4–5, Eqs.(4–6) discusses the **N*(1440)** propagator and its piN/piPiN width: the latter is approximated by three-body phase space, normalized to that state's decay width. Appendix A supplies double-pion Lagrangians. This is an explicit example of a width prescription, but not the six resonance widths or N*(1535) eta adaptation of Fix2010.
- **Ochi/Hirata/Takaki**, PRC56,1472 (1997), `nucl-th/9703058v2` (11 April 1997). Sec.II, p.4, Eqs.(2.1–2.2), treats **N*(1520)** through a bare mass and self-energy sum Sigma_piN+Sigma_sPiDelta+Sigma_dPiDelta+Sigma_rhoN. The later parameter discussion fits this state with a 120 MeV width and 58/10/10/22% fractions. The symbols N* and sets I/II/III in this paper refer to its own model, not Fix2010 N*(1535) or solution I. They must not be imported by label matching.

Versions confirmed from PDF front pages; selected width formulas visually checked. Both originals and hashes retained in the source manifest. Search terms included exact citations/titles and `PhysRevC.56.1472`. No authors contacted; no publisher-authenticated access attempted.

**Outcome:** the previously unexamined reference chain is now checked at its relevant vertices/width sections. It supplies alternative model constructions, not a unique eta-specific 2010 numerical contract. G0 status and all curated numerical inputs remain unchanged. No additional code/test run is needed for this documentary follow-up; the 73-test result remains the preceding implementation verification, not a new run.
