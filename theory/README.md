# GRAAL standalone theory: γp → ηπ⁰p

This independent package contains two theory paths. `predict`, `validate`,
and `pilot-panel5` calculate the central-value Eq. (43) tree contribution of
Döring, Oset and Strottman, *Phys. Rev. C* **73**, 045209 (2006); their
cross sections and beam asymmetry remain **partial theory**. The separate
`EtaPi0PFullModel` coherently sums seven source-linked spin-amplitude families.
`figure4-full` integrates and certifies all twelve Ajaka Figure 4 panels
without fitting the published strokes. Its numerical and physical comparison
gates are distinct from passing software tests; no complete reproduced
Figure 4 claim has yet been established. This package does not import or
modify Stage 07/08.

## Reproduce

From the repository root, using Python ≥3.10:

```bash
cd theory
python -m pip install -e '.[test]'
graal-theory predict --energy 1.2 --energy 1.202 --sobol-power 15 --output outputs/e1200
graal-theory validate --bundle outputs/e1200
python -m pytest -q
```

## Full coherent Figure 4 calculation

Production launch is pending the [convergence TDD gate](docs/2026-10-05-figure4-converged-production-tdd-plan.md): a real upper-energy bin fails the fixed Sobol normalization check at both `p5/p6` and same-order `p6/p7`. The command below documents the interface; its settings are **not certified** for the twelve-panel run.

```bash
graal-theory figure4-full --output outputs/figure4-full \
  --energy-order 4 --sobol-power 8 --replicas 8 \
  --q-order 64 --angle-order 48 --workers 4 --mode grid
```

The command keeps exact nominal/accessible bin bounds, correlated scrambled
Sobol replicas, energy and sample-size refinements, direct/grid comparisons,
and three-pair normalization checks. It writes predictions and residuals as
CSV/JSON, covariance JSON, a 4×3 PDF, and a validation report. Exit `0`
requires every physically accessible bin and resolved published point to
pass; exit `2` records a complete negative or incomplete scientific result.
This command is separate from the Eq. (43) pilot. The strong matrix is bounded
at `W ≤ 1.80 GeV`; `W ≤ 1.60` is the source's qualitative scattering-agreement
region and `1.60 < W ≤ 1.80` is a source-used extension, not a quantified
uncertainty band. Primary photon-energy weighting is uniform. Global azimuth
is integrated analytically from the full H/V spin matrices, with the same
Ajaka V−H sign. No parameter is selected by closeness to Figure 4.

## Figure 4 panel-5 pilot

```bash
graal-theory pilot-panel5 \
  --published-csv ../test_data/beam_asymmetry/ajaka2008_figure4_digitized.csv \
  --output outputs/panel5_eq43
```

This writes `panel5.pdf` and `prediction.json` for \(p\eta\),
\(1.20\leq E_\gamma<1.30\) GeV, on the ten 0.04-GeV analysis mass bins,
compared with four digitized Ajaka points. The CLI accepts only the reviewed
digitization checksum; changes to those points require review of the source.
Missing curve bins are outside kinematic support, not extrapolated zeros;
an accessible but unsampled bin aborts the run. The Ajaka points are digitized
and their displayed bars contain statistical errors only, not systematics.
The calculation averages the two polarized spin sums separately and forms
\(\Sigma=2\int\cos(2\phi)(d\sigma_V-d\sigma_H)/\int(d\sigma_V+d\sigma_H)\),
where \(\phi\) is the azimuth of the pair momentum around the photon axis.
This sign follows the analysis convention \(Y_V-Y_H\). Five-point or
single-energy evaluation is insufficient near the high-mass kinematic edge;
the pilot defaults to nine Gauss–Legendre photon-energy nodes and scrambled
Sobol \(2^{15}\) events per node; the CLI requires at least nine nodes and
\(2^{14}\) events per node. Without flux inputs, energy weighting is
**uniform** and no azimuth fit is performed. No acceptance correction,
coherent non-tree amplitude, or theory uncertainty is included. Another channel can reuse the harmonic
reduction, but needs its own sourced polarized amplitude.
The output is the continuous \(\cos2\phi\) coefficient. Whether Ajaka's
published fit corrected finite azimuth-bin averaging has not been verified;
a 12-bin center-only fit can attenuate this harmonic by about 4.5%.

The Ajaka 2008 Letter (DOI `10.1103/PhysRevLett.100.052003`, p. 4) confirms
four photon-energy, ten invariant-mass, and twelve azimuth bins and says that
the beam asymmetry was extracted with a `cos(2φ)` dependence following its
Ref. [14]. It does **not** specify whether the fit used bin centers or
bin-averaged cosine values. The separate prediction below therefore follows
the **raw Stage 07 center-fit convention**, not a claimed exact Ajaka fit.
Stage 07 now converts this raw amplitude to its published ratio Sigma using
the approved 8/12/16-bin divisors; see the
[finite-bin convention](../docs/research/2026-10-09-finite-phi-bin-correction.md).

## Measured-flux panel-5 comparison

```bash
graal-theory pilot-panel5 \
  --published-csv ../test_data/beam_asymmetry/ajaka2008_figure4_digitized.csv \
  --flux-root ../data/00_external/flux_calibrated.root \
  --run-manifest ../config/run_manifest.csv \
  --sobol-power 17 --energy-nodes 72 \
  --output outputs/panel5_flux_eq43_reviewed
```

Install the optional `flux` extra (`pip install -e '.[flux]'`) when using a
minimal theory environment. The ROOT adapter is standalone: it does not import
Stage 07. It uses proton/UV runs in the manifest only when each has exactly one
POL1/POL2/BREM triplet, then selects positive-flux strips in
\(1.20\leq E_\gamma<1.30\) GeV. UV polarization comes from the same
inverse-Compton transfer formula and constants as the analysis. Each of the
equal-width energy slices is evaluated at its combined-flux centroid, with
V/H photon fluxes and flux-weighted polarizations retained separately. The
continuous curve weights the intrinsic fully polarized cross sections by
combined flux. The second curve folds each state's polarization into expected
12-bin yields, normalizes V/H separately, and fits the Stage 07 ratio to
`cos(2φ)` at bin centers with inverse-Poisson-variance weights. It does not
run Stage 07's data-dependent low-p-value fallback; absolute expected event
counts and thus its significance are undefined without target/acceptance.
Neither curve includes detector acceptance or omitted coherent amplitudes.

`prediction.json` records both `sigma` (continuous) and `sigma_phi_fit`,
where `sigma_phi_fit` remains the raw center-fit amplitude, before the
finite-bin correction applied to newly extracted experimental ratio points.
Do not identify it with the corrected experimental Sigma without matching
that convention; for the 12-bin transfer, the approved divisor is `0.9549`.
The JSON also records
ROOT/manifest paths and SHA-256 hashes, selection counts, flux totals,
effective polarizations, model parameters, and numerical settings. In this
calibration, 1,021 of 1,426 manifest P/UV runs have complete triplets; 14,294
exposures are retained and 53 strips with invalid flux are skipped. These
are the measured-flux subset, **not** a claim of complete run coverage.

Numerical scan with 36 energy slices and Sobol powers 16, 17, and 18 changes
the continuous and fitted values by at most about 0.002 in the populated
1.50–1.66 GeV mass bins. The upper 1.68–1.72 GeV bin is **not converged**:
its continuous value changes by up to 0.019 and its fitted value by up to
0.016 in the same scan. Doubling energy slices from 36 to 72 at power 17
changes that edge bin by 0.002 or less, so the dominant issue is phase-space
sampling near the kinematic boundary. The edge result remains exploratory;
do not use it as a validated curve point or extend the method to other panels
on the strength of that point alone.

`--sobol-power 15` computes nested 2¹⁵ and 2¹⁶ Sobol samples per energy;
the higher-resolution result is saved. `predict` accepts repeated `--energy`
or a grid specified by `--energy-min`, `--energy-max`, `--energy-step`.
`--replace` replaces an existing output bundle. `validate` requires both
1.200 and 1.202 GeV in the bundle. Exit code 0 means all checks passed, 2
means a completed scientific comparison failed, and 1 means invalid input or
runtime failure. Generated runs remain untracked in `outputs/`.

Each bundle contains `manifest.json` (scope, parameter provenance, numerical
configuration, validation state), `results.npz` (partial total cross section
and three invariant-mass densities), and `convergence.json`. Validation adds
`validation/comparison.json`, `validation/invariant_masses.pdf`, and
`validation/total_cross_section.pdf`. The Figure 14 dotted tree curve and
Figure 19 full-model point are **different targets**: the latter is used only
to check the paper's approximate factor-of-two statement, never as a claimed
reproduction of the full model.

Numerical convention: GeV, natural units, metric +−−−, laboratory photon
energy, real float64 and complex128 arrays. The sampler checks conservation
and on-shell conditions. Acceptance checks compare phase-space volume with
independent quadrature (0.5%), successive Sobol resolutions (1% integrated,
3% populated bins), the digitized Figure 14 dotted curve (20% model tolerance
plus recorded reading uncertainty), and the 1.202 GeV factor-of-two relation.
No parameter is fitted to these reference curves.
An all-massless three-body test also checks the phase-space normalization
against the closed form Φ₃(s) = s/(256π³). Regular wheel installs include the
versioned parameter and digitization files as package resources.

See [model_scope.md](references/model_scope.md) for inclusion/exclusion and
[parameter_provenance.md](references/parameter_provenance.md) for each physical
input and equation-to-code mapping. Bibliography lives in
[`sources.json`](references/sources.json); digitization calibration and
uncertainty are in [`digitization.json`](references/digitization.json).
