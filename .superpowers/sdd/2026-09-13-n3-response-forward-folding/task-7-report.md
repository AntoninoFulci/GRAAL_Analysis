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

## Independent-review fix round 1

Regression tests first exposed six concrete bypasses against `b94709c`:
missing CSV release fields, mutable nested QA, coherent `Sigma=2` tampering,
forged response endpoints/derivatives, empty-destination rename replacement,
and absent S4 artifact-inventory discovery.

Fixes:

- reader reruns nominal forward folding from authenticated counts, N3 response,
  approved signs, and release-QA policy. It compares Sigma, nuisance yields,
  Hessian covariance, expected counts, residuals, deviance contributions,
  rank, convergence, and canonical keys;
- `sigma_fit_v1.csv` includes per-bin event count/deviance contribution,
  global deviance/ndof, exact S4 count input/config hashes, and exact N3
  input/config hashes. Reader recomputes every value;
- reader reruns response propagation from authenticated N3 covariance blocks
  and sealed covariance scope. Canonical mode IDs/order, eigenvalues, steps,
  schemes, endpoint fits, derivatives, and final covariance must match;
- release QA binds minimum-event and maximum-deviance policy, parameter bounds,
  approved orientation signs/reviewers, and authenticated N3 closure. Returned
  QA uses recursive immutable mappings/tuples;
- publication uses destination-specific exclusive lock. Final authority reload
  and staged validation run inside lock. Kernel no-replace rename uses macOS
  `renamex_np(RENAME_EXCL)` or Linux `renameat2(RENAME_NOREPLACE)`; Windows
  rename already rejects existing destinations, and unsupported POSIX systems
  fail closed. Empty destination created during race remains untouched. Cleanup
  removes only owned staging and inode-matched empty lock;
- artifact inventory accepts S4 releases only with exact canonical triplet;
  partial, extra, legacy, and symlinked layouts reject generation.

Fresh verification:

1. focused evidence/CLI/inventory: 37 passed;
2. root-free polarization suite: 419 passed;
3. `make verify`: syntax and 2,711-run manifest valid; 335 common and 419
   polarization tests passed; artifact inventory verified; diff check clean;
4. `make test`: 878 passed with PyROOT; four pre-existing Task 8 legacy
   Figure-4 config-fixture failures remain. No Task 8 file changed;
5. Graphify snapshot and `ARTIFACTS.json` regeneration remain Task 9. Runtime
   inventory recognition and tests are included here.

## Independent-review fix round 2

Regression tests against `cf2c02f` reproduced three remaining publication
hazards: a crashed process left a permanent destination lock, publisher and
inventory disagreed on valid release IDs, and staged bytes could change after
independent validation but before rename.

Fixes:

- user-space publication locks were removed. Kernel no-replace rename is the
  sole publisher serialization boundary. A real two-thread rendezvous at the
  rename syscall proves exactly one publisher succeeds; the other receives an
  overwrite rejection. Existing empty-destination race coverage remains;
- stale `.publish.lock` state is neither consulted nor removed. It cannot block
  publication, and foreign state is never cleaned up by this command;
- `scripts/s4_release_id.py` defines one shared portable grammar:
  `[A-Za-z0-9][A-Za-z0-9._-]*`. Publisher, evidence reader, and inventory use
  it. Therefore `.fit-v1` is intentionally invalid: leading dots are reserved
  for owned staging. Whitespace, slash, backslash, dot segments, absolute paths,
  and traversal are rejected consistently;
- inventory ignores only strict publisher staging names
  `.<valid-release-id>.staging-<8 tempfile chars>` that are real directories.
  Arbitrary dot entries, stale locks, symlinks, and malformed releases fail;
- publication snapshots exact triplet bytes before independent validation and
  compares a second stable snapshot plus freshly reloaded authority fingerprint
  immediately before kernel rename. Each snapshot hashes bytes read from an
  open file descriptor, compares pre/post `fstat`, then re-stats every pathname
  and exact directory membership. Normal concurrent write, replacement, link,
  truncation, or entry mutation during final hashing therefore fails. No claim
  is made against a privileged adversary able to alter bytes after the final
  checks and before the syscall; staging is publisher-owned private state.

Fresh verification:

1. focused publisher/reader/count/inventory: 128 passed;
2. `make verify PYTHON=/opt/local/bin/python`: exit 0; manifest valid, 339
   common and 433 root-free polarization tests passed, saved inventory valid;
3. `make test PYTHON=/opt/local/bin/python`: 896 passed with PyROOT; exactly
   four known Task 8 legacy Figure-4 fixture failures remain;
4. `git diff --check`: clean.

## Independent-review fix round 3

Regression tests executed both documented file entrypoints with `PYTHONPATH`
removed, first from repository root and then from an unrelated working
directory. Both initially failed before argument parsing because direct file
execution exposed only the script directory on `sys.path`, while the shared
release-ID validator is canonically owned by `scripts/s4_release_id.py`.

Both entrypoints now add their deterministic repository root only when Python
is running them as un-packaged files (`__package__` is empty). Module imports
retain their normal package path, and publisher, evidence reader, and inventory
still consume one release-ID grammar source.

Fresh verification:

1. exact direct-entrypoint regressions: 2 passed from both working directories;
2. coupled CLI/evidence/inventory suite: 57 passed;
3. `make verify`: exit 0; manifest valid, 340 common and 434 root-free
   polarization tests passed, saved inventory valid;
4. both requested `/opt/local/bin/python ... --help` commands with
   `PYTHONPATH` removed: exit 0;
5. `git diff --check`: clean. No Task 8 file changed.
