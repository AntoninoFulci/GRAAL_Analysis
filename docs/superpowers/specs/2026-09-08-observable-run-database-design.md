# Observable Run Database Design

**Date:** 2026-09-08
**Status:** approved in chat; implementation pending

## Goal

Turn completed strip-energy/flux artifacts into a reproducible database of
runs usable for physics observables. Runs with missing or unreliable flux
normalization remain available to studies of cuts and kinematics, but never
enter cross sections or beam-asymmetry extraction.

No `h80` or ROOT rescan is required. Selection operates only on the existing
manifest and published artifact bundle.

## Inputs

The command consumes:

- canonical `config/run_manifest.csv`;
- `strip_energy_lookup.csv`;
- `flux_by_run_energy.csv`;
- `strip_energy_flux_qa.json`.

`flux_by_group_energy.csv` from the source bundle is not trusted for the new
selection because it contains contributions from runs that may be rejected.
It is regenerated from filtered per-run rows.

Every input must exist, match its exact schema, and be internally consistent.
Run metadata repeated in lookup and flux rows must match the canonical
manifest. Duplicate keys, unknown manifest runs, non-finite numeric values,
unknown QA schema versions, and unclassified QA errors abort publication.

## Quality model

Every manifest run receives exactly one status, ordered by precedence:

1. `bad`: unusable for observables;
2. `review`: excluded conservatively pending physics review;
3. `good`: admitted to observable extraction.

Status comes from stable reason codes rather than prose matching alone.
Multiple reason codes may apply to one run.

### Bad reasons

- `missing_h80`: run absent from inclusive `h80` lookup input;
- `nonzero_flux_without_lookup`: at least one nonzero-flux strip lacks energy;
- `monotonic_inversion`: run-specific strip-energy lookup fails monotonicity;
- `run_flux_conservation_failure`: raw per-run conservation fails;
- `brem_period_outlier`: in-range BREM sum exceeds configured multiple of
  same-period median.

The BREM metric uses `ajaka_cross_section` rows from
`flux_by_run_energy.csv`. For each run, BREM is summed over those bins. The
baseline is median of available run totals in the same `source_period`.
Default threshold is `100.0`. Equality with threshold is an outlier. Periods
with fewer than five usable totals or a non-positive median do not silently
classify outliers: affected runs receive `review` reason
`brem_baseline_unavailable`.

Threshold is configurable and stored in QA. Run IDs are never hardcoded.

### Review reasons

- `negative_net_flux`: at least one energy bin has negative `POL1-BREM` or
  `POL2-BREM` under the provisional convention;
- `negative_raw_brem`: at least one finite raw BREM bin is negative;
- `low_strip_statistics`: QA reports strip event count below threshold;
- `high_energy_mad`: QA reports excessive within-strip energy dispersion;
- `flux_underflow_overflow`: ROOT flux underflow or overflow was nonzero;
- `brem_baseline_unavailable`: period-level BREM test cannot be evaluated.

Warnings without a run number remain global QA warnings. They cannot silently
change a run to `good` or `bad`.

### Good status

A run is `good` only when it has no bad or review reason. Observable outputs
contain only `good` runs. `review` remains fail-closed until physical meaning,
normalization, and exposure handling of BREM are confirmed.

## Outputs

Command publishes a separate output directory atomically. Source artifacts
remain byte-for-byte untouched.

### `run_quality.csv`

One row for every canonical manifest run, sorted by `run_number`:

```text
run_number,source_period,target,beam_type,group,classification_source,
source_file,quality_status,reason_codes,nonzero_unmapped_strip_count,
negative_net_bin_count,brem_reference_sum,brem_period_median,brem_ratio
```

`reason_codes` uses sorted `;`-separated codes. Missing BREM metrics serialize
as empty fields.

### `run_manifest_observables.csv`

Canonical seven-column manifest containing only `good` runs. It must pass
existing `validate_manifest()` unchanged.

### Filtered physics artifacts

- `strip_energy_lookup.csv`: source lookup rows for good runs only;
- `flux_by_run_energy.csv`: source per-run flux rows for good runs only;
- `flux_by_group_energy.csv`: regenerated from filtered run rows using
  `aggregate_group_flux()`.

Rows retain existing schemas and deterministic ordering. All filtered run and
group rows must have `status=valid`.

### `observable_run_qa.json`

Contains:

- schema and policy version;
- absolute or user-supplied input paths;
- SHA-256 for every input file;
- configured reference binning, BREM ratio, and minimum period size;
- counts by status, reason, group, and status/group;
- source and output run counts;
- global source-QA warnings;
- SHA-256 for every produced CSV;
- `valid`, true only when publication invariants pass.

## Command

```bash
python scripts/build_observable_run_database.py \
  --manifest config/run_manifest.csv \
  --strip-energy-dir results/strip_energy_flux \
  --output-dir results/observable_runs
```

Optional controls:

```text
--brem-reference-binning ajaka_cross_section
--brem-outlier-ratio 100.0
--minimum-period-runs 5
```

## Failure behavior

Output publication uses `atomic_output_directory()`. Invalid inputs or
invariants return nonzero and preserve any previous valid destination.
Failure diagnostics name exact input, row, key, or QA field. No partial
observable database is published.

## Verification

Pure tests cover status precedence, reason accumulation, BREM period median,
threshold boundary, unavailable baselines, and deterministic status counts.
CLI tests cover schema validation, metadata conflicts, unclassified QA errors,
canonical filtered manifest, filtering, regenerated aggregation, hashes,
atomic replacement, and current transferred production artifacts.

Production acceptance expected from current bundle under default policy:

- `good=2373`;
- `review=151`;
- `bad=187`;
- good groups: `P_UV=1256`, `P_VIS=323`, `D_UV=532`, `D_VIS=262`.

These counts are regression evidence for this exact input bundle, not constants
embedded in classification code.
