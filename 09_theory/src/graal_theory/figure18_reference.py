"""Independent, source-bounded PRC73 Figure 18 high-energy check."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path


PDF_SHA256 = "19a2fbce10ed8201a29bdfbcfb9f3690a280d943c1e83db01aa1b2057d20eccb"
COLUMNS = ("mass_gev", "dsigma_dmass_microbarn_per_gev", "reading_error")


@dataclass(frozen=True)
class Figure18Point:
    mass_gev: float
    dsigma_dmass_microbarn_per_gev: float
    reading_error: float


def load_figure18_full_1700(csv_path: Path, metadata_path: Path,
                             source_pdf_path: Path | None = None) -> tuple[Figure18Point, ...]:
    metadata = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
    if (not isinstance(metadata, dict) or metadata.get("source_pdf_sha256") != PDF_SHA256
            or metadata.get("figure") != 18 or metadata.get("pdf_page") != 14
            or metadata.get("energy_gev") != 1.7
            or metadata.get("curve_kind") != "full_model_solid"
            or metadata.get("supported_mass_interval_gev") != [1.515, 1.8]):
        raise ValueError("Figure 18 source metadata or digest mismatch")
    if source_pdf_path is not None:
        actual = hashlib.sha256(Path(source_pdf_path).read_bytes()).hexdigest()
        if actual != PDF_SHA256:
            raise ValueError("Figure 18 PDF digest mismatch")
    for key in ("trace_method", "ambiguity", "reading_error_kind", "calibration"):
        if not metadata.get(key):
            raise ValueError(f"Figure 18 metadata missing {key}")
    points = []
    with Path(csv_path).open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != COLUMNS:
            raise ValueError("Figure 18 CSV columns differ from audited schema")
        for index, row in enumerate(reader, 2):
            if None in row or set(row) != set(COLUMNS):
                raise ValueError(f"Figure 18 row {index} has extra or missing fields")
            try:
                mass, density, error = (float(row[column]) for column in COLUMNS)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Figure 18 row {index} is nonnumeric") from exc
            if (not all(math.isfinite(v) for v in (mass, density, error))
                    or mass < 1.515 or mass > 1.80 or density < 0 or error <= 0):
                raise ValueError(f"Figure 18 row {index} outside W<=1.80 or reading bounds")
            points.append(Figure18Point(mass, density, error))
    if len(points) < 2 or any(a.mass_gev >= b.mass_gev
                              for a,b in zip(points,points[1:])):
        raise ValueError("Figure 18 trace requires ordered distinct source points")
    return tuple(points)
