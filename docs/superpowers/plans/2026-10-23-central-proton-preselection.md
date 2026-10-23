# Central-proton preselection and local asymmetry comparison

> **For agentic workers:** Execute inline, using existing selection, reconstruction and asymmetry tools.

**Goal:** Accept central recoil protons with exactly four central photons, no identified pions, and the agreed forward-charge topology; compare local before/after asymmetries with Ajaka.

**Architecture:** Keep selection in `02_event_selector/select_events.py`. Preserve every input branch and existing atomic publication. Run both selections from the same local h80 files into a new study directory; reuse identical reconstruction settings, frozen BDT models, calibrated flux, energy grids and estimators.

**Spec:** User-approved discussion: exactly four central gammas; exactly one proton; zero central/forward identified pions; theta <25 degrees requires one forward charge, theta >=25 degrees requires zero. Assume proton/pion PID cuts disjoint.

**Constraints:** Do not overwrite previous campaigns or unrelated working-tree edits. Do not train new models. No kinematic fit. Missing uncertainty or unestimable bins remain missing. Treat shared-event before/after shifts as descriptive unless paired covariance is calculated.

## Task 1: Selection

- [x] Add real ROOT fixtures covering central/forward acceptance, the 25-degree boundary, 3/5 photons, 0/2 protons, pion veto, and additional forward charges. Test missing required PID branches and preservation of previous output on failure.
- [x] Run new tests against old selector and confirm expected failures.
- [x] Update filter, required branches, and selector documentation. Update existing fixtures to carry valid proton/pion data.
- [x] Run selection and metadata integration tests, then repository suite; record failures and review diff.

## Task 2: Local comparison

- [x] Inventory local UV1998/VIS1999 h80 inputs, models and flux; record hashes and executable commands.
- [x] Generate before/after h85 with old/new predicates, recording counts, central/forward composition, overlap, and inclusive run universe.
- [x] Reconstruct both arms with chi2 and frozen BDT, chi2<10, missing mass +/-0.06 GeV, no fit.
- [x] Extract ratio and likelihood with identical nominal energy bins and adaptive phi-binning settings, preserving original run exposures in both arms.
- [x] Produce before/after/Ajaka overlays, numerical CSV/JSON, case table and report; inspect plots and verify counts/provenance.

## Review focus

Empty/multiple protons must be rejected before indexing; exactly 25 degrees belongs to central branch; nonzero pion angle values still veto; missing PID branches fail explicitly; legacy local files lack raw-track/provenance payload and cannot establish detector acceptance or purity.

## Execution result

Completed inline. Selection regression RED: 12 expected failures; GREEN: 38 focused tests. Repository suite: 1483 passed, one preexisting plotting warning. Independent review: no material findings. All 18 analysis commands exited zero. Exposure/source/model/count invariants and final images verified. Report: `docs/reports/2026-10-23-central-proton-preselection.md`; artifacts: `results/central-proton-selection-20261023/report.html`. Existing unrelated working-tree edits preserved; no commit created.
