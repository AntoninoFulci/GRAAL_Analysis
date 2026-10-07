"""Crash-safe, content-addressed Figure 4 basis checkpoints."""

from __future__ import annotations

from dataclasses import asdict, fields, is_dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Mapping

import numpy as np

from .figure4_basis import BasisBinCertificate, BasisBinMoment


_TYPES = {item.__name__: item for item in (BasisBinCertificate, BasisBinMoment)}


def _digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def fingerprint_inputs(target: str, paths: Mapping[str, Path], settings: Mapping) -> str:
    """Hash source/data contents and numerical policy, including uncommitted code."""
    if target not in ("ajaka", "native") or not paths:
        raise ValueError("unknown target or empty fingerprint inputs")
    payload = {"target": target, "files": {name: _digest(Path(path))
               for name, path in sorted(paths.items())}, "settings": settings}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False,
                                     separators=(",", ":")).encode()).hexdigest()


def _pack(value, arrays: dict[str, np.ndarray]):
    if isinstance(value, np.ndarray):
        name = f"array_{len(arrays)}"
        if value.dtype.hasobject:
            raise ValueError("object arrays forbidden in basis checkpoint")
        arrays[name] = value
        return {"__array__": name}
    if is_dataclass(value):
        if type(value).__name__ not in _TYPES:
            raise ValueError("unsupported checkpoint dataclass")
        return {"__type__": type(value).__name__,
                "fields": {field.name: _pack(getattr(value, field.name), arrays)
                           for field in fields(value)}}
    if isinstance(value, tuple):
        return {"__tuple__": [_pack(item, arrays) for item in value]}
    if isinstance(value, dict):
        return {key: _pack(item, arrays) for key, item in value.items()}
    if isinstance(value, (np.integer, np.floating)):
        value = value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return {"__float__": repr(value)}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ValueError(f"unsupported checkpoint value: {type(value).__name__}")


def _unpack(value, arrays):
    if isinstance(value, list):
        return [_unpack(item, arrays) for item in value]
    if not isinstance(value, dict):
        return value
    if "__array__" in value:
        result = np.asarray(arrays[value["__array__"]])
        result.setflags(write=False)
        return result
    if "__tuple__" in value:
        return tuple(_unpack(item, arrays) for item in value["__tuple__"])
    if "__float__" in value:
        if value["__float__"] not in ("nan", "inf", "-inf"):
            raise ValueError("invalid nonfinite checkpoint value")
        return float(value["__float__"])
    if "__type__" in value:
        kind = _TYPES[value["__type__"]]
        return kind(**{name: _unpack(item, arrays)
                       for name, item in value["fields"].items()})
    return {name: _unpack(item, arrays) for name, item in value.items()}


def _bin_name(key: tuple[int, str, int]) -> str:
    energy, pair, mass = key
    if (type(energy) is not int or energy < 0 or pair not in ("p_pi0", "p_eta", "eta_pi0")
            or type(mass) is not int or mass < 0):
        raise ValueError("invalid basis bin key")
    return f"{energy}_{pair}_{mass}.npz"


def _atomic_bytes(path: Path, contents: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class BasisCheckpoint:
    def __init__(self, path: Path, manifest: dict):
        self.path = path
        self.manifest = manifest

    @classmethod
    def open(cls, path: Path, *, target: str, keys: tuple[tuple[int, str, int], ...],
             fingerprint: str, resume: bool) -> BasisCheckpoint:
        path = Path(path)
        if target not in ("ajaka", "native") or len(fingerprint) != 64:
            raise ValueError("invalid target or fingerprint")
        names = tuple(_bin_name(key) for key in keys)
        if len(names) != len(set(names)) or not names:
            raise ValueError("basis bin keys must be unique and nonempty")
        expected = {"version": 1, "target": target, "fingerprint": fingerprint,
                    "keys": list(names)}
        manifest_path = path / "manifest.json"
        if manifest_path.exists():
            if not resume:
                raise FileExistsError(f"basis checkpoint already exists: {path}")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if any(manifest.get(key) != value for key, value in expected.items()):
                raise ValueError("basis run fingerprint, target or bins mismatch")
        else:
            if path.exists() and any(path.iterdir()):
                raise ValueError("checkpoint directory has no manifest")
            manifest = {**expected, "bins": {}, "complete": False}
            path.mkdir(parents=True, exist_ok=True)
        checkpoint = cls(path, manifest)
        if manifest.get("complete") and checkpoint.pending_keys():
            checkpoint.manifest["complete"] = False
        checkpoint._write_manifest()
        return checkpoint

    def _write_manifest(self):
        contents = (json.dumps(self.manifest, sort_keys=True, indent=2,
                               allow_nan=False) + "\n").encode()
        _atomic_bytes(self.path / "manifest.json", contents)

    def _valid(self, name: str) -> bool:
        record = self.manifest["bins"].get(name)
        path = self.path / "bins" / name
        return (isinstance(record, dict) and path.is_file()
                and record.get("sha256") == _digest(path))

    def pending_keys(self) -> tuple[tuple[int, str, int], ...]:
        return tuple(self._key_from_name(name) for name in self.manifest["keys"]
                     if not self._valid(name))

    def write(self, key: tuple[int, str, int], certificate: BasisBinCertificate):
        name = _bin_name(key)
        if name not in self.manifest["keys"] or not isinstance(certificate, BasisBinCertificate):
            raise ValueError("unexpected bin or certificate")
        arrays = {}
        metadata = _pack(certificate, arrays)
        arrays["metadata"] = np.frombuffer(json.dumps(metadata, sort_keys=True,
                                                        allow_nan=False).encode(), dtype=np.uint8)
        path = self.path / "bins" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f".{name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                np.savez_compressed(stream, **arrays)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        self.manifest["bins"][name] = {"sha256": _digest(path),
                                       "status": certificate.status}
        self.manifest["complete"] = False
        self._write_manifest()

    def read(self, key: tuple[int, str, int]) -> BasisBinCertificate:
        name = _bin_name(key)
        if name not in self.manifest["keys"] or not self._valid(name):
            raise ValueError("missing or corrupt basis bin")
        with np.load(self.path / "bins" / name, allow_pickle=False) as archive:
            metadata = json.loads(archive["metadata"].tobytes().decode())
            result = _unpack(metadata, archive)
        if not isinstance(result, BasisBinCertificate):
            raise ValueError("invalid basis bin contents")
        return result

    def finish(self):
        pending = self.pending_keys()
        if pending:
            raise ValueError(f"missing or corrupt basis bins: {pending[0]}")
        for name in self.manifest["keys"]:
            self.read(self._key_from_name(name))
        self.manifest["complete"] = True
        self._write_manifest()

    @staticmethod
    def _key_from_name(name):
        energy, remainder = name.split("_", 1)
        for pair in ("p_pi0", "p_eta", "eta_pi0"):
            if remainder.startswith(pair + "_"):
                return int(energy), pair, int(remainder[len(pair)+1:-4])
        raise ValueError("invalid bin filename")


def basis_panels(certificates: Mapping[tuple[int, str, int], BasisBinCertificate],
                 coefficients, *, energy_order: int, sobol_power: int,
                 replica_seeds: tuple[int, ...], mode: str = "grid"):
    """Contract uniform-energy basis into all twelve source or fitted panels."""
    from .figure4_integration import (Figure4BinMoment, Figure4CertifiedBin,
                                      Figure4PanelResult, apply_pair_total_gate,
                                      covariance_from_replicates)
    from .figure4_reference import PAIR_MASS_AXES

    c = np.asarray(coefficients, dtype=np.float64)
    if c.shape != (3,) or not np.isfinite(c).all() or c[0] != 1.:
        raise ValueError("panel coefficients must be finite source-centered three-vector")
    panels = {}
    expected = {(energy, pair, index) for energy in range(4)
                for pair in PAIR_MASS_AXES for index in range(10)}
    if set(certificates) != expected:
        raise ValueError("Ajaka basis must have all 120 nominal bins")
    for energy in range(4):
        energy_range = (1.10+.10*energy, 1.20+.10*energy)
        for pair, (low, high) in PAIR_MASS_AXES.items():
            edges = np.linspace(low, high, 11)
            bins = []
            replicas_by_bin = {}
            for index in range(10):
                certificate = certificates[energy, pair, index]
                moment = certificate.moment
                if (moment.energy_rule != "uniform" or moment.pair != pair
                        or not np.allclose(moment.energy_range_gev, energy_range, atol=1e-12, rtol=0)
                        or not np.allclose(moment.mass_range_gev, edges[index:index+2], atol=1e-12, rtol=0)):
                    raise ValueError(f"Ajaka basis bin identity mismatch {(energy, pair, index)}")
                status = certificate.status
                reason = certificate.reason
                numerator = denominator = vertical = horizontal = mass_numerator = source_used = 0.
                if status == "calculated":
                    try:
                        estimate = certificate.predict(c)
                        numerator, denominator = estimate.numerator, estimate.denominator
                        vertical, horizontal = moment.polarized_normalizations(c)
                        mass_numerator = moment.weighted_mass_gev(c)*denominator
                        source_used = moment.source_used_extension_fraction(c)*denominator
                        if len(certificate.checks) >= 4+len(replica_seeds):
                            replicas_by_bin[index] = certificate.checks[4:4+len(replica_seeds)]
                    except ValueError as exc:
                        status, reason = "masked_nonconverged", (str(exc),)
                projected = Figure4BinMoment(
                    pair, energy_range, moment.mass_range_gev,
                    moment.accessible_energy_gev, moment.accessible_mass_gev,
                    moment.energy_nodes_gev, numerator, denominator,
                    vertical, horizontal, mass_numerator, source_used,
                    status, moment.reason)
                bins.append(Figure4CertifiedBin(projected, status, reason,
                    certificate.numerical_error_bound, {}))
            covariance = np.full((10, 10), np.nan)
            valid = tuple(replicas_by_bin)
            if valid:
                replica_sigma = np.array([
                    [replicas_by_bin[index][replica].evaluate(c).sigma for index in valid]
                    for replica in range(len(replica_seeds))])
                covariance[np.ix_(valid, valid)] = covariance_from_replicates(replica_sigma)
            errors = [float("nan")]*3
            accessible = [index for index, item in enumerate(bins)
                          if item.status != "masked_kinematic"]
            if accessible and all(index in replicas_by_bin for index in accessible):
                for column, field in enumerate(("denominator", "vertical_normalization",
                                                "horizontal_normalization")):
                    totals = []
                    for replica in range(len(replica_seeds)):
                        total = 0.
                        for index in accessible:
                            candidate = replicas_by_bin[index][replica]
                            if field == "denominator":
                                total += candidate.evaluate(c).denominator
                            else:
                                norm = candidate.polarized_normalizations(c)
                                total += norm[0 if field == "vertical_normalization" else 1]
                        totals.append(total)
                    errors[column] = float(np.std(totals, ddof=1)/np.sqrt(len(totals)))
            panels[energy, pair] = Figure4PanelResult(
                pair, energy_range, edges, tuple(bins), covariance,
                energy_order, sobol_power, replica_seeds, mode, *errors)
    return apply_pair_total_gate(panels)


def _json_safe(value):
    if isinstance(value, np.ndarray):
        return _json_safe(value.tolist())
    if isinstance(value, (np.integer, np.floating)):
        return _json_safe(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_safe(item) for item in value]
    return value


def write_fit_bundle(output: Path, sourced_panels, fitted_panels,
                     sourced_comparison, fitted_comparison, fit_result,
                     provenance: Mapping[str, str], data_covariance: np.ndarray) -> Path:
    """Publish source and fitted comparisons under distinct, atomic paths."""
    from .figure4_comparison import write_figure4_run
    from .figure4_fit import FitResult

    if not isinstance(fit_result, FitResult):
        raise ValueError("fit_result must be a FitResult")
    output = Path(output)
    if output.exists():
        raise FileExistsError(f"fit output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        write_figure4_run(staging/"sourced", sourced_panels,
                          sourced_comparison, provenance, claim_kind="sourced")
        fitted_status = "fit_unavailable"
        if fitted_panels is not None:
            if fitted_comparison is None:
                raise ValueError("fitted panels require fitted comparison")
            write_figure4_run(staging/"fitted", fitted_panels,
                              fitted_comparison, provenance, claim_kind="fitted")
            fitted_status = json.loads((staging/"fitted"/"manifest.json").read_text())["status"]
        else:
            (staging/"fitted").mkdir()
            (staging/"fitted"/"manifest.json").write_text(
                json.dumps({"status": fitted_status, "reason": fit_result.status})+"\n")
        (staging/"fit.json").write_text(json.dumps(_json_safe(asdict(fit_result)),
                                            indent=2, allow_nan=False)+"\n")
        (staging/"data_covariance.json").write_text(json.dumps(
            _json_safe(np.asarray(data_covariance)), allow_nan=False)+"\n")
        (staging/"manifest.json").write_text(json.dumps({
            "fit_status": fit_result.status,
            "sourced_status": sourced_comparison.status,
            "fitted_status": fitted_status,
            "data_sha256": fit_result.data_fingerprint,
            "model_fingerprint": fit_result.model_fingerprint,
            "provenance": dict(provenance),
        }, indent=2, allow_nan=False)+"\n")
        os.replace(staging, output)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return output
