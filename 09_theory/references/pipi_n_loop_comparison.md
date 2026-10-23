# P65 ππN loop: external check and mass conventions

Audit date: 2026-10-02. Numerical implementation inspected at commit
`4e01b28c70876d291a9d8420dbf270e4ec7fc784`.

The direct P65 Eq. (26) loop agrees with the sign, energy dependence, and
approximate scale of P65 Fig. 11 within the visual-reading uncertainty below.
Together with the passing numerical and matrix tests, this completes the
bounded **ππN intermediate** milestone. This is not the published full model:
VMD is next, followed by coherent photoproduction, the twelve Figure 4 panels,
and the native-bin fit. P73 Fig. 15 remains a deferred full-model check.

## Sources and reproducibility

Primary sources are Inoue, Oset, Vicente Vacas, *Phys. Rev. C* **65**, 035204
(2002), Eqs. (25)-(30) and Fig. 11 on printed p. 035204-8; and Döring, Oset,
Strottman, *Phys. Rev. C* **73**, 045209 (2006), Eqs. (5)-(6). See the
[equation source map](nstar_1535_tmatrix_source_map.md) and
[approved design](../docs/2026-10-02-nstar1535-pipi-n-design.md).

SHA-256 values, paths relative to repository root:

| Input | SHA-256 |
| --- | --- |
| `tmp/pdfs/PhysRevC.65.035204.pdf` | `e8861394ef3fb86c005694d3cb82d8c2b905e39dbe384903f58392d644cff6ac` |
| `tmp/pdfs/10.1103@PhysRevC.73.045209.pdf` | `19a2fbce10ed8201a29bdfbcfb9f3690a280d943c1e83db01aa1b2057d20eccb` |
| `theory/references/nstar1535_reduced_parameters.json` | `8e0a34e9f7b8e490f3987bf71755106210ec48e02c6b68a751095c7cec253358` |
| `theory/references/nstar1535_final_subtractions.json` | `dc1affec4b469b6d9f77f24b1145967fa02adca49e193ae117c1a154c84987fc` |
| `theory/src/graal_theory/amplitudes/pipi_n.py` | `23a42c50f45366f687a15be62a9e813296e7214e0b3b92a85ee409fa7904d76b` |

Hash verification from repository root:

```bash
shasum -a 256 tmp/pdfs/PhysRevC.65.035204.pdf tmp/pdfs/10.1103@PhysRevC.73.045209.pdf theory/references/nstar1535_reduced_parameters.json theory/references/nstar1535_final_subtractions.json theory/src/graal_theory/amplitudes/pipi_n.py
```

The common loop masses are modern **PDG-2024 implementation conventions**, not
author-specified common masses: `mπ = 0.13957039 GeV` and
`MN = (0.93827208816 + 0.93956542052)/2 = 0.93891875434 GeV`.
Their provenance is in the unchanged
[mass record](nstar1535_reduced_parameters.json). They are distinct from the
physical, charge-dependent masses used in the six two-body channels.
The intermediate matrix uses the separate P65 Eq. (28)
[final-fit subtraction record](nstar1535_final_subtractions.json), with
`μ = 1.2 GeV` and `(aπN, aηN, aKΛ, aKΣ) = (2.0, 0.1, 1.5, -2.8)`;
the reduced record remains unchanged.

## Frozen loop readout and integration convergence

All loop values in the tables are `Im G̃ / (10⁸ MeV⁵)`. Since
`1 GeV⁵ = 10¹⁵ MeV⁵`, one plotted unit is `10⁻⁷ GeV⁵`. The real part is
zero. The exact prescribed readout command, run from `theory/`, is:

```bash
PYTHONPATH=src python -c 'from graal_theory.amplitudes.pipi_n import pipi_n_loop; m=.13957039; n=(.93827208816+.93956542052)/2; print([(w, pipi_n_loop(w,m,n).imag/1e-7) for w in (1.25,1.35,1.45,1.55,1.65)])'
```

| W (GeV) | 96×96 accepted value | 48×48 value | Absolute 48/96 difference (plot units) | Relative difference |
| --- | ---: | ---: | ---: | ---: |
| 1.25 | -0.014729723665 | -0.014729784179 | 6.05144004e-8 | 4.10831878e-6 |
| 1.35 | -1.278877528459 | -1.278882998315 | 5.46985601e-6 | 4.27707571e-6 |
| 1.45 | -8.188103615230 | -8.188139187197 | 3.55719669e-5 | 4.34434743e-6 |
| 1.55 | -27.459418836084 | -27.459538770244 | 1.19934160e-4 | 4.36768749e-6 |
| 1.65 | -67.773851474889 | -67.774147841114 | 2.96366225e-4 | 4.37286975e-6 |

Every point satisfies `|G96-G48| ≤ max(10⁻¹² GeV⁵, 10⁻³ |G96|)`.
The largest absolute difference is `2.96366225e-11 GeV⁵`; the largest
relative difference is about 4.37 ppm. These differences are convergence
diagnostics, not rigorous integration-error bounds; the displayed digits
record reproducible floating-point output rather than physical precision.

## Fig. 11 visual check

The original PDF's eighth page was rendered and visually inspected, including
its Eq. (26), units, caption, and printed page number. A larger Fig. 11 crop
was also inspected. Reproduce the crop from repository root:

```bash
XDG_CACHE_HOME=/private/tmp pdftoppm -f 8 -l 8 -r 300 -x 1310 -y 2350 -W 1020 -H 650 -png -singlefile tmp/pdfs/PhysRevC.65.035204.pdf tmp/pdfs/pipi_n_fig11_crop
```

The plot extends approximately from 1000 to 1800 MeV, with labeled energy
ticks at 1100, 1300, 1500, and 1700 MeV and vertical tick spacing of
50 units of `10⁸ MeV⁵`. Conservative manual readings are:

| W (GeV) | Fig. 11 visual reading (plot units) | Calculation (rounded) |
| --- | ---: | ---: |
| 1.25 | 0 ± 2 (unresolved from zero line) | -0.015 |
| 1.35 | -2 ± 2 (near zero line) | -1.28 |
| 1.45 | -10 ± 3 | -8.19 |
| 1.55 | -28 ± 3 | -27.46 |
| 1.65 | -68 ± 4 | -67.77 |

The ± values describe approximate reading uncertainty from line width,
placement between ticks, and raster resolution. They are neither source
error bars nor statistical confidence intervals. No automated digitization
or precision fit was performed. The two lowest points cannot independently
resolve the tiny calculated values or locate the threshold accurately.
At higher energies the negative sign, accelerating increase in magnitude,
and scale agree; there is no material discrepancy visible at this precision.
No normalization factor, mass, vertex, or subtraction constant was fitted to
the figure. This is a coarse external loop check, not validation of the full
coupled-channel or photoproduction prediction.

## Sensitivity to the common loop masses

Only the common masses supplied to `pipi_n_loop` are varied here, holding
everything else fixed. The alternative neutral-pion mass is the same
PDG-2024 record's `0.1349768 GeV`. These alternatives diagnose a mass
convention; they do not form a statistical uncertainty band and do not
recalculate a fitted matrix or vary the vertex polynomials.

| W (GeV) | Charged pion, proton | Charged pion, neutron | Neutral pion, average nucleon |
| --- | ---: | ---: | ---: |
| 1.25 | -0.015662588069 | -0.013835336917 | -0.030537757422 |
| 1.35 | -1.298890787250 | -1.259078197645 | -1.525231498551 |
| 1.45 | -8.261544716719 | -8.115107635124 | -8.989727887174 |
| 1.55 | -27.630480491742 | -27.289054591117 | -29.181995690185 |
| 1.65 | -68.093448550928 | -67.455193539580 | -70.806255255420 |

Define the absolute change as `|Im Galt - Im Gbaseline|` and the relative
change as that quantity divided by `|Im Gbaseline|`. Maxima are over the
five prescribed energies only:

| Alternative | Maximum absolute change (plot units), at W=1.65 GeV | Maximum relative change, at W=1.25 GeV | Relative change at W=1.65 GeV |
| --- | ---: | ---: | ---: |
| Charged pion, proton | 0.319597076039 | 6.333210% | 0.471564% |
| Charged pion, neutron | 0.318657935309 | 6.071986% | 0.470178% |
| Neutral pion, average nucleon | 3.032403780531 | 107.320640% | 4.474298% |

The overall maximum absolute shift is `3.032403780531e-7 GeV⁵`.
The neutral-pion relative shift exceeds 100% near threshold because the
baseline loop is still very small. A lower common mass makes the loop more
negative throughout this grid; the neutron choice makes it less negative.

| Common masses | Threshold MN+2mπ (GeV) | Shift from baseline (MeV) |
| --- | ---: | ---: |
| Charged pion, average nucleon (baseline) | 1.21805953434 | 0 |
| Charged pion, proton | 1.21741286816 | -0.64666618 |
| Charged pion, neutron | 1.21870620052 | +0.64666618 |
| Neutral pion, average nucleon | 1.20887235434 | -9.18718000 |

All five grid points are above all four thresholds. Each variant is exactly
zero at and below its own threshold. Relative differences against a zero
baseline would be undefined, so the grid maxima are not global maxima over
all energies. The baseline remains the charged pion and average nucleon.

Reproduce convergence and sensitivity from `theory/`:

```bash
PYTHONPATH=src python - <<'PY'
from graal_theory.amplitudes.pipi_n import pipi_n_loop, _loop_at_order
ws = (1.25, 1.35, 1.45, 1.55, 1.65)
m, proton, neutron = .13957039, .93827208816, .93956542052
average = (proton + neutron) / 2
baseline = [pipi_n_loop(w, m, average).imag / 1e-7 for w in ws]
for w, high in zip(ws, baseline):
    low = _loop_at_order(w, m, average, 48) / 1e-7
    print(w, high, low, abs(high-low), abs((high-low)/high))
for label, pion, nucleon in (
    ('baseline', m, average), ('charged/proton', m, proton),
    ('charged/neutron', m, neutron), ('neutral/average', .1349768, average),
):
    values = [pipi_n_loop(w, pion, nucleon).imag / 1e-7 for w in ws]
    changes = [abs(v-b) for v, b in zip(values, baseline)]
    relative = [d/abs(b) for d, b in zip(changes, baseline)]
    print(label, 'threshold GeV', nucleon+2*pion,
          'threshold shift MeV', (nucleon+2*pion-average-2*m)*1000)
    print('loop values', values)
    print('absolute changes', changes, 'relative changes', relative)
    print('maximum absolute', max(changes), 'maximum relative', max(relative))
PY
```

## Verification and handoff

From `theory/`, `python -m pytest -q` returned **225 passed in 48.38s**
with Python 3.14.6. The suite includes independent bounded integration at
1.25, 1.45, and 1.65 GeV, MeV/GeV normalization, threshold and convergence
guards, the P65 polynomials, P73 pion-block support and absorptive sign,
finite symmetric intermediate T and `(I-VG)T=V`, plus existing reduced and
Eq. (43) regressions. Closed six-channel two-body unitarity is not imposed
after adding ππN absorption.

Repository-root `git diff --check` passed. The milestone's committed changes
since `f1e932d` are confined to `theory/`; Stage 07/08 code and outputs were
not touched. The existing unrelated dirty files, including wiki edits about
Stage 07, were preserved and were not staged for this comparison note.
This task adds only this audit document to product files; it introduces no
public CLI, generated Figure 4 curve, refit, or full-model claim.
