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
an approval ID and two distinct named reviewers.

Period-specific Compton polarization uses tabulated `P(E_gamma)` nodes and a
covariance matrix. Interpolation is piecewise linear. Bin averages integrate
that interpolation exactly under a uniform within-bin spectrum. Extrapolation
is rejected. Current observable bundle exposes integrated 100 MeV flux, not
strip-resolved flux by polarization component. Diagnostic QA therefore records
a conservative interpolation-node envelope for unknown within-bin spectrum weighting;
it also preserves bin-average Compton covariance. Repeated runs from one period
share that uncertainty; independent period contributions combine with squared
flux weights. Final S6 release must replace or propagate this approximation.

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
visible as invalid rows and red crosses at plot boundary, never silently dropped
or represented as measured `Sigma` points. Closure at `Sigma = +/-1` gates on
bias and orientation-sign inversion; Gaussian pull gates apply only inside
physical interval because their asymptotic assumptions fail at boundary.

Finite azimuth bins use exact uniform-bin average
`cos(2 phi_center) sin(delta_phi) / delta_phi`. Residual sub-bin acceptance
variation remains a diagnostic assumption and belongs in final systematic
validation.

Common-acceptance cancellation is a diagnostic comparison assumption. It does
not replace Person 1's immutable N3 acceptance handoff or S6
systematic/release validation.

Person 2 accepts N3 only from
`results/physics/normalization/handoffs/<acceptance_release_id>/`. Publication
is atomic and contains exactly `acceptance_v1.csv`,
`acceptance_phi_response_v1.csv`, and `acceptance_qa.json`. Release validation
rejects legacy root-level destinations, incomplete or extra files, symlinks,
release-ID mismatch, invalid QA, Gate 0 mismatch, missing N2 linkage, or any
CSV hash mismatch. N2 reconstruction digest in acceptance QA must equal actual
reconstruction-inventory digest consumed by S6. Canonical polarization config
must explicitly approve same release ID and directory. Phi-response schema
approval additionally requires non-empty approval ID and two distinct
reviewers; `acceptance_qa.json` must carry same approval ID. Schema authority
`config/schemas/acceptance_phi_response_v1.schema.json` fixes exact response
columns, masks, weighted-covariance equations and complete joint mass-phi grid.
Scalar/common-acceptance diagnostics cannot satisfy this release gate.

## Comparison grid

Configured diagnostic layout uses:

- four energy bins: 1.1–1.2, 1.2–1.3, 1.3–1.4, 1.4–1.5 GeV;
- three columns: `M(p pi0)`, `M(p eta)`, `M(eta pi0)`;
- ten invariant-mass bins per panel;
- twelve azimuth bins on `[0, pi)`;
- physical mass limits derived separately for each energy row from framework
  particle masses and that row's maximum center-of-mass energy.

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
  --output-dir results/diagnostics/polarization/figure4_comparison
```

Command validates exact Gate 0 hashes before reading events. Outputs are a PNG,
one CSV row per fitted mass bin including invalid bins, and a QA JSON containing
repo-relative input/output paths, hashes, byte sizes, artifact roles, allowed-use
labels, exact complete-run inventory, direct flux/state-map/Compton sources,
Compton variances, producer commit, and reproducible command. Producer commit
defaults to repository `HEAD`; `--producer-commit` permits explicit injection
for controlled builds. Bundle is staged then published as one new directory;
existing destinations are never overwritten. QA schema v2 marks product
`diagnostic`, `release_eligible=false`, and unusable for release physics.

## S4 forward-folded fit evidence

Canonical S4 consumes authenticated N2 reconstruction and immutable N3 bytes;
it never accepts caller-built count tables or N4 yields. Provenance edges are
`N2 -> S4`, `N3 -> S4`, `N3 -> S6`, and explicitly `N4 -/-> S4`. N4 remains
owned by cross-section stages N5–N7.

N3 provides a complete joint `(true mass,true phi) -> (reco mass,reco phi)`
matrix for both orientations. Every true/reco cell is explicit. Columns retain
lost-event inefficiency instead of being renormalized. For true cell `i` and
reco cells `j,k`, with `G=sumw_generated_true`, `G2=sumw2_generated_true`,
`S2j=sumw2_selected_migration[j,i]`, and `pj=R[j,i]`, validation reconstructs:

```text
R[j,i] = sumw_selected_migration[j,i] / G
Cov(pj,pk) = (pj*pk*G2 - pk*S2j - pj*S2k) / G^2
Var(pj) = (S2j*(1 - 2*pj) + pj^2*G2) / G^2
```

Blocks must be finite, symmetric and positive semidefinite within approved
config tolerances. Allowed masks are exactly `valid`,
`invalid_zero_generated`, `invalid_low_effective_statistics`,
`invalid_nonphysical_weights`, and `invalid_incomplete_coverage`. Invalid
blocks stay serialized and make S4 non-releasable. One response per
`beam_group` and orientation is pooled across its declared source periods;
period-dependent response requires a new beam group or schema version.

Expected reco counts jointly fold true mass and phi. Positive true-mass yields
and bounded `Sigma[m]` are shared across all source periods and orientations.
Nominal counts use `replica_id=0`; bootstrap replicas use one deterministic
Poisson(1) weight per N2 file hash, tree and entry, shared across all three
observables. Their ordered Sigma vectors produce `C_stat`; Fisher/Hessian
covariance remains a named diagnostic. Deterministic eigenmode refits of N3
weighted covariance produce separate named systematic `C_response`.

S4 publication contains exactly:

```text
results/physics/polarization_fits/<fit_release_id>/azimuth_counts_v1.csv
results/physics/polarization_fits/<fit_release_id>/sigma_fit_v1.csv
results/physics/polarization_fits/<fit_release_id>/sigma_fit_qa.json
```

```bash
python 08_polarization/fit_sigma.py \
  --acceptance-handoff results/physics/normalization/handoffs/<acceptance_release_id>/acceptance_qa.json \
  --reco-inventory results/reconstruction/inventory.json \
  --config config/physics/polarization_v1.json \
  --fit-release-id <fit_release_id> \
  --output-root results/physics/polarization_fits
```

Writer stages complete bytes, validates them, then performs one atomic rename.
No-overwrite rejects existing destinations. Wrong-directory, incomplete
triplet, extra file, symlink, legacy path, noncanonical release ID, changed
authority, invalid response block, insufficient events/rank, boundary
pathology, optimizer failure, residual/deviance failure, bootstrap failure, or
non-PSD covariance returns runtime/QA failure without partial publication.
CLI exit status is `0` only for complete valid publication, `1` for runtime or
QA rejection, and `2` for usage errors.

## S6 release contract

Physics release consists of exactly:

```text
results/physics/polarization/sigma_v1.csv
results/physics/polarization/sigma_covariance.npz
results/physics/polarization/polarization_qa.json
```

- `sigma_v1.csv`: `analysis_version`, unique elementary-bin keys, complete N1
  physical acceptance key (`channel`, target/beam group, energy and
  `cos_theta` edges, observable, selection), physical `sigma`,
  `stat_uncertainty`, JSON systematic components, `validity_mask`, `fit_id`,
  `input_sha256`, `config_sha256`, event count and fit GOF;
- `sigma_covariance.npz`: exact arrays `covariance`, `bin_keys`,
  `stat_covariance`, `systematic_covariance`, and scalar `schema_version`;
- `polarization_qa.json`: cross-hashes, producer commit, config/Gate 0/
  acceptance-table, phi-response and QA hashes, actual input file records,
  fit QA, closure/sign QA,
systematic sources, and approved numeric QA policy. Policy must equal canonical
hash-validated config; current supported systematic combination is explicitly
`independent_sources_quadrature`.

Fit QA must bind exact `acceptance_phi_response_v1.csv` SHA-256 and declare
`response_application=forward_folded`. A diagnostic-only or differently hashed
response cannot validate as S6.

S6 performs full replay from exact hashed S4 bytes: N3 response parsing, count
parsing, nominal and every successful bootstrap fit, expected counts,
deviance, `C_stat`, and `C_response`. Replayed Sigma, nuisance yields and
matrices must agree within config-pinned tolerances. Literal QA claims never
replace numeric replay. All serialized file records use canonical
repository-relative POSIX paths; absolute/dotted/backslash paths and symlinks
fail closed.

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
- Person 1 immutable acceptance table/phi-response/QA handoff missing for final
  S6 release;
- shared P0 validator/output artifact still needs joint implementation and
  two-reviewer approval before S7 mappings can pass.

Event-count, deviance/ndof, closure bias/pull, and minimum-systematics
thresholds and systematic-combination policy remain `pending_owner_approval`.
Validator requires same approved policy in canonical config and QA, approval
ID, and two distinct reviewers; no experimental release can pass meanwhile.

No substitute, inferred mapping, legacy ROOT file, or paper-derived numeric
content is accepted.

Schema and software availability do not approve experimental production.
Canonical config remains `status=blocked`, carries null scientific thresholds
and empty owner approvals, and therefore cannot emit real S4/S6 physics. Any
shared schema, QA policy, public CLI or handoff change requires two-owner
approval from Persona 1 and Persona 2; automated review is additional evidence,
not an owner signature.
