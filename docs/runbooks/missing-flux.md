# Missing-flux audit and experimental study

## Full-statistics farm campaign and anomalous-run recovery

The [19 October farm campaign](../reports/2026-10-19-farm-flux-recovery.md)
uses a separate source snapshot and environment, with the complete proton h80
files and reconstructed events from the same production campaign. Preparation:

```bash
python -m flux_studies.prepare_native_recovery \
  --manifest config/run_manifest.csv --raw-flux /path/to/flux.root \
  --calibrated-flux /campaign/common/flux_calibrated.root \
  --h80-dir /campaign/h80 --output-dir /new-study/prepared
```

This requires every proton period in the manifest. It freezes inclusive counts,
input identity, full-campaign factor-100 findings, a derived quality policy and
realistic missing-state masks. Existing exclusions persist; newly diagnosed
factor-100 runs and previous factor-100 exclusions are hidden in all states and
become experimental recovery requests. Their measured flux is never truth.
The shared production policy is not rewritten.

Pass `--counts-cache prepared/h80_counts.json`,
`--reference-study prepared` and
`--run-quality prepared/run_quality_exclusions.json` to `study_native_recovery`,
along with the campaign's calibrated/raw flux and UV/VIS reconstructed paths.
The three-block CLI also accepts `--counts-cache` instead of repeated `--h80`
and the same `--run-quality`. Both retain their previous defaults.

`scripts/run_farm_flux_study.sh` runs one of `prepare`, `realistic`, `block3`
inside an already provisioned snapshot; its four arguments are stage, study
directory, production campaign directory and h80 directory. Set `GRAAL_PYTHON`
to the isolated interpreter, load its matching ROOT environment, and provide
`study_dir/flux.root` as the raw-flux source. Output directories must be new.
The farm report records the exact Slurm wrapper and submitted job identifiers.

`candidate_attempts.csv`/`candidate_attempt_spectra.npz` retain every calculable
experimental prediction, including unsupported extrapolations labeled as such.
`candidate_support.json` explains count/geometry support; only supported
predictions also enter `candidate_predictions.csv`. No candidate is adopted.

## Realistic gaps and observable closure (19 October 2026)

`python -m flux_studies.study_realistic_gaps` inventories all missing calibrated
P states, builds masks matching locally supported gaps (including unavailable
neighbor runs), runs training-only model searches and compares the same selected
events with native, roundtrip and reconstructed flux. Required arguments are
`--calibrated-flux`, repeated `--h80`, `--reco-uv`, `--reco-vis` and a new
`--output-dir`; manifest/raw flux default to repository inputs. Default seed142.
See [exact command, results and limits](../reports/2026-10-19-realistic-flux-closure.md).

Candidate CSV/NPZ arrays use a common energy grid and remain experimental.
Publication requires observed left/right donor-distance support and event counts
within the available training range. Rejections remain in `candidate_support.json`.
No automatic substitution into production: native strip axes, correlated flux
uncertainties, independent confirmation and physical tolerance are still needed.
The closure uses profile-standard energy bins and fixed 12-bin phi fits, both
ratio and likelihood; BREM-only masks do not test the central Sigma response.

## Calibrated-neighbor benchmark (19 October 2026)

To compare event-normalized neighbor interpolation and ML against known
calibrated spectra, use the separate calibrated-study entry point:

```bash
python -m flux_studies.study_calibrated_neighbors \
  --calibrated-flux data/00_external/flux_calibrated.root \
  --h80 test_data/pre_analyzed/pre_analisi_1998_uv.root \
  --h80 test_data/pre_analyzed/pre_analisi_1999_vis.root \
  --output-dir results/my-calibrated-neighbor-study
```

The output directory must be new. This explicitly exploratory pilot assumes
15 minutes per run and stable conditions within each manifest period, as
requested by the user; no measured timestamps are invented. Counts include
all h80 entries per run/state. The full manifest order supplies the neighbor
coordinate, including runs without usable calibration. Defaults: 128 common
energy bins over 0.5--2.0 GeV, seed 42, one- and three-run masking blocks.
`--block-size` is repeatable. All spectra must fit the common energy range.
Adjacent held-out blocks can create gaps longer than the nominal block size.

Train/validation/test are run-disjoint; inner training-only blocked tuning
selects parameters for Ridge, RBF Kernel Ridge and Extra Trees. Each family has
direct and hybrid predictions plus fixed-reference controls; the hybrid uses
the positive ML shape scaled to the event-normalized interpolation integral.
Use `--models ridge kernel_ridge extra_trees` (default: all three) to choose
families. Validation residuals calibrate exploratory bands; held-out truth
never enters predictions or model selection. These periods were inspected in
the preceding pilot, so this is development evaluation, not independent
confirmation. Complete PDF atlases,
diagnostics, CSV metrics and aligned NPZ arrays are written separately from
production. This benchmark does not reconstruct or adopt missing production
flux. See [pilot results and BREM anomalies](../reports/2026-10-19-calibrated-flux-neighbors.md).
See the [hybrid/model-search results](../reports/2026-10-19-hybrid-flux-model-search.md)
for cleaned-data comparisons, parameter grids, coverage and complete atlases.

The shared v2 policy `config/run_quality_exclusions.json` excludes whole runs
1322, 1441, 1454, 1482, 1970, 1988, 2055 and 2064. For 1322, 1482 and 1970,
at least one state's measured flux per inclusive event is
outside [0.01, 100] times its period/state median. The evidence and source
hashes are frozen from the pilot; diagnostics do not silently add exclusions.
The other five runs are explicit user exclusions after inspecting prior BREM
prediction errors, with distinct `decision_basis` and frozen benchmark evidence;
they are not claimed to satisfy the factor-100 criterion.
All states of these runs are excluded from training, donors, evaluation,
observable exposures and observable event selections. Original split roles
are preserved using the pre-exclusion run universe. Policy identity is recorded
in study and observable provenance and included in pipeline dependencies.
Existing observable outputs are not rewritten: rerun extraction to apply the
policy. Production flux ROOT files remain unchanged.

The original raw-missing audit/study below retains its stricter acquisition
metadata requirements and is not silently switched to the pilot assumptions.

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

## Native calibrated-neighbor development study

The standalone native study now propagates reconstructed flux through the
existing Σ estimators, without changing production inputs or the launcher.
It reuses the validated local inclusive h80 count cache and the frozen realistic
mask design. PyTorch is optional for the rest of the analysis; install it in an
isolated environment based on the ROOT-compatible interpreter:

```bash
python3 -m venv --system-site-packages .venv-flux
.venv-flux/bin/python -m pip install -r 07_flux_studies/requirements-neural.txt
MPLCONFIGDIR=/tmp/graal-mpl XDG_CACHE_HOME=/tmp/graal-cache \
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
.venv-flux/bin/python -m flux_studies.study_native_recovery \
  --output-dir results/native-flux-recovery-new --replicas 64
.venv-flux/bin/python -m flux_studies.native_diagnostics \
  results/native-flux-recovery-new
```

The output directory must be new. Default source paths correspond to the local
1998 UV / 1999 VIS development inputs; CLI flags override them. The count cache
is checked against ROOT UUIDs, entry totals and inclusive count totals. The
native strip audit must pass before training. Predictions and independent
strip-to-energy axes are saved separately.

Outputs include native and energy spectrum overlays, full model grids and
learning curves, aligned flux replicas, conditional observable covariance,
and comparisons without recovery, with recovery and with known flux (oracle).
The statistical-plus-flux precision and paired RMSE proxy are diagnostics;
failed replica denominators remain visible. Independent bias/coverage and
missing-state energy calibration are still prerequisites for production.

For an independent masking geometry within the same development periods, the
existing `study_calibrated_neighbors` CLI accepts `--representation native_strip`
and `--models ridge kernel_ridge extra_trees mlp cnn1d --block-size 3`.
This is a complementary stress test, not independent experimental confirmation.
See [the native recovery report](../reports/2026-10-19-native-flux-recovery.md)
for definitions, results and exact reproducible commands.
