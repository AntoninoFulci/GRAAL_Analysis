# 6C kinematic fit

`reconstruction.core.kinematic_fit` fits four photons, recoil proton, and
tagged beam under ηπ⁰ reaction constraints.

## Constraints and parameters

Six constraints:

- four-momentum conservation;
- heavy-meson mass;
- light-meson mass.

Sixteen measured parameters are four photon `(E, θ, φ)` triplets, proton
`(p, θ, φ)`, and beam energy. Diagonal covariance comes from
`FitCovariance`; default reaction is stationary proton target with proton
recoil.

Iterative Lagrange-multiplier solver recalculates constraints and numerical
Jacobian until constraint and χ² convergence or iteration limit. Result holds
fitted photons, proton, covariance, χ², six degrees of freedom, iteration
count, and convergence status.

## Selection

With default fit enabled, event must converge and have confidence level at
least `--fit-cl` (default 0.01). Four-momentum constraint subsumes missing-mass
information, so missing-mass window is not additionally applied.

`--no-fit` disables fit and restores missing-mass selection around configured
partner mass.

## Validation

```bash
python -m reconstruction.validate_kinematic_fit \
  --signal 03_mc_simulation/data/eta_pi0_mc.root \
  --validation-mode closure \
  --out-dir results/plots
```

Signal generator stores unsmeared truth branches for pull, confidence-level,
condition-number, and failure analysis. Because generator smearing and fit
share current resolution model, this is closure validation, not independent
detector calibration. `calibration` mode requires explicit provenance.

## Output

Fit-enabled reconstruction stores fitted mesons, proton, four photons,
`fit_chi2`, `fit_ndf`, and `fit_converged` alongside raw branches.
