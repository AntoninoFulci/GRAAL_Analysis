# Farm Run Manifest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and validate a deterministic CSV manifest mapping farm run files to source period, target, beam type, and analysis group.

**Architecture:** Put classification, scanning, CSV serialization, and validation in an importable `graal_common.run_manifest` module. Keep `scripts/build_run_manifest.py` as a thin farm-facing CLI that calls the module and returns explicit exit codes. Tests exercise real temporary directory trees, real CSV files, and subprocess CLI behavior.

**Tech Stack:** Python 3.10+, standard library (`argparse`, `csv`, `dataclasses`, `pathlib`, `re`), pytest.

## Global Constraints

- CSV schema is exactly `run_number,source_period,target,beam_type,group,classification_source,source_file`.
- Allowed targets: `P`, `D`, `UNKNOWN`.
- Allowed beam types: `UV`, `VIS`, `UNKNOWN`.
- Allowed groups: `P_UV`, `P_VIS`, `D_UV`, `D_VIS`, `UNASSIGNED`.
- Allowed classification sources: `automatic`, `manual`, `unresolved`.
- `source_file` is relative to scan root.
- Deuterium beam type is never inferred: generated rows use `UNKNOWN`, `UNASSIGNED`, `unresolved`.
- Unrecognized periods are retained as unresolved rows.
- Duplicate run numbers are fatal.
- Validation rejects unresolved rows and inconsistent target/beam/group combinations.
- No ROOT dependency: manifest uses directory and filename metadata only.

---

### Task 1: Classification, scanning, and deterministic CSV generation

**Files:**
- Create: `00_common/run_manifest.py`
- Create: `00_common/tests/test_run_manifest.py`

**Interfaces:**
- Produces: `RunRecord`, `ManifestError`, `classify_period(period: str) -> tuple[str, str, str, str]`
- Produces: `scan_runs(input_dir: Path) -> list[RunRecord]`
- Produces: `write_manifest(records: Sequence[RunRecord], output: Path) -> None`
- Consumes: period directories and `runNNNN.root` filenames below one scan root.

- [ ] **Step 1: Write failing classification tests**

```python
from pathlib import Path

import pytest

from graal_common.run_manifest import (
    ManifestError,
    RunRecord,
    classify_period,
    scan_runs,
    write_manifest,
)


@pytest.mark.parametrize(
    ("period", "expected"),
    [
        ("1998_uv", ("P", "UV", "P_UV", "automatic")),
        ("2000_fuv", ("P", "UV", "P_UV", "automatic")),
        ("1999_vis", ("P", "VIS", "P_VIS", "automatic")),
        ("2002_d1", ("D", "UNKNOWN", "UNASSIGNED", "unresolved")),
        ("2005_d2", ("D", "UNKNOWN", "UNASSIGNED", "unresolved")),
        ("mystery", ("UNKNOWN", "UNKNOWN", "UNASSIGNED", "unresolved")),
    ],
)
def test_classify_period(period, expected):
    assert classify_period(period) == expected
```

- [ ] **Step 2: Run classification test and verify RED**

Run:

```bash
pytest -q 00_common/tests/test_run_manifest.py::test_classify_period
```

Expected: collection error because `graal_common.run_manifest` does not exist.

- [ ] **Step 3: Implement record types and period classification**

Create `00_common/run_manifest.py`:

```python
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


FIELDNAMES = (
    "run_number",
    "source_period",
    "target",
    "beam_type",
    "group",
    "classification_source",
    "source_file",
)
RUN_FILE_RE = re.compile(r"^run([1-9][0-9]*)\.root$")
DEUTERIUM_PERIOD_RE = re.compile(r"(?:^|_)d[0-9]*$", re.IGNORECASE)


class ManifestError(ValueError):
    pass


@dataclass(frozen=True)
class RunRecord:
    run_number: int
    source_period: str
    target: str
    beam_type: str
    group: str
    classification_source: str
    source_file: str


def classify_period(period: str) -> tuple[str, str, str, str]:
    name = period.lower()
    if DEUTERIUM_PERIOD_RE.search(name):
        return "D", "UNKNOWN", "UNASSIGNED", "unresolved"
    if "fuv" in name or "uv" in name:
        return "P", "UV", "P_UV", "automatic"
    if "vis" in name:
        return "P", "VIS", "P_VIS", "automatic"
    return "UNKNOWN", "UNKNOWN", "UNASSIGNED", "unresolved"
```

- [ ] **Step 4: Run classification test and verify GREEN**

Run:

```bash
pytest -q 00_common/tests/test_run_manifest.py::test_classify_period
```

Expected: `6 passed`.

- [ ] **Step 5: Write failing scan and CSV tests**

Append to `00_common/tests/test_run_manifest.py`:

```python
def _touch_run(root: Path, period: str, run: int) -> Path:
    path = root / period / f"run{run}.root"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    return path


def test_scan_runs_sorts_numerically_and_keeps_relative_provenance(tmp_path):
    _touch_run(tmp_path, "1999_vis", 20)
    _touch_run(tmp_path, "1998_uv", 3)

    records = scan_runs(tmp_path)

    assert [record.run_number for record in records] == [3, 20]
    assert records[0].source_file == "1998_uv/run3.root"
    assert records[1].group == "P_VIS"


def test_scan_runs_rejects_duplicate_run_numbers(tmp_path):
    _touch_run(tmp_path, "1998_uv", 7)
    _touch_run(tmp_path, "1999_vis", 7)

    with pytest.raises(ManifestError, match="duplicate run 7"):
        scan_runs(tmp_path)


def test_scan_runs_rejects_malformed_run_root_name(tmp_path):
    bad = tmp_path / "1998_uv" / "runABC.root"
    bad.parent.mkdir(parents=True)
    bad.touch()

    with pytest.raises(ManifestError, match="malformed run filename"):
        scan_runs(tmp_path)


def test_scan_runs_rejects_empty_scan(tmp_path):
    with pytest.raises(ManifestError, match="no run files"):
        scan_runs(tmp_path)


def test_write_manifest_uses_fixed_schema_and_stable_order(tmp_path):
    records = [
        RunRecord(3, "1998_uv", "P", "UV", "P_UV", "automatic",
                  "1998_uv/run3.root")
    ]
    output = tmp_path / "manifest.csv"

    write_manifest(records, output)

    assert output.read_text() == (
        "run_number,source_period,target,beam_type,group,"
        "classification_source,source_file\n"
        "3,1998_uv,P,UV,P_UV,automatic,1998_uv/run3.root\n"
    )
```

- [ ] **Step 6: Run scan/CSV tests and verify RED**

Run:

```bash
pytest -q 00_common/tests/test_run_manifest.py
```

Expected: classification tests pass; scan and write tests fail because functions are undefined.

- [ ] **Step 7: Implement deterministic scanning and writing**

Append to `00_common/run_manifest.py`:

```python
def scan_runs(input_dir: Path) -> list[RunRecord]:
    root = Path(input_dir)
    if not root.is_dir():
        raise ManifestError(f"input directory not found: {root}")

    candidates = sorted(root.rglob("run*.root"))
    malformed = [path for path in candidates if RUN_FILE_RE.fullmatch(path.name) is None]
    if malformed:
        raise ManifestError(f"malformed run filename: {malformed[0].relative_to(root)}")

    records: list[RunRecord] = []
    seen: dict[int, Path] = {}
    for path in candidates:
        match = RUN_FILE_RE.fullmatch(path.name)
        assert match is not None
        run_number = int(match.group(1))
        if run_number in seen:
            raise ManifestError(
                f"duplicate run {run_number}: "
                f"{seen[run_number].relative_to(root)} and {path.relative_to(root)}"
            )
        seen[run_number] = path
        period = path.parent.name
        target, beam_type, group, source = classify_period(period)
        records.append(
            RunRecord(
                run_number,
                period,
                target,
                beam_type,
                group,
                source,
                path.relative_to(root).as_posix(),
            )
        )

    if not records:
        raise ManifestError(f"no run files found under {root}")
    return sorted(records, key=lambda record: record.run_number)


def write_manifest(records: Sequence[RunRecord], output: Path) -> None:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "run_number": record.run_number,
                    "source_period": record.source_period,
                    "target": record.target,
                    "beam_type": record.beam_type,
                    "group": record.group,
                    "classification_source": record.classification_source,
                    "source_file": record.source_file,
                }
            )
```

- [ ] **Step 8: Run Task 1 tests and verify GREEN**

Run:

```bash
pytest -q 00_common/tests/test_run_manifest.py
```

Expected: `11 passed`.

- [ ] **Step 9: Commit Task 1**

```bash
git add 00_common/run_manifest.py 00_common/tests/test_run_manifest.py
git commit -m "feat: generate farm run manifest"
```

---

### Task 2: Strict manifest validation

**Files:**
- Modify: `00_common/run_manifest.py`
- Modify: `00_common/tests/test_run_manifest.py`

**Interfaces:**
- Consumes: CSV at `Path`.
- Produces: `read_manifest(path: Path) -> list[RunRecord]`
- Produces: `validate_manifest(path: Path) -> list[RunRecord]`
- Validation returns parsed records on success and raises `ManifestError` with row-specific messages on failure.

- [ ] **Step 1: Write failing complete-manifest validation test**

Append to imports:

```python
from graal_common.run_manifest import validate_manifest
```

Append test:

```python
def test_validate_manifest_accepts_complete_consistent_rows(tmp_path):
    path = tmp_path / "manifest.csv"
    path.write_text(
        "run_number,source_period,target,beam_type,group,"
        "classification_source,source_file\n"
        "3,1998_uv,P,UV,P_UV,automatic,1998_uv/run3.root\n"
        "20,2002_d1,D,VIS,D_VIS,manual,2002_d1/run20.root\n"
    )

    records = validate_manifest(path)

    assert [record.group for record in records] == ["P_UV", "D_VIS"]
```

- [ ] **Step 2: Run success test and verify RED**

Run:

```bash
pytest -q 00_common/tests/test_run_manifest.py::test_validate_manifest_accepts_complete_consistent_rows
```

Expected: import error because `validate_manifest` does not exist.

- [ ] **Step 3: Implement CSV parsing and base validation**

Append constants and functions to `00_common/run_manifest.py`:

```python
ALLOWED_TARGETS = {"P", "D", "UNKNOWN"}
ALLOWED_BEAM_TYPES = {"UV", "VIS", "UNKNOWN"}
ALLOWED_GROUPS = {"P_UV", "P_VIS", "D_UV", "D_VIS", "UNASSIGNED"}
ALLOWED_SOURCES = {"automatic", "manual", "unresolved"}


def read_manifest(path: Path) -> list[RunRecord]:
    manifest = Path(path)
    if not manifest.is_file():
        raise ManifestError(f"manifest not found: {manifest}")
    with manifest.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != list(FIELDNAMES):
            raise ManifestError(
                f"invalid columns: expected {','.join(FIELDNAMES)}, "
                f"got {','.join(reader.fieldnames or [])}"
            )
        records = []
        for row_number, row in enumerate(reader, start=2):
            try:
                run_number = int(row["run_number"])
            except (TypeError, ValueError):
                raise ManifestError(
                    f"row {row_number}: run_number must be a positive integer"
                ) from None
            records.append(
                RunRecord(
                    run_number,
                    row["source_period"],
                    row["target"],
                    row["beam_type"],
                    row["group"],
                    row["classification_source"],
                    row["source_file"],
                )
            )
    return records


def validate_manifest(path: Path) -> list[RunRecord]:
    records = read_manifest(path)
    if not records:
        raise ManifestError("manifest has no data rows")

    expected_run = -1
    seen: set[int] = set()
    for row_number, record in enumerate(records, start=2):
        prefix = f"row {row_number}: "
        if record.run_number <= 0:
            raise ManifestError(prefix + "run_number must be a positive integer")
        if record.run_number in seen:
            raise ManifestError(prefix + f"duplicate run {record.run_number}")
        if record.run_number <= expected_run:
            raise ManifestError(prefix + "rows must be ordered by run_number")
        seen.add(record.run_number)
        expected_run = record.run_number
        if not record.source_period:
            raise ManifestError(prefix + "source_period is empty")
        if not record.source_file:
            raise ManifestError(prefix + "source_file is empty")
        if record.target not in ALLOWED_TARGETS:
            raise ManifestError(prefix + f"invalid target {record.target!r}")
        if record.beam_type not in ALLOWED_BEAM_TYPES:
            raise ManifestError(prefix + f"invalid beam_type {record.beam_type!r}")
        if record.group not in ALLOWED_GROUPS:
            raise ManifestError(prefix + f"invalid group {record.group!r}")
        if record.classification_source not in ALLOWED_SOURCES:
            raise ManifestError(
                prefix + f"invalid classification_source "
                f"{record.classification_source!r}"
            )
        if (
            record.target == "UNKNOWN"
            or record.beam_type == "UNKNOWN"
            or record.group == "UNASSIGNED"
            or record.classification_source == "unresolved"
        ):
            raise ManifestError(prefix + "classification is unresolved")
        expected_group = f"{record.target}_{record.beam_type}"
        if record.group != expected_group:
            raise ManifestError(
                prefix + f"group {record.group!r} conflicts with "
                f"target/beam {expected_group!r}"
            )
        source = Path(record.source_file)
        if source.is_absolute():
            raise ManifestError(prefix + "source_file must be relative")
        if source.name != f"run{record.run_number}.root":
            raise ManifestError(
                prefix + "source_file basename does not match run_number"
            )
    return records
```

- [ ] **Step 4: Run success test and verify GREEN**

Run:

```bash
pytest -q 00_common/tests/test_run_manifest.py::test_validate_manifest_accepts_complete_consistent_rows
```

Expected: `1 passed`.

- [ ] **Step 5: Write failing rejection matrix**

Append:

```python
@pytest.mark.parametrize(
    ("row", "message"),
    [
        ("3,2002_d1,D,UNKNOWN,UNASSIGNED,unresolved,2002_d1/run3.root",
         "classification is unresolved"),
        ("3,1998_uv,P,UV,P_VIS,manual,1998_uv/run3.root",
         "conflicts with target/beam"),
        ("0,1998_uv,P,UV,P_UV,automatic,1998_uv/run0.root",
         "positive integer"),
        ("3,1998_uv,P,BLUE,P_UV,manual,1998_uv/run3.root",
         "invalid beam_type"),
        ("3,1998_uv,P,UV,P_UV,automatic,/farm/1998_uv/run3.root",
         "must be relative"),
        ("3,1998_uv,P,UV,P_UV,automatic,1998_uv/run4.root",
         "does not match run_number"),
    ],
)
def test_validate_manifest_rejects_invalid_rows(tmp_path, row, message):
    path = tmp_path / "manifest.csv"
    path.write_text(
        "run_number,source_period,target,beam_type,group,"
        "classification_source,source_file\n" + row + "\n"
    )
    with pytest.raises(ManifestError, match=message):
        validate_manifest(path)


def test_validate_manifest_rejects_duplicate_and_unsorted_rows(tmp_path):
    path = tmp_path / "manifest.csv"
    path.write_text(
        "run_number,source_period,target,beam_type,group,"
        "classification_source,source_file\n"
        "20,1999_vis,P,VIS,P_VIS,automatic,1999_vis/run20.root\n"
        "3,1998_uv,P,UV,P_UV,automatic,1998_uv/run3.root\n"
    )
    with pytest.raises(ManifestError, match="ordered by run_number"):
        validate_manifest(path)


def test_validate_manifest_rejects_wrong_schema(tmp_path):
    path = tmp_path / "manifest.csv"
    path.write_text("run_number,target\n3,P\n")
    with pytest.raises(ManifestError, match="invalid columns"):
        validate_manifest(path)
```

- [ ] **Step 6: Run validation tests and verify failures are specific**

Run:

```bash
pytest -q 00_common/tests/test_run_manifest.py
```

Expected before fixes: any missed constraint fails with its named message.

- [ ] **Step 7: Adjust implementation until full validation matrix passes**

Do not weaken test expectations. Keep first-error behavior deterministic by
checking fields in order shown in Step 3.

- [ ] **Step 8: Run Task 2 tests and verify GREEN**

Run:

```bash
pytest -q 00_common/tests/test_run_manifest.py
```

Expected: all manifest unit tests pass.

- [ ] **Step 9: Commit Task 2**

```bash
git add 00_common/run_manifest.py 00_common/tests/test_run_manifest.py
git commit -m "feat: validate curated run manifest"
```

---

### Task 3: Farm-facing CLI and end-to-end verification

**Files:**
- Create: `scripts/build_run_manifest.py`
- Modify: `00_common/tests/test_run_manifest.py`

**Interfaces:**
- Consumes generation args: `--input-dir PATH --output PATH`.
- Consumes validation arg: `--validate PATH`.
- Produces exit `0` plus summary on success; argparse exit `2` for invalid CLI;
  exit `1` plus `ERROR: ...` on manifest errors.

- [ ] **Step 1: Write failing CLI generation test**

Append imports and helper:

```python
import subprocess
import sys


SCRIPT = Path(__file__).parents[2] / "scripts" / "build_run_manifest.py"


def test_cli_generates_manifest_from_farm_tree(tmp_path):
    raw = tmp_path / "raw"
    _touch_run(raw, "1998_uv", 3)
    _touch_run(raw, "2002_d1", 20)
    output = tmp_path / "generated.csv"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--input-dir",
            str(raw),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0
    assert "Generated 2 runs" in result.stdout
    assert output.is_file()
```

- [ ] **Step 2: Run CLI generation test and verify RED**

Run:

```bash
pytest -q 00_common/tests/test_run_manifest.py::test_cli_generates_manifest_from_farm_tree
```

Expected: failure because script does not exist.

- [ ] **Step 3: Implement CLI**

Create `scripts/build_run_manifest.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from graal_common.run_manifest import (
    ManifestError,
    scan_runs,
    validate_manifest,
    write_manifest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate or validate the GRAAL run manifest."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--input-dir", type=Path)
    mode.add_argument("--validate", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.input_dir is not None and args.output is None:
        parser.error("--output is required with --input-dir")
    if args.validate is not None and args.output is not None:
        parser.error("--output cannot be used with --validate")
    return args


def main() -> int:
    args = parse_args()
    try:
        if args.validate is not None:
            records = validate_manifest(args.validate)
            counts = Counter(record.group for record in records)
            groups = ", ".join(
                f"{group}={counts[group]}" for group in sorted(counts)
            )
            print(f"Valid manifest: {len(records)} runs ({groups})")
            return 0

        records = scan_runs(args.input_dir)
        write_manifest(records, args.output)
        unresolved = sum(
            record.classification_source == "unresolved" for record in records
        )
        print(
            f"Generated {len(records)} runs -> {args.output} "
            f"({unresolved} unresolved)"
        )
        return 0
    except (ManifestError, OSError) as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run CLI generation test and verify GREEN**

Run:

```bash
pytest -q 00_common/tests/test_run_manifest.py::test_cli_generates_manifest_from_farm_tree
```

Expected: `1 passed`.

- [ ] **Step 5: Write failing CLI validation and error tests**

Append:

```python
def test_cli_validates_curated_manifest(tmp_path):
    path = tmp_path / "manifest.csv"
    path.write_text(
        "run_number,source_period,target,beam_type,group,"
        "classification_source,source_file\n"
        "3,1998_uv,P,UV,P_UV,automatic,1998_uv/run3.root\n"
    )
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--validate", str(path)],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0
    assert "Valid manifest: 1 runs (P_UV=1)" in result.stdout


def test_cli_returns_one_for_duplicate_farm_run(tmp_path):
    raw = tmp_path / "raw"
    _touch_run(raw, "1998_uv", 3)
    _touch_run(raw, "1999_vis", 3)
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--input-dir",
            str(raw),
            "--output",
            str(tmp_path / "generated.csv"),
        ],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 1
    assert "ERROR: duplicate run 3" in result.stdout


def test_cli_requires_output_for_generation(tmp_path):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--input-dir", str(tmp_path)],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 2
    assert "--output is required with --input-dir" in result.stderr
```

- [ ] **Step 6: Run CLI tests and verify GREEN**

Run:

```bash
pytest -q 00_common/tests/test_run_manifest.py
```

Expected: all manifest tests pass.

- [ ] **Step 7: Run full repository verification**

Run:

```bash
pytest -q
git diff --check
```

Expected: all tests pass; `git diff --check` prints nothing.

- [ ] **Step 8: Smoke-test help text**

Run:

```bash
python scripts/build_run_manifest.py --help
```

Expected: help lists mutually exclusive `--input-dir` and `--validate`, plus
`--output`.

- [ ] **Step 9: Commit Task 3**

```bash
git add scripts/build_run_manifest.py 00_common/tests/test_run_manifest.py
git commit -m "feat: add farm run manifest CLI"
```

