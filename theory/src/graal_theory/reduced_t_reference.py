"""Signed reduced S11 projection and independently traced P73 Figure 1 data."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from graal_theory.amplitudes.nstar1535_reduced import ReducedTParameters, reduced_tmatrix


def isospin_half_s11_eta(w_gev: float, parameters: ReducedTParameters) -> complex:
    """P65 Eq. (10), using the positive-eigenvalue I=1/2 charge combination."""
    t = reduced_tmatrix(w_gev, parameters)
    rho = np.zeros(3)
    for i in range(3):
        meson = parameters.meson_masses_gev[i]
        baryon = parameters.baryon_masses_gev[i]
        if w_gev <= meson + baryon:
            raise ValueError("S11 eta projection requires open pi N and eta p channels")
        q = np.sqrt((w_gev*w_gev-(meson+baryon)**2) *
                    (w_gev*w_gev-(meson-baryon)**2))/(2*w_gev)
        rho[i] = baryon*q/(4*np.pi*w_gev)
    # Condon-Shortley CG gives (-1/sqrt(3), +sqrt(2/3)) for
    # (|1,0;p>, |1,+1;n>); P65 |pi+> = -|1,+1> makes both charge
    # coefficients negative. The outer minus is P65 Eq. (10).
    u = (-1/np.sqrt(3), -np.sqrt(2/3))
    return complex(-np.sqrt(rho[2]) *
                   (u[0]*np.sqrt(rho[0])*t[0, 2] +
                    u[1]*np.sqrt(rho[1])*t[1, 2]))


@dataclass(frozen=True)
class Fig1Point:
    energy_gev: float
    real_s11: float
    imag_s11: float
    reading_error: float


_FIG1_GRID = (1.50, 1.52, 1.54, 1.56, 1.58, 1.60, 1.62, 1.64)
_FIG1_COLUMNS = ("energy_gev", "real_s11", "imag_s11", "reading_error")
_CURVE = "dashed: reduced without t-channel vector exchange and pi pi N"


def load_fig1_reduced(
    csv_path: Path, metadata_path: Path, pdf_path: Path,
) -> tuple[Fig1Point, ...]:
    """Load hand-traced dashed strokes only when provenance and grid match."""
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if (not isinstance(metadata, dict) or metadata.get("figure") != 1
            or metadata.get("source_page") != 3
            or metadata.get("printed_page") != "045209-3"
            or metadata.get("curve") != _CURVE
            or not isinstance(metadata.get("reference_csv_sha256"), str)
            or len(metadata["reference_csv_sha256"]) != 64
            or any(digit not in "0123456789abcdef"
                   for digit in metadata["reference_csv_sha256"])
            or not isinstance(metadata.get("axis_calibration"), dict)
            or not metadata["axis_calibration"]
            or any(not isinstance(metadata.get(key), str) or not metadata[key].strip()
                   for key in ("trace_method", "uncertainty_method"))):
        raise ValueError("invalid PRC 73 Figure 1 metadata")
    digest = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    if metadata.get("source_pdf_sha256") != digest:
        raise ValueError("PDF digest differs from reviewed PRC 73 source")
    csv_bytes = csv_path.read_bytes()
    reader = csv.DictReader(io.StringIO(csv_bytes.decode("utf-8"), newline=""))
    if tuple(reader.fieldnames or ()) != _FIG1_COLUMNS:
        raise ValueError("invalid Figure 1 CSV columns")
    rows = list(reader)
    if len(rows) != len(_FIG1_GRID):
        raise ValueError("Figure 1 needs eight predeclared energies")
    points = []
    for row, energy in zip(rows, _FIG1_GRID):
        if set(row) != set(_FIG1_COLUMNS):
            raise ValueError("invalid Figure 1 CSV row")
        point = Fig1Point(*(float(row[key]) for key in _FIG1_COLUMNS))
        if (not np.isclose(point.energy_gev, energy, rtol=0, atol=1e-10)
                or not np.all(np.isfinite(tuple(vars(point).values())))
                or point.reading_error < 0.02):
            raise ValueError("invalid Figure 1 point")
        points.append(point)
    if hashlib.sha256(csv_bytes).hexdigest() != metadata["reference_csv_sha256"]:
        raise ValueError("CSV digest differs from reviewed PRC 73 Figure 1 trace")
    return tuple(points)


def compare_fig1_reduced(
    parameters: ReducedTParameters, points: tuple[Fig1Point, ...],
) -> list[dict[str, float]]:
    """Return signed model-minus-publication residuals; never refit inputs."""
    result = []
    for point in points:
        predicted = isospin_half_s11_eta(point.energy_gev, parameters)
        result.append({
            "energy_gev": point.energy_gev,
            "predicted_real": predicted.real,
            "predicted_imag": predicted.imag,
            "reference_real": point.real_s11,
            "reference_imag": point.imag_s11,
            "residual_real": predicted.real-point.real_s11,
            "residual_imag": predicted.imag-point.imag_s11,
            "reading_error": point.reading_error,
        })
    return result
