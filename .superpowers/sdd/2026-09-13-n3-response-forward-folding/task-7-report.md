# Task 7 — Atomic S4 Evidence CLI

## Scope

Implemented exact immutable S4 evidence publication and strict independent
reading. No N4 yield, real physics output, Graphify refresh, or S6 release
change was introduced.

## Published contract

`fit_sigma.py` accepts only explicit canonical repository-relative config,
N2 inventory, N3 QA, fit release ID, and output-root paths. It reloads the
loader-sealed `CountAuthority`, builds counts from authenticated N2 ROOT bytes,
runs the authority-only nominal fit, and verifies that the private replay over
the serialized count table is byte-equal. It then fits replicas `1..B` in
order, validates the full shared-event Sigma matrix with Task 5 bootstrap QA,
and propagates Task 6 response covariance using the loader-sealed N3 scope.

Publication writes this exact triplet into an owned sibling staging directory:

- `azimuth_counts_v1.csv`
- `sigma_fit_v1.csv`
- `sigma_fit_qa.json`

The staged bytes are independently validated before one rename. Existing
destinations are rejected. Pre-rename failures remove only the owned staging
directory. Fit release IDs are one canonical path component, closing a
test-proven path-traversal failure.

CLI exit semantics are `0` valid publication, `1` runtime/QA rejection, and
`2` usage failure. `Makefile` exposes `fit-sigma` through `$(PYTHON)` and has no
newest-release discovery.

## Evidence schema and reader

`fit_evidence.py` publishes `FIT_EVIDENCE_FILENAMES`, `FitEvidence`, and
`validate_fit_evidence`. The fit CSV stores canonical bin identity, Sigma,
bootstrap/Hessian uncertainty and variance, nuisance log-yield, and response
variance. QA stores exact CSV hashes, full authenticated authority records,
optimizer implementation/version/options/bounds, bootstrap IDs and every
successful global Sigma vector, statistical covariance and Hessian ratios,
complete nominal fit arrays, and response covariance with retained modes and
endpoint refits.

The reader rejects extra/missing/link/legacy placement, noncanonical paths,
changed or coherently rehashed CSV semantics, malformed arrays/order/shapes,
non-PSD or rank-deficient covariance, incomplete bootstrap coverage, failed
ratio QA, inconsistent residual/deviance arrays, invalid response-mode
reconstruction, detached config/N2/N3/Gate0/state/Compton/flux bytes, and N4
claims. It reloads the complete `CountAuthority` graph and compares the exact
serialized authority payload; literal provenance strings are insufficient.

Reconstruction inventories now publish
`artifact_kind=n2_metadata_reconstruction`; staged S4 validation requires that
authenticated byte. Existing inventory loading remains compatible outside the
S4 release boundary.

## TDD evidence

1. Initial collection RED: `fit_sigma` and `fit_evidence` modules missing.
2. Exact-triplet and usage GREEN: 2 passed.
3. Round-trip/tamper and atomic publication GREEN: 10 passed.
4. Inventory-kind RED: missing `artifact_kind`; GREEN after builder binding.
5. Make-target RED: `fit-sigma` absent; GREEN after supported-Python target.
6. Path traversal RED: `../escape` reached temporary-directory construction;
   GREEN after single-component release-ID validation.
7. Final focused Task 7 suite: 17 passed.
8. Coupled Task 1–7 suite: 273 passed.

## Verification

- `make verify PYTHON=/opt/local/bin/python`: exit 0; 334 common tests and 413
  root-free polarization tests passed; manifest and artifact inventory valid.
- `make test PYTHON=/opt/local/bin/python`: PyROOT available; 870 tests passed.
  Four pre-existing legacy Figure 4 config-fixture failures remain, already
  reserved for Task 8; none involves Task 7 evidence or inventory behavior.
- `git diff --check`: clean.

## Self-review

Exact staging ownership, no-overwrite behavior, authority reloads, canonical
global order, full bootstrap vectors, named separate covariances, N2-only
provenance, and deterministic JSON/CSV serialization were checked against the
Task 7 brief and approved design. Task 8 can consume `FitEvidence` and replay
its stored nominal, bootstrap, and response evidence without ROOT access to the
published directory.
