# Native-strip flux recovery and measurement benefit

User approved local execution, PyTorch MLP and CNN grid searches, and comparison of measurement precision with and without recovered runs. Farm deployment remains deferred.

Preserve eight existing whole-run exclusions. Inclusive h80 counts and fixed 15-minute positions remain the normalization inputs. Train on native 128-strip flux, after auditing strip identity; energy calibration remains independent of hidden target flux. Never use validation/test truth in fitting or parameter selection. Keep real missing spectra experimental.

Compare linear interpolation, Extra Trees hybrid, kernel ridge hybrid, MLP hybrid and 1D CNN hybrid using identical whole-run/block splits. Neural models predict nonnegative normalized shapes with interpolated integral. Grid search uses training-only inner folds and repeated initializations.

Estimate correlated reconstruction uncertainty from synchronized block resampling and held-out validation residuals, preserving entire spectra and cross-state/shared-donor dependence. Propagate replicas through existing observable extraction; document finite-sample and coverage limitations without asserting unearned calibration.

Acceptance budgets, with statistical error fixed from true-flux extraction: representation shift <=0.05 sigma_stat at every evaluable point; mean reconstruction bias <=0.10 sigma_stat including bias-estimate uncertainty; added flux uncertainty <=0.30 sigma_stat; coverage compatible with 68/95 percent nominal levels. Missing evidence means unvalidated, not passed.

Compare without-recovery, recovered, and oracle (true masked flux) extractions. Report total error including flux reconstruction, bias and covariance; increased count alone is not improvement. Produce measured-versus-predicted spectra, grid diagnostics, uncertainty/coverage and observable precision plots. Preserve production files and historical results.
