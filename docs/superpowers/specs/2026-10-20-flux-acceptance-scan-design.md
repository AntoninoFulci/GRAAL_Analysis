# Progressive acceptance of reconstructed calibrated flux

User authorization, 20 October 2026: implement the discussed strict-to-loose
acceptance scan, document it for a paper, and run parallel tests on `trima` with
at most 40 allocated CPU cores. No synthetic flux is authorized for production
by this experiment alone.

## Scientific question and fixed safeguards

Determine whether adding whole runs selected using observable-at-inference
flux diagnostics improves the precision of Sigma without unacceptable
reconstruction bias. Twelve globally excluded runs remain excluded everywhere.
Use the existing native 128-strip Extra Trees hybrid prediction, Kernel Ridge
as a discrepancy diagnostic, and event-normalized two-neighbor interpolation.
Keep acquisition duration at the agreed 15 minutes.

Acceptance must not inspect the masked target's true flux, spectral errors or
observed asymmetry. Require every artificially missing state of an accepted
run to pass. True target axes may be used only for measured-run closure; they
are not evidence that an actual missing-state energy axis is available.

The fixed no-recovery baseline removes every masked run for every threshold.
The matched oracle uses true flux for exactly the selected recovered sample:
changing event composition must not be misclassified as reconstruction bias.
Keep unavailable fits, missing replicas, and no-acceptance settings explicit.

## Experiment and documentation

Before submitting jobs, freeze the source, twelve-run policy, input hashes,
candidate threshold ladder, seeds, partitions, acceptance definitions and
ranking rule in machine-readable artifacts. Preserve prior farm outputs.
Reserve an outer run-block sample before development; never train, calibrate
uncertainty or select thresholds on it. Development resamplings share data
and are correlated. The outer sample is untouched by this new scan, but the
underlying campaign has been examined before: call it internal confirmation,
never independent experimental validation.

Perform multiple blocked development splits and one conditional internal
confirmation after threshold selection. Keep ordinary model grid search
inside training folds. Validation residuals alone determine predictive
uncertainty. Use the same model predictions and synchronized replicas at
every threshold in a split.

Report acceptance counts, event recovery, per-state spectral diagnostics,
paired observable differences, statistical and conditional flux errors,
conditional precision gain, empirical predictive coverage, unavailable cases
and sensitivity across correlated development repetitions. No global average
may hide unsupported periods or failing individual observable points.

Compare a fixed nested ladder of stringent to looser cuts on donor separation,
count support, donor normalization disagreement, ET/KRR shape disagreement,
and predicted uncertainty. Threshold numbers are analyst choices, not physical
constants. No parameter is chosen using target truth. The detailed numerical
protocol is frozen before execution in the scan configuration.

Prefer the feasible policy with best conditional precision on development;
do not invent an optimum if none passes the fixed diagnostic budgets.
Representation budget 0.05 oracle statistical sigma, bias budget 0.10, flux
contribution budget 0.30; uncertainty coverage must be assessed rather than
assumed. A screening pass does not establish independent mean-bias or coverage
certification. Production adoption remains false pending those checks and
actual missing-state energy calibration.

## Ownership

Existing closure owns event/exposure population comparisons. A small new scan
module owns inference-time diagnostics and whole-run decisions. A separate
driver owns partitioning, repeated fitting, immutable outputs and farm jobs.
Use existing ROOT readers, model grids, replicas, reporting and plotting.
No new ML framework, production flux format or observable estimator.
