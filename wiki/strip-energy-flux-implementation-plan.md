# Strip→Eγ Lookup and Flux Integration Implementation Plan

**Goal:** Build deterministic farm tooling that derives run-specific
`Xstrip → Eγ` lookups from inclusive `h80` trees and integrates
`POL1/POL2/BREM` flux into publication energy bins and manifest groups.

**Architecture:** Pure validation, lookup, binning, integration, aggregation,
and serialization logic lives in `graal_common.strip_energy_flux`. ROOT input
adaptation and command orchestration live in
`scripts/build_strip_energy_flux.py`. Tests first exercise pure functions,
then run CLI against real miniature ROOT files. The production h80 path
streams validated entries into an invocation-owned SQLite spool and computes
exact median/MAD with disk-backed order statistics; it never materializes the
event corpus in Python.

**Tech Stack:** Python 3.10+, standard library, PyROOT, pytest, existing
`graal_common.run_manifest`.

## Implementation Status

**Status:** implemented; farm production validation pending.

Tasks 1–6 and the final-review fix wave are implemented as of 2026-07-30.
All 37 task checkboxes are marked complete; their original RED snippets remain
as the historical execution recipe, not live open work. Final-review rulings
and operational evidence are consolidated in
[Strip-energy flux: maintenance](strip-energy-flux-maintenance),
[Design strip-energy flux](strip-energy-flux-design) and
[Current Status](Current-Status). Git history preserves the task-level audit
trail.

## Global Constraints

- Work directly on `main`; do not create git worktrees.
- Use inclusive `h80`, never selected `h85`, to derive lookup.
- Lookup key is `(RunNumber, integer Xstrip)` and value is median `beam.E()`.
- Never pool, interpolate, or extrapolate between runs or periods.
- Strip domain is exactly integers 1 through 128.
- Preserve original `POL1`, `POL2`, and `BREM` sums.
- Compute `pol1_net = POL1 - BREM`, `pol2_net = POL2 - BREM`, and
  `total_net = pol1_net + pol2_net`.
- Never mix `P/D` or `UV/VIS`; group only by manifest `group`.
- Assign whole strips to bins; no fractional boundary allocation.
- Bin semantics are `[low, high)`, with final right edge included.
- Ajaka cross-section preset is 15 uniform bins from 0.95 to 1.50 GeV.
- Ajaka Sigma preset edges are 1.10, 1.20, 1.30, 1.40, 1.50 GeV.
- Output must be deterministic and atomically replaced.
- A runtime failure before completed publication must preserve an existing
  output byte-for-byte and write minimal invalid QA to a unique sibling whose
  exact path is printed on stderr.
- Reject an output directory when either its normalized lexical path or its
  resolved target equals or contains any supplied input path.
- Structural invalidity, unmapped nonzero flux, or negative net flux must
  produce QA output and nonzero CLI exit.
- Negative-net bins are diagnosed after complete integration: preserve every
  raw/net run and group row, mark affected rows `status=invalid`, list exact
  `(binning, run, bin)` coordinates in QA, and keep completed artifacts
  available. A group row remains invalid if any contributing run row is
  invalid, even when other runs offset its aggregate net value.
- Nonzero ROOT histogram underflow/overflow is warning-only QA and is never
  included in physical strip sums.
- Complete or malformed flux keys outside the authoritative manifest are
  warning-only QA. Requested runs still require exactly one valid canonical
  `POL1`, `POL2`, and `BREM`.
- QA must enforce raw-flux conservation: included plus out-of-range equals
  physical-strip totals per run/state, and group rows equal contributing run
  rows.

## File Map

- Create `00_common/strip_energy_flux.py`: pure records, validation,
  statistics, binning, integration, aggregation, CSV/JSON serialization.
- Create `00_common/tests/test_strip_energy_flux.py`: pure unit tests.
- Create `scripts/build_strip_energy_flux.py`: PyROOT readers, CLI, atomic
  output orchestration.
- Create `00_common/tests/test_build_strip_energy_flux.py`: real ROOT CLI
  integration and failure tests.
- Modify `wiki/pipeline.md`: farm command, inputs, outputs, validation flow.
- Modify `wiki/data-formats.md`: document lookup, flux CSV, and QA schemas.
- Create `wiki/strip-energy-flux-maintenance.md`: provisional assumptions,
  operations, provenance, and future-correction map.
- Modify `wiki/Home.md`: link the maintenance handoff.

---

### Task 1: Energy binning and run-specific lookup

**Files:**

- Create: `00_common/strip_energy_flux.py`
- Create: `00_common/tests/test_strip_energy_flux.py`

**Interfaces:**

- Produces:
  - `StripEnergyFluxError`
  - `EnergyBinning(name: str, edges_gev: tuple[float, ...])`
  - `EnergySample(run_number: int, xstrip: float, energy_gev: float)`
  - `StripEnergyRecord(run_number, xstrip, event_count,
    energy_median_gev, energy_mad_gev, energy_min_gev, energy_max_gev,
    provenance)`
  - `AJAKA_CROSS_SECTION`
  - `AJAKA_SIGMA`
  - `normalize_xstrip(value: float) -> int`
  - `energy_bin_index(energy_gev: float, binning: EnergyBinning) -> int | None`
  - `build_strip_energy_lookup(samples: Iterable[EnergySample])
    -> tuple[StripEnergyRecord, ...]` (small/reference inputs only)
  - `build_strip_energy_lookup_on_disk(samples: Iterable[EnergySample],
    database: Path, *, run_numbers: Iterable[int], batch_size: int = 4096)
    -> StripEnergyLookupBuild` (production exact path)
  - `find_monotonic_inversions(records: Sequence[StripEnergyRecord])
    -> tuple[dict[str, object], ...]`

`StripEnergyLookupBuild.records` is bounded by requested manifest runs × 128;
`observed_runs` and `event_count` carry QA facts. SQLite holds validated event
rows and uses indexed exact median/MAD queries with `temp_store=FILE`.

- [x] **Step 1: Write failing preset, boundary, and lookup tests**

```python
import math

import pytest

from graal_common.strip_energy_flux import (
    AJAKA_CROSS_SECTION,
    AJAKA_SIGMA,
    EnergySample,
    StripEnergyFluxError,
    build_strip_energy_lookup,
    energy_bin_index,
    normalize_xstrip,
)


def test_ajaka_binning_presets_are_exact():
    assert len(AJAKA_CROSS_SECTION.edges_gev) == 16
    assert AJAKA_CROSS_SECTION.edges_gev[0] == pytest.approx(0.95)
    assert AJAKA_CROSS_SECTION.edges_gev[-1] == pytest.approx(1.50)
    assert AJAKA_SIGMA.edges_gev == (1.10, 1.20, 1.30, 1.40, 1.50)


def test_energy_bins_are_left_closed_and_final_bin_is_right_closed():
    assert energy_bin_index(1.10, AJAKA_SIGMA) == 0
    assert energy_bin_index(1.20, AJAKA_SIGMA) == 1
    assert energy_bin_index(1.50, AJAKA_SIGMA) == 3
    assert energy_bin_index(math.nextafter(1.50, math.inf), AJAKA_SIGMA) is None


def test_lookup_uses_median_and_mad_per_run_strip():
    records = build_strip_energy_lookup(
        [
            EnergySample(7, 12.0, 1.20),
            EnergySample(7, 12.0, 1.22),
            EnergySample(7, 12.0, 1.80),
            EnergySample(7, 13.0, 1.30),
        ]
    )
    first = records[0]
    assert (first.run_number, first.xstrip, first.event_count) == (7, 12, 3)
    assert first.energy_median_gev == pytest.approx(1.22)
    assert first.energy_mad_gev == pytest.approx(0.02)
    assert first.energy_min_gev == pytest.approx(1.20)
    assert first.energy_max_gev == pytest.approx(1.80)


@pytest.mark.parametrize("value", [0.0, 129.0, 12.25, math.nan, math.inf])
def test_xstrip_rejects_out_of_domain_or_nonintegral_values(value):
    with pytest.raises(StripEnergyFluxError):
        normalize_xstrip(value)
```

- [x] **Step 2: Run tests and verify RED**

Run:

```bash
pytest -q 00_common/tests/test_strip_energy_flux.py
```

Expected: collection error because `graal_common.strip_energy_flux` does not
exist.

- [x] **Step 3: Implement immutable records, preset validation, bin lookup,
  median, and MAD**

Core implementation:

```python
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from math import isfinite
from statistics import median
from typing import Iterable, Sequence


class StripEnergyFluxError(ValueError):
    pass


@dataclass(frozen=True)
class EnergyBinning:
    name: str
    edges_gev: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.name:
            raise StripEnergyFluxError("binning name is empty")
        if len(self.edges_gev) < 2:
            raise StripEnergyFluxError("binning needs at least two edges")
        if not all(isfinite(edge) for edge in self.edges_gev):
            raise StripEnergyFluxError("binning edges must be finite")
        if any(right <= left for left, right in zip(
            self.edges_gev, self.edges_gev[1:]
        )):
            raise StripEnergyFluxError("binning edges must be strictly increasing")


AJAKA_CROSS_SECTION = EnergyBinning(
    "ajaka_cross_section",
    tuple(0.95 + index * (1.50 - 0.95) / 15 for index in range(16)),
)
AJAKA_SIGMA = EnergyBinning(
    "ajaka_sigma", (1.10, 1.20, 1.30, 1.40, 1.50)
)


@dataclass(frozen=True)
class EnergySample:
    run_number: int
    xstrip: float
    energy_gev: float


@dataclass(frozen=True)
class StripEnergyRecord:
    run_number: int
    xstrip: int
    event_count: int
    energy_median_gev: float
    energy_mad_gev: float
    energy_min_gev: float
    energy_max_gev: float
    provenance: str = "observed"


def normalize_xstrip(value: float) -> int:
    if not isfinite(value):
        raise StripEnergyFluxError("Xstrip must be finite")
    strip = round(value)
    if abs(value - strip) > 1e-6:
        raise StripEnergyFluxError(f"Xstrip is not integral: {value}")
    if not 1 <= strip <= 128:
        raise StripEnergyFluxError(f"Xstrip outside 1..128: {value}")
    return strip


def energy_bin_index(energy_gev: float, binning: EnergyBinning) -> int | None:
    if not isfinite(energy_gev):
        raise StripEnergyFluxError("energy must be finite")
    if energy_gev < binning.edges_gev[0] or energy_gev > binning.edges_gev[-1]:
        return None
    for index, (low, high) in enumerate(
        zip(binning.edges_gev, binning.edges_gev[1:])
    ):
        if low <= energy_gev < high:
            return index
    return len(binning.edges_gev) - 2


def build_strip_energy_lookup(
    samples: Iterable[EnergySample],
) -> tuple[StripEnergyRecord, ...]:
    grouped: dict[tuple[int, int], list[float]] = defaultdict(list)
    for sample in samples:
        if sample.run_number <= 0:
            raise StripEnergyFluxError("run_number must be positive")
        if not isfinite(sample.energy_gev) or sample.energy_gev <= 0:
            raise StripEnergyFluxError("beam energy must be finite and positive")
        grouped[(sample.run_number, normalize_xstrip(sample.xstrip))].append(
            sample.energy_gev
        )
    records = []
    for (run_number, strip), energies in sorted(grouped.items()):
        center = median(energies)
        records.append(
            StripEnergyRecord(
                run_number,
                strip,
                len(energies),
                center,
                median(abs(value - center) for value in energies),
                min(energies),
                max(energies),
            )
        )
    return tuple(records)
```

Implement `find_monotonic_inversions` by grouping records per run, sorting by
strip, and inferring direction from sign of covariance between strip number
and median energy. Zero covariance marks direction undetermined in QA instead
of inventing one. For determined direction, emit one dictionary per adjacent
step whose signed change contradicts it. Dictionary keys must be `run_number`,
`direction`, `left_strip`, `right_strip`, `left_energy_gev`,
`right_energy_gev`, and `delta_gev`.

- [x] **Step 4: Add monotonicity tests**

```python
def test_monotonicity_accepts_decreasing_map_and_reports_local_inversion():
    records = build_strip_energy_lookup(
        [
            EnergySample(7, 1, 1.50),
            EnergySample(7, 2, 1.40),
            EnergySample(7, 3, 1.45),
            EnergySample(7, 4, 1.20),
        ]
    )
    inversions = find_monotonic_inversions(records)
    assert len(inversions) == 1
    assert inversions[0]["left_strip"] == 2
    assert inversions[0]["right_strip"] == 3
    assert inversions[0]["delta_gev"] == pytest.approx(0.05)
```

- [x] **Step 5: Run focused tests and verify GREEN**

Run:

```bash
pytest -q 00_common/tests/test_strip_energy_flux.py
```

Expected: all Task 1 tests pass.

- [x] **Step 6: Commit Task 1**

```bash
git add 00_common/strip_energy_flux.py \
        00_common/tests/test_strip_energy_flux.py
git commit -m "feat: derive run strip energy lookup"
```

---

### Task 2: Pure flux integration and group aggregation

**Files:**

- Modify: `00_common/strip_energy_flux.py`
- Modify: `00_common/tests/test_strip_energy_flux.py`

**Interfaces:**

- Consumes: Task 1 `EnergyBinning`, `StripEnergyRecord`,
  `energy_bin_index`; existing `graal_common.run_manifest.RunRecord`.
- Produces:
  - `StripFlux(run_number, xstrip, pol1, brem, pol2)`
  - `FluxBinRecord(binning, run_number, source_period, target, beam_type,
    group, energy_low_gev, energy_high_gev, pol1, brem, pol2, pol1_net,
    pol2_net, total_net, status)`
  - `GroupFluxBinRecord(binning, target, beam_type, group, energy_low_gev,
    energy_high_gev, pol1, brem, pol2, pol1_net, pol2_net, total_net, status)`
  - `integrate_run_flux(...) -> tuple[FluxBinRecord, ...]`
  - `aggregate_group_flux(...) -> tuple[GroupFluxBinRecord, ...]`

- [x] **Step 1: Write failing integration tests**

```python
from graal_common.run_manifest import RunRecord
from graal_common.strip_energy_flux import (
    EnergyBinning,
    StripEnergyRecord,
    StripFlux,
    aggregate_group_flux,
    integrate_run_flux,
)


def lookup(run, strip, energy):
    return StripEnergyRecord(run, strip, 10, energy, 0.0, energy, energy)


def manifest(run, group="P_UV"):
    target, beam = group.split("_")
    return RunRecord(
        run, "period", target, beam, group, "manual",
        f"period/run{run}.root",
    )


def test_flux_integration_sums_whole_strips_and_subtracts_brem_twice():
    bins = EnergyBinning("two_bins", (1.0, 1.2, 1.4))
    result = integrate_run_flux(
        manifest(7),
        [lookup(7, 1, 1.10), lookup(7, 2, 1.19), lookup(7, 3, 1.30)],
        [
            StripFlux(7, 1, 100.0, 10.0, 80.0),
            StripFlux(7, 2, 50.0, 5.0, 40.0),
            StripFlux(7, 3, 20.0, 2.0, 16.0),
        ],
        bins,
    )
    assert (result[0].pol1, result[0].brem, result[0].pol2) == (
        150.0, 15.0, 120.0
    )
    assert result[0].pol1_net == 135.0
    assert result[0].pol2_net == 105.0
    assert result[0].total_net == 240.0


def test_nonzero_flux_without_lookup_is_fatal():
    with pytest.raises(StripEnergyFluxError, match="nonzero flux"):
        integrate_run_flux(
            manifest(7), [], [StripFlux(7, 12, 1.0, 0.0, 1.0)],
            EnergyBinning("one", (1.0, 1.5)),
        )


def test_negative_net_flux_preserves_raw_bin_with_invalid_status():
    result = integrate_run_flux(
        manifest(7), [lookup(7, 1, 1.2)],
        [StripFlux(7, 1, 2.0, 3.0, 4.0)],
        EnergyBinning("one", (1.0, 1.5)),
    )
    assert (result[0].pol1, result[0].brem, result[0].pol2) == (2.0, 3.0, 4.0)
    assert (result[0].pol1_net, result[0].pol2_net) == (-1.0, 1.0)
    assert result[0].status == "invalid"
```

- [x] **Step 2: Run focused tests and verify RED**

Run:

```bash
pytest -q 00_common/tests/test_strip_energy_flux.py
```

Expected: import failure for `StripFlux`.

- [x] **Step 3: Implement flux records and integration**

Implementation rules:

```python
@dataclass(frozen=True)
class StripFlux:
    run_number: int
    xstrip: int
    pol1: float
    brem: float
    pol2: float


@dataclass(frozen=True)
class FluxBinRecord:
    binning: str
    run_number: int
    source_period: str
    target: str
    beam_type: str
    group: str
    energy_low_gev: float
    energy_high_gev: float
    pol1: float
    brem: float
    pol2: float
    pol1_net: float
    pol2_net: float
    total_net: float
    status: str


def integrate_run_flux(
    manifest: RunRecord,
    lookup: Sequence[StripEnergyRecord],
    strips: Sequence[StripFlux],
    binning: EnergyBinning,
) -> tuple[FluxBinRecord, ...]:
    energy_by_strip = {
        record.xstrip: record.energy_median_gev
        for record in lookup
        if record.run_number == manifest.run_number
    }
    sums = [[0.0, 0.0, 0.0] for _ in binning.edges_gev[:-1]]
    for strip in strips:
        if strip.run_number != manifest.run_number:
            raise StripEnergyFluxError("flux run conflicts with manifest")
        values = (strip.pol1, strip.brem, strip.pol2)
        if not all(isfinite(value) for value in values):
            raise StripEnergyFluxError("flux contents must be finite")
        if strip.xstrip not in energy_by_strip:
            if any(value != 0.0 for value in values):
                raise StripEnergyFluxError(
                    f"run {manifest.run_number} strip {strip.xstrip}: "
                    "nonzero flux without lookup"
                )
            continue
        index = energy_bin_index(energy_by_strip[strip.xstrip], binning)
        if index is not None:
            for state, value in enumerate(values):
                sums[index][state] += value
    result = []
    for index, (low, high) in enumerate(
        zip(binning.edges_gev, binning.edges_gev[1:])
    ):
        pol1, brem, pol2 = sums[index]
        pol1_net = pol1 - brem
        pol2_net = pol2 - brem
        status = "invalid" if pol1_net < 0 or pol2_net < 0 else "valid"
        result.append(FluxBinRecord(
            binning.name,
            manifest.run_number,
            manifest.source_period,
            manifest.target,
            manifest.beam_type,
            manifest.group,
            low,
            high,
            pol1,
            brem,
            pol2,
            pol1_net,
            pol2_net,
            pol1_net + pol2_net,
            status,
        ))
    return tuple(result)
```

`FluxBinRecord.status` is `"invalid"` when either net component is negative
and `"valid"` otherwise. Negative-net rows are returned rather than raised so
the CLI can serialize their raw values and report exact bin coordinates.
`aggregate_group_flux` recomputes raw/net sums and propagates `"invalid"` from
any contributing run row even if the aggregate net is nonnegative. Structural
errors still carry run and strip context.

- [x] **Step 4: Add aggregation separation test**

```python
def test_group_aggregation_never_mixes_manifest_groups():
    bins = EnergyBinning("one", (1.0, 1.5))
    p = integrate_run_flux(
        manifest(7, "P_UV"), [lookup(7, 1, 1.2)],
        [StripFlux(7, 1, 10.0, 1.0, 8.0)], bins,
    )
    d = integrate_run_flux(
        manifest(8, "D_UV"), [lookup(8, 1, 1.2)],
        [StripFlux(8, 1, 20.0, 2.0, 16.0)], bins,
    )
    grouped = aggregate_group_flux((*p, *d))
    assert [row.group for row in grouped] == ["D_UV", "P_UV"]
    assert [row.total_net for row in grouped] == [32.0, 16.0]
```

- [x] **Step 5: Run tests and verify GREEN**

Run:

```bash
pytest -q 00_common/tests/test_strip_energy_flux.py
```

Expected: all Task 1 and Task 2 tests pass.

- [x] **Step 6: Commit Task 2**

```bash
git add 00_common/strip_energy_flux.py \
        00_common/tests/test_strip_energy_flux.py
git commit -m "feat: integrate flux by energy and group"
```

---

### Task 3: Deterministic CSV and QA serialization

**Files:**

- Modify: `00_common/strip_energy_flux.py`
- Modify: `00_common/tests/test_strip_energy_flux.py`

**Interfaces:**

- Produces:
  - `LOOKUP_FIELDS = ("run_number", "source_period", "target", "beam_type",
    "group", "xstrip", "event_count", "energy_median_gev",
    "energy_mad_gev", "energy_min_gev", "energy_max_gev", "provenance")`
  - `RUN_FLUX_FIELDS = ("binning", "run_number", "source_period", "target",
    "beam_type", "group", "energy_low_gev", "energy_high_gev", "pol1",
    "brem", "pol2", "pol1_net", "pol2_net", "total_net", "status")`
  - `GROUP_FLUX_FIELDS = ("binning", "target", "beam_type", "group",
    "energy_low_gev", "energy_high_gev", "pol1", "brem", "pol2",
    "pol1_net", "pol2_net", "total_net", "status")`
  - `write_lookup_csv(path, records, manifest_by_run)`
  - `write_run_flux_csv(path, records)`
  - `write_group_flux_csv(path, records)`
  - `write_qa_json(path, qa)`
  - `atomic_output_directory(destination: Path)` context manager

- [x] **Step 1: Write failing schema, ordering, and atomicity tests**

```python
import csv
import json


def test_lookup_csv_has_fixed_schema_and_numeric_order(tmp_path):
    output = tmp_path / "lookup.csv"
    records = [lookup(20, 2, 1.2), lookup(3, 12, 1.3), lookup(3, 1, 1.1)]
    manifests = {3: manifest(3), 20: manifest(20, "D_VIS")}
    write_lookup_csv(output, records, manifests)
    with output.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]["run_number"] == "3"
    assert rows[0]["xstrip"] == "1"
    assert tuple(rows[0]) == LOOKUP_FIELDS


def test_qa_json_is_stable_and_ends_with_newline(tmp_path):
    output = tmp_path / "qa.json"
    write_qa_json(output, {"valid": True, "schema_version": 1})
    assert output.read_text() == (
        '{\n  "schema_version": 1,\n  "valid": true\n}\n'
    )


def test_atomic_output_does_not_replace_destination_on_failure(tmp_path):
    destination = tmp_path / "result"
    destination.mkdir()
    (destination / "sentinel").write_text("old")
    with pytest.raises(RuntimeError):
        with atomic_output_directory(destination) as staging:
            (staging / "new").write_text("partial")
            raise RuntimeError("stop")
    assert (destination / "sentinel").read_text() == "old"
    assert not (destination / "new").exists()
```

- [x] **Step 2: Run focused tests and verify RED**

Run:

```bash
pytest -q 00_common/tests/test_strip_energy_flux.py
```

Expected: import failure for serialization interfaces.

- [x] **Step 3: Implement fixed schemas and atomic output**

Use `csv.DictWriter(..., lineterminator="\n")`, `dataclasses.asdict`,
`json.dumps(qa, indent=2, sort_keys=True) + "\n"`, and a sibling staging
directory created with `tempfile.mkdtemp(prefix=f".{destination.name}.",
dir=destination.parent)`.

Atomic context behavior:

```python
@contextmanager
def atomic_output_directory(destination: Path) -> Iterator[Path]:
    destination = Path(destination)
    if destination.exists() and not destination.is_dir():
        raise StripEnergyFluxError(f"destination is not a directory: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(
        prefix=f".{destination.name}.", dir=destination.parent
    ))
    backup: Path | None = None
    try:
        yield staging
        if destination.exists():
            backup = Path(tempfile.mkdtemp(
                prefix=f".{destination.name}.previous.",
                dir=destination.parent,
            ))
            backup.rmdir()
            destination.replace(backup)
        try:
            staging.replace(destination)
        except BaseException:
            if backup is not None and backup.exists() and not destination.exists():
                backup.replace(destination)
            raise
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    if backup is not None:
        try:
            shutil.rmtree(backup)
        except OSError:
            pass
```

Before creating staging, reject destination when it exists but is not a
directory. Allocate a unique invocation-owned backup only when replacing an
existing destination; never delete or reuse a pre-existing sibling. After the
staging directory has replaced the destination, backup cleanup is best-effort:
cleanup failure must not make the already-published output fail.

- [x] **Step 4: Run focused tests and verify GREEN**

Run:

```bash
pytest -q 00_common/tests/test_strip_energy_flux.py
```

Expected: all serialization tests pass.

- [x] **Step 5: Commit Task 3**

```bash
git add 00_common/strip_energy_flux.py \
        00_common/tests/test_strip_energy_flux.py
git commit -m "feat: serialize strip energy flux artifacts"
```

---

### Task 4: ROOT input adapters

**Files:**

- Create: `scripts/build_strip_energy_flux.py`
- Create: `00_common/tests/test_build_strip_energy_flux.py`

**Interfaces:**

- Consumes: Task 1 `EnergySample`; Task 2 `StripFlux`.
- Produces:
  - `iter_h80_samples(preanalysis_dir: Path)
    -> tuple[Iterator[EnergySample], dict[str, object]]` for production
  - `read_h80_samples(preanalysis_dir: Path)` only as a small-fixture
    compatibility adapter that consumes the stream
  - `read_flux_histograms(path: Path, run_numbers: Sequence[int])
    -> tuple[list[StripFlux], dict[str, object]]`

- [x] **Step 1: Write real ROOT fixtures and failing adapter test**

Create helpers in test:

```python
from array import array
from pathlib import Path

import pytest

from scripts import build_strip_energy_flux as cli


def write_h80(path: Path, entries):
    import ROOT
    output = ROOT.TFile(str(path), "RECREATE")
    tree = ROOT.TTree("h80", "h80")
    vector_type = "ROOT::Math::LorentzVector<ROOT::Math::PxPyPzE4D<double> >"
    vector = getattr(ROOT, vector_type)
    beam = vector()
    run_number = array("i", [0])
    xstrip = array("f", [0.0])
    tree.Branch("beam", vector_type, beam)
    tree.Branch("RunNumber", run_number, "RunNumber/I")
    tree.Branch("Xstrip", xstrip, "Xstrip/F")
    for run, strip, energy in entries:
        run_number[0] = run
        xstrip[0] = strip
        beam.SetPxPyPzE(0.0, 0.0, energy, energy)
        tree.Fill()
    tree.Write()
    output.Close()


def write_flux(path: Path, run, values):
    import ROOT
    output = ROOT.TFile(str(path), "RECREATE")
    for suffix, contents in values.items():
        histogram = ROOT.TH1D(f"run{run}_{suffix}", "", 128, 0.0, 128.0)
        for strip, value in contents.items():
            histogram.SetBinContent(strip, value)
        histogram.Write()
    output.Close()


def test_root_adapters_read_h80_and_flux_triplet(tmp_path):
    pre = tmp_path / "pre"
    pre.mkdir()
    write_h80(pre / "pre_7.root", [(7, 12, 1.2), (7, 13, 1.3)])
    flux = tmp_path / "flux.root"
    write_flux(flux, 7, {
        "POL1": {12: 100}, "POL2": {12: 80}, "BREM": {12: 10},
    })
    samples, h80_qa = cli.read_h80_samples(pre)
    strips, flux_qa = cli.read_flux_histograms(flux, [7])
    assert [(row.run_number, row.xstrip) for row in samples] == [
        (7, 12.0), (7, 13.0)
    ]
    assert strips[11].pol1 == pytest.approx(100.0)
    assert strips[11].brem == pytest.approx(10.0)
    assert h80_qa["entries"] == 2
    assert flux_qa["run_count"] == 1
```

- [x] **Step 2: Run adapter test and verify RED**

Run:

```bash
pytest -q \
  00_common/tests/test_build_strip_energy_flux.py::test_root_adapters_read_h80_and_flux_triplet
```

Expected: import error because script does not exist.

- [x] **Step 3: Implement guarded ROOT readers**

`iter_h80_samples` must recursively sort `*.root`, reject empty input, zombie
files, missing `h80`, and missing `RunNumber/Xstrip/beam`. Read only those
branches and yield one validated sample at a time. The list-building example
below is historical fixture code and is not the production interface:

```python
tree.SetBranchStatus("*", 0)
for branch in ("RunNumber", "Xstrip", "beam"):
    tree.SetBranchStatus(branch, 1)
for entry_index, entry in enumerate(tree):
    yield validate_energy_sample(EnergySample(
        float(entry.RunNumber), float(entry.Xstrip), float(entry.beam.E())
    ))
```

`read_flux_histograms` must open one file, require exact triplet per requested
run, require `TH1` inheritance, `GetDimension() == 1`,
`GetNbinsX() == 128`, x-axis edges equal to integers 0 through 128 within
`1e-6`, and finite bin contents. Strip 1 maps to ROOT bin 1 although its center
is 0.5; strip 128 maps to ROOT bin 128 although its center is 127.5. Parse every
key matching
`run<N>_(POL1|POL2|BREM)` before selecting requested runs; QA records complete
run triplets absent from manifest and malformed/incomplete triplets. Create one
`StripFlux` per physical strip. Record nonzero underflow/overflow as
warning-only QA and exclude it from physical strip sums. Wrap branch-value
conversion failures, including a `beam` object without `E()`, in a
path-and-entry-contextual `StripEnergyFluxError`. Semantic validation failures
for run, strip, and energy carry the same source context.

- [x] **Step 4: Add malformed ROOT tests**

Cover:

- missing `h80`;
- missing branch;
- missing `BREM`;
- histogram with 127 bins;
- histogram with 128 bins but wrong x-axis edges;
- nonzero underflow/overflow reported;
- requested run absent.
- complete flux run absent from manifest reported as extra.

Use exact assertions such as:

```python
with pytest.raises(StripEnergyFluxError, match="run7_BREM"):
    cli.read_flux_histograms(flux, [7])
```

- [x] **Step 5: Run adapter tests and verify GREEN**

Run:

```bash
pytest -q 00_common/tests/test_build_strip_energy_flux.py
```

Expected: all ROOT adapter tests pass.

- [x] **Step 6: Commit Task 4**

```bash
git add scripts/build_strip_energy_flux.py \
        00_common/tests/test_build_strip_energy_flux.py
git commit -m "feat: read h80 strip energies and ROOT flux"
```

---

### Task 5: CLI orchestration, QA, and farm artifacts

**Files:**

- Modify: `scripts/build_strip_energy_flux.py`
- Modify: `00_common/tests/test_build_strip_energy_flux.py`

**Interfaces:**

- Consumes all Task 1–4 interfaces and
  `validate_manifest(Path) -> list[RunRecord]`.
- Produces:
  - `parse_custom_binnings(values: Sequence[str])
    -> tuple[EnergyBinning, ...]`
  - `build_qa_payload(args, manifest, lookup, run_flux, h80_qa, flux_qa,
    errors) -> dict[str, object]`
  - `run(args: argparse.Namespace) -> int`
  - `main() -> int`
- Produces CLI:

```text
python scripts/build_strip_energy_flux.py
  --preanalysis-dir PATH
  --manifest PATH
  --flux PATH
  --output-dir PATH
  [--min-events-per-strip 1]
  [--max-mad-gev 0.005]
  [--monotonic-tolerance-gev 0.002]
  [--binning NAME:EDGE,EDGE,...]
```

Without `--binning`, both Ajaka presets run. Every repeated `--binning` adds a
named custom scheme after both presets. Names must be unique and edges must
pass `EnergyBinning` validation.

Parser implementation:

```python
def parse_custom_binnings(values: Sequence[str]) -> tuple[EnergyBinning, ...]:
    result = []
    seen = {AJAKA_CROSS_SECTION.name, AJAKA_SIGMA.name}
    for value in values:
        name, separator, raw_edges = value.partition(":")
        if not separator or not name or not raw_edges:
            raise StripEnergyFluxError(
                "custom binning must use NAME:EDGE,EDGE,..."
            )
        if name in seen:
            raise StripEnergyFluxError(f"duplicate binning name: {name}")
        try:
            edges = tuple(float(edge) for edge in raw_edges.split(","))
        except ValueError:
            raise StripEnergyFluxError(
                f"custom binning {name}: edges must be numeric"
            ) from None
        result.append(EnergyBinning(name, edges))
        seen.add(name)
    return tuple(result)
```

- [x] **Step 1: Write failing end-to-end success test**

```python
def test_cli_writes_lookup_run_group_and_valid_qa(tmp_path):
    pre, flux, manifest_path, output = make_complete_fixture(tmp_path)
    result = subprocess.run(
        [
            sys.executable, str(SCRIPT),
            "--preanalysis-dir", str(pre),
            "--manifest", str(manifest_path),
            "--flux", str(flux),
            "--output-dir", str(output),
        ],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert sorted(path.name for path in output.iterdir()) == [
        "flux_by_group_energy.csv",
        "flux_by_run_energy.csv",
        "strip_energy_flux_qa.json",
        "strip_energy_lookup.csv",
    ]
    qa = json.loads((output / "strip_energy_flux_qa.json").read_text())
    assert qa["valid"] is True
    assert qa["manifest_run_count"] == 2
    assert qa["h80_run_count"] == 2
    assert qa["flux_run_count"] == 2
    assert "Wrote 2-run strip-energy flux analysis" in result.stdout
```

`make_complete_fixture` creates one `P_UV` run and one `D_VIS` run, all 128
strip lookup entries, exact flux triplets, and a validator-compatible manifest.

- [x] **Step 2: Run end-to-end test and verify RED**

Run:

```bash
pytest -q \
  00_common/tests/test_build_strip_energy_flux.py::test_cli_writes_lookup_run_group_and_valid_qa
```

Expected: CLI argument parsing or missing `main` failure.

- [x] **Step 3: Implement CLI and orchestration**

Implementation sequence inside `main()`:

```python
records = validate_manifest(args.manifest)
manifest_by_run = {record.run_number: record for record in records}
manifest_runs = set(manifest_by_run)
with tempfile.TemporaryDirectory(
    prefix=f".{args.output_dir.name}.energy-spool.",
    dir=args.output_dir.parent,
) as spool:
    samples, h80_qa = iter_h80_samples(args.preanalysis_dir)
    lookup_build = build_strip_energy_lookup_on_disk(
        samples,
        Path(spool) / "h80-energy.sqlite3",
        run_numbers=manifest_runs,
    )
lookup = lookup_build.records
sample_runs = set(lookup_build.observed_runs)
extra_h80 = sorted(sample_runs - manifest_runs)
missing_h80 = sorted(manifest_runs - sample_runs)
strips, flux_qa = read_flux_histograms(args.flux, sorted(manifest_runs))
binnings = [
    AJAKA_CROSS_SECTION,
    AJAKA_SIGMA,
    *parse_custom_binnings(args.binning),
]

errors = []
if extra_h80:
    errors.append(f"h80 runs absent from manifest: {extra_h80}")
if missing_h80:
    errors.append(f"manifest runs absent from h80: {missing_h80}")

run_flux = []
for binning in binnings:
    for run in sorted(manifest_runs & sample_runs):
        try:
            run_flux.extend(integrate_run_flux(
                manifest_by_run[run],
                [row for row in lookup if row.run_number == run],
                [row for row in strips if row.run_number == run],
                binning,
            ))
        except StripEnergyFluxError as exc:
            errors.append(str(exc))

qa = build_qa_payload(
    args=args,
    manifest=records,
    lookup=lookup,
    run_flux=run_flux,
    h80_qa=h80_qa,
    flux_qa=flux_qa,
    errors=errors,
)
with atomic_output_directory(args.output_dir) as staging:
    write_lookup_csv(staging / "strip_energy_lookup.csv", lookup, manifest_by_run)
    write_run_flux_csv(staging / "flux_by_run_energy.csv", run_flux)
    write_group_flux_csv(
        staging / "flux_by_group_energy.csv",
        aggregate_group_flux(run_flux),
    )
    write_qa_json(staging / "strip_energy_flux_qa.json", qa)
return 0 if qa["valid"] else 1
```

The spool is unique to the invocation and cleaned by the context manager.
Pre-index the manifest-bounded lookup and flux by run to avoid quadratic
scans. CSV serializers stream row dictionaries rather than allocating a
second row list. QA must include threshold values, preset edges, counts,
missing/extra runs, empty strips, nonzero unmapped strips, inversions above
tolerance, MAD warnings, low-stat warnings, under/overflow, negative net
errors, conservation failures, and sorted error strings.

Negative-net QA entries identify every affected row by binning name, run
number, and zero-based bin index. Those rows and their group aggregates remain
in the completed CSV artifacts with `status=invalid`; QA is invalid and the CLI
returns `1`. Underflow/overflow entries do not invalidate QA by themselves.
Complete and malformed flux runs outside `manifest_runs` are likewise
warning-only; `read_flux_histograms` still raises for any requested run that
lacks exactly one canonical valid triplet.

For each binning, `build_qa_payload` also records lookup energies below/above
range and total raw flux excluded with them. Out-of-range strips are valid and
diagnostic; no flux is folded into boundary bins.

Wrap orchestration in `run(args)`. `main()` catches
`ManifestError`, `StripEnergyFluxError`, `OSError`, and ROOT adapter failures.
When `--output-dir` does not exist and is usable, the catch path may write a
minimal atomic QA there containing `schema_version`, input paths,
`"valid": false`, and exact error text. If the destination already exists, it
must remain byte-for-byte untouched; write that QA to a unique
`<output>.failure.<token>/` sibling and print its absolute path to stderr
before returning `1`. Argument syntax errors remain argparse exit `2`.

- [x] **Step 4: Add invalid-but-diagnostic CLI tests**

Test independently:

- one missing h80 manifest run;
- one nonzero flux strip missing lookup;
- one negative `POL1-BREM`;
- local monotonic inversion;
- MAD and low-stat warnings do not fail alone;
- real subprocess rerun preserves all four existing artifact bytes when ROOT
  reading fails and publishes minimal invalid QA to a unique sibling;
- invalid completed analysis writes QA with `"valid": false` and exits 1.
- malformed ROOT input writes minimal invalid QA and exits 1.
- repeated custom binning name exits 1 with diagnostic QA.
- custom bin edges appear in run/group CSV and QA.
- complete and incomplete extra flux runs are warning-only while requested
  run triplets remain strict.
- semantic run/strip/energy errors include ROOT file and entry index.

Exact negative-flux assertion:

```python
assert result.returncode == 1
qa = json.loads((output / "strip_energy_flux_qa.json").read_text())
assert qa["valid"] is False
assert any("negative net flux" in error for error in qa["errors"])
assert [
    (item["binning"], item["run_number"], item["bin_index"])
    for item in qa["negative_net_errors"]
] == [("ajaka_cross_section", 7, 1)]
```

Exact custom-binning assertions:

```python
custom = parse_custom_binnings(["fine:1.0,1.1,1.2"])
assert custom == (EnergyBinning("fine", (1.0, 1.1, 1.2)),)
with pytest.raises(StripEnergyFluxError, match="duplicate binning name"):
    parse_custom_binnings(["fine:1.0,1.1", "fine:1.1,1.2"])
```

- [x] **Step 5: Run integration tests and verify GREEN**

Run:

```bash
pytest -q 00_common/tests/test_build_strip_energy_flux.py
```

Expected: all CLI and ROOT integration tests pass.

- [x] **Step 6: Run whole suite**

Run:

```bash
pytest -q
```

Expected: all repository tests pass.

- [x] **Step 7: Commit Task 5**

```bash
git add scripts/build_strip_energy_flux.py \
        00_common/tests/test_build_strip_energy_flux.py \
        00_common/strip_energy_flux.py
git commit -m "feat: build farm strip energy flux artifacts"
```

---

### Task 6: Farm documentation and final verification

**Files:**

- Modify: `wiki/pipeline.md`
- Modify: `wiki/data-formats.md`

**Interfaces:**

- Consumes final CLI and schemas.
- Produces exact operator instructions for farm run and returned artifacts.

- [x] **Step 1: Add pipeline command**

Add section after pre-analysis:

````markdown
## Lookup strip→Eγ e integrazione flussi

Questo passaggio usa tutti gli `h80` inclusivi:

```bash
python scripts/build_strip_energy_flux.py \
  --preanalysis-dir data/pre_analyzed \
  --manifest config/run_manifest.csv \
  --flux data/flux/flux.root \
  --output-dir results/strip_energy_flux
```

Exit `0` significa QA valida. Exit `1` lascia comunque report diagnostico in
`strip_energy_flux_qa.json`; non usare CSV fisici finché `valid` non è `true`.
Riportare dalla farm tutta la cartella `results/strip_energy_flux/`.
````

- [x] **Step 2: Document exact schemas and physical convention**

In `wiki/data-formats.md`, copy field lists from design and state:

```text
pol1_net = pol1 - brem
pol2_net = pol2 - brem
total_net = pol1_net + pol2_net
```

Document energy units GeV, strip domain 1–128, `[low, high)` semantics, final
right-edge inclusion, and group separation.

- [x] **Step 3: Run documentation and code checks**

Run:

```bash
rg -n "build_strip_energy_flux|strip_energy_lookup|total_net" \
  wiki/pipeline.md wiki/data-formats.md
git diff --check
pytest -q
```

Expected: all three terms found, no whitespace errors, all tests pass.

- [x] **Step 4: Run CLI help smoke test**

Run:

```bash
python scripts/build_strip_energy_flux.py --help
```

Expected: exit 0 and all four required path flags, three QA threshold flags,
and repeatable custom binning flag listed.

- [x] **Step 5: Inspect final diff and commits**

Run:

```bash
git status --short
git log --oneline -8
```

Expected: only intended documentation changes remain before final commit;
history contains one focused commit for each prior task.

- [x] **Step 6: Commit Task 6**

```bash
git add wiki/pipeline.md wiki/data-formats.md
git commit -m "docs: add farm strip energy flux workflow"
```

- [x] **Step 7: Final fresh verification**

Run:

```bash
python scripts/build_run_manifest.py --validate config/run_manifest.csv
pytest -q
git diff --check
git status --short --branch
```

Expected:

- manifest valid with 2711 runs;
- full test suite has zero failures;
- no whitespace errors;
- worktree clean;
- branch ahead of `origin/main` only by intended commits.

## Execution Completion Gate

Implementation is complete only when:

- every checkbox above is complete;
- RED and GREEN evidence exists for each functional task;
- final QA integration fixture is valid;
- invalid fixtures write diagnostic QA and exit nonzero;
- full repository test suite passes fresh;
- farm command is documented;
- worktree is clean.
