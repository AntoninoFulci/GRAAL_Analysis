# GRAAL standalone theory: γp → ηπ⁰p

This independent package calculates only the central-value, tree-level
Δ*(1700) → ηΔ(1232) → ηπ⁰p contribution of Döring, Oset and Strottman,
*Phys. Rev. C* **73**, 045209 (2006), Figure 11 and Eq. (43). Its total cross
section and invariant-mass spectra are **partial theory**, not the full
coherent Figure 19 prediction, not beam asymmetry, and not an experimental
overlay. It does not import or modify Stage 07 or any existing analysis stage.

## Reproduce

From the repository root, using Python ≥3.10:

```bash
cd theory
python -m pip install -e '.[test]'
graal-theory predict --energy 1.2 --energy 1.202 --sobol-power 15 --output outputs/e1200
graal-theory validate --bundle outputs/e1200
python -m pytest -q
```

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
