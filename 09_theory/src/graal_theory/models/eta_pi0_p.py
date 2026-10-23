"""The gamma p -> eta pi0 p Eq. 43 partial reaction model."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import numpy as np
from numpy.typing import NDArray

from ..amplitudes.delta1700 import Delta1700Parameters, tree_amplitude
from ..phase_space import ThreeBodySample
from ..sources import PhysicalParameter, SourceRef, load_source_registry, validate_parameter_sources
from ..spin import transverse_polarizations


REQUIRED_TREE_PARAMETER_UNITS = {
    "proton_mass": "GeV",
    "pi0_mass": "GeV",
    "eta_mass": "GeV",
    "charged_pion_mass": "GeV",
    "delta_mass": "GeV",
    "delta_pole_width": "GeV",
    "delta1700_mass": "GeV",
    "delta1700_nominal_width": "GeV",
    "rho_mass": "GeV",
    "f_delta_n_pi": "1",
    "g_eta_delta": "1",
    "g1_prime": "m_N^-1",
    "g2_prime": "m_N^-2",
    "n_pi_branching_fraction": "1",
    "g_rho": "1",
    "f_rho": "1",
    "f_tilde_delta_pi": "1",
    "g_tilde_delta_pi": "1",
}
REQUIRED_TREE_PARAMETER_NAMES = frozenset(REQUIRED_TREE_PARAMETER_UNITS)


def load_central_parameters(
    parameter_path: Path,
    source_path: Path,
) -> dict[str, PhysicalParameter]:
    sources = load_source_registry(source_path)
    raw = json.loads(parameter_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("central parameter file must be an object")
    missing = sorted(REQUIRED_TREE_PARAMETER_NAMES - raw.keys())
    unexpected = sorted(raw.keys() - REQUIRED_TREE_PARAMETER_NAMES)
    if missing or unexpected:
        raise ValueError(f"central parameter names: missing={missing}, unexpected={unexpected}")
    parameters = {}
    for name, entry in raw.items():
        if not isinstance(entry, dict) or set(entry) != {"value", "unit", "source_key", "locator"}:
            raise ValueError(f"parameter {name!r} requires value, unit, source_key, locator")
        if entry["unit"] != REQUIRED_TREE_PARAMETER_UNITS[name]:
            raise ValueError(f"parameter {name!r} requires unit {REQUIRED_TREE_PARAMETER_UNITS[name]}")
        source_key = entry["source_key"]
        if source_key not in sources:
            raise ValueError(f"parameter {name!r} references unknown source {source_key!r}")
        source_record = sources[source_key]
        persistent_id = source_record.get("doi") or source_record.get("arxiv")
        raw_value = entry["value"]
        if isinstance(raw_value, dict) and set(raw_value) == {"real", "imag"}:
            value = complex(raw_value["real"], raw_value["imag"])
        elif isinstance(raw_value, (int, float)) and not isinstance(raw_value, bool):
            value = float(raw_value)
        else:
            raise ValueError(f"parameter {name!r} has malformed value")
        parameters[name] = PhysicalParameter(
            name, value, entry["unit"],
            SourceRef(source_key, persistent_id, entry["locator"]),
        )
    validate_parameter_sources(parameters)
    return parameters


@dataclass(frozen=True)
class EtaPi0PModel:
    parameters: Delta1700Parameters

    @classmethod
    def from_files(cls, parameter_path: Path, source_path: Path) -> "EtaPi0PModel":
        physical = load_central_parameters(parameter_path, source_path)
        return cls(Delta1700Parameters.from_parameters(physical))

    @property
    def masses(self) -> tuple[float, float, float]:
        p = self.parameters
        return p.eta_mass_gev, p.pi0_mass_gev, p.proton_mass_gev

    def polarized_matrix_element_squared(
        self,
        sample: ThreeBodySample,
        polarization: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        """Sum final proton spin, average initial proton spin for one photon state."""
        epsilon = np.asarray(polarization, dtype=np.float64)
        if (
            epsilon.shape != (3,)
            or not np.all(np.isfinite(epsilon))
            or not np.isclose(np.linalg.norm(epsilon), 1.0, atol=1e-12)
            or not np.isclose(epsilon[2], 0.0, atol=1e-12)
        ):
            raise ValueError("photon polarization must be a unit transverse vector")
        amplitude = tree_amplitude(sample, epsilon, self.parameters)
        return np.sum(np.abs(amplitude) ** 2, axis=(1, 2)) / 2.0

    def matrix_element_squared(
        self,
        sample: ThreeBodySample,
        *,
        polarizations: tuple[NDArray[np.float64], NDArray[np.float64]] | None = None,
    ) -> NDArray[np.float64]:
        if polarizations is None:
            polarizations = transverse_polarizations(np.array([0.0, 0.0, 1.0]))
        if len(polarizations) != 2:
            raise ValueError("two transverse photon polarizations are required")
        basis = np.asarray(polarizations, dtype=np.float64)
        if basis.shape != (2, 3) or not np.allclose(basis @ basis.T, np.eye(2), atol=1e-12) or not np.allclose(basis[:, 2], 0.0, atol=1e-12):
            raise ValueError("photon polarizations must be orthonormal and transverse")
        total = np.zeros(len(sample.momenta), dtype=np.float64)
        for epsilon in basis:
            total += self.polarized_matrix_element_squared(sample, epsilon)
        return total / 2.0
