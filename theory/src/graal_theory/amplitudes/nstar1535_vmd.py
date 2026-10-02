"""Source-linked vector masses for the N*(1535) VMD variant."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from graal_theory.sources import PhysicalParameter, SourceRef, load_source_registry


@dataclass(frozen=True)
class VectorMasses:
    rho_gev: float
    kstar_gev: float

    def __post_init__(self) -> None:
        for name in ("rho_gev", "kstar_gev"):
            value = getattr(self, name)
            if (isinstance(value, (bool, np.bool_))
                    or not isinstance(value, (int, float, np.integer, np.floating))
                    or not np.isfinite(value) or value <= 0):
                raise ValueError(f"{name} must be a finite positive real")


def load_vector_masses(parameter_path: Path, source_path: Path) -> VectorMasses:
    """Load positive GeV masses with the Inoue source and paper locators."""
    raw = json.loads(parameter_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != {"m_rho", "m_kstar"}:
        raise ValueError("VMD parameter names differ from source schema")
    sources = load_source_registry(source_path)
    values = {}
    for name in ("m_rho", "m_kstar"):
        entry = raw[name]
        if (not isinstance(entry, dict)
                or set(entry) != {"value", "unit", "source_key", "locator"}
                or entry["unit"] != "GeV"
                or entry["source_key"] != "inoue_2002"
                or "inoue_2002" not in sources
                or not isinstance(entry["locator"], str)
                or not entry["locator"].strip()
                or "://" in entry["locator"]
                or isinstance(entry["value"], (bool, np.bool_))
                or not isinstance(entry["value"], (int, float, np.integer, np.floating))
                or not np.isfinite(entry["value"])
                or entry["value"] <= 0):
            raise ValueError(f"invalid VMD entry {name}")
        source = sources["inoue_2002"]
        ref = SourceRef("inoue_2002", source.get("doi") or source.get("arxiv"),
                        entry["locator"])
        values[name] = float(PhysicalParameter(
            name, float(entry["value"]), "GeV", ref).value)
    return VectorMasses(values["m_rho"], values["m_kstar"])
