"""Seven-family coherent gamma p -> eta pi0 p production model.

Physical methods always add every complex spin matrix before the spin sum.
Only the explicitly selected diagnostic methods may restrict whole families;
the gauge partners inside a family remain inseparable.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
import json
from numbers import Complex, Real
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

import numpy as np
from numpy.typing import NDArray

from ..amplitudes.chiral_photoproduction import (
    chiral_contact_amplitude, external_pi0_amplitude, internal_pi0_amplitude,
)
from ..amplitudes.decuplet_rescattering import (
    eta_delta_rescattering_amplitude, k_sigma_star_rescattering_amplitude,
)
from ..amplitudes.delta1700 import Delta1700Parameters, tree_amplitude
from ..amplitudes.nstar1535_final_fit import load_final_fit_parameters
from ..amplitudes.nstar1535_full import reconstructed_full_tmatrix
from ..amplitudes.nstar1535_reduced import ReducedTParameters, load_reduced_parameters
from ..amplitudes.nstar1535_vmd import VectorMasses, load_vector_masses
from ..amplitudes.production_loops import (
    ProductionParameters, QuadratureSettings, load_production_parameters,
)
from ..amplitudes.propagators import Delta1700WidthParameters
from ..amplitudes.resonance_photoproduction import explicit_resonance_amplitude
from ..kinematics import invariant_mass, validate_final_state
from ..phase_space import ThreeBodySample
from ..sources import PhysicalParameter
from .eta_pi0_p import load_central_parameters


FAMILY_NAMES = (
    "chiral_contact", "external_pi0", "internal_pi0", "explicit_resonances",
    "eta_delta_rescattering", "k_sigma_star_rescattering", "eq43_tree",
)


def _finite_scalar(value: object, name: str, *, complex_allowed: bool = False) -> None:
    kind = Complex if complex_allowed else Real
    allowed = "complex" if complex_allowed else "real"
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, kind):
        raise ValueError(f"{name} must be a finite {allowed} scalar")
    try:
        numeric = complex(value) if complex_allowed else float(value)
        if not np.isfinite(numeric):
            raise ValueError("nonfinite or outside double-precision range")
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite {allowed} scalar: {exc}") from exc


def _validate_scalars(record, label: str, *, skip=(), complex_fields=()) -> None:
    for field in fields(record):
        name = field.name
        if name in skip:
            continue
        value = getattr(record, name)
        _finite_scalar(value, f"{label}.{name}", complex_allowed=name in complex_fields)
        if ("mass_gev" in name or "cutoff_gev" in name) and value <= 0:
            raise ValueError(f"{label}.{name} must be positive")
        if "width_gev" in name and value < 0:
            raise ValueError(f"{label}.{name} must be nonnegative")


def _frozen_provenance(value, name: str) -> Mapping[str, PhysicalParameter]:
    if (not isinstance(value, Mapping)
            or any(not isinstance(key, str) or not isinstance(record, PhysicalParameter)
                   for key, record in value.items())):
        raise ValueError(f"{name} must map parameter names to PhysicalParameter records")
    return MappingProxyType(dict(value))


@dataclass(frozen=True)
class FullModelParameters:
    """Validated immutable parameter blocks; final-fit inputs stay separate."""

    tree: Delta1700Parameters
    strong: ReducedTParameters
    vector_masses: VectorMasses
    production: ProductionParameters

    def __post_init__(self) -> None:
        for name, expected in (("tree", Delta1700Parameters), ("strong", ReducedTParameters),
                               ("vector_masses", VectorMasses), ("production", ProductionParameters)):
            if not isinstance(getattr(self, name), expected):
                raise ValueError(f"{name} requires {expected.__name__}")
        tree, production = self.tree, self.production
        _validate_scalars(tree, "tree", skip=("width_parameters", "provenance"),
                          complex_fields=("g_eta_delta",))
        if not isinstance(tree.width_parameters, Delta1700WidthParameters):
            raise ValueError("tree.width_parameters requires Delta1700WidthParameters")
        _validate_scalars(tree.width_parameters, "tree.width_parameters")
        # Re-run nested records' own domain checks, including caller replacements.
        width = replace(tree.width_parameters)
        strong, vectors = replace(self.strong), replace(self.vector_masses)
        _validate_scalars(production, "production", skip=("quadrature", "provenance"),
                          complex_fields=("g_k_sigma_star",))
        if not isinstance(production.quadrature, QuadratureSettings):
            raise ValueError("production.quadrature requires QuadratureSettings")
        quadrature = replace(production.quadrature)
        shared = (
            (tree.eta_mass_gev, strong.meson_masses_gev[2]),
            (tree.pi0_mass_gev, strong.meson_masses_gev[0]),
            (tree.proton_mass_gev, strong.baryon_masses_gev[0]),
            (tree.pion_reference_mass_gev, strong.meson_masses_gev[1]),
            (width.pole_mass_gev, tree.delta1700_mass_gev),
            (width.proton_mass_gev, tree.proton_mass_gev),
            (width.pion_mass_gev, tree.pion_reference_mass_gev),
            (width.delta_mass_gev, tree.delta_mass_gev),
            (width.delta_pole_width_gev, tree.delta_width_gev),
        )
        if any(not np.isclose(a, b, rtol=0, atol=1e-12) for a, b in shared):
            raise ValueError("tree, width and strong records require consistent shared masses/widths")
        if tree.delta_mass_gev <= tree.proton_mass_gev+tree.pion_reference_mass_gev:
            raise ValueError("tree.delta_mass_gev must exceed proton-pion threshold")
        if production.sigma_star_mass_gev <= strong.baryon_masses_gev[4]+tree.pi0_mass_gev:
            raise ValueError("production.sigma_star_mass_gev must exceed Lambda-pi0 threshold")
        object.__setattr__(self, "tree", replace(tree, width_parameters=width,
            provenance=_frozen_provenance(tree.provenance, "tree.provenance")))
        object.__setattr__(self, "strong", strong)
        object.__setattr__(self, "vector_masses", vectors)
        object.__setattr__(self, "production", replace(production, quadrature=quadrature,
            provenance=_frozen_provenance(production.provenance, "production.provenance")))

    @property
    def proton_mass_gev(self) -> float:
        return self.tree.proton_mass_gev


def _real_array(value, name: str) -> NDArray[np.float64]:
    try:
        raw = np.asarray(value)
        # NumPy would silently turn bools mixed with floats into real entries.
        mixed_bool = (not isinstance(value, np.ndarray)
                      and any(isinstance(item, (bool, np.bool_))
                              for item in np.asarray(value, dtype=object).flat))
        if raw.dtype.kind not in "iuf" or mixed_bool or not np.all(np.isfinite(raw)):
            raise ValueError("requires finite real values without bools or complex casts")
        with np.errstate(over="raise", invalid="raise"):
            result = np.asarray(raw, dtype=np.float64)
        if not np.all(np.isfinite(result)):
            raise ValueError("requires finite float64 values")
        return result
    except (TypeError, ValueError, OverflowError, FloatingPointError) as exc:
        raise ValueError(f"{name}: {exc}") from exc


def _polarization(value) -> NDArray[np.float64]:
    epsilon = _real_array(value, "photon polarization")
    if (epsilon.shape != (3,)
            or not np.isclose(np.linalg.norm(epsilon), 1., rtol=0, atol=1e-12)
            or abs(epsilon[2]) > 1e-12):
        raise ValueError("photon polarization must be a unit transverse three-vector")
    return epsilon


def _polarization_basis(value) -> NDArray[np.float64]:
    basis = _real_array((np.array([1., 0., 0.]), np.array([0., 1., 0.]))
                        if value is None else value, "photon polarizations")
    if (basis.shape != (2, 3)
            or not np.allclose(basis @ basis.T, np.eye(2), rtol=0, atol=1e-12)
            or np.any(abs(basis[:, 2]) > 1e-12)):
        raise ValueError("photon polarizations must be two orthonormal transverse vectors")
    return basis


def _coherent_sum(matrices) -> NDArray[np.complex128]:
    try:
        with np.errstate(over="raise", invalid="raise"):
            result = np.add.reduce(tuple(matrices))
        if not np.all(np.isfinite(result)):
            raise ValueError("nonfinite coherent amplitude")
        return result
    except FloatingPointError as exc:
        raise ValueError(f"coherent amplitude overflow: {exc}") from exc


def _spin_weight(amplitude) -> NDArray[np.float64]:
    try:
        with np.errstate(over="raise", invalid="raise"):
            result = np.sum(np.abs(amplitude)**2, axis=(1, 2))/2.
        if not np.all(np.isfinite(result)):
            raise ValueError("nonfinite spin-summed weight")
        return result
    except FloatingPointError as exc:
        raise ValueError(f"spin-summed weight overflow: {exc}") from exc


def _photon_average(weights) -> NDArray[np.float64]:
    # Divide before adding, so two finite large weights do not overflow.
    return np.add.reduce(tuple(weight/2. for weight in weights))


def _selection(families: tuple[str, ...]) -> tuple[str, ...]:
    if (not isinstance(families, tuple) or not families
            or any(not isinstance(name, str) or name not in FAMILY_NAMES for name in families)
            or len(set(families)) != len(families)):
        raise ValueError("diagnostic families must be a nonempty tuple of distinct whole family names")
    return families


@dataclass(frozen=True)
class EtaPi0PFullModel:
    parameters: FullModelParameters

    def __post_init__(self) -> None:
        if not isinstance(self.parameters, FullModelParameters):
            raise ValueError("parameters requires FullModelParameters")

    @classmethod
    def from_files(cls, reference_dir: Path) -> "EtaPi0PFullModel":
        references = Path(reference_dir)
        sources = references / "sources.json"
        # The legacy tree loader predates strict complex-component validation.
        # Guard its raw values here without changing the standalone Eq. 43 path.
        central_path = references / "central_parameters.json"
        central = json.loads(central_path.read_text(encoding="utf-8"))
        if isinstance(central, dict):
            eta_entry = central.get("g_eta_delta")
            if isinstance(eta_entry, dict):
                value = eta_entry.get("value")
                if isinstance(value, dict) and set(value) == {"real", "imag"}:
                    for component, numeric in value.items():
                        _finite_scalar(numeric, f"g_eta_delta.{component}")
        tree = Delta1700Parameters.from_parameters(load_central_parameters(
            central_path, sources))
        reduced = load_reduced_parameters(references / "nstar1535_reduced_parameters.json", sources)
        strong = load_final_fit_parameters(reduced, references / "nstar1535_final_subtractions.json", sources)
        vectors = load_vector_masses(references / "nstar1535_vmd_masses.json", sources)
        production = load_production_parameters(references / "eta_pi0_p_full_parameters.json", sources)
        return cls(FullModelParameters(tree, strong, vectors, production))

    @property
    def masses(self) -> tuple[float, float, float]:
        tree = self.parameters.tree
        return tree.eta_mass_gev, tree.pi0_mass_gev, tree.proton_mass_gev

    def _validate_sample(self, sample: ThreeBodySample) -> int:
        if not isinstance(sample, ThreeBodySample):
            raise ValueError("full model requires ThreeBodySample")
        initial = _real_array(sample.initial, "sample.initial")
        momenta = _real_array(sample.momenta, "sample.momenta")
        masses = _real_array(sample.masses, "sample.masses")
        if (momenta.ndim != 3 or momenta.shape[1:] != (3, 4) or not len(momenta)
                or initial.shape != (len(momenta), 4)):
            raise ValueError("sample requires nonempty momenta (N,3,4) and initial (N,4)")
        if masses.shape != (3,) or not np.allclose(masses, self.masses, rtol=0, atol=1e-12):
            raise ValueError("sample masses must follow (eta,pi0,proton) ordering")
        if np.any(abs(initial[:, 1:]) > 1e-12):
            raise ValueError("sample must be in the overall CM frame")
        if not np.allclose(initial[:, 0], initial[0, 0], rtol=0, atol=1e-12):
            raise ValueError("sample initial CM energy must be identical for all events")
        if np.any(initial[:, 0] <= sum(self.masses)) or np.any(momenta[:, :, 0] <= 0):
            raise ValueError("sample requires open three-body threshold and positive final energies")
        validate_final_state(initial, momenta, self.masses)
        for name in ("weights_gev2", "s12_gev2"):
            value = _real_array(getattr(sample, name), f"sample.{name}")
            if value.shape != (len(momenta),) or np.any(value < 0):
                raise ValueError(f"sample.{name} requires N finite nonnegative values")
        expected_s12 = invariant_mass(momenta[:, 0]+momenta[:, 1])**2
        if not np.allclose(sample.s12_gev2, expected_s12, rtol=0, atol=1e-12):
            raise ValueError("sample.s12_gev2 must match eta-pi0 invariant")
        return len(momenta)

    def _families(self, sample, polarization, names) -> Mapping[str, NDArray[np.complex128]]:
        size = self._validate_sample(sample)
        epsilon = _polarization(polarization)
        p = self.parameters

        def strong_t(w_gev: float) -> NDArray[np.complex128]:
            return reconstructed_full_tmatrix(w_gev, p.strong, p.vector_masses)

        # Concrete family functions retain ownership of their indivisible subterms.
        functions = {
            "chiral_contact": lambda: chiral_contact_amplitude(sample, epsilon, p.production, p.strong, strong_t),
            "external_pi0": lambda: external_pi0_amplitude(sample, epsilon, p.production, p.strong, strong_t),
            "internal_pi0": lambda: internal_pi0_amplitude(sample, epsilon, p.production, p.strong, strong_t),
            "explicit_resonances": lambda: explicit_resonance_amplitude(sample, epsilon, p.production, p.tree, p.strong, strong_t),
            "eta_delta_rescattering": lambda: eta_delta_rescattering_amplitude(sample, epsilon, p.production, p.tree, p.strong, strong_t),
            "k_sigma_star_rescattering": lambda: k_sigma_star_rescattering_amplitude(sample, epsilon, p.production, p.tree, p.strong, strong_t),
            "eq43_tree": lambda: tree_amplitude(sample, epsilon, p.tree),
        }
        result = {}
        for name in names:
            value = functions[name]()
            if (not isinstance(value, np.ndarray) or value.shape != (size, 2, 2)
                    or value.dtype != np.dtype(np.complex128) or not np.all(np.isfinite(value))):
                raise ValueError(f"{name}: family amplitude requires finite complex128 (N,2,2)")
            # Snapshot after validation; the diagnostic never freezes a producer's array.
            matrix = value.copy()
            matrix.setflags(write=False)
            result[name] = matrix
        return MappingProxyType(result)

    def family_amplitudes(self, sample: ThreeBodySample, polarization) -> Mapping[str, NDArray[np.complex128]]:
        """Read-only diagnostics for all seven complete family spin matrices."""
        return self._families(sample, polarization, FAMILY_NAMES)

    def amplitude(self, sample: ThreeBodySample, polarization) -> NDArray[np.complex128]:
        """Physical eventwise complex sum, always containing all seven families."""
        return _coherent_sum(self.family_amplitudes(sample, polarization).values())

    def polarized_matrix_element_squared(self, sample: ThreeBodySample, polarization) -> NDArray[np.float64]:
        full = self.amplitude(sample, polarization)
        return _spin_weight(full)

    def matrix_element_squared(self, sample: ThreeBodySample, *, polarizations=None) -> NDArray[np.float64]:
        """Average two orthonormal transverse photon states after the spin sum."""
        basis = _polarization_basis(polarizations)
        return _photon_average(self.polarized_matrix_element_squared(sample, epsilon)
                               for epsilon in basis)

    def selected_amplitude(self, sample: ThreeBodySample, polarization,
                           families: tuple[str, ...]) -> NDArray[np.complex128]:
        """Diagnostic coherent amplitude for a validated selection of whole families."""
        return _coherent_sum(self._families(sample, polarization, _selection(families)).values())

    def selected_matrix_element_squared(self, sample: ThreeBodySample, families: tuple[str, ...],
                                        polarizations=None) -> NDArray[np.float64]:
        """Diagnostic photon average; no selection changes the physical methods."""
        names = _selection(families)
        basis = _polarization_basis(polarizations)
        return _photon_average(_spin_weight(self.selected_amplitude(sample, epsilon, names))
                               for epsilon in basis)
