# PRC 73 Fig. 1 reduced S11 comparison

Status: **discrepant** for the frozen PDG 2024 mass input set. This is a
comparison of the **dashed reduced** curve only, not the full solid curve,
experimental dots, P73 Fig. 15, or an Ajaka Figure 4 calculation. No input
was fitted to the traced points.

## Definition and provenance

The calculated quantity is the dimensionless `pi N(I=1/2) -> eta N` S11
partial wave. The charge-basis isospin vector is
`(-1/sqrt(3), -sqrt(2/3))` in `(pi0 p, pi+ n)` order: standard
Condon-Shortley coefficients in the `(pi0 p, |1,+1> n)` basis are
`(-1/sqrt(3), +sqrt(2/3))`, and P65 Sec. III B fixes
`|pi+> = -|1,+1>`. The P73 Table I pion block gives this vector
eigenvalue 2. Each transition is rescaled by P65 Eq. (10),
`S_ij = -sqrt(rho_i rho_j) T_ij`, with `rho_i=M_i q_i/(4 pi W)`.
The strong `T` has `GeV^-1` units; `S11` is dimensionless.

The reference values in [p73_fig1_reduced.csv](p73_fig1_reduced.csv) were
fixed before model values were inspected. They come from P73 PDF page 3,
printed 045209-3, Fig. 1 dashed vector strokes. Poppler SVG path styles
separate dashed strokes from solid strokes and experimental dots; a
400-dpi PNG was checked visually. Both axis calibrations, PDF checksum,
and reading method are in [p73_fig1_reduced.json](p73_fig1_reduced.json).
Each component has conservative absolute reading bound `+/-0.020`.

Reproduction command, from `theory/`:

```bash
PYTHONPATH=src python -c 'from pathlib import Path; from graal_theory.amplitudes.nstar1535_reduced import load_reduced_parameters; from graal_theory.reduced_t_reference import load_fig1_reduced, compare_fig1_reduced; root=Path("."); p=load_reduced_parameters(root/"references/nstar1535_reduced_parameters.json",root/"references/sources.json"); pts=load_fig1_reduced(root/"references/p73_fig1_reduced.csv",root/"references/p73_fig1_reduced.json",root/"../tmp/pdfs/10.1103@PhysRevC.73.045209.pdf"); [print(row) for row in compare_fig1_reduced(p,pts)]'
```

## Model-minus-reference residuals

All amplitudes and residuals below are dimensionless. `*` marks a component
whose absolute residual exceeds the fixed `0.020` reading bound.

| W (GeV) | Re model | Re dashed | Delta Re | Im model | Im dashed | Delta Im |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1.50 | +0.2085 | +0.206 | +0.0025 | +0.2406 | +0.214 | +0.0266* |
| 1.52 | +0.1374 | +0.174 | -0.0366* | +0.4227 | +0.390 | +0.0327* |
| 1.54 | -0.0899 | -0.034 | -0.0559* | +0.4325 | +0.454 | -0.0215* |
| 1.56 | -0.1904 | -0.178 | -0.0124 | +0.2662 | +0.308 | -0.0418* |
| 1.58 | -0.1677 | -0.174 | +0.0063 | +0.1416 | +0.166 | -0.0244* |
| 1.60 | -0.1271 | -0.134 | +0.0069 | +0.0769 | +0.089 | -0.0121 |
| 1.62 | -0.0990 | -0.103 | +0.0040 | +0.0374 | +0.045 | -0.0076 |
| 1.64 | -0.0816 | -0.084 | +0.0024 | +0.0067 | +0.014 | -0.0073 |

The largest absolute residual is `0.0559` (real at 1.54 GeV). The
physical-sheet loop sign, six-channel unitarity, kernel symmetry, and linear
equation are independently tested. The source sections inspected do not print
a complete original 2002 mass table; the explicit PDG 2024 masses here may
shift thresholds and shape. This caveat does not convert above-bound residuals
into agreement, nor identify their sole cause. No VMD or `pi pi N` corrections
are present in this reduced calculation.

SHA-256 of exact inputs:

```text
e8861394ef3fb86c005694d3cb82d8c2b905e39dbe384903f58392d644cff6ac  tmp/pdfs/PhysRevC.65.035204.pdf
19a2fbce10ed8201a29bdfbcfb9f3690a280d943c1e83db01aa1b2057d20eccb  tmp/pdfs/10.1103@PhysRevC.73.045209.pdf
8e0a34e9f7b8e490f3987bf71755106210ec48e02c6b68a751095c7cec253358  theory/references/nstar1535_reduced_parameters.json
1848ed42bd8ab7bd00f8f9b0e4d057249b7a199b8dfb88db6bc64d3e13a47962  theory/references/p73_fig1_reduced.csv
```
