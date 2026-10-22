# Strict 4γ + p asymmetry study implementation plan

> **For agentic workers:** Use superpowers:executing-plans inline. The user authorized this restrictive experiment after brainstorming; no further physics-choice approval is needed.

**Goal:** Measure changes in asymmetry when reconstructed events contain exactly four photon candidates and one proton candidate, with no doubtful or extra tracks.

**Architecture:** Add an opt-in comparison command using existing reconstructed raw-track diagnostics and existing asymmetry/paired-bootstrap routines. Do not modify nominal data, PID, reconstruction, BDT, or the concurrently edited event reader.

**Tech Stack:** Existing Python, PyROOT, NumPy, matplotlib and estimator code.

**Spec:** User decisions in this conversation: exclude doubtful candidates, require exactly four photons and one proton, run a restrictive comparison.

## Global constraints and derivation

- Baseline reconstruction has at least four **central** photons and exactly one PID-selected proton; h85 requires one forward charged track. With exactly five total tracks the retained topology must therefore be four central neutrals and one forward proton. This is a subset of the existing baseline, not a new full-acceptance analysis.
- Require `Nass_3 == 4`, all `Itipo_track == 11`, `n_photons_input == 4`, `Nparf == 1`, positive in-range `Index_trf`, addressed `Iass_trf in {6,7}`, and `Nparf_strange == 0`.
- Require provenance `selection.protons == exactly_one`, `selection.photons == first_four_of_at_least_four`, no-fit eta_pi0 reconstruction, and complete typed raw diagnostics. The unique reconstructed proton must be forward once all central codes are 11. Do not reimplement legacy PID or claim ICENTR_CLASS was measured.
- Validate counts, identities and raw/reconstructed photon agreement; malformed metadata aborts. Zero forward indices are explicitly vetoed rather than treated as first association. `N_traf` contains association candidates and need not equal one.
- Keep nominal pairing, kinematics, run universe, flux, polarization, energy/mass bins and BDT threshold. No background correction in either arm; measured changes remain selection diagnostics, not background-subtracted signal shifts.
- Use common run-block draws stratified by period, retaining zero-yield exposed runs. Report failed fits and unavailable covariance, never substitute zeros. Run bootstrap uncertainty is a diagnostic, not calibrated event/Poisson significance.
- Run both UV/VIS and chi2/BDT samples with 64 paired replicas, seed 20261021. Preserve all outputs in a new study directory. Record source and input hashes, masks and per-reason cutflow.

## Review focus

1. Extra ignored central tracks and fifth photons must fail despite valid reconstructed daughters.
2. Forward index is an index, not a PID; unused association candidates must not count as extra tracks.
3. Missing provenance/diagnostics or inconsistent photon counts must fail closed.
4. Empty selected samples keep exposure and report unestimable points.
5. Before/after share flux and random run draws; identity selection gives exactly zero difference.

## Tasks

- [x] Add behavioral tests for strict topology, raw ROOT schema/provenance, malformed indices and identity/empty comparisons; run them in failure before implementation.
- [x] Add `08_observable_extraction/compare_track_selection.py`, reusing raw snapshot validation, existing extraction, plotting and paired bootstrap helpers. Run focused selection/comparison tests.
- [x] Execute four production comparisons with immutable nominal inputs. Inspect figures, cutflows, estimator coverage and paired shifts; write a concise scientific report with limits.
- [x] Obtain independent review, address substantive findings, verify changed files and preserve unrelated edits.

## Execution ledger

- Ruling: shared checkout, new study-specific files only — existing event reader and cross-section work are concurrent; no worktree/branch changes or cumulative commit.
- Ruling: the exclusive topology removes the need to reconstruct all legacy ICENTR_CLASS categories. Current PID plus the raw inventory suffices for this subset. This does not validate neutral/photon purity.
- Verification: 18 new tests failed with the absent study module, then passed. Selection/comparison suite: 40 passed; raw-metadata, event-reader and systematic suite: 33 passed. One existing empty-plot legend warning; no failed tests.
- Independent review: no actionable findings; reviewer independently ran the 18 new tests and inspected completed VIS BDT output. No nominal source files modified by this experiment.
- Completed four comparisons, 64 paired replicas each: UV chi2 131576 → 24181; UV BDT 100641 → 18762; VIS chi2 29854 → 7545; VIS BDT 11888 → 2941 (counts after common flux eligibility).
- UV likelihood, Eγ 1.30–1.40 GeV, Mpπ0 1.16–1.20 GeV: ΔΣ = −0.12806 ± 0.03563 (chi2), −0.13251 ± 0.04044 (BDT). VIS likelihood, Mηπ0 0.68–0.72 GeV: ΔΣ = +0.08539 ± 0.02522 (chi2), +0.08196 ± 0.03931 (BDT). Errors are paired run diagnostics; no global-significance or signal-purity claim.
- Verified all four masks against their rejection arrays, cutflow totals and 64-replica shapes; inspected all 20 PDF pages as rendered PNGs. HTML local links and embedded image data validated; no browser surface available for full-page HTML rendering.
- Direct cross-check: raw-track fields match original local run1321 h70 for 27 reconstructed events.
- Deliverables: [self-contained report](../../../results/2026-10-21-strict-4gamma-proton/report.html), per-sample PDF/ROOT/JSON/NPZ, all_points.csv, summary.json, retention.png and reproducible report generator. Nominal files remain unchanged.
