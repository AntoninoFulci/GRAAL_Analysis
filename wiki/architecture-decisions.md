# Architectural decisions

This page records decisions visible in current source and tests. It is not a
history of previous implementations.

## Numbered directories, clean package names

Physical directories communicate pipeline order. `pyproject.toml` maps them to
valid Python names because identifiers cannot begin with digits. Tests verify
responsibility subpackages remain importable after refactoring.

## Shared physics definitions

Masses, hypotheses, channels, photon pairing, and Stage-1 features live in
`graal_common`. Training, inference, reconstruction, and plotting import these
contracts rather than keeping copies. Cross-module tests verify shared feature
identity and exact schema.

## MC channel and analysis hypothesis are separate

`MCChannel` describes generated reaction/file. `Hypothesis` describes two
mesons tested against four observed photons. Some incomplete background final
states cannot choose a hypothesis; callers must provide one instead of code
guessing silently.

## Signal prior is not signal cross-section

ηπ⁰ signal cross-section is analysis output, so registry does not use it as
training input. Signal/background training balance is explicit
`signal_prior`. Backgrounds retain measured/estimated relative cross-section
weights integrated over measured beam spectrum.

## Beam reweighting is required

Generators sample channel-dependent flat beam ranges. Stage 4 measures beam
spectrum from selected detector data and reweights MC. Feature build fails when
beam spectrum is missing rather than training on incompatible distribution.

## ROOT-free cores, ROOT adapters

Event decisions, pairing, kinematic fit, and plotting kinematics use NumPy and
plain dataclasses. ROOT-specific chain, branch, and file handling stays in
runtime/adapters. This makes physics rules unit-testable without detector
files while keeping native ROOT storage at boundaries.

## Explicit training/runtime artifacts

Stage-1 dataset uses validated eight-key NPZ schema. Runtime bundle uses named
model, threshold, provenance, and metrics contracts. Gate validates provenance
hypothesis before scoring. Old or incomplete artifacts fail loudly.

## χ² and BDT outputs share reconstruction path

Topology guards, pairing, cuts, fit, and branches live in common runtime. BDT
gate is optional injection before pairing. This makes gate intended controlled
difference between comparison samples.

## Fit selection replaces missing-mass selection

Default 6C fit imposes four-momentum conservation, so confidence-level cut
replaces missing-mass window. Disabling fit restores missing-mass fallback.

## Fail-loud data boundaries

Commands reject missing input directories, empty file sets, missing trees,
missing required cuts, malformed manifests, incompatible model provenance,
and invalid schemas. Silent reuse of stale downstream files is avoided where
input discovery returns zero.

## Separate inputs and rebuilt results

Detector-derived data belongs under `data/`; reconstructed trees and plots
belong under `results/`. Bulk artifacts are ignored. Versioned runtime model
bundle and reference plot remain near owning code because they are required or
reviewed repository assets.

## In-repository wiki is canonical

Markdown under `wiki/` is versioned source. Remote GitHub Wiki is deployment
target updated explicitly by `scripts/sync-wiki.sh`.
