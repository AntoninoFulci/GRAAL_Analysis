# Cross-section physical inputs implementation plan

> **For agentic workers:** Use executing-plans or scoped parallel execution; verify each deliverable before integration.

**Goal:** Digitize/reproduce Ajaka Figs. 2–3, extract real-data net yields, implement signal detector-chain acceptance, and assemble provisional cross sections where supported.
**Architecture:** Reference digitization, net-yield extraction and detector MC have disjoint ownership. Existing Stage 08 inference consumes validated outputs. Root agent owns integration and provisional campaign configuration.
**Tech Stack:** Python/NumPy/SciPy/ROOT/matplotlib; existing Fortran GEANT3/LAGDIG/PREAN under digest-pinned Docker.
**Spec:** User's explicit numbered instructions in conversation, extending docs/superpowers/specs/2026-10-21-cross-section-extraction-design.md.

## Global constraints

- User authorizes actual implementation and execution; no repeat design approval.
- Move paper to docs/papers with descriptive filename; preserve original bytes.
- Digitize primary plotted data/errors with provenance, no invented points; distinguish nominal energies from integration windows. Reproduce all 15 Fig.3 panels.
- Assume Ajaka target length 12 cm for all periods; explicitly provisional density convention and unknown errors, retain TODO to verify run assignments.
- Full systematic campaign deferred at user's request; preserve statistical covariance needed for inference.
- Build signal response through GEANT3 → LAGDIG → PREAN → current selection/reconstruction. Generated denominator includes all losses; verify identities and MC weight convention.
- No hidden normalization to Ajaka and no claim of full physical validation from smoke tests. Preserve unrelated dirty work. No commit/push.

## Review focus

Digitized axes and units; clipped/lost error bars; model-biased background subtraction; MC ID conservation and losses; target/BR factors counted once; low/zero acceptance not silently extrapolated.

## Tasks and ownership

- [ ] Root: move paper, maintain plan/status, configure explicit provisional target and statistical-only scope, integrate references/yields/response into Stage08.
- [x] Reference worker: docs/papers metadata, references/ajaka figure2/3 data and scripts/plotting for faithful reproduction; visual verification and point provenance.
- [x] Yield worker: new Stage08 signal_yields modules and tests, real data extraction in results/cross-section-net-yields-20261021; compatible net-yield/signature files.
- [ ] MC worker: resources/geant3, Stage03 GEANT3 bridge and tests; isolated source patch/build signal channel, full-chain small run and auditable acceptance inputs.
- [ ] Root: validate artifacts and focused tests, final report with exact completed outputs and any empirically demonstrated remaining blockers.

## Execution record

Paper moved to docs/papers/Ajaka_2008_EtaPi0_Photoproduction_PRL100_052003.pdf.
Parallel work authorized by dispatching-parallel-agents skill. Full uncertainty studies intentionally deferred. User target assumption supersedes previous no-default requirement, but provisional normalization remains labeled.


Integration update:
- Paper moved with SHA preserved; Fig2/3 reproducible vector digitization complete.
- Real UV yields exported, explicitly provisional/model_inadequate; VIS no estimable contract.
- Joint cross-period covariance integrated; contradictory independence declarations rejected.
- Provisional target/BR/flux assumption file and four campaign configs written; actual response paths remain pending.
- Stage08 full suite:310 passed, one preexisting empty-legend warning. Read-only review found shared-covariance bypass; regression first failed then passed after fix.
- Technical detector chain reaches current BDT: instrumented1000 generated ->996 h70 ->787 h85 ->46 selected, with unique original event identities and matching data selection signature. Polarization mapping applied explicitly.
- Ruling: instrumented MC is diagnostic only. Clean replay still stalls; do not use its46/1000 efficiency to normalize physics. Transport cause and period mapping remain open.
- Ruling: preserve zero covariance in empty differential cells; require supported binning/appropriate inference, no artificial variance floor.
- Full systematic campaign and target-per-period verification remain TODO by user request.

Final verification: Stage03 91 + Stage08 310 =401 tests passed; two MC launcher review guards corrected with RED/GREEN regressions.

User steering: no logbook available, proceed autonomously. Provisional mapping now resolves seven proton periods from source run intervals/wrappers (1289 runs); old cylinder and BGO-only trigger explicitly assumed, base21/run3629 initial. No further user input required to prepare configurations.

Latest outcome: explicit prompt gg daughter generation and truth validation implemented, initial proton profile21/run3629/OLD_CYL executable. Clean1000 gives117 digitized, so physical transport remains unresolved. Frozen runtime resources prevent concurrent source edits changing an active shell. Final complete suites92+310=402 passed; no simulation containers left active. Acceptance task intentionally not checked complete.

Final read-only review found no new substantive defects in prompt-decay boosts, daughter identity/conservation validation, or frozen runtime resources. Proton21 end-to-end current chain:1000 generated ->117 h70 ->117 h80 ->0 h85 ->0 reconstructed; response publication rejected for zero acceptance. Physical acceptance remains incomplete and is not replaced with the successful diagnostic period26 value.
