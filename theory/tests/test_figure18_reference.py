"""Bounded independent PRC73 Figure 18 full-model source reading."""

import csv
import json
from pathlib import Path

import pytest

from graal_theory.figure18_reference import load_figure18_full_1700


REFERENCES = Path(__file__).resolve().parents[1]/"references"
PDF = Path(__file__).resolve().parents[2]/"tmp/pdfs/10.1103@PhysRevC.73.045209.pdf"


def test_figure18_full_source_is_bounded_and_pdf_authenticated(tmp_path):
    rows = load_figure18_full_1700(
        REFERENCES/"p73_figure18_full_1700.csv",
        REFERENCES/"p73_figure18_full_1700.json", PDF)
    assert len(rows) >= 2
    assert all(point.mass_gev <= 1.80 and point.reading_error > 0 for point in rows)
    bad_csv = tmp_path/"bad.csv"
    with bad_csv.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("mass_gev", "dsigma_dmass_microbarn_per_gev", "reading_error"))
        writer.writerow((1.81, 4., 2.))
        writer.writerow((1.82, 3., 2.))
    with pytest.raises(ValueError, match="1.80"):
        load_figure18_full_1700(bad_csv,
            REFERENCES/"p73_figure18_full_1700.json", PDF)
    bad_metadata = tmp_path/"bad.json"
    record = json.loads((REFERENCES/"p73_figure18_full_1700.json").read_text())
    record["source_pdf_sha256"] = "0"*64
    bad_metadata.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="digest"):
        load_figure18_full_1700(REFERENCES/"p73_figure18_full_1700.csv",
            bad_metadata, PDF)
