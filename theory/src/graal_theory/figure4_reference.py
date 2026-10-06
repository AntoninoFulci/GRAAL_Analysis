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
    status: str = "resolved"


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
