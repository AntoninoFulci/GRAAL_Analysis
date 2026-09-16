# Calibration and flux

Calibration workflow derives run-specific tagger strip energies from inclusive
h80 events, integrates ROOT flux histograms into energy bins, aggregates by
target/beam group, and writes a portable QA bundle.

## Inputs

- pre-analysis directory containing `pre_*.root` with tree `h80`;
- validated `config/run_manifest.csv`;
- ROOT file containing per-run `POL1`, `BREM`, and `POL2` histograms;
- output directory.

Run:

```bash
python scripts/build_run_manifest.py --validate config/run_manifest.csv

python scripts/build_strip_energy_flux.py \
  --preanalysis-dir data/pre_analyzed \
  --manifest config/run_manifest.csv \
  --flux data/flux/flux.root \
  --output-dir results/strip_energy_flux
```

Optional controls:

| Option | Default |
|---|---:|
| `--min-events-per-strip` | `1` |
| `--max-mad-gev` | `0.005` |
| `--monotonic-tolerance-gev` | `0.002` |
| `--binning NAME:EDGE,...` | repeatable; adds custom binning |

Built-in `ajaka_cross_section` and `ajaka_sigma` binnings are always produced.

## Lookup construction

For each observed `(run_number, Xstrip)` pair, lookup records event count,
median `beam.E()`, median absolute deviation, minimum, maximum, and `observed`
provenance. Strip index must normalize to integer range 1–128. Runs are never
pooled, so target, beam type, and acquisition period remain distinct.

Monotonic inversions, low statistics, large MAD, empty strips, unmapped strips,
and manifest/run mismatches are retained in QA.

## Flux integration

Lookup assigns each strip to energy bins. Bins use `[low, high)` except final
bin includes right edge. Strips outside binning range are reported, not folded
into edge bins.

For each run and energy bin:

```text
pol1_net = pol1 - brem
pol2_net = pol2 - brem
total_net = pol1_net + pol2_net
```

Negative net flux marks row invalid and makes QA invalid. Raw and negative
values remain in CSV for diagnosis. Group output sums run rows without mixing
target or beam type; invalid contributor keeps group row invalid.

## Output schemas

### `strip_energy_lookup.csv`

```text
run_number,source_period,target,beam_type,group,xstrip,event_count,
energy_median_gev,energy_mad_gev,energy_min_gev,energy_max_gev,provenance
```

### `flux_by_run_energy.csv`

```text
binning,run_number,source_period,target,beam_type,group,
energy_low_gev,energy_high_gev,pol1,brem,pol2,
pol1_net,pol2_net,total_net,status
```

### `flux_by_group_energy.csv`

Same flux columns, keyed by binning, target, beam type, group, and energy bin.

### `strip_energy_flux_qa.json`

Schema version 1 records input paths, thresholds, binnings, run and strip
counts, malformed triplets, missing/extra runs, monotonic and spread warnings,
underflow/overflow, out-of-range flux, negative net errors, structural errors,
and final `valid` flag.

## Atomic publication

Writers stage all output in temporary sibling directory. Successful publish
replaces destination atomically; interrupted or failed writes do not leave a
partially refreshed bundle.

## Exit codes

| Exit | Meaning | Artifacts |
|---:|---|---|
| 0 | Analysis completed and QA valid | All four artifacts |
| 1 | QA invalid or handled runtime/input error | Full diagnostic bundle when processing completed; minimal QA when possible for early failure |
| 2 | Command usage error from `argparse` | No analysis artifacts |

Never consume CSV outputs for physics extraction unless QA JSON has
`"valid": true`.
