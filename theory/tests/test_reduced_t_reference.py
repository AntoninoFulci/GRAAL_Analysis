"""Published reduced S11 phase and independent reference checks."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pytest

from graal_theory.amplitudes.nstar1535_reduced import (
    C_COEFFICIENTS,
    load_reduced_parameters,
    reduced_tmatrix,
)
from graal_theory.reduced_t_reference import (
    compare_fig1_reduced,
    isospin_half_s11_eta,
    load_fig1_reduced,
)


ROOT = Path(__file__).resolve().parents[2]
REFERENCES = ROOT / "theory" / "references"
PARAM = REFERENCES / "nstar1535_reduced_parameters.json"
SOURCES = REFERENCES / "sources.json"
FIG1_CSV = REFERENCES / "p73_fig1_reduced.csv"
FIG1_META = REFERENCES / "p73_fig1_reduced.json"
P73_PDF = ROOT / "tmp" / "pdfs" / "10.1103@PhysRevC.73.045209.pdf"


def test_isospin_half_phase_is_fixed_by_charge_basis():
    # Standard <1,0;1/2,+1/2|1/2,+1/2> = -1/sqrt(3) and
    # <1,+1;1/2,-1/2|1/2,+1/2> = +sqrt(2/3).
    # P65 |pi+> = -|1,+1> turns the latter charge coefficient negative.
    u = np.array([-1/np.sqrt(3), -np.sqrt(2/3)])
    np.testing.assert_allclose(C_COEFFICIENTS[:2, :2] @ u, 2*u)
    p = load_reduced_parameters(PARAM, SOURCES)
    w = 1.54
    t = reduced_tmatrix(w, p)
    rho = []
    for i in (0, 1, 2):
        m, baryon = p.meson_masses_gev[i], p.baryon_masses_gev[i]
        q = np.sqrt((w*w-(m+baryon)**2)*(w*w-(m-baryon)**2))/(2*w)
        rho.append(baryon*q/(4*np.pi*w))
    expected = -np.sqrt(rho[2]) * (
        u[0]*np.sqrt(rho[0])*t[0, 2] +
        u[1]*np.sqrt(rho[1])*t[1, 2])
    assert isospin_half_s11_eta(w, p) == pytest.approx(expected)


def test_projection_requires_open_channels():
    p = load_reduced_parameters(PARAM, SOURCES)
    with pytest.raises(ValueError, match="open"):
        isospin_half_s11_eta(1.48, p)


def test_fig1_reference_rejects_changed_pdf(tmp_path):
    altered = tmp_path / "wrong.pdf"
    altered.write_bytes(b"not PRC 73")
    with pytest.raises(ValueError, match="PDF"):
        load_fig1_reduced(FIG1_CSV, FIG1_META, altered)


def test_fig1_reference_has_signed_both_components():
    points = load_fig1_reduced(FIG1_CSV, FIG1_META, P73_PDF)
    assert [p.energy_gev for p in points] == pytest.approx(
        [1.50, 1.52, 1.54, 1.56, 1.58, 1.60, 1.62, 1.64])
    assert all(np.isfinite((p.real_s11, p.imag_s11, p.reading_error)).all()
               and p.reading_error > 0 for p in points)
    assert points[0].real_s11 > 0 and points[-1].real_s11 < 0
    assert all(p.imag_s11 >= 0 for p in points)


def test_fig1_reference_rejects_changed_grid_and_nonfinite_value(tmp_path):
    with FIG1_CSV.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    path = tmp_path / "changed.csv"
    for field, value in (("energy_gev", "1.521"), ("real_s11", "nan")):
        modified = [dict(row) for row in rows]
        modified[1][field] = value
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(modified)
        with pytest.raises(ValueError, match="point"):
            load_fig1_reduced(path, FIG1_META, P73_PDF)


def test_fig1_reference_rejects_same_grid_value_substitution(tmp_path):
    with FIG1_CSV.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    rows[3]["imag_s11"] = "0.425"  # Plausible experimental dot, not dashed stroke.
    changed = tmp_path / "wrong-trace.csv"
    with changed.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match="CSV digest"):
        load_fig1_reduced(changed, FIG1_META, P73_PDF)


def test_fig1_reference_rejects_missing_metadata(tmp_path):
    metadata = json.loads(FIG1_META.read_text(encoding="utf-8"))
    del metadata["axis_calibration"]
    path = tmp_path / "changed.json"
    path.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ValueError, match="metadata"):
        load_fig1_reduced(FIG1_CSV, path, P73_PDF)


def test_comparison_keeps_observed_values_and_signed_residuals():
    p = load_reduced_parameters(PARAM, SOURCES)
    points = load_fig1_reduced(FIG1_CSV, FIG1_META, P73_PDF)
    rows = compare_fig1_reduced(p, points)
    assert len(rows) == 8
    for row, point in zip(rows, points):
        assert row["reference_real"] == point.real_s11
        assert row["reference_imag"] == point.imag_s11
        assert row["residual_real"] == pytest.approx(row["predicted_real"] - point.real_s11)
        assert row["residual_imag"] == pytest.approx(row["predicted_imag"] - point.imag_s11)
