"""Bibliographic and numerical parameter provenance."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import numpy as np


@dataclass(frozen=True)
class SourceRef:
    citation_key: str
    persistent_id: str
    locator: str

    def __post_init__(self) -> None:
        if not self.citation_key.strip() or not self.persistent_id.strip():
            raise ValueError("source requires citation key and persistent identifier")


@dataclass(frozen=True)
class PhysicalParameter:
    name: str
    value: float | complex
    unit: str
    source: SourceRef

    def __post_init__(self) -> None:
        numeric = complex(self.value)
        if not self.name.strip():
            raise ValueError("parameter name must be nonempty")
        if not np.isfinite(numeric.real) or not np.isfinite(numeric.imag):
            raise ValueError(f"parameter {self.name!r} must be finite")
        if not self.unit.strip():
            raise ValueError(f"parameter {self.name!r} requires a unit")
        if not self.source.locator.strip() or "://" in self.source.locator:
            raise ValueError(f"parameter {self.name!r} requires a source locator")


def load_source_registry(path: Path) -> dict[str, dict[str, str]]:
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, dict) or not records:
        raise ValueError("source registry must be a nonempty object")
    for key, record in records.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("source keys must be nonempty strings")
        if not isinstance(record, dict):
            raise ValueError(f"source {key!r} must be an object")
        if not str(record.get("citation", "")).strip():
            raise ValueError(f"source {key!r} has no citation")
        identifiers = (record.get("doi"), record.get("arxiv"))
        if not any(isinstance(value, str) and value.strip() for value in identifiers):
            raise ValueError(f"source {key!r} has no persistent identifier")
    return records


def validate_parameter_sources(parameters: Mapping[str, PhysicalParameter]) -> None:
    for key, parameter in parameters.items():
        if key != parameter.name:
            raise ValueError(f"parameter key/name mismatch: {key!r}")
        if not parameter.unit.strip() or not parameter.source.locator.strip():
            raise ValueError(f"parameter {key!r} has incomplete provenance")
