# 05 — 6C Kinematic Fit

The NumPy kinematic fitter adjusts measured photons, recoil proton, and tagged
beam energy by the smallest covariance-weighted amount that satisfies four-
momentum conservation and both meson mass constraints.

## Six Constraints

For fitted parameters `eta`, measured parameters `y`, diagonal covariance `V`,
and constraints `f(eta)=0`, the objective is:

```math
\chi^2=(y-\eta)^T V^{-1}(y-\eta).
```

The six components returned by `_constraints` are:

```text
px_in - px_out
py_in - py_out
pz_in - pz_out
E_in  - E_out
m²(heavy photon pair) - M²_heavy
m²(light photon pair) - M²_light
```

The first four use `beam + stationary target - recoil - sum(photons)`. The
last two use the chosen best pairing after raw photons have been reordered
heavy-first/light-second. Degrees of freedom are fixed at six.

The default `FitReactionModel` uses proton target and proton recoil masses.
This is independent of the CLI's raw missing-mass `--partner` setting.

## Fit Inputs

One event becomes 16 measured parameters:

```text
[E, theta, phi] × 4 photons
[P, theta, phi] × 1 recoil proton
[E]              tagged beam along +z
```

Four-vectors use `[px, py, pz, E]`. Photons and beam are constrained massless;
the fitted recoil energy is recomputed from momentum and configured recoil
mass.

Default one-sigma resolutions are:

| Measurement | Sigma |
|---|---:|
| photon energy | 10% of measured E |
| photon theta | 5° |
| photon phi | 3° |
| proton momentum | 4% of measured P |
| proton theta | 3° |
| proton phi | 2° |
| beam energy | `0.016 / 2.354820045... GeV` |

`FitCovariance.covariance_diag` squares these sigmas and evaluates relative
terms at the measured point. The covariance remains fixed during iteration.
`ResolutionModel` is the narrow protocol for supplying another 16-variance
model; no calibrated detector covariance is currently the default.

Inputs must have shapes `(4,4)`, `(4,)`, `(4,)`, finite values, positive photon
and beam energies, and strictly positive finite variances.

## Convergence and Diagnostics

The fitter uses a central-difference `6 × 16` Jacobian and Lagrange-multiplier
updates, solving linear systems rather than forming explicit inverses. Default
limits are 10 iterations, scaled constraint tolerance `1e-8`, absolute and
relative chi-square stability tolerances `1e-8`, and maximum constraint-matrix
condition number `1e14`.

`FitResult` reports:

| Field | Meaning |
|---|---|
| `chi2`, `ndf` | covariance-weighted displacement and six degrees of freedom |
| `converged` | both constraint and stability conditions succeeded |
| `failure_reason` | `invalid_input`, `singular_constraint_matrix`, `invalid_fitted_parameters`, `invalid_fitted_covariance`, or `max_iterations` |
| `condition_number` | condition number of `F V Fᵀ` |
| `fitted_cov` | diagonal of constrained parameter covariance |

Non-convergence is returned as data, not raised. Reconstruction rejects a
non-converged fit or one with `confidence_level(chi2, 6) < fit_cl`. The default
CL cut is 0.01. A non-converged chi-square is kept far above any sensible cut.

Validation command:

```bash
python -m reconstruction.validate_kinematic_fit \
  --signal 03_mc_simulation/data/eta_pi0_mc.root \
  --out-dir results/plots \
  --validation-mode closure
```

It reports convergence, chi-square mean, an energy pull, raw/fitted eta width
and mean, CL-uniformity KS statistic, condition numbers, and failure counts;
when Matplotlib is available it writes `kinfit_validation.png`.

Default signal MC shares smearing assumptions with the fitter, so closure mode
tests implementation closure, not detector calibration. `--validation-mode
calibration` requires explicit independent-sample `--provenance` and labels the
result accordingly.

## Fitted Outputs

For retained eta-pi0 rows, reconstruction writes:

```text
eta_fit_gamma1, eta_fit_gamma2, eta_fit
pi0_fit_gamma1, pi0_fit_gamma2, pi0_fit
proton_fit
fit_chi2, fit_ndf, fit_converged
```

Raw branches remain alongside them. Raw `missing` is not recomputed from fitted
vectors. `fitted_cov`, failure reason, and condition number are diagnostic
return fields but are not persisted in reconstruction ROOT trees. Because
failed fits are rejected, stored `fit_converged` is always 1.

When fitting is disabled, none of these branches are created and raw missing-
mass selection applies instead. Observable extraction explicitly chooses raw
or fit branch families; their meanings must not be mixed.

Tests in `05_reconstruction/tests/test_kinematic_fit.py` cover constraint
closure, covariance scaling, condition failures, confidence levels, reaction
masses, and structured failure reasons.

See [reconstruction](05-reconstruction),
[chi-square pairing](05-chi-square-pairing), and
[systematics and outputs](07-systematics-and-outputs).
