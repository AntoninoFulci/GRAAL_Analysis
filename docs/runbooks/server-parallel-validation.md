# Server validation: h70 to observables with 40 CPUs

Run from the checkout root, in the server's allocated CPU environment. Load
ROOT and its matching Python first. `--cpus 40` is a total CPU budget, not 40
processes each using 40 threads. Set fewer CPUs if the scheduler assigned fewer.
The code does not submit farm jobs or reserve machine resources.
Observable extraction defaults to one process independently of that budget;
override with `--extraction-workers N`, where `1 <= N <= --cpus`.

## Environment and automated acceptance

Update the working branch and install with the existing farm setup. Replace
both paths with the server's actual paths:

```bash
git switch codex/dalitz-completion
git pull --ff-only
GRAAL_RAW=/path/to/graal_data
GRAAL_PYTHON=/path/to/pyroot-compatible-python
./scripts/setup.sh --mode farm --raw-target "$GRAAL_RAW" --python "$GRAAL_PYTHON"
source .venv/bin/activate
python -c 'import ROOT, joblib; from graal_common.parallel import available_cpus; print("ROOT", ROOT.gROOT.GetVersion(), "CPUs", available_cpus())'
```

Set the real 1998 UV raw fixture for the preanalysis integration tests. The
fixture is read only; tests clone small subsets into temporary directories.

```bash
export GRAAL_RAW_SAMPLE="$GRAAL_RAW/1998_uv/run1321.root"
test -r "$GRAAL_RAW_SAMPLE"
python -m pytest -q -rs \
  00_common/tests/test_parallel.py \
  tests/test_raw_track_metadata.py \
  tests/test_parallel_preanalysis.py \
  tests/test_parallel_pipeline.py \
  03_mc_simulation/tests/test_generator_seeds.py \
  04_bdt_training/tests/test_parallel_features.py \
  05_reconstruction/tests/test_parallel_reconstruction.py \
  07_flux_studies/tests/test_parallel.py \
  08_observable_extraction/tests/test_parallel.py \
  tests/test_plot_campaign.py
python -m pytest -q -rs
```

Required: no failures, the new h70 integration test must execute rather than
skip, correct ROOT/PyROOT imports. Other historical tests may require local
fixtures; inspect every skip. Tests compare every h80 event branch, reconstructed
rows and scores, source identities, raw/selected cutflows, deterministic MC
arrays, feature arrays, bin fits, bootstrap draws/covariances and failure cleanup.
Two-worker tests exercise actual processes, not a mocked scheduler.

Focused tests can reuse a lightweight worker before it imports ROOT. Locally,
that import raised worker RSS from 46 MB to 516 MB, triggering joblib's 300 MB
growth guard and a clean worker replacement warning; all tasks completed.
Repeated worker recycling in a real campaign still warrants checking memory.

## Small end-to-end server campaign

Prepare `GRAAL_RAW_BENCH` containing a representative subset in the original
acquisition directory layout, including UV and VIS. Use real unique files;
do not duplicate events under invented filenames. Keep the same subset for all
measurements. For h70 scaling to 40 workers, include at least 40 independent
raw files. A single raw file currently uses one ROOT process.

```bash
GRAAL_RAW_BENCH=/path/to/representative-h70-subset
python -m scripts.run_preanalysis \
  --raw-dir "$GRAAL_RAW_BENCH" --output-dir results/h80-server-smoke --cpus 4
python scripts/run_pipeline.py --mode test_data \
  --preanalysis-dir results/h80-server-smoke --require-current-preanalysis \
  --output-dir results/test_server_smoke --cpus 4 --seed 20261014
```

Answer the launcher's confirmation after inspecting the printed commands.
`test_data` uses 100,000 MC events per channel and rebuilds the test artifact
area; it does not replace production intermediates. Flux input and run manifest
must cover the chosen runs. Extremely small samples can legitimately have no
estimable Sigma bins; use enough exposure/events to exercise extraction/plots.

## Scaling measurements

On Linux, GNU `time -v` reports elapsed time and memory for the launched process
family; it is not a sum of simultaneous RSS across all worker processes. Also
monitor job/cgroup memory and disk throughput with the server's monitoring.
Run one benchmark at a time, with fresh destinations. Output names below must
not already exist for h70; the test launcher replaces its named test campaign.

```bash
mkdir -p results/server-benchmark-logs
for n in 1 4 8 16 40; do
  /usr/bin/time -v -o "results/server-benchmark-logs/h70-${n}.txt" \
    python -m scripts.run_preanalysis --raw-dir "$GRAAL_RAW_BENCH" \
      --output-dir "results/h80-bench-${n}" --cpus "$n"
done

# All pipeline timings consume the SAME h80 files, excluding h70 variability.
for n in 1 4 8 16 40; do
  /usr/bin/time -v -o "results/server-benchmark-logs/pipeline-${n}.txt" \
    python scripts/run_pipeline.py --mode test_data \
      --preanalysis-dir results/h80-bench-1 --require-current-preanalysis \
      --output-dir "results/test_server_cpu${n}" --cpus "$n" --seed 20261014
done
```

The launcher still asks for confirmation on each run; batch submission may pipe
`printf 's\n'` explicitly after reviewing configuration. Compare stage durations
in `pipeline_commands.log`, not only total duration. Reject runs with worker
errors, missing outputs, different event identities/counts or unexplained
physics differences. ROOT UUIDs, timestamps, process IDs and resource metadata
can differ; file SHA equality is not an event-equivalence test. XGBoost and
parallel floating reductions may differ at roundoff level; investigate changes
in accepted events, not merely different binary model files.

The automated equivalence suite is the correctness gate. Before adopting the
fastest configuration, compare its real-data cutflows and fit/bin availability
against the one-CPU baseline and inspect resulting diagnostics. Forty CPUs are
not guaranteed fastest: memory bandwidth, ROOT compression and disk can dominate.

## Measured extraction policy on trimax

On the 40-file UV/VIS smoke campaign, extraction alone was repeated using the
same reconstructed files from `test_server_bench_cpu40`, without rebuilding
MC or training. Measured elapsed times:

| Extraction workers | UV | VIS |
| --- | ---: | ---: |
| 1 | 42.04 s | 12.54 s |
| 4 | 45.60 s | 14.44 s |
| 8 | 47.05 s | 20.07 s |

The launcher therefore defaults extraction to one worker, keeping the requested
budget for other stages. The standalone extraction CLI still supports
`--workers N`. Larger production samples may have a different optimum; measure
before increasing `--extraction-workers`. These timings do not establish an
optimum for h70 conversion, reconstruction or other stages.

## Verified trimax smoke run, 2026-10-15

Code revision `b52c920` was tested with Python 3.14.8 and ROOT 6.40.04.
The fixed input comprised 20 real raw files from each of `1998_uv` and
`1999_vis`. These are smoke measurements, not full-production estimates.
Benchmarks ran consecutively, before the validation workloads started.

| Stage | Configuration | Elapsed | Sampled peak aggregate PSS |
| --- | --- | ---: | ---: |
| h70 to h80, before compression fix | 40 CPUs | 402.14 s | 16.99 GiB |
| h70 to h80, preserving compression | 40 CPUs | 94.05 s | 18.04 GiB |
| h80 to campaign plots, preserving compression | 40 CPUs, extraction workers 1 | 197.36 s | 9.01 GiB |

Preserving compression reduced h70 elapsed time by 4.28 times at the same
40-CPU budget. This compares two versions at 40 CPUs; it is not a measurement
of the fixed version's one-to-40-CPU scaling. PSS was sampled across descendants
from Linux `/proc/*/smaps_rollup`; summed RSS would double-count shared pages.

The server suite passed all 1152 tests in 503.76 s, with no skips and one known
empty-legend warning in `test_gate_comparison.py`. All 49 h80 branches matched
the serial reference exactly across 25,779,739 rows; both runs discarded
2,186,783 events without a tagger. Reconstructed rows, after alignment by raw
identity, and calibrated flux arrays also matched exactly. Reconstruction
counts were UV chi2 2735 / BDT 2217 and VIS chi2 1284 / BDT 608.

The first observable comparison stopped at a likelihood Sigma difference of
`1.52e-8`, exceeding its initial `atol=1e-8` plus `rtol=1e-6`. A single-bin
replay reproduced both stored fits from their native row orders; canonical raw
identity order produced identical complete fits, including profile intervals
and NLL. This isolates floating-point summation/optimizer roundoff from event
or selection changes. The failed check and replay remain in the report.

The documented comparison policy uses `rtol=1e-6, atol=1e-8` generally,
`atol=1e-7` for Sigma, uncorrected Sigma and total systematic error, and
`rtol=0, atol=1e-6` for dimensionless correlations. Identities, counts, cutflows,
bin inventories and discrete fit diagnostics must match exactly. Against the
serial campaign, maximum Sigma difference was `5.74e-8`, total covariance
difference `9.24e-9`, and correlation difference `1.92e-7`. Every nonzero matrix
difference is retained rather than describing covariances as bitwise equal.

Server artifacts are under
`results/server-validation-20261015-JB5LgN/fast-merge/`: `acceptance.json`
(consolidated final result), `tests/pytest.log`,
`data/results.json` (exact h80 checks), `numerical-diagnostic.json`,
`fit-order-repro.json`, and `accepted-comparison/results.json` (campaign
comparison). The original strict comparison is preserved in `data.log`.

## Production launch after acceptance

Use new output directories. The h70 driver refuses to replace any existing h80
directory and publishes only after all shards and counters validate. The launcher
requires both profile inputs and the current tagger-discard/raw-identity contract.
An empty h80 is allowed with that contract; acquisition run/state counters are
copied through h85 and retained in reconstruction even with zero selected yield.

```bash
python -m scripts.run_preanalysis \
  --raw-dir "$GRAAL_RAW" --output-dir data/02_pre_analyzed_parallel --cpus 40
python scripts/run_pipeline.py --mode production \
  --preanalysis-dir data/02_pre_analyzed_parallel --require-current-preanalysis \
  --output-dir results/server_parallel_20261014 \
  --cpus 40 --extraction-workers 1 --seed 20261014
```

Changing seed policy or command arguments invalidates the corresponding cached
MC/BDT artifacts. The new launcher uses explicit nonzero MC seeds and
`channel-v1` feature RNG streams. Direct legacy builder calls preserve their
historical serial stream; compare workers=1 and workers>1 using channel-v1.

## Resource and scientific limits

- Selection/calibration use explicit ROOT threads; training uses explicit
  XGBoost threads. Reconstruction/features/fit/bootstrap workers have one native
  numerical thread each. MC channels run concurrently within the budget.
- Stages and UV/VIS chains remain ordered: a stage owns the budget until it
  finishes. MC concurrency is limited by channel count; feature concurrency by
  channel count; plotting by three independent output sets. No nested all-core pools.
- h70 is parallel by raw file; reconstruction additionally splits a large file
  into entry ranges. Outputs merge in deterministic source/range order.
  Parent merges disable inherited ROOT implicit multithreading before writing;
  worker count never exceeds the number of available tasks.
  Merged files preserve the first input's ROOT compression setting. ROOT treats
  implicit setting `1` and explicit ZLIB setting `101` as different; using the
  merger default would unnecessarily rewrite and recompress every tree basket.
  Regression checks require no compression change for matching input shards.
- Observable CLI `--workers N` applies to per-bin fits and bootstrap replicas;
  callbacks inside replicas use one worker. Launcher `--extraction-workers`
  defaults to one after the server measurements above. Launcher bootstrap remains disabled.
  Enable standalone diagnostic replicas only with an explicit study command and
  unchanged paired-run seed/universe. No final uncertainty choice is implied.
- Flux study `--workers N` accelerates blocked holdout fits. Predictive replicas
  remain serial to preserve their conditional RNG stream and shared nuisance draws.
- Server timings above apply only to the tested smoke subset. Scientific
  prerequisites for polygon cuts, strange tracks, charged backgrounds and final
  uncertainty inference remain unchanged.
