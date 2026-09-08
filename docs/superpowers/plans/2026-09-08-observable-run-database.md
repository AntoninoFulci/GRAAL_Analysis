# Observable Run Database Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic artifact-only workflow that classifies every run and publishes a good-only manifest and flux bundle without rereading ROOT or `h80`.

**Architecture:** New pure module owns artifact parsing, per-run quality policy, filtering, and deterministic serialization. Thin CLI validates paths/options and atomically publishes a separate observable bundle. Existing manifest and strip-energy/flux record types, writers, and group aggregation remain authoritative and are reused.

**Tech Stack:** Python 3.10+, standard library, pytest, existing `graal_common.run_manifest` and `graal_common.strip_energy_flux`; no PyROOT dependency.

**Spec:** `docs/superpowers/specs/2026-09-08-observable-run-database-design.md`

## Global Constraints

- Never modify or append columns to `config/run_manifest.csv`.
- Never rescan ROOT or `h80`; consume published CSV/JSON artifacts only.
- Never hardcode production run IDs or expected production counts in classifier code.
- Status precedence is `bad` over `review` over `good`; observable outputs contain only `good` runs.
- Default BREM rule is `run in-range BREM >= 100.0 × same-period median`, using `ajaka_cross_section` and at least five period runs.
- Unknown QA schema, unclassified source-QA errors, duplicate keys, metadata conflicts, non-finite values, or invalid output invariants abort publication.
- Source bundle remains untouched; destination publication is atomic and deterministic.
- Every behavior change follows RED-GREEN-REFACTOR.

---

### Task 1: Pure run-quality policy

**Files:**
- Create: `00_common/observable_runs.py`
- Create: `00_common/tests/test_observable_runs.py`

**Interfaces:**
- Consumes: `RunRecord`, `FluxBinRecord`, structured QA dictionaries.
- Produces:
  - `ObservableRunError(ValueError)`
  - `QUALITY_FIELDS: tuple[str, ...]`
  - `BremMetric(reference_sum: float | None, period_median: float | None, ratio: float | None)`
  - `RunQuality(run: RunRecord, quality_status: str, reason_codes: tuple[str, ...], nonzero_unmapped_strip_count: int, negative_net_bin_count: int, brem: BremMetric)`
  - `calculate_brem_metrics(manifest: Sequence[RunRecord], run_flux: Sequence[FluxBinRecord], *, reference_binning: str, outlier_ratio: float, minimum_period_runs: int) -> tuple[dict[int, BremMetric], set[int], set[int]]`; returned sets are outlier runs and runs whose baseline is unavailable.
  - `classify_run_quality(manifest: Sequence[RunRecord], source_qa: Mapping[str, object], run_flux: Sequence[FluxBinRecord], *, reference_binning: str = "ajaka_cross_section", brem_outlier_ratio: float = 100.0, minimum_period_runs: int = 5) -> tuple[RunQuality, ...]`

- [ ] **Step 1: Write failing policy tests**

Add focused tests demonstrating:

```python
def test_bad_precedes_review_and_accumulates_sorted_reasons():
    qa = qa_for_runs(
        missing_h80=[7],
        negative=[7],
        unmapped=[7, 7],
    )
    quality = classify_run_quality(manifest_rows(7), qa, valid_flux_rows(7))
    assert quality[0].quality_status == "bad"
    assert quality[0].reason_codes == (
        "missing_h80",
        "negative_net_flux",
        "nonzero_flux_without_lookup",
    )
    assert quality[0].nonzero_unmapped_strip_count == 2
    assert quality[0].negative_net_bin_count == 1


def test_brem_threshold_uses_period_median_without_run_ids():
    rows = brem_rows({1: 10, 2: 10, 3: 10, 4: 10, 5: 1000})
    metrics, outliers, unavailable = calculate_brem_metrics(
        manifest_rows(1, 2, 3, 4, 5), rows,
        reference_binning="ajaka_cross_section",
        outlier_ratio=100.0,
        minimum_period_runs=5,
    )
    assert outliers == {5}
    assert unavailable == set()
    assert metrics[5].ratio == pytest.approx(100.0)


def test_short_or_zero_median_period_is_review_not_good():
    quality = classify_run_quality(
        manifest_rows(1, 2), qa_for_runs(), brem_rows({1: 0, 2: 1}),
        minimum_period_runs=5,
    )
    assert {row.quality_status for row in quality} == {"review"}
    assert all("brem_baseline_unavailable" in row.reason_codes for row in quality)
```

Also cover `monotonic_inversion`, run-scope conservation, MAD, low statistics,
underflow/overflow, clean `good`, invalid thresholds, duplicate manifest runs,
and unknown run numbers inside structured QA.

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
pytest -q 00_common/tests/test_observable_runs.py
```

Expected: collection failure because `graal_common.observable_runs` does not exist.

- [ ] **Step 3: Implement minimal policy**

Use per-run `set[str]` reason accumulation and `Counter` diagnostics. Sum BREM
with `math.fsum`; validate finite values and classify finite negative raw BREM
bins as `negative_raw_brem` review findings. Group baselines strictly
by manifest `source_period`. Classify every manifest run exactly once, sorted
numerically. Map structured QA sections directly; group-scope conservation
failures raise `ObservableRunError` because they cannot be assigned safely.

- [ ] **Step 4: Run focused and common tests**

Run:

```bash
pytest -q 00_common/tests/test_observable_runs.py 00_common/tests/test_strip_energy_flux.py
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add 00_common/observable_runs.py 00_common/tests/test_observable_runs.py
git commit -m "feat(flux): classify observable runs"
```

---

### Task 2: Strict artifact readers and deterministic writers

**Files:**
- Modify: `00_common/observable_runs.py`
- Modify: `00_common/tests/test_observable_runs.py`

**Interfaces:**
- Consumes: exact schemas `LOOKUP_FIELDS`, `RUN_FLUX_FIELDS`, manifest map, source QA schema v1.
- Produces:
  - `read_lookup_artifact(path: Path, manifest_by_run: Mapping[int, RunRecord]) -> tuple[StripEnergyRecord, ...]`
  - `read_run_flux_artifact(path: Path, manifest_by_run: Mapping[int, RunRecord]) -> tuple[FluxBinRecord, ...]`
  - `read_source_qa(path: Path) -> dict[str, object]`
  - `validate_source_qa_errors(qa: Mapping[str, object]) -> None`
  - `write_run_quality_csv(path: Path, rows: Sequence[RunQuality]) -> None`
  - `sha256_file(path: Path) -> str`

- [ ] **Step 1: Write failing reader/writer tests**

Tests must prove exact header acceptance, duplicate lookup key rejection,
duplicate flux key rejection, finite numeric validation, positive integer
validation, status vocabulary validation, manifest metadata equality, unknown
run rejection, malformed JSON rejection, QA schema v1 enforcement, and stable
empty metric serialization:

```python
def test_quality_writer_uses_fixed_schema_and_empty_missing_metrics(tmp_path):
    path = tmp_path / "run_quality.csv"
    write_run_quality_csv(path, [quality_row(7, brem=BremMetric(None, None, None))])
    row = next(csv.DictReader(path.open(newline="")))
    assert tuple(row) == QUALITY_FIELDS
    assert row["brem_reference_sum"] == ""
    assert row["brem_period_median"] == ""
    assert row["brem_ratio"] == ""
```

For source errors, construct one QA payload whose messages correspond exactly
to structured missing/unmapped/negative/run-conservation findings and verify
acceptance. Add one unrelated error string and verify
`ObservableRunError("unclassified source QA error")`.

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
pytest -q 00_common/tests/test_observable_runs.py
```

Expected: failures for missing reader/writer functions.

- [ ] **Step 3: Implement strict streaming readers and writers**

Parse CSV through `csv.DictReader(strict=True)`. Include path and row number in
every diagnostic. Reconstruct existing immutable records, preserving numeric
values. Validate formulas with `math.isclose`:

```text
pol1_net = pol1 - brem
pol2_net = pol2 - brem
total_net = pol1_net + pol2_net
```

Recognize source errors only when represented by structured QA sections.
Compare structured identity, not arbitrary substring suppression. Reuse
canonical manifest metadata and deterministic newline conventions.

- [ ] **Step 4: Run focused tests**

Run:

```bash
pytest -q 00_common/tests/test_observable_runs.py
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add 00_common/observable_runs.py 00_common/tests/test_observable_runs.py
git commit -m "feat(flux): validate observable artifacts"
```

---

### Task 3: Artifact-only observable database CLI

**Files:**
- Create: `scripts/build_observable_run_database.py`
- Create: `00_common/tests/test_build_observable_run_database.py`

**Interfaces:**
- Consumes CLI options `--manifest`, `--strip-energy-dir`, `--output-dir`, `--brem-reference-binning`, `--brem-outlier-ratio`, `--minimum-period-runs`.
- Produces exit `0` plus atomic six-file bundle: `run_quality.csv`, `run_manifest_observables.csv`, `strip_energy_lookup.csv`, `flux_by_run_energy.csv`, `flux_by_group_energy.csv`, `observable_run_qa.json`.
- Produces exit `1` and stderr diagnostic on validation/runtime failure; existing destination remains unchanged. Argparse syntax errors remain exit `2`.

- [ ] **Step 1: Write failing CLI integration tests**

Build ROOT-free miniature source bundles with two periods and at least five
runs per evaluable period. Exercise subprocess CLI. Assert:

```python
assert completed.returncode == 0
assert {p.name for p in output.iterdir()} == {
    "run_quality.csv",
    "run_manifest_observables.csv",
    "strip_energy_lookup.csv",
    "flux_by_run_energy.csv",
    "flux_by_group_energy.csv",
    "observable_run_qa.json",
}
assert validate_manifest(output / "run_manifest_observables.csv")
assert qa["valid"] is True
assert qa["counts_by_status"] == {"bad": 1, "good": 8, "review": 1}
```

Verify bad/review runs never appear in filtered lookup/run-flux outputs;
regenerated group sums equal only good rows; all emitted statuses are valid;
input/output hashes match bytes; output ordering is deterministic across two
runs; unknown source error fails; metadata conflict fails; pre-existing
sentinel survives failure; output-inside-input path is rejected.

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
pytest -q 00_common/tests/test_build_observable_run_database.py
```

Expected: failure because CLI script does not exist.

- [ ] **Step 3: Implement CLI orchestration**

Resolve these source paths beneath `--strip-energy-dir`:

```python
SOURCE_FILES = (
    "strip_energy_lookup.csv",
    "flux_by_run_energy.csv",
    "strip_energy_flux_qa.json",
)
```

Validate destination does not equal or contain any input, mirroring existing
lexical and resolved path checks. Read and classify. Select `quality_status ==
"good"`; require at least one good run. Filter source records, require every
good run has lookup and complete rows for every QA-declared binning, then call
`aggregate_group_flux()`. Reject any non-valid filtered/group row.

Within `atomic_output_directory(output_dir)`, write five CSV files first,
compute their SHA-256 digests, then write QA. QA uses sorted dictionaries and
records policy version `1`, source QA digest, counts by status/reason/group,
global warnings, source/output run counts, and output digests. Do not copy or
modify source files.

- [ ] **Step 4: Run CLI and regression tests**

Run:

```bash
pytest -q 00_common/tests/test_build_observable_run_database.py 00_common/tests/test_observable_runs.py
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/build_observable_run_database.py 00_common/tests/test_build_observable_run_database.py
git commit -m "feat(flux): build good-run artifact bundle"
```

---

### Task 4: Farm workflow, schemas, and production acceptance

**Files:**
- Modify: `wiki/pipeline.md`
- Modify: `wiki/data-formats.md`
- Modify: `wiki/strip-energy-flux-maintenance.md`
- Modify: `wiki/Current-Status.md`

**Interfaces:**
- Consumes: completed CLI from Task 3 and transferred `results/strip_energy_flux/` bundle.
- Produces: documented command, status semantics, schemas, provenance, operational warning that only `run_manifest_observables.csv` may normalize observables.

- [ ] **Step 1: Add documentation contract**

Document exact command:

```bash
python scripts/build_observable_run_database.py \
  --manifest config/run_manifest.csv \
  --strip-energy-dir results/strip_energy_flux \
  --output-dir results/observable_runs
```

Document six outputs, every `run_quality.csv` column, QA policy v1, reason-code
vocabulary, `good/review/bad` precedence, BREM threshold, no-rescan property,
and separation between full manifest for cut/kinematic studies and good-only
manifest for observables. Update status from “farm validation pending” to
production QA received and observable-run curation implemented.

- [ ] **Step 2: Run production command against transferred artifacts**

Run:

```bash
python scripts/build_observable_run_database.py \
  --manifest config/run_manifest.csv \
  --strip-energy-dir results/strip_energy_flux \
  --output-dir results/observable_runs
```

Expected exit `0`; QA counts must be `good=2373`, `review=151`, `bad=187` and
good-group counts `P_UV=1256`, `P_VIS=323`, `D_UV=532`, `D_VIS=262`. Verify
these from produced files rather than embedding them in implementation.

- [ ] **Step 3: Run full verification**

Run:

```bash
pytest -q
python -m compileall -q 00_common scripts
python scripts/build_run_manifest.py --validate config/run_manifest.csv
git diff --check
```

Expected: all commands exit `0` with no test failures or compile errors.

- [ ] **Step 4: Commit**

```bash
git add wiki/pipeline.md wiki/data-formats.md \
  wiki/strip-energy-flux-maintenance.md wiki/Current-Status.md
git commit -m "docs(flux): document observable run policy"
```
