# N3 Response and S4 Forward-Folding Design

**Status:** proposed; architecture approved jointly, written specification
pending final owner review

**Approval ID:** `N3-MASS-PHI-RESPONSE-V1-2026-09-13`

## Goal

Freeze a portable, content-addressed N3 response schema and use it in a
deterministically replayable S4 fit. The fit must build azimuthal counts from
metadata-bearing N2 reconstruction, forward-fold a joint mass-and-azimuth
response, and produce evidence that the S6 validator can recompute from exact
input bytes.

This design closes four PR #9 review findings: response content was not
validated, N3 identity was not externally anchored, canonical release config
was not strictly validated, and serialized provenance accepted absolute paths.

## Scope and ownership

Person 1 owns N3 production and its three-file immutable publication. Person 2
owns N3 consumption, N2 count construction, S4 fitting, closure, S6 validation,
and the S4 evidence publication. Both persons review the schema authority,
serialized fields, QA policy, public documentation, and shared test targets.

N4 yields are never an S4 input. No experimental result may be emitted while
canonical config status is blocked or any upstream authority is absent.

## Published artifacts

### N3 acceptance handoff

The existing atomic directory remains exactly:

```text
results/physics/normalization/handoffs/<acceptance_release_id>/
├── acceptance_v1.csv
├── acceptance_phi_response_v1.csv
└── acceptance_qa.json
```

### S4 fit evidence

S4 publishes one new immutable directory:

```text
results/physics/polarization_fits/<fit_release_id>/
├── azimuth_counts_v1.csv
├── sigma_fit_v1.csv
└── sigma_fit_qa.json
```

Publication uses a sibling staging directory followed by one atomic rename.
Existing destinations, symlinks, incomplete triplets, extra files, legacy
root-level files, and paths outside the repository are rejected.

### S6 release

S6 remains exactly three files at `results/physics/polarization/`:

```text
sigma_v1.csv
sigma_covariance.npz
polarization_qa.json
```

S6 references one immutable S4 evidence directory and replays its fit. S4
evidence never lives below the exact S6 directory.

## Canonical schema authority

The N3 response schema authority is:

```text
config/schemas/acceptance_phi_response_v1.schema.json
```

It contains `schema_version=1`,
`schema_id=graal.acceptance_phi_response.v1`, the exact ordered CSV columns,
enums, the period `[0, pi)`, normalization definition, covariance equations,
and matrix-completeness rules. Canonical polarization config and N3 QA both
record its repository-relative path, exact SHA-256, and approval ID
`N3-MASS-PHI-RESPONSE-V1-2026-09-13`.

The schema file is an authority, not a generated artifact. Changing any field,
equation, enum, bin-coverage rule, or tolerance requires a new schema version,
new approval ID, and joint review.

## N3 response CSV schema

`acceptance_phi_response_v1.csv` has exactly these ordered columns:

```text
schema_version
analysis_version
acceptance_release_id
channel
target
beam_group
Egamma_low
Egamma_high
cos_theta_low
cos_theta_high
observable
selection_id
orientation
true_mass_bin
true_mass_low_gev
true_mass_high_gev
true_phi_bin
true_phi_low
true_phi_high
reco_mass_bin
reco_mass_low_gev
reco_mass_high_gev
reco_phi_bin
reco_phi_low
reco_phi_high
n_generated_true
sumw_generated_true
sumw2_generated_true
n_selected_migration
sumw_selected_migration
sumw2_selected_migration
response_probability
response_stat_uncertainty
validity_mask
input_sha256
config_sha256
```

Rows use canonical ascending order by physical key, orientation, true-mass,
true-phi, reconstructed-mass, and reconstructed-phi indices. Text keys are
non-empty. Numeric bin edges are finite and strictly ordered. Counts are
nonnegative integers. Weight sums and squared-weight sums are finite and
nonnegative. Hashes are lowercase SHA-256.

For each physical key and orientation, true and reconstructed axes use the
same complete mass partition and the same complete azimuth partition. Mass
edges equal the approved fit binning for that energy/observable. Azimuth has
exactly `figure4_comparison.phi_bins` contiguous bins covering `[0, pi)` with
no gaps, overlaps, or implicit wrap. Both `parallel` and `perpendicular` are
mandatory.

Every Cartesian cell is explicit, including zero-migration cells. With
`M=mass_bins` and `P=phi_bins`, each orientation contains exactly
`(M*P)^2` rows. Missing cells never mean zero.

One response matrix is defined per `beam_group` and orientation, not per
`source_period`. It is reused for every source period mapped to that beam group.
N3 QA must prove that the pooled MC configuration, detector conditions, and
selection are valid for every covered period. If period-dependent response is
required, the periods must become distinct beam groups under v1 or the schema
must be versioned; consumers may not silently choose a period-specific matrix.

## Response normalization and weighted covariance

For true cell `i` and reconstructed cell `j`:

```text
R[j,i] = sumw_selected_migration[j,i] / sumw_generated_true[i]
```

Generated values repeat identically across every reconstructed cell belonging
to the same true cell. The sum of selected counts across reconstructed cells
cannot exceed the generated count. With nonnegative weights, the sum of
selected weights cannot exceed the generated weight within approved numerical
tolerance. Every probability lies in `[0,1]`, and
`sum_j R[j,i] <= 1+tolerance`. The difference from one is lost-event
inefficiency; validators never renormalize a column.

Let `G=sumw_generated_true`, `G2=sumw2_generated_true`,
`S2j=sumw2_selected_migration[j,i]`, and `pj=R[j,i]`. The covariance across
reconstructed cells sharing true cell `i` is reconstructed as:

```text
Cov(pj,pk) = (pj*pk*G2 - pk*S2j - pj*S2k) / G^2       for j != k
Var(pj)    = (S2j*(1 - 2*pj) + pj^2*G2) / G^2
```

`response_stat_uncertainty` equals `sqrt(max(Var,0))` within schema tolerance.
Each covariance block must be finite, symmetric, and positive semidefinite
within the approved eigenvalue tolerance. A materially negative variance or
eigenvalue rejects N3.

## Validity masks and thresholds

Allowed masks are exactly:

```text
valid
invalid_zero_generated
invalid_low_effective_statistics
invalid_nonphysical_weights
invalid_incomplete_coverage
```

Every row in one true-cell block carries the same mask. A releasable physical
bin requires every true-cell block and both orientations to be `valid`. Invalid
blocks remain serialized; they are never dropped or converted into zeros.

`minimum_generated_effective_events_per_true_phi`, probability tolerance,
uncertainty tolerance, and covariance eigenvalue tolerance live in approved
canonical config. Effective events are `G^2/G2`; zero `G2` is invalid.

The canonical `response_validation` object defines exactly:

```text
minimum_generated_effective_events_per_true_phi
probability_absolute_tolerance
uncertainty_absolute_tolerance
uncertainty_relative_tolerance
covariance_eigenvalue_absolute_tolerance
finite_difference_relative_step
finite_difference_absolute_step
replay_absolute_tolerance
replay_relative_tolerance
```

Every value is finite and nonnegative; event minimum and both finite-difference
steps are strictly positive. No CLI override may weaken these limits.

## N3 trust anchor

`acceptance_qa.json` remains schema v1 and valid only when it records:

- release ID and producer Git commit;
- exact hashes of both acceptance CSV files;
- Gate 0 handoff hash and N2 reconstruction-inventory hash;
- response-schema path, schema SHA-256, and approval ID;
- count checks, matrix checks, weighted covariance checks, and closure, each
  with `valid=true`;
- `weighted_covariance_checks` also carries mandatory exact booleans
  `shared_mc_across_blocks=false` and `cross_block_covariance=false`; missing,
  non-boolean, or true claims reject schema v1;
- overall `valid=true`.

Canonical polarization config records `acceptance_qa_sha256`. Because N3 QA
hashes both CSVs and the schema authority, this digest transitively anchors the
complete N3 publication. Replacing any byte under an existing release ID fails
validation. Corrections require a new release ID and newly approved digest.

## Portable serialized paths

Every serialized path in config, Gate 0, reconstruction inventories, N3 QA,
S4 QA, S6 QA, and file records is a canonical repository-relative POSIX path.
Absolute paths, empty components, `.`, `..`, backslashes, duplicate lexical
forms, paths outside the repository, symlinks, and non-regular files are
rejected. One shared validator in `08_polarization/contracts.py` implements
this rule; specialized readers do not duplicate weaker variants.

## Azimuth-count schema

`azimuth_counts_v1.csv` contains one row per physical key, source period,
orientation, bootstrap replica, reconstructed-mass bin, and reconstructed-
azimuth bin. Exact columns are:

```text
schema_version
analysis_version
fit_release_id
bin_set_id
channel
target
beam_group
source_period
Egamma_low
Egamma_high
cos_theta_low
cos_theta_high
observable
selection_id
orientation
replica_id
reco_mass_bin
reco_mass_low_gev
reco_mass_high_gev
reco_phi_bin
reco_phi_low
reco_phi_high
observed_count
exposure
beam_polarization
beam_polarization_variance
gate0_handoff_sha256
n2_reconstruction_sha256
state_mapping_sha256
compton_source_sha256
config_sha256
input_sha256
```

Counts are nonnegative integers built directly from N2 events carrying
`RunNumber`, `Polarization`, and `Xstrip`. `source_period` and orientation come
only from approved state mapping. Exposure comes from valid observable-run
flux. Beam polarization and variance come from the approved period-specific
Compton source. Every expected reconstructed mass-and-azimuth cell is explicit,
including zero-count cells. Counts from N4 yields are rejected by provenance
and cannot satisfy this schema.

`replica_id=0` is the nominal sample. IDs `1..B` are deterministic Poisson(1)
bootstrap replicas. Config fixes `B`, bootstrap algorithm version, and seed;
`B` must exceed the full published Sigma-vector dimension. For every N2 event,
the stable event key is the N2 file SHA-256, tree name, and zero-based entry
index. SHA-256 of algorithm version, seed, replica ID, and event key is mapped
to a uniform variate and then through the Poisson(1) inverse CDF. The same
event multiplier is used for all three pair observables, orientations, and
derived bins. This preserves cross-observable correlations without serializing
ROOT events. All replica grids are complete and ordered; missing replica cells
never mean zero.

## Forward-folded likelihood

Release fitting has one public boundary:
`fit_sigma_forward_folded(*, authority: CountAuthority, replica_id=0)`. It
accepts no caller-provided count table, config, or response. The entry point
reloads the loader-sealed authority from canonical paths, builds counts
internally from its authenticated N2 ROOT inventory, then reloads and compares
the full transitive authority fingerprint before invoking the numerical fit.
The resulting count value graph must contain exact immutable table, row, and
grid types.

The private `_fit_sigma_forward_folded_core(counts, response, *, config,
replica_id=0)` supports synthetic tests, controlled Task 6 response
perturbations, and S6 replay of independently authenticated serialized
evidence. It is not an S4 release interface and cannot establish provenance
from caller objects.

For orientation/period group `o`, reconstructed cell `r`, true-mass bin `m`,
and true-azimuth bin `i`:

```text
mu[o,r] = F[o] * sum_(m,i) R[o,r,(m,i)] * lambda[m]
          * delta_phi[i]/pi
          * (1 + sign[o] * P[o] * Sigma[m] * C[i])
```

Here `lambda[m] > 0` is the unpolarized true-mass yield,
`Sigma[m] in [-1,1]`, and:

```text
C[i] = (sin(2*phi_high) - sin(2*phi_low))
       / (2*(phi_high - phi_low))
```

The fit maximizes the joint Poisson likelihood across both orientations, all
periods, reconstructed mass bins, and reconstructed azimuth bins for one
observable and kinematic bin. Exposure is not replaced by a free
orientation-scale nuisance. Approved exposure uncertainty enters S5/S6
systematics. Fit failure, non-finite expectation, insufficient rank, boundary
pathology, incomplete response coverage, or failed residual QA rejects S4.

The fitted parameter vector contains every `Sigma[m]` and `log(lambda[m])`.
The Hessian/Fisher covariance preserves correlations created by mass migration.
`sigma_fit_v1.csv` publishes the ordered Sigma estimates, statistical
uncertainties, nuisance yields, fit identifiers, deviance contributions, event
counts, and exact input/config hashes.

Nominal fitting uses only `replica_id=0`. Every bootstrap replica is then fit
with identical response, initialization, bounds, and tolerances. The sample
covariance of the ordered Sigma vectors is the published statistical covariance.
Because each event receives one shared multiplier before all observables are
projected, this matrix preserves correlations within and between the three
observables. Hessian covariance remains a named fit diagnostic and must agree
with bootstrap diagonal uncertainties within approved closure limits; it is not
substituted for the release covariance. Failed replicas above the approved
fraction, inadequate replica rank, non-finite covariance, or loss of positive
semidefiniteness rejects S4.

## Response-statistical propagation

S4 first fits the nominal response. For each true-cell response covariance
block it performs a deterministic eigendecomposition, orders eigenvectors by
descending eigenvalue with a fixed sign convention, discards only eigenmodes
below the approved numerical tolerance, and finite-differences the full fitted
Sigma vector along each retained mode. Steps are config-approved and use
bound-aware one-sided differences when required. Physical endpoint checks use
the approved probability absolute tolerance, including the column-sum limit
`1 + probability_absolute_tolerance`. The resulting Jacobian action
accumulates:

```text
C_response = J * C_R * J^T
```

Blocks from disjoint physical bins and independently generated MC samples are
independent. A producer using shared MC across such blocks must publish an
explicit cross-block covariance under a future schema version; v1 rejects a QA
claim of shared samples. These claims come only from the byte-authenticated N3
QA snapshot: its loader-sealed typed scope is retained by `AcceptanceHandoff`,
transported by `CountAuthority`, and required by response propagation with the
same config-pinned QA SHA-256. `C_response` is a named S6 systematic source and
is not folded into statistical covariance.

## S4 evidence and deterministic replay

`sigma_fit_qa.json` records:

- schema version, fit release ID, analysis version, producer commit, and valid;
- hashes of counts and fit CSVs;
- N3 release ID, N3 QA hash, response CSV hash, response-schema hash, and
  approval ID;
- config, Gate 0, N2 inventory, state-map, Compton, and flux hashes;
- optimizer name/version, bounds, tolerances, finite-difference step, and
  deterministic initialization;
- ordered bin keys, fitted nuisance values, expected counts, deviance,
  statistical covariance, and response covariance;
- convergence, rank, residual, closure, sign, and response-propagation QA.

S6 validation loads exact hashed bytes and independently repeats response
parsing, count parsing, forward fit, expected-count construction, deviance,
all bootstrap fits, statistical covariance, and response-covariance
propagation. Replayed Sigma, nuisance parameters, expected counts, deviance,
and covariance matrices must match S4 evidence within approved absolute and
relative tolerances. A literal claim such as
`response_application=forward_folded` has no authority without successful
replay.

Canonical S4 invocation is:

```bash
python 08_polarization/fit_sigma.py \
  --acceptance-handoff results/physics/normalization/handoffs/<acceptance_release_id>/acceptance_qa.json \
  --reco-inventory results/reconstruction/inventory.json \
  --config config/physics/polarization_v1.json \
  --fit-release-id <fit_release_id> \
  --output-root results/physics/polarization_fits
```

All inputs are explicit, repository-relative paths. Defaults may point to
canonical authorities but may not discover newest releases by directory scan.

## Canonical config release gate

Before S4 or S6 can pass, canonical config must have:

```text
schema_version = 1
analysis_version = polarization-v1
status = approved
blocked_reasons = []
```

Its acceptance section must match N3 release ID, handoff directory, N3 QA hash,
schema authority path/hash, approval ID, and at least two distinct reviewers.
Config analysis version must equal counts, S4 fit, S4 QA, S6 CSV, and S6 QA.

Repository config remains `blocked` until real Gate 0, state mapping, Compton
sources, N2 reconstruction, N3 triplet, QA thresholds, and shared P0 interface
exist. Schema approval alone never changes top-level release readiness.

## Compatibility and failure behavior

The current scalar-acceptance `fit_sigma_binned` remains available only for
synthetic diagnostic comparison. Its output cannot populate S4 evidence or
pass S6 validation. Existing N3 files lacking schema authority, joint mass-phi
axes, complete cells, approved masks, N3 QA digest anchoring, or portable paths
fail closed. No automatic migration or inference is allowed.

All CLIs return `0` only for complete valid publication, `1` for completed
runtime/QA rejection, and `2` for usage errors that publish nothing. Failure
never overwrites an existing artifact or leaves a partial destination.

## Testing and acceptance

Implementation follows test-driven development. Required tests cover:

1. exact schema columns, ordering, enums, and content-addressed authority;
2. complete joint mass-phi grids for both orientations;
3. normalization, explicit zero cells, loss inefficiency, masks, and thresholds;
4. weighted sandwich covariance, including nonuniform weights and PSD rejection;
5. portable-path rejection across every serialized record reader;
6. N3 wholesale replacement under the same release ID;
7. canonical config schema, status, blockers, and analysis-version binding;
8. Asimov Sigma recovery with off-diagonal mass and azimuth migration;
9. sign inversion, insufficient-rank, boundary, and failed-convergence cases;
10. response-covariance propagation against analytic or high-statistics reference;
11. deterministic shared-event bootstrap and nonzero cross-observable covariance;
12. S4 replay equality and tampering of counts, response, fit, expected counts,
    nuisance parameters, deviance, and covariance;
13. atomic CLI publication and no-overwrite behavior;
14. proof that N4-derived counts cannot satisfy S4 provenance;
15. full `make verify`, `make test`, Graphify refresh, artifact inventory, path
    scan, and two-owner re-review before merge.

No real physics artifact is created by tests. Fixtures use temporary synthetic
data and deterministic seeds.
