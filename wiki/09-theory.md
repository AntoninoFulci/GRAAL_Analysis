# Stage 09: retired theory and restart

The previous stage 09 implementation was retired on **26 October 2026**, at the user's request, to restart theory and theoretical cross-section calculations from zero. Its Python package, CLI, models, numerical routines, fit/probe scripts and tests are no longer active in this checkout. There is no replacement implementation or theory command to install or run.

Experimental beam-asymmetry extraction in [stage 08](08-observable-extraction) remains active, including its calibration, estimators, covariance and plotting contracts. The common cross-section reference weights used for BDT backgrounds also remain active; they are separate from the retired theory model. The analysis launcher ends with experimental products and plots.

## Preserved evidence

Original papers remain in [docs/papers](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/docs/papers). Bibliography, digitized targets, parameter provenance and historical comparison notes are preserved under [docs/reference/theory](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/docs/reference/theory/index.md). These records describe the retired attempt; they do not establish accepted parameters, a validated model or current operating commands.

The complete local source snapshot, including uncommitted changes and generated package metadata, is preserved in `results_test/theory-reset-20261026/theory-before-reset.tar.gz` and `results_test/theory-reset-20261026/archive/09_theory/`. The archive was checked against every recorded file hash before retirement. Its manifest is local diagnostic evidence, not a promise that ignored archives are available in a fresh clone. Tracked source history is also retained in Git.

Last historical status: **0/12 certified complete Figure 4 panels**. The preserved farm snapshot dated **2026-10-23T13:02:26Z** recorded a `diagnostic_converged` pilot, array 23 launched and `fit_status=not_started`. Retirement neither changes that evidence nor reports current queue state; no remote campaign was modified.

## Restart boundary

Future work starts with an explicit request defining the observable, primary model source, conventions, units, normalization and independently checkable benchmark. Agree that scientific contract before introducing a new implementation. Old fitted parameters, numerical kernels and convergence claims are not default inputs to the restart.

A comparison with measured Sigma must declare stage-08 products, reconstruction, measured flux and run manifest, and match the [finite-bin convention](finite-bin-correction). A theoretical cross-section prediction and an experimental absolute cross-section extraction are distinct tasks. Acceptance, efficiency, luminosity and uncertainty requirements must be declared for the latter. Passing software tests alone cannot establish either measurement validity or model reproduction.
