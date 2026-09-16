# Current Project Wiki Design

## Goal

Replace historical, mixed-language repository documentation with an English,
code-derived description of the current GRAAL analysis pipeline.

## Scope

- Keep `README.md` concise: purpose, prerequisites, editable install, primary
  pipeline command, test command, and wiki link.
- Rebuild `wiki/` navigation around current architecture and operations.
- Preserve detailed physics and stage documentation only when source code,
  tests, configuration, or versioned artifacts support it.
- Remove historical implementation plans and publication roadmap material.
- Correct existing comments and docstrings only where repository refactoring
  made them false or misleading.
- Do not change runtime behavior, command-line interfaces, data formats, or
  user-facing program output.

## Documentation Structure

### Core pages

- `Home.md`: project purpose, supported analysis, short pipeline overview, and
  navigation.
- `architecture.md`: high-level component boundaries and Mermaid dependency
  diagram.
- `repository-structure.md`: tracked source/config/artifact layout and package
  name mapping from numbered directories.
- `pipeline.md`: startup entry point, eight stages, flags, data flow, and
  failure/reuse behavior.
- `data-and-storage.md`: ROOT trees, NPZ/JSON/CSV artifacts, directory
  ownership, persistence, and generated-output policy.
- `configuration.md`: shell environment variables, pipeline flags, manifest,
  channel registry, reconstruction configuration, and model provenance.
- `development.md`: Python/ROOT prerequisites, dependency installation,
  editable package setup, and focused command examples.
- `testing.md`: pytest configuration, test boundaries, ROOT test doubles, and
  `--test-data` integration workflow.
- `architecture-decisions.md`: decisions visible in code, including shared
  physics contracts, ROOT-free cores, explicit artifact schemas, numbered
  stage directories, and fail-loud boundaries.
- `extension-points.md`: code-backed extension seams for channels,
  hypotheses, cuts, reconstruction gates, fit models, plots, binnings, and
  calibration adapters.

### Detailed component pages

- Retain and rewrite pre-analysis, cuts, event selection, Monte Carlo,
  Stage-1 features/training, reconstruction, chi-square pairing, BDT gate,
  kinematic fit, and plotting pages.
- Merge implemented strip-energy/flux behavior into current calibration and
  storage documentation.
- Consolidate repeated commands and schemas into core pages; detailed pages
  link back instead of duplicating them.

### Removed pages

- `wiki/publication-roadmap.md`
- `wiki/strip-energy-flux-design.md`
- `wiki/strip-energy-flux-implementation-plan.md`
- `wiki/physics-channels-survey.md` when claims cannot be derived from current
  repository behavior; code-backed channel registry facts move to Monte Carlo
  and extension documentation.

## Source of Truth

Documentation claims must be traceable to:

- `run_pipeline.sh` for orchestration, defaults, reuse, and failure behavior;
- `pyproject.toml` and `04_bdt_training/requirements.txt` for packaging and
  Python dependencies;
- source entry points and shared modules for responsibilities and interfaces;
- `config/run_manifest.csv` and calibration modules for configuration;
- tests for stable contracts and supported boundary behavior;
- versioned model/plot artifacts for repository-owned generated assets.

Local ignored data directories are not treated as stable repository
structure. Runtime paths documented from executable defaults.

## Architecture Presentation

Use Mermaid only where relationships are otherwise hard to follow:

1. end-to-end data flow from raw ROOT files through plots;
2. package dependency boundaries between shared contracts, stages, and
   runtime adapters.

Tables cover directories, entry points, configuration, and persisted
artifacts. Prose explains non-obvious decisions and failure modes.

## Comment and Docstring Corrections

Update only verified stale statements:

- nine Monte Carlo channels, not six;
- current numbered module/stage references after repository reorganization;
- generated photon pairings, not removed combination tables;
- event preselection checks one forward charged track, not a proven recoil
  baryon.

Avoid new comments that restate implementation.

## Verification

- Run full pytest suite.
- Run pipeline `--help` contract.
- scan README/wiki for Italian text, removed paths, stale stage numbers,
  deleted combination-table references, and links to removed pages;
- validate every local wiki link resolves to a retained page;
- compare documented commands/defaults with source entry points;
- inspect `git diff --check` and final repository diff.
