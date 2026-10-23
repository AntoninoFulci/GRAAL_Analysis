# VMD full strong T: bounded primary-source comparison

Audit date: 2026-10-02. The scalar correction agrees with P65 Fig. 5 within
the reading bounds below. The distinguishable subset of P73 Fig. 15 agrees
within conservative absolute reading bounds; no resolved entry fails.
Overlapped entries remain unreadable, and reproduction of the complete
published strong input remains **unresolved/convention-blocked**. The
implementation is a tested **full-model reconstruction candidate**, not a
verified input to a coherent photoproduction amplitude.

## Sources and visual procedure

The [source map](nstar_1535_tmatrix_source_map.md) defines P65 and P73.
The exact local bytes were rehashed:

```text
e8861394ef3fb86c005694d3cb82d8c2b905e39dbe384903f58392d644cff6ac  tmp/pdfs/PhysRevC.65.035204.pdf
19a2fbce10ed8201a29bdfbcfb9f3690a280d943c1e83db01aa1b2057d20eccb  tmp/pdfs/10.1103@PhysRevC.73.045209.pdf
```

P65 PDF page 5 (printed 035204-5) and P73 PDF page 13 (printed
045209-13) were rendered and visually viewed, including captions, rather
than inspected only through extracted text. Reproduction commands from
the repository root:

```bash
shasum -a 256 tmp/pdfs/PhysRevC.65.035204.pdf tmp/pdfs/10.1103@PhysRevC.73.045209.pdf
VMD_FIG_DIR=$(mktemp -d)
XDG_CACHE_HOME=/private/tmp pdftoppm -f 5 -l 5 -r 300 -png -singlefile tmp/pdfs/PhysRevC.65.035204.pdf "$VMD_FIG_DIR/p65_page5"
XDG_CACHE_HOME=/private/tmp pdftoppm -f 13 -l 13 -r 300 -png -singlefile tmp/pdfs/10.1103@PhysRevC.73.045209.pdf "$VMD_FIG_DIR/p73_page13"
XDG_CACHE_HOME=/private/tmp pdftoppm -f 5 -l 5 -r 300 -x 450 -y 2460 -W 1650 -H 570 -png -singlefile tmp/pdfs/PhysRevC.65.035204.pdf "$VMD_FIG_DIR/fig5"
XDG_CACHE_HOME=/private/tmp pdftoppm -f 13 -l 13 -r 600 -x 900 -y 555 -W 1530 -H 950 -png -singlefile tmp/pdfs/10.1103@PhysRevC.73.045209.pdf "$VMD_FIG_DIR/fig15_left"
XDG_CACHE_HOME=/private/tmp pdftoppm -f 13 -l 13 -r 600 -x 2780 -y 555 -W 1530 -H 950 -png -singlefile tmp/pdfs/10.1103@PhysRevC.73.045209.pdf "$VMD_FIG_DIR/fig15_right"
```

Full-page rasters are 2550×3300 (P65) and 2475×3300 (P73) pixels at
300 dpi. Figure crops were also viewed at their native dimensions.
`pdfimages -f 13 -l 13 -list` identifies the embedded P73 figure raster
as 900×278 grayscale pixels at 150 ppi; the 600-dpi enlargement improves
tick positioning but cannot restore that source detail. All comparisons are manual figure readings,
with raster-coordinate checks of dark strokes at the selected abscissae;
no curve fit, automatic line-to-channel assignment, or parameter adjustment
was used. Dashed gaps require interpolation from neighboring segments.

Fig. 5 has two solid curves. Horizontal labels are 1100, 1300, 1500,
1700 MeV; vertical labels are 0.5, 1, 1.5, 2, with zero at the lower
border. Left: elastic pi-minus p; right: pi-minus p to K0 Lambda.
The prose repeats “left” for the strange example; the panel titles resolve
the assignment. Roughly 180 pixels represent one unit vertically in the
300-dpi crop. A conservative absolute factor-reading bound is ±0.03
(about 5 pixels), and the corner energy is read as 1.37±0.02 GeV.

Fig. 15 labels W=1400,1450,...,1700 MeV. Its left panel is
`|T^(i3)|`, with vertical labels 0.02,...,0.10 MeV^-1; its right is
`|T^(i1)|`, with labels 0,0.005,...,0.025 MeV^-1. The right frame extends
slightly below its zero tick: the frame must not be treated as zero.
At 600 dpi, left ticks give approximately 8800 pixels/(MeV^-1), and
right ticks approximately 33000 pixels/(MeV^-1). In the crops above,
W=(1450,1550,1650) corresponds approximately to x=(321,775,1227)
on the left and (322,762,1202) on the right; zero is near y=900 and
y=859, respectively. Stroke widths of several pixels, dotted gaps,
interpolation, and crowded crossings motivate deliberately conservative
absolute bounds **±0.003 MeV^-1 left** and **±0.001 MeV^-1 right**.
These are reading envelopes, not statistical errors or mass uncertainties.

Caption mapping, one-based P73 channel order:

| i | Initial channel | Caption line style |
| --- | --- | --- |
| 1 | pi0 p | dotted |
| 2 | pi+ n | dashed |
| 3 | eta p | solid |
| 4 | K+ Sigma0 | dash-dot |
| 5 | K+ Lambda | double dashed dotted |
| 6 | K0 Sigma+ | triple dashed dotted |

The multi-dash styles are traced over neighboring segments, not assigned
by their predicted magnitudes. Near crossings, or when adjacent low curves
cannot be separated reliably, no individual value is claimed.

## Source-parameter readout

The baseline loads PDG-2024 charge-dependent masses and P65 decay constants
from `nstar1535_reduced_parameters.json`, then explicitly replaces its
subtractions with `nstar1535_final_subtractions.json`: mu=1.2 GeV and
(a_piN,a_etaN,a_KLambda,a_KSigma)=(2.0,0.1,1.5,-2.8), P65 Eq. (28).
Vector masses are separately sourced, rho=0.770 and K*=0.892 GeV.
P65 Fig. 5 uses (m_pi-minus,M_p,m_K0,M_Lambda)=
(0.13957039,0.93827208816,0.497611,1.115683) GeV.
The common pi-pi-N loop uses the charged pion and mean proton/neutron
mass; this choice and the complete modern mass table are reconstruction
conventions, not a recovered numerical table from the papers.

For nonzero charge-+1 C entries, rho is assigned when meson strangeness
is unchanged and K* when it changes between channels 1–3 and 4–6.
This six-by-six family rule is an implementation convention; P65 prints
the two examples, not an exhaustive assignment. Zero C entries stay zero.
The real angular continuation and switches implement the
[design](../docs/2026-10-02-nstar1535-vmd-design.md).

Command, from `theory/` (the float conversion only standardizes display):

```bash
PYTHONPATH=src python - <<'PY'
from pathlib import Path
from scipy.optimize import brentq
from graal_theory.amplitudes.nstar1535_reduced import load_reduced_parameters
from graal_theory.amplitudes.nstar1535_final_fit import load_final_fit_parameters
from graal_theory.amplitudes.nstar1535_vmd import load_vector_masses
from graal_theory.amplitudes.nstar1535_full import reconstructed_full_tmatrix
from graal_theory.amplitudes.vmd import angular_factor
ref = Path('references')
base = load_reduced_parameters(ref/'nstar1535_reduced_parameters.json', ref/'sources.json')
final_parameters = load_final_fit_parameters(base, ref/'nstar1535_final_subtractions.json', ref/'sources.json')
vector_masses = load_vector_masses(ref/'nstar1535_vmd_masses.json', ref/'sources.json')
pi, proton = base.meson_masses_gev[1], base.baryon_masses_gev[0]
k0, lamb = base.meson_masses_gev[5], base.baryon_masses_gev[4]
def elastic(w):
    return angular_factor(w, pi, proton, pi, proton, vector_masses.rho_gev)
def strange(w):
    return angular_factor(w, pi, proton, k0, lamb, vector_masses.kstar_gev)
switch = brentq(lambda w: strange(w)-1, pi+proton, k0+lamb)
print('P65 Fig5 K* switch GeV', switch)
for w in (1.10, 1.30, 1.50, 1.70):
    print('P65 Fig5', w, 'rho raw/applied', elastic(w), elastic(w),
          'K* raw/applied', strange(w), 1 if w <= switch else strange(w))
for w in (1.40, 1.45, 1.50, 1.55, 1.60, 1.65, 1.70):
    t = reconstructed_full_tmatrix(w, final_parameters, vector_masses)
    print('P73 Fig15', w, tuple(float(abs(t[i, 2])/1000) for i in range(6)),
          tuple(float(abs(t[i, 0])/1000) for i in range(6)))
PY
```

Raw output (each P73 tuple follows channels 1–6; first tuple left panel,
second right; GeV^-1 is divided by 1000 to obtain MeV^-1):

```text
P65 Fig5 K* switch GeV 1.3701710103622766
P65 Fig5 1.1 rho raw/applied 0.9812397847446841 0.9812397847446841 K* raw/applied 1.4145086692438975 1
P65 Fig5 1.3 rho raw/applied 0.7955461740839749 0.7955461740839749 K* raw/applied 1.0968395886632933 1
P65 Fig5 1.5 rho raw/applied 0.6383217278798338 0.6383217278798338 K* raw/applied 0.8503014298477125 0.8503014298477125
P65 Fig5 1.7 rho raw/applied 0.5217916958931612 0.5217916958931612 K* raw/applied 0.6804940610150646 0.6804940610150646
P73 Fig15 1.4 (0.00874084347023003, 0.01227225348750083, 0.00468031804050475, 0.01752172217473921, 0.0293609599936655, 0.024847941888049077) (0.007543512428343494, 0.014450797489660987, 0.008740843470230028, 0.008072102874284707, 0.009714429908522672, 0.011643102293574034)
P73 Fig15 1.45 (0.011719222986633405, 0.01646509786757417, 0.013495196914359757, 0.02773846906344658, 0.0379619157470386, 0.03933111877653036) (0.008007635973273839, 0.015135876426942115, 0.011719222986633412, 0.007666006322343057, 0.008339332282780705, 0.014791488948394977)
P73 Fig15 1.5 (0.019852453698903018, 0.027875980408488748, 0.05366819320209166, 0.0605907598462507, 0.05893467514640797, 0.08588475398375693) (0.011927317615584384, 0.015614277451361451, 0.019852453698903025, 0.01771698620186978, 0.006918591865806772, 0.024102077372141106)
P73 Fig15 1.55 (0.01176082170920648, 0.016500529151751993, 0.07371265417182056, 0.05167417034539888, 0.02640549036302536, 0.07323287297182833) (0.01228359930303745, 0.00832563278845633, 0.01176082170920648, 0.021918233484992142, 0.01632194986727924, 0.009753019075371577)
P73 Fig15 1.6 (0.004116446265647459, 0.005774642233251687, 0.05542150396132683, 0.02744267431639472, 0.006536223022238387, 0.0388891286741262) (0.011516132240313889, 0.009284921767307589, 0.004116446265647457, 0.013386918709366896, 0.011925492700851656, 0.0013883668269223499)
P73 Fig15 1.65 (0.0019128187716346452, 0.0026913654340308896, 0.043654424624470486, 0.01780494594133877, 0.010830737920549059, 0.025239119588248083) (0.013442862158649418, 0.008549851458733172, 0.0019128187716346465, 0.010460373279207949, 0.008241702957876658, 0.0018000779176028732)
P73 Fig15 1.7 (0.0012196647414017554, 0.001754613850056789, 0.03497007613339523, 0.010640931058656093, 0.014189660051272479, 0.015080195865180201) (0.012893573851050446, 0.009777019771386303, 0.0012196647414017578, 0.009361369359036196, 0.006165864363938325, 0.003347158839889303)
```

## Bounded comparisons

P65 readings and applied factors (all dimensionless):

| W [GeV] | rho plot | rho calculation | K* plot | K* applied calculation |
| ---: | ---: | ---: | ---: | ---: |
| 1.10 | 0.98 | 0.98124 | 1.00 | 1.00000 |
| 1.30 | 0.79 | 0.79555 | 1.00 | 1.00000 |
| 1.50 | 0.63 | 0.63832 | 0.85 | 0.85030 |
| 1.70 | 0.52 | 0.52179 | 0.68 | 0.68049 |

All eight satisfy ±0.03; the calculated K* switch 1.370171 GeV satisfies
the 1.37±0.02 GeV corner reading. The raw K* factor exceeds one below
the switch, whereas the plotted/applied coefficient stays at one. Elastic
switching is at its threshold, 1.07784247816 GeV. At W=1.500 GeV the
elastic factor is **0.6383217**, a reduction of about 36.2%; the paper's
informal “about 25%” sentence is not the numerical normalization. Neither
the formula nor the masses were adjusted to force a factor of 0.75.

P73 table cells give **manual plot reading / calculation**, in MeV^-1.
`U` means unreadable individual line, not agreement and not discrepancy;
the calculation for every U entry is retained in the raw output above.

| Panel; i | W=1.45 GeV | W=1.55 GeV | W=1.65 GeV |
| --- | --- | --- | --- |
| Left; 1 pi0 p | 0.0115 / 0.01172 | 0.0115 / 0.01176 | U |
| Left; 2 pi+ n | 0.0163 / 0.01647 | 0.0159 / 0.01650 | U |
| Left; 3 eta p | 0.0134 / 0.01350 | 0.0736 / 0.07371 | 0.0436 / 0.04365 |
| Left; 4 K+ Sigma0 | 0.0280 / 0.02774 | 0.0509 / 0.05167 | 0.0177 / 0.01780 |
| Left; 5 K+ Lambda | U | 0.0261 / 0.02641 | 0.0109 / 0.01083 |
| Left; 6 K0 Sigma+ | U | 0.0715 / 0.07323 | 0.0252 / 0.02524 |
| Right; 1 pi0 p | U | U | 0.0136 / 0.01344 |
| Right; 2 pi+ n | U | 0.0082 / 0.00833 | U |
| Right; 3 eta p | 0.0116 / 0.01172 | U | U |
| Right; 4 K+ Sigma0 | U | 0.0212 / 0.02192 | 0.0103 / 0.01046 |
| Right; 5 K+ Lambda | U | 0.0159 / 0.01632 | U |
| Right; 6 K0 Sigma+ | U | 0.0095 / 0.00975 | U |

All **21 resolved entries** satisfy their respective bounds; **15 entries
remain unreadable**. Largest absolute residuals are approximately 0.00173
MeV^-1 (left i=6, W=1.55) and 0.00072 MeV^-1 (right i=4, W=1.55).
Resolved failures: **none**. This finite selection does not validate the
entire curves or the relative complex phases of T.

Reasons for U: left W=1.45, the two upper strange-channel traces cross;
left W=1.65, the two pion traces crowd the baseline. Right W=1.45 has
a lower three-line cluster (i=1,4,5) and an upper crossing (i=2,6);
right W=1.55 has overlapping dotted/solid traces (i=1,3); right W=1.65
has a middle cluster (i=2,5) and a lower crossing (i=3,6). Nearby distinct
segments establish the style mapping but do not justify separate readings
at these abscissae. Some resolved readings also interpolate dashed gaps;
the bounds account for this. No unresolved value is counted as a pass.

The papers do not supply the complete charge-mass dataset, common
pi-pi-N mass choice, or exhaustive vector assignment. Agreement at this
resolution cannot identify those choices uniquely. Their effects are not
included in the reading bounds and have not been estimated by retuning.
Thus the complete published-model identity remains convention-blocked even
though the resolved magnitudes are compatible. Fig. 1's S11 comparison
was not attempted: a documented charge/isospin and partial-wave conversion
would be required.

## Claim gate and handoff

1. **Scalar Eq. (12):** source factors and switching behavior agree with
   Fig. 5 at stated resolution; analytic and quadrature tests address the
   formula independently of this plot reading.
2. **Charge-+1 full strong T:** implemented as VMD-corrected WT plus one
   pi-pi-N correction, with final-fit subtractions. Tests and the resolved
   Fig. 15 subset support a reconstruction candidate. The full external
   validation remains unresolved/convention-blocked; resolve the remaining
   conventions and obtain adequate comparison evidence before treating it
   as a verified strong input to production.
3. **Coherent gamma p -> eta pi0 p amplitude:** still missing; requires all
   reaction-level production terms and relative complex phases. Strong
   magnitudes alone do not provide this amplitude.
4. **All twelve Ajaka Figure 4 curves:** not calculated by this milestone.
   They require component and coherent cross-section checks followed by
   publication-binning validation and the
   [Figure 4 claim gate](../docs/2026-10-01-figure4-theory-design.md).
5. **Native-bin fit:** a later, separate task using our higher-statistics
   asymmetries after publication validation. No parameters were fitted to
   these figures or our data. No Stage 07/08 merge or overlay is implied.

Verification on 2026-10-02: `cd theory && python -m pytest -q` completed
with **421 passed in 50.84 s**; repository `git diff --check` passed.
Numerical test success is distinct from the limited external-comparison
status above. Only the comparison note and source map are changed by this
documentation task.
