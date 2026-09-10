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
a conservative interpolation-node envelope for unknown within-bin spectrum weighting;
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

After reconstruction, build immutable inventory. Processed-run ledger has exact
columns `run_number,status`; every Gate 0 target run must appear once with
`status=complete`:

```bash
python 08_polarization/build_reco_inventory.py \
  --reco results/physics/reconstruction/reco_eta_pi0_chi2.root \
  --processed-runs results/physics/reconstruction/processed_runs.csv \
  --output results/physics/reconstruction/reco_eta_pi0_chi2_inventory.json
```

Builder validates every ROOT schema, scans observed event runs, records
zero-selected-event runs, hashes inputs, rejects failed/incomplete ledger, and
never overwrites existing inventory.

After Gate 0, signed state map, Compton inputs, and inventory exist:

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

## S6 release contract

Physics release consists of exactly:

- `sigma_v1.csv`: `analysis_version`, unique elementary-bin keys, complete N1
  physical acceptance key (`channel`, target/beam group, energy and
  `cos_theta` edges, observable, selection), physical `sigma`,
  `stat_uncertainty`, JSON systematic components, `validity_mask`, `fit_id`,
  `input_sha256`, `config_sha256`, event count and fit GOF;
- `sigma_covariance.npz`: exact arrays `covariance`, `bin_keys`,
  `stat_covariance`, `systematic_covariance`, and scalar `schema_version`;
- `polarization_qa.json`: cross-hashes, producer commit, config/Gate 0/
  acceptance hashes, actual input file records, fit QA, closure/sign QA,
systematic sources, and approved numeric QA policy. Policy must equal canonical
hash-validated config; current supported systematic combination is explicitly
`independent_sources_quadrature`.

Validator requires symmetric positive-semidefinite matrices, CSV/NPZ bin-order
identity, statistical/systematic diagonal agreement, and
`covariance = stat_covariance + systematic_covariance`. It resolves and hashes
canonical config, Gate 0, acceptance, reconstruction inventory, state-map and
Compton source bytes:

```bash
python 08_polarization/validate_sigma_release.py \
  --repository-root . \
  --results results/physics/polarization \
  --check-covariance --check-qa
```

P1/P2 aggregation pre-validation references released elementary bins in exact
order and provides explicit matrix `W` plus aggregate covariance. Validator
verifies non-overlap and `C_aggregate = W C_sigma W^T` numerically. Final
publication validation is fail-closed until shared `validate_p0_release.py`
defines a jointly approved output artifact; acceptance QA alone is never
treated as completed normalization:

```bash
python 08_polarization/validate_publication_binning.py \
  --repository-root . \
  --results results/physics/polarization \
  --mapping-dir results/physics/publication_mappings --papers P1 P2
```

Synthetic end-to-end pytest creates temporary Gate 0, authorities, Compton
curve, metadata-bearing ROOT, processed-run ledger, inventory, and injected
Sigma modulation. It then exercises production comparison CLI and checks
recovered Sigma plus CSV/PNG/QA. No experimental or published values enter.

## Current blockers

- `results/observable_runs/HANDOFF.json` missing;
- approved experimental state mapping missing;
- authoritative period Compton curves/covariance missing;
- approved orientation-sign convention missing;
- metadata-bearing proton reconstruction missing;
- Person 1 acceptance handoff missing for final S6 release.
- shared P0 validator/output artifact still needs joint implementation and
  two-reviewer approval before S7 mappings can pass.

Event-count, deviance/ndof, closure bias/pull, and minimum-systematics
thresholds and systematic-combination policy remain `pending_owner_approval`.
Validator requires same approved policy in canonical config and QA, approval
ID, and two distinct reviewers; no experimental release can pass meanwhile.

No substitute, inferred mapping, legacy ROOT file, or paper-derived numeric
content is accepted.
