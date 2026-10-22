# Cross-section extraction implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Provide a tested extraction of total and invariant-mass cross sections from reconstructed data, measured flux and independently supplied detector response, with explicit scientific readiness and Ajaka comparison.

**Architecture:** Stage 08 owns numerical inference, input validation and ROOT/PDF products. Stage 03 owns response counting from matched generated/selected MC identities. GEANT3 is an isolated, digest-pinned external resource; its historical cards and formats must not be mistaken for a ready signal calibration.

**Tech Stack:** Existing Python, NumPy, ROOT and matplotlib; Docker/OrbStack for the historical environment. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-21-cross-section-extraction-design.md`

## Global Constraints

- Baseline no 6C; preserve existing selections, quality exclusions and unrelated working changes.
- Flows are assumed already absolute/corrected per user; record this assumption.
- Target density and uncertainty have no invented defaults. Missing inputs prevent physical extraction.
- MC generated denominator includes lost events; identity matching rejects duplicates and unknown selected IDs.
- Keep POL1/POL2 distinct, model their opposite cos(2φ) terms, and use integrated photon flux without dividing by ΔE.
- No synthetic flux adoption. No normalization to Ajaka. ROOT plus PDFs are public result products.
- Unknown systematic components remain missing, never zero. Outputs remain conditional until detector/normalization validation exists.

## Review Focus

- Empty/zero-support MC cells and rank-deficient response must fail rather than fabricate a total.
- Unequal polarization exposures, target densities and periods must preserve cross-section normalization.
- Shared MC and normalization uncertainties must remain correlated between bins and samples.
- Zero-yield runs still contribute exposure; data without matching measured exposure are explicitly audited.
- Missing background corrections, real target calibration or reference bin definitions cannot silently become measured results.

## Task 1: Numerical response and extraction

Files: `03_mc_simulation/response.py`, `03_mc_simulation/tests/test_response.py`, `08_observable_extraction/core/cross_section.py`, `08_observable_extraction/tests/test_cross_section.py`.

Interfaces: `count_response(generated_ids, generated_bins, selected_ids, selected_bins, n_bins)` returns generated counts and reconstructed-by-truth counts; `response_probabilities` returns R and column multinomial covariance. `fit_cross_sections(yields, yield_covariance, design)` returns coefficients, covariance, linear estimator and goodness of fit. `design_matrix(response, luminosity, polarization, phi_edges, state)` uses columns for unpolarized cross sections and cos(2φ) nuisance amplitudes.

- [x] Write failing tests for known-σ closure with migrations and unequal H/V, units, split-period invariance, duplicate identities, zero efficiency and rank deficiency.
- [x] Run focused tests and observe failure.
- [x] Implement validated counting, finite-φ integration, GLS and first-order response covariance propagation. No arbitrary regularization or positivity clipping.
- [x] Run focused tests; expected PASS.

## Task 2: Input contracts, real-event preparation and output

Files: `08_observable_extraction/io/cross_section.py`, `08_observable_extraction/cross_sections.py`, `08_observable_extraction/tests/test_cross_section_io.py`.

Consumes Task 1. Inputs: explicit JSON analysis specification pointing to current reconstructed ROOT trees, run manifest, calibrated ROOT flux, response counts and background corrections. Source periods and inclusive run universe remain authoritative. Generated/selected response counting can be supplied as auditable event IDs and cell indices; no current smearing sample is automatically accepted as detector simulation.

- [x] Write failing ROOT fixture integration tests: complete closure, missing target, malformed response, zero-yield run exposure, source/selection mismatch, missing background and missing uncertainty reporting.
- [x] Implement `prepare_analysis(config_path)` and CLI `--config`, `--output-dir`, `--audit-only`; validate all inputs before atomic result publication.
- [x] Write ROOT points/covariances, accepted run/exposure audit, model assumptions, component readiness and input hashes. Add total/differential PDF with units.
- [x] Run integration tests; expected PASS and no output on invalid configuration.

## Task 3: GEANT3 bridge and reference comparison

Files: `03_mc_simulation/geant3.py`, `03_mc_simulation/tests/test_geant3.py`, `resources/geant3/README.md`, `08_observable_extraction/references/` metadata, cross-section plotting/input helpers.

- [x] Implement auditable detector-response preparation CLI from explicit generated/selected event identity tables. Require simulator, selection, geometry, decay and independence provenance.
- [x] Add isolated GEANT3 inspection/smoke workflow, fixed digest/platform, explicit card and output paths; never submit historical qsub wrappers. Inspect signal-channel availability and identify any real blocker rather than using another channel.
- [x] Test Docker argument construction and response-contract failures; run small real environment check where supported.
- [x] Support reference CSV with provenance and declared observable/units; reject Figure 4 Σ as a cross-section reference. Plot overlay without automatic χ² or rescaling.
- [x] Acquire Ajaka Fig.2 numerical points if reliable source/digitization is available; otherwise record missing numerical reference explicitly, without invented data.

## Task 4: Verification, documentation and readiness

Files: `docs/runbooks/cross-sections.md`, `docs/reports/2026-10-21-cross-section-implementation.md`, execution ledger.

- [x] Run meaningful synthetic closure through public CLI, including response migration and nontrivial polarization/acceptance.
- [x] Run focused new tests plus existing observable and MC tests affected by imports/contracts.
- [x] Fresh scientific/code review, fix substantive findings with regression tests.
- [x] Document commands, exact input schemas, available GEANT3 evidence, assumptions and unresolved real-data prerequisites. Do not present synthetic closure as an experimental measurement.

## Execution rulings

- Work in existing feature checkout `codex/dalitz-completion`; new files own this feature and existing user edits remain untouched. Additional worktree/approval would duplicate already-authorized work and omit uncommitted design/resources.
- No commit/push/production campaign needed for reviewable local implementation. Keep changes visible in the user's checkout.
- GEANT3 source inspection currently reveals no verified direct pηπ⁰ channel and no run→target map. Implement all independent extraction/response infrastructure and expose those prerequisites explicitly; do not invent detector calibration.

## Esito dell'esecuzione

Infrastruttura e verifiche completate; stato fisico resta condizionale.
362 test passati nelle due suite separate; revisione indipendente con
correzione dell'audit degli eventi senza esposizione. Demo Asimov e prova
GEANT3 π⁰ disponibili. Confronto numerico Ajaka non eseguito: tabella
Fig. 2 verificata ancora mancante, come previsto dal ramo alternativo del
Task 3. Canale MC segnale e associazione bersaglio/run restano prerequisiti
esterni; nessun dato fisico sostitutivo inventato.

Dettagli: [report](../../reports/2026-10-21-cross-section-implementation.md).
