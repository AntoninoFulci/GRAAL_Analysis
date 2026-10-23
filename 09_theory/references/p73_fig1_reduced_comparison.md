# PRC 73 Fig. 1 reduced S11 comparison

Status: the charge-`+1` result is **discrepant**, while the charge-zero
result is within the fixed reading bound at all eight energies. This is a
comparison of the **dashed reduced** curve only, not the full solid curve,
experimental dots, P73 Fig. 15, or an Ajaka Figure 4 calculation. No input
was fitted to the traced points. The charge-zero result does not establish
which basis P73 used or reproduce the authors' unprinted inputs.

## Definition and provenance

The calculated quantity is the dimensionless `pi N(I=1/2) -> eta N` S11
partial wave. For charge `+1`, the isospin vector is
`(-1/sqrt(3), -sqrt(2/3))` in `(pi0 p, pi+ n)` order: standard
Condon-Shortley coefficients in the `(pi0 p, |1,+1> n)` basis are
`(-1/sqrt(3), +sqrt(2/3))`, and P65 Sec. III B fixes
`|pi+> = -|1,+1>`. The P73 Table I pion block gives this vector
eigenvalue 2. For charge zero, P65 Table I order is `(K+ Sigma-, K0 Sigma0,
K0 Lambda, pi- p, pi0 n, eta n)`. The `pi N` vector in its last three
entries is `(-sqrt(2/3), +1/sqrt(3), 0)`: P65's `|pi+> = -|1,+1>` and
Condon-Shortley lowering give the two pion coefficients. The P65 pion
block also gives this vector eigenvalue 2. We take `eta n` with a
**positive relative phase**; no phase or sign was selected from Fig. 1.
The signed comparison remains **convention-blocked** insofar as the
available papers do not fix that relative phase independently. Each
transition is rescaled by P65 Eq. (10),
`S_ij = -sqrt(rho_i rho_j) T_ij`, with `rho_i=M_i q_i/(4 pi W)`.
The strong `T` has `GeV^-1` units; `S11` is dimensionless.

The reference values in [p73_fig1_reduced.csv](p73_fig1_reduced.csv) were
fixed before model values were inspected. They come from P73 PDF page 3,
printed 045209-3, Fig. 1 dashed vector strokes. Poppler SVG path styles
separate dashed strokes from solid strokes and experimental dots; a
400-dpi PNG was checked visually. Both axis calibrations, PDF/CSV checksums,
and reading method are in [p73_fig1_reduced.json](p73_fig1_reduced.json).
Each component has conservative absolute reading bound `+/-0.020`.

Reproduction command, from `theory/`:

```bash
PYTHONPATH=src python -c 'from pathlib import Path; from graal_theory.amplitudes.nstar1535_reduced import load_reduced_parameters; from graal_theory.amplitudes.nstar1535_charge_zero import load_charge_zero_parameters; from graal_theory.reduced_t_reference import load_fig1_reduced, compare_fig1_reduced, compare_fig1_charge_zero; r=Path("references"); p=load_reduced_parameters(r/"nstar1535_reduced_parameters.json",r/"sources.json"); z=load_charge_zero_parameters(r/"nstar1535_reduced_parameters.json",r/"sources.json",r/"nstar1535_charge_zero_extra.json"); pts=load_fig1_reduced(r/"p73_fig1_reduced.csv",r/"p73_fig1_reduced.json",Path("../tmp/pdfs/10.1103@PhysRevC.73.045209.pdf")); print("+1 thresholds",[round(m+b,9) for m,b in zip(p.meson_masses_gev,p.baryon_masses_gev)]); print("0 thresholds",[round(m+b,9) for m,b in zip(z.meson_masses_gev,z.baryon_masses_gev)]); [print(name,row) for name,rows in (("+1",compare_fig1_reduced(p,pts)),("0",compare_fig1_charge_zero(z,pts))) for row in rows]'
```

The explicit PDG 2024 mass policy gives these physical thresholds, in the
array order used by each calculation:

| Basis | Channel thresholds (GeV) |
| :--- | :--- |
| charge `+1` | `pi0 p` 1.073248888; `pi+ n` 1.079135811; `eta p` 1.486134088; `K+ Sigma0` 1.686319000; `K+ Lambda` 1.609360000; `K0 Sigma+` 1.686981000 |
| charge zero | `K+ Sigma-` 1.691126000; `K0 Sigma0` 1.690253000; `K0 Lambda` 1.613294000; `pi- p` 1.077842478; `pi0 n` 1.074542221; `eta n` 1.487427421 |

## Model-minus-reference residuals

All amplitudes and residuals below are dimensionless. `*` marks a component
whose absolute residual exceeds the fixed `0.020` reading bound.

### Charge `+1`

| W (GeV) | Re model | Re dashed | Delta Re | Im model | Im dashed | Delta Im |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1.50 | +0.208471 | +0.206 | +0.002471 | +0.240613 | +0.214 | +0.026613* |
| 1.52 | +0.137448 | +0.174 | -0.036552* | +0.422725 | +0.390 | +0.032725* |
| 1.54 | -0.089910 | -0.034 | -0.055910* | +0.432547 | +0.454 | -0.021453* |
| 1.56 | -0.190358 | -0.178 | -0.012358 | +0.266178 | +0.308 | -0.041822* |
| 1.58 | -0.167721 | -0.174 | +0.006279 | +0.141592 | +0.166 | -0.024408* |
| 1.60 | -0.127123 | -0.134 | +0.006877 | +0.076878 | +0.089 | -0.012122 |
| 1.62 | -0.098988 | -0.103 | +0.004012 | +0.037450 | +0.045 | -0.007550 |
| 1.64 | -0.081630 | -0.084 | +0.002370 | +0.006662 | +0.014 | -0.007338 |

The maximum absolute real residual is `0.055910459470373375` at 1.54 GeV;
the maximum absolute imaginary residual is `0.041821602205580455` at 1.56
GeV. Of eight values per component, 2 real and 5 imaginary residuals exceed
the fixed `0.020` bound.

### Charge zero

| W (GeV) | Re model | Re dashed | Delta Re | Im model | Im dashed | Delta Im |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1.50 | +0.205272 | +0.206 | -0.000728 | +0.212114 | +0.214 | -0.001886 |
| 1.52 | +0.174160 | +0.174 | +0.000160 | +0.389523 | +0.390 | -0.000477 |
| 1.54 | -0.034285 | -0.034 | -0.000285 | +0.454712 | +0.454 | +0.000712 |
| 1.56 | -0.178704 | -0.178 | -0.000704 | +0.307816 | +0.308 | -0.000184 |
| 1.58 | -0.174523 | -0.174 | -0.000523 | +0.166182 | +0.166 | +0.000182 |
| 1.60 | -0.134291 | -0.134 | -0.000291 | +0.089316 | +0.089 | +0.000316 |
| 1.62 | -0.103397 | -0.103 | -0.000397 | +0.045365 | +0.045 | +0.000365 |
| 1.64 | -0.084447 | -0.084 | -0.000447 | +0.013496 | +0.014 | -0.000504 |

The maximum absolute real residual is `0.0007281269890551667` at 1.50 GeV;
the maximum absolute imaginary residual is `0.0018859484953983874` at 1.50
GeV. Zero real and zero imaginary residuals exceed `0.020`.

The charge-zero calculation closely follows the frozen trace under the stated
phase and mass policy. This is evidence relevant to the charge-basis
hypothesis, not proof that P73 Fig. 1 used charge zero. P73 does not specify
that basis for Fig. 1, and P65/P73 do not print a complete historical mass
table. The physical-sheet loop sign, six-channel unitarity, kernel symmetry,
and linear equation are independently tested. No VMD or `pi pi N` corrections
are present in this reduced calculation. The next bounded decision is to
resolve any remaining source or convention gap, then specify the full strong
corrections separately. A later native-bin fit needs measured covariance and
must separate physics parameters from luminosity, beam polarization, acceptance,
and other experimental nuisances.

SHA-256 of exact inputs:

```text
e8861394ef3fb86c005694d3cb82d8c2b905e39dbe384903f58392d644cff6ac  tmp/pdfs/PhysRevC.65.035204.pdf
19a2fbce10ed8201a29bdfbcfb9f3690a280d943c1e83db01aa1b2057d20eccb  tmp/pdfs/10.1103@PhysRevC.73.045209.pdf
8e0a34e9f7b8e490f3987bf71755106210ec48e02c6b68a751095c7cec253358  theory/references/nstar1535_reduced_parameters.json
1848ed42bd8ab7bd00f8f9b0e4d057249b7a199b8dfb88db6bc64d3e13a47962  theory/references/p73_fig1_reduced.csv
```
