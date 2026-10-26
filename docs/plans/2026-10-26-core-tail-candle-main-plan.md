# Core/Tail Candle Test on Current Main Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the equal-event eta/pi0 core-versus-tail candle stability test to the repository's current Stage-08 extraction and campaign workflow.

**Architecture:** A pure selector creates deterministic balanced event samples after normal profile/exposure filtering. The existing extraction workflow fits them as additional named samples, records a strict ROOT provenance contract, and emits profile and combined diagnostics without changing the nominal result.

**Tech Stack:** Python, NumPy, PyROOT, Matplotlib, pytest, current `graal_workflow` planner.

**Spec:** `docs/plans/2026-10-26-core-tail-candle-main-spec.md`

## Global Constraints

- Core is the inclusive raw-mass rectangle around shared `M_ETA` and `M_PI0`, half-width `0.05` GeV in both axes.
- Tails are the finite-mass OR-complement; non-finite masses enter neither sample.
- Keep all tails and sample core without replacement using seed `20261024`, preserving source order.
- Apply the split independently to UV and VIS after the normal profile/exposure selection.
- Preserve nominal extraction behavior when candle flags are absent; do not commit generated ROOT/PDF artifacts.

## Review Focus

- An event exactly on any rectangle boundary belongs to core.
- NaN or infinite eta/pi0 masses are excluded and counted, never classified as tails.
- Seed validation rejects booleans and negative/non-integral values; sampling is repeatable and source ordered.
- Malformed or mixed legacy/new candle provenance fails closed without weakening current ROOT contract checks.
- Equal global event counts do not require matching fitted-bin coverage; plotting tolerates independently missing bins.

---

### Task 1: Pure balanced core/tail selector

**Files:**
- Modify: `08_observable_extraction/io/reconstructed_events.py`
- Test: `08_observable_extraction/tests/test_reconstructed_events.py`

**Interfaces:**
- Consumes: `EventArrays`, shared `M_ETA`, `M_PI0`.
- Produces: immutable `CandleSplit(core, tails, full_core_count, tail_count, excluded_nonfinite_count)` and `split_candle_core_tails(events, half_width_gev, seed)`.

- [ ] **Step 1: Write failing selector tests** for inclusive boundaries, OR-complement tails, non-finite exclusion, deterministic order-preserving balance, seed/width validation, and explicit empty/imbalanced failures containing `core=N tails=N`.
- [ ] **Step 2: Run** `python -m pytest -q 08_observable_extraction/tests/test_reconstructed_events.py` and confirm failures are due to the absent interface.
- [ ] **Step 3: Implement the minimal immutable split contract and selector.**
- [ ] **Step 4: Re-run the focused test and confirm green.**
- [ ] **Step 5: Commit** selector and tests as `feat: add balanced candle event split`.

### Task 2: Stage-08 extraction and strict ROOT provenance

**Files:**
- Modify: `08_observable_extraction/beam_asymmetry.py`
- Modify: `08_observable_extraction/workflow.py`
- Modify: `08_observable_extraction/io/root_input.py`
- Test: `08_observable_extraction/tests/test_beam_asymmetry_cli.py`
- Test: `08_observable_extraction/tests/test_root_input.py`
- Test: `08_observable_extraction/tests/test_extraction.py`

**Interfaces:**
- Consumes: `split_candle_core_tails`; existing `extract_sample`, ROOT payload, energy/best-binning contracts.
- Produces: CLI flags `--candle-mass-half-width` and `--candle-balance-seed`; fitted samples `raw_bdt_core` and `raw_bdt_tails`; `CandleContract` exposed as `RootOutputContract.candle`.

- [ ] **Step 1: Add failing CLI/workflow tests** proving candle mode is optional, requires nominal `raw_bdt`, rejects sideband mode, preserves nominal points, fits both extra samples, and errors if either sample has no fitted points overall.
- [ ] **Step 2: Add failing ROOT-reader tests** for a valid count-bearing round trip and rejection of incomplete, duplicate, unknown, semantically inconsistent, or mixed legacy/new candle fields while retaining current grid/best-binning validation.
- [ ] **Step 3: Run the three focused test files and confirm expected red failures.**
- [ ] **Step 4: Implement parser flags, post-selection splitting/extraction, provenance emission, and strict `CandleContract` parsing.**
- [ ] **Step 5: Run the focused tests and all Stage-08 tests; confirm green.**
- [ ] **Step 6: Commit** as `feat: extract candle core and tail asymmetries`.

### Task 3: Candle diagnostics and UV/VIS composition

**Files:**
- Create: `08_observable_extraction/plotting/candle.py`
- Modify: `08_observable_extraction/workflow.py`
- Modify: `08_observable_extraction/combine_profiles.py`
- Modify: `scripts/plot_campaign.py`
- Test: `08_observable_extraction/tests/test_candle_plotting.py`
- Test: `08_observable_extraction/tests/test_combine_profiles.py`
- Test: `tests/test_plot_campaign.py`

**Interfaces:**
- Consumes: candle sample points and `RootOutputContract.candle`.
- Produces: `candle_mass_plane.pdf`, per-profile and combined `comparison_candle_{ratio,likelihood}.pdf`.

- [ ] **Step 1: Write failing plotting tests** for the complete finite mass plane, full ±0.05 rectangle, count validation/annotation, Core/Code labels, both estimators, and independently missing fitted bins.
- [ ] **Step 2: Write failing composition/replot tests** requiring both sample names plus valid provenance, identical UV/VIS scientific semantics, and allowing different counts/seeds per profile.
- [ ] **Step 3: Run the focused plotting/composition tests and confirm red failures.**
- [ ] **Step 4: Implement the plotting module and conditional workflow/combine/campaign integration.**
- [ ] **Step 5: Run focused tests and all Stage-08/campaign plotting tests; confirm green.**
- [ ] **Step 6: Commit** as `feat: plot candle core tail comparisons`.

### Task 4: Current workflow planner and operator documentation

**Files:**
- Modify: `graal_workflow/planning.py`
- Modify: `tests/test_run_pipeline.py`
- Modify: `README.md`
- Create: `docs/runbooks/core-tail-candle-test.md`

**Interfaces:**
- Consumes: Task-2 CLI flags.
- Produces: both UV and VIS extraction commands explicitly carry width `0.05` and seed `20261024`.

- [ ] **Step 1: Add a failing planner test** asserting both profile commands contain the exact candle width and seed once and existing energy/best-binning arguments remain intact.
- [ ] **Step 2: Run the planner test and confirm it fails because the flags are absent.**
- [ ] **Step 3: Add the planner flags and concise README/runbook documentation, including outputs and the distinction between global event balance and fitted-bin coverage.**
- [ ] **Step 4: Run planner, CLI, and documentation-adjacent tests; confirm green.**
- [ ] **Step 5: Commit** as `docs: enable and document candle campaign test`.

### Task 5: Branch verification and pull request

**Files:**
- Verify only; do not add generated campaign artifacts.

**Interfaces:**
- Consumes: completed Tasks 1-4.
- Produces: reviewed feature branch and pull request against `main`.

- [ ] **Step 1: Run all focused candle, workflow, ROOT, plotting, and planner tests.**
- [ ] **Step 2: Run the complete repository test suite from the isolated clone and record exact results.**
- [ ] **Step 3: Inspect `git diff --check`, branch diff/stat, and tracked files; ensure no data, results, caches, or environments are staged.**
- [ ] **Step 4: Request one independent whole-branch review; fix only Critical/Important findings with tests and re-run verification.**
- [ ] **Step 5: Push the feature branch and create a PR against `main` with scientific definition, tests, and compatibility notes.**
