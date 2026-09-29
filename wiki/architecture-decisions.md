# Architectural Decisions

The current structure separates shared contracts, numerical cores, ROOT
adapters, command entry points, and persisted artifacts. These boundaries are
enforced by package layout and tests rather than by a central service.

## Shared Contracts

`graal_common` owns facts that must agree across multiple stages:

- channel and hypothesis registries;
- meson masses, cross sections, and Compton calculations;
- photon-pair enumeration and scoring inputs;
- ROOT tree/vector helpers;
- filesystem publication helpers;
- Stage-1 feature ordering and artifact provenance schemas.

Consumers import these definitions instead of copying constants or lists. A
new physics channel therefore changes one registry and its tests, after which
generation, status reporting, weighting, and hypothesis resolution observe the
same entry.

**Consequence:** shared modules must remain lightweight and cannot import a
stage-specific runtime merely for convenience.

## ROOT-Free Cores

Numerical decisions are kept separate from storage adapters where practical.
`reconstruction.core` receives arrays and structured event inputs; ROOT-facing
code in `reconstruction.runtime` opens trees, translates objects, parses CLI
options, and writes results. Observable extraction similarly separates models,
estimators, background correction, and covariance from ROOT input/output.

This boundary makes physical calculations testable with small arrays and avoids
requiring live ROOT files for every unit test. ROOT adapters still receive
integration tests because tree names, branches, and object ownership are part
of the supported boundary.

**Consequence:** new numerical logic belongs in a core module unless it
intrinsically operates on a ROOT object.

## Explicit Artifacts

Stage boundaries are persisted rather than hidden in process memory. Important
examples include:

- `h80`, `h85`, and `mc` ROOT trees;
- beam-spectrum and Stage-1 dataset NPZ files;
- hyperparameter JSON and the model/threshold/provenance bundle;
- reconstructed and sideband ROOT trees;
- calibration CSV, QA JSON, and calibrated ROOT objects;
- observable ROOT files, covariance data, diagnostics, and PDFs.

Artifact schemas include enough metadata to reject incompatible reuse. The
Stage-1 runtime bundle is deliberately three-part: model weights alone cannot
establish the feature schema, threshold, or physics hypothesis used in
training.

**Consequence:** changing a persisted schema requires updating its producer,
consumer, validation, provenance, tests, and documentation together.

## Fail-Loud Boundaries

Scientific pipelines can produce plausible-looking output from incompatible
or stale input, so trust boundaries prefer contextual failure over silent
fallback. Examples include:

- setup refusing to overwrite an existing data path or mismatched link;
- event selection checking tree and branch presence before processing;
- MC status distinguishing internal errors from genuinely missing channels;
- the Stage-1 gate refusing incomplete bundles or hypothesis mismatches;
- calibration rejecting malformed ROOT structure, invalid axes, unsafe output
  placement, or numerically invalid fits;
- observable estimators rejecting missing strata and nonphysical domains.

Warnings are reserved for conditions whose documented policy permits continued
analysis, such as old-but-present MC files or selected calibration quality
findings. Pages must state whether each condition warns or fails.

## Numbered Directories, Valid Package Names

Numbers keep processing order visible to humans, while `pyproject.toml` maps
directories to valid Python package identifiers. This avoids a second wrapper
tree and keeps source beside stage artifacts and tests.

**Consequence:** a new numbered Python stage must update package mapping,
installation checks, test paths, repository-layout tests, and documentation.

## Atomic Publication

Where partial output could be mistaken for a valid run, producers write to a
staging location, validate the result, and only then replace the destination.
The previous valid output survives failures before publication.

**Consequence:** maintainers must not simplify staged writes into incremental
updates without preserving rollback behavior and tests.

## Tests as Boundary Specifications

Tests encode cross-stage expectations: feature order, runtime artifact names,
package imports, tree contracts, calibration validation, reconstruction
branches, and result schemas. They are evidence for documentation and must be
read alongside producers and consumers.

**Consequence:** a green unit test for an internal helper is insufficient when
the change crosses a persisted or package boundary; the relevant contract or
integration test must also pass.
