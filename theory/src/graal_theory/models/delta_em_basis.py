"""Exact event-amplitude basis for the two Delta(1700) EM couplings."""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass, replace
import hashlib
import json
from collections.abc import Mapping

import numpy as np
from numpy.typing import NDArray

from ..phase_space import ThreeBodySample
from .eta_pi0_p_full import EtaPi0PFullModel


def _record(value):
    """Canonical snapshot, including provenance omitted by dataclass equality."""
    if is_dataclass(value):
        return {field.name: _record(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _record(item) for key, item in sorted(value.items())}
    if isinstance(value, (tuple, list)):
        return [_record(item) for item in value]
    if isinstance(value, complex):
        return {"real": value.real, "imag": value.imag}
    if isinstance(value, np.generic):
        return value.item()
    return value


def _fingerprint(model: EtaPi0PFullModel, anchor: tuple[float, float]) -> str:
    parameters = model.parameters
    fixed_tree = replace(parameters.tree, g1_prime=anchor[0], g2_prime=anchor[1])
    payload = {
        "tree": _record(fixed_tree),
        "strong": _record(parameters.strong),
        "vector_masses": _record(parameters.vector_masses),
        "production": _record(parameters.production),
        "grid": None if model.strong_grid is None else model.strong_grid.fingerprint,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DeltaEMBasis:
    matrices: NDArray[np.complex128]
    anchor_g1: float
    anchor_g2: float
    fingerprint: str

    def coefficients(self, g1_prime: float, g2_prime: float) -> NDArray[np.float64]:
        values = np.asarray((g1_prime, g2_prime))
        if values.shape != (2,) or values.dtype.kind not in "iuf" or not np.isfinite(values).all():
            raise ValueError("EM couplings must be finite real scalars")
        coefficients = np.array((1., float(g1_prime)-self.anchor_g1,
                                 float(g2_prime)-self.anchor_g2), dtype=np.float64)
        if not np.isfinite(coefficients).all():
            raise ValueError("EM coefficient difference must be finite")
        return coefficients

    def reconstruct(self, g1_prime: float, g2_prime: float) -> NDArray[np.complex128]:
        with np.errstate(over="raise", invalid="raise"):
            result = np.einsum("a,anij->nij", self.coefficients(g1_prime, g2_prime),
                               self.matrices)
        if not np.isfinite(result).all():
            raise ValueError("reconstructed amplitude must be finite")
        return result

    def validate_model(self, model: EtaPi0PFullModel) -> None:
        if not isinstance(model, EtaPi0PFullModel) or _fingerprint(
                model, (self.anchor_g1, self.anchor_g2)) != self.fingerprint:
            raise ValueError("model fixed-physics fingerprint does not match basis")


def delta_em_event_basis(model: EtaPi0PFullModel, sample: ThreeBodySample,
                         polarization: NDArray[np.float64]) -> DeltaEMBasis:
    """Freeze complete seven-family amplitudes at source and unit EM offsets."""
    if not isinstance(model, EtaPi0PFullModel):
        raise ValueError("model requires EtaPi0PFullModel")
    tree = model.parameters.tree
    anchor = (tree.g1_prime, tree.g2_prime)
    source = model.amplitude(sample, polarization)

    def shifted(g1: float, g2: float) -> NDArray[np.complex128]:
        parameters = replace(model.parameters, tree=replace(tree, g1_prime=g1, g2_prime=g2))
        return EtaPi0PFullModel(parameters, model.strong_grid).amplitude(sample, polarization)

    matrices = np.stack((source, shifted(anchor[0]+1., anchor[1])-source,
                         shifted(anchor[0], anchor[1]+1.)-source)).astype(np.complex128)
    if matrices.shape != (3, len(sample.momenta), 2, 2) or not np.isfinite(matrices).all():
        raise ValueError("EM basis requires finite complex spin matrices")
    matrices.setflags(write=False)
    return DeltaEMBasis(matrices, *anchor, _fingerprint(model, anchor))
