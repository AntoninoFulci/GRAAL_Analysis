"""P65 Eq. (28) final-fit subtractions, separate from the reduced inputs.

Using these inputs with pi-pi-N alone yields an intermediate variant;
the published final model also contains vector-meson exchange.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from graal_theory.amplitudes.nstar1535_reduced import ReducedTParameters
from graal_theory.sources import PhysicalParameter, SourceRef, load_source_registry


_FINAL_NAMES = ("mu", "a_piN", "a_etaN", "a_KLambda", "a_KSigma")


def _validated_final_values(raw: dict, sources: dict) -> dict[str, float]:
    values = {}
    for name in _FINAL_NAMES:
        entry = raw[name]
        unit = "GeV" if name == "mu" else "1"
        if (not isinstance(entry, dict)
                or set(entry) != {"value", "unit", "source_key", "locator"}
                or entry["unit"] != unit
                or entry["source_key"] != "inoue_2002"
                or "inoue_2002" not in sources
                or not isinstance(entry["locator"], str)
                or not entry["locator"].strip()
                or not isinstance(entry["value"], (int, float))
                or isinstance(entry["value"], bool)):
            raise ValueError(f"invalid final fit entry {name}")
        source = sources["inoue_2002"]
        ref = SourceRef("inoue_2002", source.get("doi") or source.get("arxiv"),
                        entry["locator"])
        values[name] = float(PhysicalParameter(
            name, float(entry["value"]), unit, ref).value)
    if values["mu"] <= 0:
        raise ValueError("final fit mu must be positive")
    return values


def load_final_fit_parameters(
    base: ReducedTParameters, parameter_path: Path, source_path: Path,
) -> ReducedTParameters:
    """Return new final-fit inputs, preserving masses and the reduced record.

    The existing class name is retained for compatibility; it does not label
    these final-fit values as reduced-model parameters.
    """
    raw = json.loads(parameter_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != set(_FINAL_NAMES):
        raise ValueError("final fit parameter names differ from source schema")
    values = _validated_final_values(raw, load_source_registry(source_path))
    if values["mu"] != base.mu_gev:
        raise ValueError("final fit mu differs from base mu")
    return replace(
        base,
        mu_gev=values["mu"],
        subtraction_constants=(
            values["a_piN"], values["a_piN"], values["a_etaN"],
            values["a_KSigma"], values["a_KLambda"], values["a_KSigma"],
        ),
    )
