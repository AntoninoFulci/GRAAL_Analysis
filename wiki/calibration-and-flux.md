# Calibration and flux

Calibration workflow derives run-specific tagger strip energies from inclusive
h80 events, integrates ROOT flux histograms into energy bins, aggregates by
target/beam group, and writes a portable QA bundle.

## Inputs

- pre-analysis directory containing `pre_*.root` with tree `h80`;
- validated `config/run_manifest.csv`;
- ROOT file containing per-run `POL1`, `POL2`, and `BREM` histograms;
- output directory.

Run:

```bash
python scripts/build_run_manifest.py --validate config/run_manifest.csv

python scripts/build_strip_energy_flux.py \
  --preanalysis-dir data/02_pre_analyzed/pre_analisi \
  --manifest config/run_manifest.csv \
  --flux data/00_external/flux.root \
  --output-dir results/strip_energy_flux
```

Optional controls:

| Option | Default |
|---|---:|
| `--min-events-per-strip` | `1` |
| `--max-mad-gev` | `0.005` |
| `--monotonic-tolerance-gev` | `0.002` |
| `--progress-every-events` | `250000`; `0` disables event-level updates |
| `--threads` | all CPU cores visible to process |
| `--binning NAME:EDGE,...` | repeatable; adds custom binning |

Progress is written immediately to stderr with timestamp and elapsed time.
Messages cover manifest loading, each h80 file, periodic event counts, each
flux run, QA/integration phases, and artifact writes.

The h80 scan uses ROOT RDataFrame with implicit multithreading. Override worker
count with `--threads N`, or set `FLUX_THREADS=N` for
`scripts/run_beam_asymmetry_overnight.sh`. Its default also uses all online CPU
cores.

Built-in `ajaka_cross_section` and `ajaka_sigma` binnings are always produced.

## Lookup construction

For each observed `(run_number, Xstrip)` pair, lookup records event count,
median `beam.E()`, median absolute deviation, minimum, maximum, and `observed`
provenance. Strip index must normalize to integer range 1–128. Runs are never
pooled, so target, beam type, and acquisition period remain distinct.

Median and MAD remain exact: no histogram approximation is used. A compiled
C++ accumulator stores only beam-energy `double` values and processes one run
at a time. Python receives final run/strip summaries rather than one object per
event, bounding event storage to the largest run instead of the full dataset.

Monotonic inversions, low statistics, large MAD, empty strips, unmapped strips,
and manifest/run mismatches are retained in QA.

## Flux integration

Lookup assigns each strip to energy bins. Bins use `[low, high)` except final
bin includes right edge. Strips outside binning range are reported, not folded
into edge bins.

Histogram names have fixed physical meaning for every run:

```text
runXXXX_POL1 -> vertical-polarization final flux
runXXXX_POL2 -> horizontal-polarization final flux
runXXXX_BREM -> bremsstrahlung final flux
```

These are three independent final exposures. BREM is never subtracted from
POL1 or POL2. ROOT histogram bin errors are not physical flux uncertainties and
are ignored. Negative contents are fatal. Complete flux runs absent from the
manifest are recorded and warned about, then ignored. Group output sums run
rows without mixing target or beam type; invalid contributor keeps group row
invalid.

## Output schemas

### `strip_energy_lookup.csv`

```text
run_number,source_period,target,beam_type,group,xstrip,event_count,
energy_median_gev,energy_mad_gev,energy_min_gev,energy_max_gev,provenance
```

### `flux_by_run_energy.csv`

```text
binning,run_number,source_period,target,beam_type,group,
energy_low_gev,energy_high_gev,flux_pol1,flux_pol2,flux_brem,status
```

### `flux_by_group_energy.csv`

Same flux columns, keyed by binning, target, beam type, group, and energy bin.

### `flux_by_run_strip.csv`

```text
schema_version,run_number,source_period,target,beam_type,group,xstrip,
energy_median_gev,flux_pol1,flux_pol2,flux_brem,status
```

This event-likelihood input preserves run/strip exposure and calibrated energy.
Rows with non-positive selected POL1 or POL2 exposure are invalid.

### `strip_energy_flux_qa.json`

Schema version 2 records input paths, thresholds, binnings, run and strip
counts, malformed triplets, missing/extra runs, monotonic and spread warnings,
underflow/overflow, out-of-range final fluxes, structural errors, warnings, and
final `valid` flag.

## Atomic publication

Writers stage all output in temporary sibling directory. Successful publish
replaces destination atomically; interrupted or failed writes do not leave a
partially refreshed bundle.

## Exit codes

| Exit | Meaning | Artifacts |
|---:|---|---|
| 0 | Analysis completed and QA valid | All five artifacts |
| 1 | QA invalid or handled runtime/input error | Full diagnostic bundle when processing completed; minimal QA when possible for early failure |
| 2 | Command usage error from `argparse` | No analysis artifacts |

Never consume CSV outputs for physics extraction unless QA JSON has
`"valid": true`.
