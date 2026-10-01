# Figure 4 Reference Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an audited numerical reference for the twelve published Figure 4 theory lines and an explicit source-dependency inventory, before planning the full coherent calculation. This is the first executable slice of the approved spec, not the full-model implementation.

**Architecture:** Keep source audit and published-line data inside standalone `theory/`; add one small loader that validates the reference data and its PDF identity. No calculated theory is added in this plan. The coherent-amplitude and twelve-panel prediction work from the approved spec will receive a separate implementation plan after this audit fixes its source and phase conventions.

**Tech Stack:** Python 3.10+, standard-library `csv`, `hashlib`, `json`, `dataclasses`; existing `pytest`; Poppler `pdftotext`/`pdftoppm` and existing Matplotlib for manual source inspection.

**Spec:** `theory/docs/2026-10-01-figure4-theory-design.md`

## Global Constraints

- Scope: publication Figure 4 reference and amplitude source inventory only; no Stage 07/08 edits or output changes.
- Existing Eq. (43) pilot stays labeled `partial tree contribution`; traced curves stay labeled `published theory reference`, never calculated output.
- Source PDF is `tmp/pdfs/PhysRevLett.100.052003.pdf`, page 5, SHA-256 `7fdf85fe56fa8b0e232d070269e3e58d4d7ca542dcd9ac2287291abaa6b4f1cb`.
- The twelve panels are three pairs (`p_pi0`, `p_eta`, `eta_pi0`) by energy bins 0–3: `[1.10,1.20)`, `[1.20,1.30)`, `[1.30,1.40)`, `[1.40,1.50]` GeV.
- No source parameter, phase, or formula is inferred from visual agreement with Figure 4. Missing dependencies remain explicit blockers for the corresponding amplitude.
- Preserve all pre-existing worktree edits. Stage and commit only paths owned by the current task.

## Review Focus

1. Wrong Figure 4 PDF or changed revision must fail checksum validation (Task 2 test).
2. Missing or duplicated panel/abscissa must fail reference loading (Task 2 tests).
3. Nonfinite/out-of-axis mass, `|Sigma| > 1`, or nonpositive reading error must fail loading (Task 2 tests).
4. Experimental circles accidentally traced as theory must be caught by source-overlay review and separate curve-kind metadata (Task 3 review and test).
5. A missing external scattering-amplitude source must remain marked blocked, not silently converted into an implementable term (Task 1 audit check).

## File map

- `theory/references/figure4_amplitude_inventory.md` — diagram-by-diagram source, phase, and missing-dependency audit; no executable amplitude.
- `theory/src/graal_theory/figure4_reference.py` — validated loader for the published theory-line reference; no model evaluation or plotting.
- `theory/tests/test_figure4_reference.py` — synthetic malformed-input tests and real reference smoke test.
- `theory/references/ajaka2008_figure4_theory.csv` — manually reviewed theory-line samples only.
- `theory/references/ajaka2008_figure4_theory.json` — PDF hash, page, curve identity, calibration and uncertainty method.
- `theory/scripts/review_figure4_trace.py` — 4-by-3 visual review plot of the traced reference; no physics model.

All six paths are new; no currently dirty tracked file needs modification. Existing `theory/pyproject.toml` already packages `*.csv` and `*.json` in `graal_theory.references`.

## Spec coverage for this slice

Task 1 covers the spec's amplitude inventory and missing-source gate. Tasks 2–3 cover independently reviewed twelve-line reference data, PDF identity, and visual review. The spec's coherent amplitude, phase-space edge integration, calculated twelve-panel curves, and comparison with our finer-binned data are **not** deliverables of this plan: the first two require the source audit; the publication comparison follows their validation; our-data integration is a later milestone by the spec. This split prevents an implementation plan from inventing unavailable coupled-channel equations.

### Task 1: Audit amplitude sources and stopping conditions

**Files:**
- Create: `theory/references/figure4_amplitude_inventory.md`

**Interfaces:**
- Consumes: approved spec, local 2006 PRC/PLB PDFs, existing `theory/references/sources.json` and `parameter_provenance.md`.
- Produces: reviewed term/source table used to scope the later coherent-model plan; no Python API.

- [ ] **Step 1: Read source locators and verify PDFs**

Run from repository root:

```bash
shasum -a 256 'tmp/pdfs/10.1103@PhysRevC.73.045209.pdf' 'tmp/pdfs/10.1016@j.physletb.2006.06.022.pdf' 'tmp/pdfs/nucl-th-0012065.pdf' 'tmp/pdfs/nucl-th-0407025.pdf'
pdftotext -layout 'tmp/pdfs/10.1103@PhysRevC.73.045209.pdf' - | rg -n 'FIG\. (6|7|8|9|10|11|12|13|14)|\(26\)|\(39\)|\(40\)|\(41\)|\(42\)|\(43\)|\[8\]|\[17\]|\[21\]'
```

Expected: PRC Eq. (43) is existing tree; Eq. (26) inserts production terms into rescattering; Fig. 14 solid line is coherent sum. PRC Ref. [8] is Inoue, Oset, Vicente Vacas, *Phys. Rev. C* **65**, 035204 (2002), and its PDF is not in the supplied folder at planning time. Record any further unresolved dependency found in equations, loop regularization, or phase conventions.

- [ ] **Step 2: Write inventory with one row per distinct amplitude family**

Use `apply_patch` to create a document with columns `family`, `PRC locator`, `needed external source`, `phase/coupling evidence`, `local PDF`, `status`. Cover at minimum: chiral contact (Fig. 6), meson pole plus Kroll–Ruderman (Fig. 7), intermediate pion emission (Fig. 8), explicit-resonance/Delta Kroll–Ruderman terms (Fig. 9), eta-Delta and K-Sigma-star rescattering plus Sigma-star Kroll–Ruderman (Fig. 10; Eqs. 39–42 inserted into Eq. 26), and the isolated Eq. (43) tree (Fig. 11). Include separate row for coupled-channel `N*(1535)` transition matrix used by Eq. (26). Use `implemented_partial`, `sourced_not_implemented`, or `blocked_missing_source` only when evidence supports it. Identify each external paper by full citation, not guessed DOI.

- [ ] **Step 3: Check inventory against Figure 14 captions and bibliography**

Run:

```bash
rg -n 'Fig\. (6|7|8|9|10|11|14)|Eq\. (26|39|40|41|42|43)|Inoue|blocked_missing_source|implemented_partial' theory/references/figure4_amplitude_inventory.md
git diff --check -- theory/references/figure4_amplitude_inventory.md
```

Expected: all named families appear, unresolved Ref. [8] is visibly blocked, existing Eq. (43) alone is `implemented_partial`; no claim that the full amplitude is sourced yet. Read PRC Fig. 14 caption beside the table before approval.

- [ ] **Step 4: Commit only the inventory**

```bash
git add theory/references/figure4_amplitude_inventory.md
git diff --cached --name-only
git commit -m 'docs(theory): audit Figure 4 amplitudes'
```

Expected staged list: one inventory file. If source audit finds additional missing references, keep their status blocked and report them; do not improvise an amplitude.

### Task 2: Validate published-line data independently of the model

**Files:**
- Create: `theory/src/graal_theory/figure4_reference.py`
- Create: `theory/tests/test_figure4_reference.py`

**Interfaces:**
- Consumes: CSV columns `pair,energy_bin,mass_gev,sigma,reading_error`; JSON keys `source_pdf_sha256`, `source_page`, `figure`, `curve_kind`, `trace_method`, `uncertainty_method`.
- Produces: `PublishedCurvePoint(pair: str, energy_bin: int, mass_gev: float, sigma: float, reading_error: float)` and `load_published_theory_curves(csv_path: Path, metadata_path: Path, source_pdf_path: Path | None = None) -> tuple[PublishedCurvePoint, ...]`. Optional PDF permits installed-package use without redistributing the source paper; when supplied, its bytes must match metadata.

- [ ] **Step 1: Write failing tests for a complete synthetic 4-by-3 reference**

Create `theory/tests/test_figure4_reference.py` with a fixture helper that writes 24 rows (two increasing masses per panel). Use this complete test body; keep tests for source identity separate from real-data review:

```python
import csv
import hashlib
import json
from pathlib import Path

import pytest

from graal_theory.figure4_reference import (
    EXPECTED_PANELS,
    load_published_theory_curves,
)

PAIRS = {"p_pi0": (1.0, 1.4), "p_eta": (1.4, 1.8), "eta_pi0": (0.6, 1.0)}
COLUMNS = ("pair", "energy_bin", "mass_gev", "sigma", "reading_error")


def _write_fixture(tmp_path, *, edit_rows=None, edit_metadata=None):
    rows = [
        {"pair": pair, "energy_bin": energy_bin, "mass_gev": low + offset,
         "sigma": -0.2, "reading_error": 0.02}
        for energy_bin in range(4)
        for pair, (low, _) in PAIRS.items()
        for offset in (0.10, 0.20)
    ]
    if edit_rows is not None:
        rows = edit_rows(rows)
    csv_path = tmp_path / "curves.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"PDF fixture")
    metadata = {
        "source_pdf_sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
        "source_page": 5,
        "figure": 4,
        "curve_kind": "published_full_coherent_theory",
        "trace_method": "fixture pixels",
        "uncertainty_method": "fixture half-stroke",
    }
    if edit_metadata is not None:
        edit_metadata(metadata)
    metadata_path = tmp_path / "curves.json"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    return csv_path, metadata_path, pdf_path


def test_complete_reference_loads_sorted(tmp_path):
    points = load_published_theory_curves(*_write_fixture(tmp_path))
    assert len(points) == 24
    assert {(p.pair, p.energy_bin) for p in points} == EXPECTED_PANELS
    assert points == tuple(sorted(points, key=lambda p: (p.energy_bin, p.pair, p.mass_gev)))


def test_changed_pdf_fails_digest(tmp_path):
    csv_path, metadata_path, pdf_path = _write_fixture(tmp_path)
    pdf_path.write_bytes(b"different PDF")
    with pytest.raises(ValueError, match="PDF digest"):
        load_published_theory_curves(csv_path, metadata_path, pdf_path)


def test_missing_panel_fails(tmp_path):
    paths = _write_fixture(
        tmp_path,
        edit_rows=lambda rows: [r for r in rows if not (r["pair"] == "p_eta" and r["energy_bin"] == 3)],
    )
    with pytest.raises(ValueError, match="panel"):
        load_published_theory_curves(*paths)


def test_duplicate_abscissa_fails(tmp_path):
    paths = _write_fixture(tmp_path, edit_rows=lambda rows: rows + [rows[-1].copy()])
    with pytest.raises(ValueError, match="mass"):
        load_published_theory_curves(*paths)


@pytest.mark.parametrize(
    ("field", "value"),
    [("sigma", 1.01), ("mass_gev", float("nan")), ("mass_gev", 9.0),
     ("reading_error", 0.0)],
)
def test_invalid_point_fails(tmp_path, field, value):
    def change(rows):
        rows[0][field] = value
        return rows
    with pytest.raises(ValueError, match="row"):
        load_published_theory_curves(*_write_fixture(tmp_path, edit_rows=change))


def test_experimental_curve_label_fails(tmp_path):
    def change(metadata):
        metadata["curve_kind"] = "experimental_points"
    with pytest.raises(ValueError, match="curve_kind"):
        load_published_theory_curves(*_write_fixture(tmp_path, edit_metadata=change))


def test_extra_csv_field_fails(tmp_path):
    csv_path, metadata_path, pdf_path = _write_fixture(tmp_path)
    text = csv_path.read_text(encoding="utf-8")
    csv_path.write_text(text.replace("-0.2,0.02\n", "-0.2,0.02,extra\n", 1), encoding="utf-8")
    with pytest.raises(ValueError, match="row"):
        load_published_theory_curves(csv_path, metadata_path, pdf_path)
```

- [ ] **Step 2: Run test to verify red state**

```bash
cd theory
python -m pytest -q tests/test_figure4_reference.py
```

Expected: collection fails because `graal_theory.figure4_reference` does not yet exist.

- [ ] **Step 3: Implement minimal validated loader**

Create `figure4_reference.py` with this implementation. It checks each malformed row before panel coverage, so diagnostics remain specific:

```python
"""Audited samples of Ajaka 2008 Figure 4 published theory lines."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

EXPECTED_COLUMNS = ("pair", "energy_bin", "mass_gev", "sigma", "reading_error")
PAIR_MASS_AXES = {"p_pi0": (1.0, 1.4), "p_eta": (1.4, 1.8), "eta_pi0": (0.6, 1.0)}
EXPECTED_PANELS = {(pair, energy) for pair in PAIR_MASS_AXES for energy in range(4)}


@dataclass(frozen=True)
class PublishedCurvePoint:
    pair: str
    energy_bin: int
    mass_gev: float
    sigma: float
    reading_error: float


def load_published_theory_curves(
    csv_path: Path, metadata_path: Path, source_pdf_path: Path | None = None,
) -> tuple[PublishedCurvePoint, ...]:
    metadata = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
    if not isinstance(metadata, dict):
        raise ValueError("reference metadata must be an object")
    if metadata.get("figure") != 4 or metadata.get("source_page") != 5:
        raise ValueError("reference must identify Figure 4, PDF page 5")
    if metadata.get("curve_kind") != "published_full_coherent_theory":
        raise ValueError("curve_kind must identify published full coherent theory")
    for key in ("trace_method", "uncertainty_method"):
        if not isinstance(metadata.get(key), str) or not metadata[key].strip():
            raise ValueError(f"missing {key}")
    recorded_digest = metadata.get("source_pdf_sha256")
    if not isinstance(recorded_digest, str) or len(recorded_digest) != 64 or any(
        char not in "0123456789abcdef" for char in recorded_digest
    ):
        raise ValueError("invalid source PDF digest")
    if source_pdf_path is not None:
        digest = hashlib.sha256(Path(source_pdf_path).read_bytes()).hexdigest()
        if recorded_digest != digest:
            raise ValueError("PDF digest differs from reviewed source")

    grouped: dict[tuple[str, int], list[PublishedCurvePoint]] = {
        key: [] for key in EXPECTED_PANELS
    }
    with Path(csv_path).open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != EXPECTED_COLUMNS:
            raise ValueError("reference CSV columns differ from expected schema")
        for row_number, row in enumerate(reader, start=2):
            if None in row:
                raise ValueError(f"invalid row {row_number}: extra CSV field")
            try:
                pair = row["pair"]
                energy_bin = int(row["energy_bin"])
                mass = float(row["mass_gev"])
                sigma = float(row["sigma"])
                error = float(row["reading_error"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"invalid row {row_number}") from exc
            key = (pair, energy_bin)
            if key not in EXPECTED_PANELS:
                raise ValueError(f"invalid row {row_number}: unknown panel {key}")
            low, high = PAIR_MASS_AXES[pair]
            if not all(math.isfinite(x) for x in (mass, sigma, error)) or not (
                low <= mass <= high and abs(sigma) <= 1.0 and error > 0.0
            ):
                raise ValueError(f"invalid row {row_number}: physical range or error")
            grouped[key].append(PublishedCurvePoint(pair, energy_bin, mass, sigma, error))

    for key, points in grouped.items():
        if len(points) < 2:
            raise ValueError(f"panel {key} needs at least two theory-line points")
        if any(a.mass_gev >= b.mass_gev for a, b in zip(points, points[1:])):
            raise ValueError(f"mass positions must increase in panel {key}")
    return tuple(sorted(
        (point for points in grouped.values() for point in points),
        key=lambda point: (point.energy_bin, point.pair, point.mass_gev),
    ))
```

Do not import Stage 07 or model code. Keep the extra-CSV-field test: a correct header alone does not reject a row with an additional field.

- [ ] **Step 4: Run green tests and standalone suite**

```bash
cd theory
python -m pytest -q tests/test_figure4_reference.py
python -m pytest -q
```

Expected: all tests pass. If the dirty worktree contains unrelated failing tests, record exact failure and verify this test file separately; do not change unrelated files under this task.

- [ ] **Step 5: Commit only loader and tests**

```bash
git add theory/src/graal_theory/figure4_reference.py theory/tests/test_figure4_reference.py
git diff --cached --name-only
git commit -m 'feat(theory): validate Figure 4 reference'
```

Expected staged list: loader and its test only.

### Task 3: Trace and review all twelve published theory lines

**Files:**
- Create: `theory/references/ajaka2008_figure4_theory.csv`
- Create: `theory/references/ajaka2008_figure4_theory.json`
- Create: `theory/scripts/review_figure4_trace.py`
- Modify: `theory/tests/test_figure4_reference.py`

**Interfaces:**
- Consumes: Task 2 loader and Ajaka 2008 Figure 4, PDF page 5.
- Produces: reviewed, source-hashed numerical curve reference usable by the later full-model comparison; no computed theory output.

- [ ] **Step 1: Render the source at high resolution**

```bash
pdftoppm -f 5 -l 5 -r 600 -png -singlefile tmp/pdfs/PhysRevLett.100.052003.pdf /private/tmp/ajaka2008_figure4_page5_600dpi
shasum -a 256 tmp/pdfs/PhysRevLett.100.052003.pdf
```

Expected digest: value in Global Constraints. Inspect the rendered page, not OCR text, because Figure 4 lines and circles overlap.

- [ ] **Step 2: Digitize visible theory strokes**

Use `apply_patch` for the CSV and JSON. Sample every visible curve at approximately 0.01 GeV and at extrema/endpoints; omit hidden stretches rather than inventing interpolation through experimental markers. For each panel calibrate pixel `x` with its printed mass ticks and pixel `y` with its `Sigma=0` and `±0.4` ticks. Record these calibration anchors, render DPI, trace date, and a per-point `reading_error` method in JSON. The CSV contains only theory strokes, never published circles; use pair names and energy-bin indices from Global Constraints. Record no point outside its printed curve extent. Resolve each ambiguous crossing by reinspection at higher zoom, or omit that sample and explain the omission in JSON.

- [ ] **Step 3: Add real-data regression test**

Append this test to `theory/tests/test_figure4_reference.py`:

```python
def test_reviewed_ajaka_figure4_theory_reference_loads():
    root = Path(__file__).resolve().parents[1]
    source = root.parent / "tmp/pdfs/PhysRevLett.100.052003.pdf"
    metadata_path = root / "references/ajaka2008_figure4_theory.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["source_pdf_sha256"] == "7fdf85fe56fa8b0e232d070269e3e58d4d7ca542dcd9ac2287291abaa6b4f1cb"
    points = load_published_theory_curves(
        root / "references/ajaka2008_figure4_theory.csv",
        metadata_path,
        source if source.is_file() else None,
    )
    assert len(points) >= 24
    assert {(point.pair, point.energy_bin) for point in points} == EXPECTED_PANELS
```

Import `Path` and `EXPECTED_PANELS` in that test file. The JSON must set `curve_kind` to `published_full_coherent_theory`, `figure` to 4, `source_page` to 5, and the source PDF digest to the value above.

- [ ] **Step 4: Add review plot of reference data**

Create `theory/scripts/review_figure4_trace.py` with this body; it writes only ignored/generated `theory/outputs/figure4_reference_review.pdf`:

```python
"""Render traced Ajaka Figure 4 theory lines for source-page review."""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from graal_theory.figure4_reference import (
    PAIR_MASS_AXES,
    load_published_theory_curves,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / "tmp/pdfs/PhysRevLett.100.052003.pdf"
POINTS = load_published_theory_curves(
    ROOT / "references/ajaka2008_figure4_theory.csv",
    ROOT / "references/ajaka2008_figure4_theory.json",
    SOURCE if SOURCE.is_file() else None,
)
PAIRS = ("p_pi0", "p_eta", "eta_pi0")
fig, axes = plt.subplots(4, 3, figsize=(10, 10), sharex="col", sharey=True)
for energy_bin in range(4):
    for column, pair in enumerate(PAIRS):
        ax = axes[energy_bin, column]
        panel = [p for p in POINTS if p.pair == pair and p.energy_bin == energy_bin]
        x = [p.mass_gev for p in panel]
        y = [p.sigma for p in panel]
        error = [p.reading_error for p in panel]
        ax.errorbar(x, y, yerr=error, fmt="k.", markersize=3, capsize=1)
        ax.axhline(0, color="0.6", linewidth=0.5)
        ax.set_xlim(*PAIR_MASS_AXES[pair])
        ax.set_ylim(-0.8, 0.4)
        ax.set_title(f"{pair}, energy bin {energy_bin}")
        if energy_bin == 3:
            ax.set_xlabel("pair mass [GeV]")
        if column == 0:
            ax.set_ylabel("Sigma")
destination = ROOT / "outputs/figure4_reference_review.pdf"
destination.parent.mkdir(parents=True, exist_ok=True)
fig.tight_layout()
fig.savefig(destination)
plt.close(fig)
print(destination)
```

- [ ] **Step 5: Verify numeric and visual fidelity**

```bash
cd theory
python -m pytest -q tests/test_figure4_reference.py
python -m pytest -q
PYTHONPATH=src python scripts/review_figure4_trace.py
```

Expected: all twelve panels load; no malformed points; review PDF exists. Its unconnected markers must not bridge omitted/occluded strokes. Compare it beside source page 5 at the same axes, especially the sign-changing `p_eta` top-row line and overlaps in the lower rows. Review every panel, record reviewer/date and any omitted ambiguity in JSON. A test passing is not a substitute for this visual review. Do not tune points to current Eq. (43) output.

- [ ] **Step 6: Commit only reference data, review script, and its real-data test**

```bash
git add theory/references/ajaka2008_figure4_theory.csv theory/references/ajaka2008_figure4_theory.json theory/scripts/review_figure4_trace.py theory/tests/test_figure4_reference.py
git diff --cached --name-only
git commit -m 'docs(theory): trace Ajaka Figure 4 curves'
```

Expected staged list: two reference files, review script, and real-data test. Report row counts, panel coverage, reading uncertainties, PDF digest, and unresolved source dependencies. Do not call this a reproduced theoretical calculation.

## Next plan gate

After Tasks 1–3, write the **coherent-amplitude implementation plan** from the audited inventory and acquired primary sources. It must name exact complex amplitude equations, coupled-channel transition inputs, phase conventions, component regressions, and integration tests. If any required source remains unavailable, request it or document a scientifically distinct reduced-model target; do not fill the gap with Figure 4 curve fitting. Only after that implementation passes can a third plan add the twelve-panel calculated comparison and later our higher-statistics binning.
