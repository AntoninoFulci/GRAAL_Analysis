# Repository maintenance

- Current technical documentation lives in `wiki/`; keep exactly one project README at the repository root. `docs/` contains only `papers/`, `plans/`, and `reference/`. Retire completed/obsolete operating plans after preserving unique evidence and mapping open scientific work to `wiki/status.md`.
- Preserve raw inputs, the immutable UV+VIS cohort in `data_test/sample/`, detector cuts by period, original papers/bibliography, Fortran, manifests, BDT bundles/provenance and GEANT4 snapshots. Never rewrite historical scientific output to satisfy a new test or metadata contract. Record relocation hashes and update active consumers.
- Inputs/links belong in `data/` and `data_test/`; production output in `results/`, reusable production products in `results/_cache/`. Tests, diagnostics, reports, generated graphs/builds and agent work use explicit `results_test/<campaign>/` roots (active Graphify output is `graphify-out/`). Set bytecode off, absolute `TMPDIR`/`MPLCONFIGDIR`, pytest `--basetemp` and `cache_dir` there.
- Preserve the scientific owner boundaries and established cuts, 26-feature order, flux/exposure policy, ratio/likelihood conventions, binnings and finite-bin divisors. New reconstruction provenance is schema 2 / `pairing_missing_mass`. Calibration, statistical inference and theory fits remain valid scientific operations.
- Stage 09 theory runs only on explicit request with declared inputs after stage 08. Do not launch long scientific jobs or modify existing farm campaigns for maintenance. Keep dated diagnostic evidence distinct from production validation and live queue state.
- Validate the affected boundary and required integration checks, retain logs, then review the diff. Coordinate file ownership when working with others; do not revert unrelated work. Git integration/publication belongs to the designated integrator. Never use reset-hard, clean, force push or worktree deletion to discard unpreserved sources; verify backups before removing refs.

## Graphify

When the user types `/graphify`, read and use the installed graphify skill (`~/.Codex/skills/graphify/SKILL.md`, or its installed equivalent) before other work. Treat a stale graph as historical evidence; rebuild from the current corpus before claiming current architecture. Exclude generated/archived instructions and graph self-ingestion.

## Context7

For library, framework, SDK, API, CLI-tool or cloud-service documentation (syntax, configuration, migration, setup or library-specific debugging), use Context7 even when the answer seems familiar. Start with `resolve-library-id` using the library and question unless an exact `/org/project` ID is supplied. Choose by exact name, relevance, source reputation, snippet coverage and benchmark score; retry a poor match. Then use `query-docs` for the full question, one concept per query, and answer from the retrieved documentation. General refactoring, scripts written from scratch, business-logic debugging, code review and programming concepts do not require Context7.
