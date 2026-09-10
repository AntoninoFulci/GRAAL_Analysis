# Beam polarization and Sigma

## Scope

This package owns proton-channel beam-polarization handling and extraction of
the beam asymmetry `Sigma`. It also produces an original diagnostic grid for
comparison with a four-energy-by-three-invariant-mass presentation. Published
points, fitted curves, digitized coordinates, plotting code, and visual styling
are not inputs.

Current repository state is blocked for experimental output. Missing inputs
are recorded in `config/physics/polarization_v1.json`; validators fail closed.

## Scientific contracts

Each accepted event must carry `RunNumber`, recorded `Polarization`, and
`Xstrip`, plus metadata-bearing reconstructed four-vectors. Legacy files in
`results/reco/` are forbidden because they lack required run/state metadata.

Reconstruction input needs a JSON inventory with schema version, producer Git
commit, exact Gate 0 handoff hash, tree/vector selection, ROOT paths and hashes,
`complete_run_coverage=true`, and explicit run numbers. Run set must equal
target run set in hash-validated Gate 0 `run_manifest_observables.csv`; subset
or superset is rejected. Every ROOT file schema is checked independently.

State interpretation comes only from an approved, hashed map with two
reviewers. Each interval binds:

- run range and recorded state code;
- source period;
- `parallel` or `perpendicular` orientation;
- exact accepted flux column, `pol1_net` or `pol2_net`.

Names `POL1` and `POL2` never imply an orientation. Sign convention also needs
explicit two-reviewer approval.

Period-specific Compton polarization uses tabulated `P(E_gamma)` nodes and a
covariance matrix. Interpolation is piecewise linear. Bin averages integrate
that interpolation exactly under a uniform within-bin spectrum. Extrapolation
is rejected. Current observable bundle exposes integrated 100 MeV flux, not
strip-resolved flux by polarization component. Diagnostic QA therefore records
a conservative endpoint envelope for unknown within-bin spectrum weighting;
final S6 release must replace or propagate this approximation.

## Observable and estimator

For each pair `p pi0`, `p eta`, and `eta pi0`, analysis forms pair four-vector
sum. Invariant mass follows `M^2 = E^2 - |p|^2`. Azimuth is transverse angle of
pair momentum in lab frame, reduced to `[0, pi)`. Vanishing transverse pair
momentum is invalid.

Counts are split by approved orientation sign and binned in energy, invariant
mass, and azimuth. Model for one azimuth bin is

```text
mu_V = F_V A c (1 + P_V Sigma cos(2 phi))
mu_H = F_H A c (1 - P_H Sigma cos(2 phi))
```

`F` is accepted run flux; `P` is flux-weighted Compton polarization; `A c` is
one common unknown efficiency/rate per azimuth bin. Conditioning on total
count removes that common nuisance exactly and gives a binomial likelihood.
This estimator allows unequal vertical/horizontal flux and polarization.
`Sigma` is bounded to `[-1, 1]`. Empty or angularly incomplete mass bins remain
visible as invalid rows, never silently dropped.

Finite azimuth bins use exact uniform-bin average
`cos(2 phi_center) sin(delta_phi) / delta_phi`. Residual sub-bin acceptance
variation remains a diagnostic assumption and belongs in final systematic
validation.

Common-acceptance cancellation is a diagnostic comparison assumption. It does
not replace Person 1 acceptance handoff or S6 systematic/release validation.

## Comparison grid

Configured diagnostic layout uses:

- four energy bins: 1.1–1.2, 1.2–1.3, 1.3–1.4, 1.4–1.5 GeV;
- three columns: `M(p pi0)`, `M(p eta)`, `M(eta pi0)`;
- ten invariant-mass bins per panel;
- twelve azimuth bins on `[0, pi)`;
- physical mass limits derived from framework particle masses and maximum
  center-of-mass energy.

Only framework results appear. Output title, colors, typography, axes, QA, and
serialization are project-native.

## Command

After Gate 0, signed state map, Compton inputs, and metadata-bearing
reconstruction exist:

```bash
python 08_polarization/build_figure4_comparison.py \
  --reco-inventory results/physics/reconstruction/reco_eta_pi0_chi2_inventory.json \
  --output-dir results/physics/polarization/figure4_comparison
```

Command validates exact Gate 0 hashes before reading events. Outputs are a PNG,
one CSV row per fitted mass bin including invalid bins, and a QA JSON containing
input/output hashes and exact complete-run inventory. Bundle is staged and then
published as one new directory; existing destinations are never overwritten.
QA marks this product `diagnostic` and `release_eligible=false`.

## Current blockers

- `results/observable_runs/HANDOFF.json` missing;
- approved experimental state mapping missing;
- authoritative period Compton curves/covariance missing;
- approved orientation-sign convention missing;
- metadata-bearing proton reconstruction missing;
- Person 1 acceptance handoff missing for final S6 release.

No substitute, inferred mapping, legacy ROOT file, or paper-derived numeric
content is accepted.
