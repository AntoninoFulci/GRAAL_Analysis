# Missing-flux audit and experimental study

Stage `07_flux_studies` sits between `06_calibration` and
`08_observable_extraction`. Python imports remain `observable_extraction`.
After updating this checkout, refresh the editable installation with the
PyROOT-compatible interpreter: `python -m pip install -e . --no-deps --no-build-isolation`.
Commands using the old `07_observable_extraction/` source path must use `08_`.
Historical reports and campaign artifacts retain their original provenance.

## Standalone audit

```bash
python -m flux_studies.audit_flux \
  --manifest config/run_manifest.csv \
  --raw-flux data/00_external/flux.root \
  --calibrated-flux data/00_external/flux_calibrated.root \
  --output-dir results/my-flux-audit/missing_flux
```

The output directory must not exist. Raw input and manifest are required;
calibrated input is optional. This audit also works when production calibration
fails because raw histograms are missing. A new calibration emits
`flux_calibrated.qa.json`; pass it with `--calibration-qa` to diagnose h80/strip
coverage. A stale sidecar never certifies coverage. Without compatible QA,
coverage remains unknown. Target defaults to P; use `--beam-type UV|VIS` and
repeatable `--period` to restrict the domain. D requires `--target D`.

`audit.json` summarizes counts and input identities; `inventory.csv` lists every
run/state and all detected problems; `strip_inventory.csv` records values,
errors, axes and validity by strip. `input_integrity.json` confirms source
hashes before and after the operation. Scientific defects do not abort the
inventory. Unreadable files or invalid inputs return a nonzero exit status.
BREM zero is valid data, but an all-zero histogram has no normalized shape.
Missing calibrated data are not evidence of missing raw histograms.

## Acquisition metadata

Pass `--run-metadata conditions.json`. Example schema (example numbers are not
measurements; replace them with acquisition evidence):

```json
{
  "schema_version": 1,
  "records": [{
    "run_number": 1321,
    "state": "POL1",
    "source": "acquisition log identifier",
    "start_utc": "1998-01-01T10:00:00Z",
    "end_utc": "1998-01-01T10:05:00Z",
    "configuration_id": "documented-setup",
    "laser_id": "documented-laser",
    "experiment_group": "Vinci",
    "exposure": {
      "value": 300,
      "error": 3,
      "unit": "s",
      "definition": "live_time",
      "uncertainty_group": "clock-calibration"
    }
  }]
}
```

One record per run/state. Period, target and beam are taken from the manifest;
explicit copies must match it. Missing conditions remain unknown; no compatible
donor is inferred from run-number proximity. `experiment_group` is optional;
Vinci plots require explicit identification. Acquisition timestamps must specify
UTC. Exposure definition and units must match between donor and target. Its
error is absolute in the supplied units. Missing exposure permits shape-only
predictions; missing exposure error prevents absolute interval claims.
A shared uncertainty identifier uses a common nuisance draw, with each record's
specified relative uncertainty. Do not assign a common ID to independent errors.

## Study

```bash
python -m flux_studies.study_missing_flux \
  --manifest config/run_manifest.csv \
  --raw-flux data/00_external/flux.root \
  --run-metadata conditions.json \
  --mode offline --folds 5 --replicas 200 --seed 42 \
  --mask-states POL1 --mask-states POL1,POL2 \
  --output-dir results/my-flux-study/missing_flux
```

Without `--mask-states`, each state is masked separately. Patterns of actual
missing states are included as additional validation patterns. `offline` allows
future compatible donors; `causal` restricts training and predictors to earlier
acquisitions. Overlapping run intervals are kept in the same hold-out block.
Nearest donor, mean/median templates, linear interpolation and multi-output
Ridge use the same held-out targets. Ridge tuning and scaling occur within
training folds; uncertainty calibration also excludes outer hold-outs.

`study.json` records status, prerequisites, folds, exclusions, denominators and
paired metrics. `validation.csv`, `study.root` and `plots/` appear when hold-outs
are possible. ROOT retains estimates, measured truth, metadata, covariances,
and aligned replicas with validity masks. Use jointly valid replica IDs when
forming cross-target covariance; do not treat synthetic targets as independent.
Uncertainty combines block-resampled donor/model variation with training-only
out-of-fold residuals. Empirical marginal coverage is reported separately.
These exploratory intervals are not a guaranteed coverage construction.

Candidate predictions for truly absent raw states go only into
`synthetic_flux.root`, under a `synthetic/` namespace that the production loader
does not accept. Invalid measured histograms and missing energy calibrations
are not automatically replaced. No synthetic file is produced when there are
no eligible candidates. All methods remain separately labeled; software does
not select a physical winner or claim adoption criteria have been met.

Statuses: `not_executable` means missing acquisition evidence;
`insufficient_data` means no valid hold-out design; `exploratory` means numerical
comparisons are available, not physical validation. Those scientific outcomes
return zero and preserve the report. Technical failures return nonzero and
cancel publication. Inputs are never edited.

## Launcher

```bash
python scripts/run_pipeline.py --mode production --flux-study audit
python scripts/run_pipeline.py --mode production --flux-study study \
  --flux-study-metadata conditions.json
```

Default is `--flux-study off`. Enabled study runs once, immediately after common
calibration. Its output is `<campaign>/missing_flux/`. UV/VIS extraction still
reads only `<campaign>/common/flux_calibrated.root`. The launcher does not
repair missing raw data or continue after a failed calibration; use standalone
audit for that diagnosis. Synthetic propagation into Σ is separate future work.
