# Flux recovery cleanup and event budget

User-approved scope: retain Extra Trees, Kernel Ridge and interpolation; remove
unused neighbor models; exclude all twelve anomalous/manual runs completely;
estimate recovery only for genuinely missing flux with measured support.

1. Remove Ridge/MLP/CNN neighbor factories, grids and optional neural dependency.
   Retain historical evidence and the independent raw-flux Ridge study.
2. Promote full-campaign anomalies to the shared whole-run policy. Excluded
   runs must never enter recovery, including through old inventory files.
3. Produce a reproducible event budget using frozen support diagnostics and
   full h80 counts. Count unique run/state entries, distinguish supported
   spectra, complete supported runs and production-accepted recovery.
4. Update report and runbook; verify model isolation, exclusion propagation,
   event accounting and existing affected tests.

No synthetic flux is accepted into production before independent energy-axis,
uncertainty/coverage and observable-bias validation. Existing farm artifacts
remain historical evidence. No commit or deployment is requested.

Pre-flight: inventory filtering owns exclusions; model registry owns available
families; budget consumes those same exclusions and frozen support diagnostics.

Completed: retained-model cleanup; global twelve-run policy; exclusion-safe
inventory targets; reproducible whole-run event budget; report/runbook update.
Verification: full suite 1276 passed, one pre-existing empty-legend warning;
independent read-only review found no actionable bugs. All accounting inputs
unchanged across the budget calculation. No production flux adopted.
Farm production checkout predates the shared policy; existing outputs were
not regenerated. Next extraction must use the updated code snapshot. Frozen
farm study and unrelated work preserved. No commit/push/deployment performed.
