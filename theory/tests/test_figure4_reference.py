import csv
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from graal_theory.figure4_reference import EXPECTED_PANELS, load_published_theory_curves


PAIRS = {"p_pi0": (1.0, 1.4), "p_eta": (1.4, 1.8), "eta_pi0": (0.6, 1.0)}
COLUMNS = ("pair", "energy_bin", "mass_gev", "sigma", "reading_error")


def _write_fixture(tmp_path, *, edit_rows=None, edit_metadata=None):
    rows = [
        {
            "pair": pair,
            "energy_bin": energy_bin,
            "mass_gev": low + offset,
            "sigma": -0.2,
            "reading_error": 0.02,
        }
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
    [("sigma", 1.01), ("mass_gev", float("nan")), ("mass_gev", 9.0), ("reading_error", 0.0)],
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
    contents = csv_path.read_text(encoding="utf-8")
    csv_path.write_text(contents.replace("-0.2,0.02\n", "-0.2,0.02,extra\n", 1), encoding="utf-8")
    with pytest.raises(ValueError, match="row"):
        load_published_theory_curves(csv_path, metadata_path, pdf_path)


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


def test_review_plot_script_renders_reference():
    root = Path(__file__).resolve().parents[1]
    output = root / "outputs/figure4_reference_review.pdf"
    result = subprocess.run(
        [sys.executable, str(root / "scripts/review_figure4_trace.py")],
        cwd=root,
        env={**os.environ, "PYTHONPATH": str(root / "src")},
        text=True,
        capture_output=True,
        check=True,
    )
    assert result.stdout.strip() == str(output)
    assert output.read_bytes().startswith(b"%PDF-")
