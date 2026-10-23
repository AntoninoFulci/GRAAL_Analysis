"""Ordered Stage 07 UV ratio points and their matching covariance rows."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path

import numpy as np
from numpy.typing import NDArray


BinKey = tuple[str, int, int]
_PAIRS = ("p_pi0", "p_eta", "eta_pi0")
_BRANCHES = ("sample_id", "estimator_id", "pair_id", "energy_bin", "mass_bin",
             "energy_low_gev", "energy_high_gev", "mass_low_gev", "mass_high_gev",
             "sigma", "stat_low", "stat_high")


def _mapping(text: str) -> dict[str, dict[int, str]]:
    result: dict[str, dict[int, str]] = {"sample": {}, "estimator": {}, "pair": {}}
    try:
        for line in text.splitlines():
            parts = line.split()
            if len(parts) != 3 or parts[0] not in result:
                raise ValueError("malformed id_mapping")
            kind, raw_id, name = parts
            identifier = int(raw_id)
            if identifier in result[kind] or name in result[kind].values():
                raise ValueError("duplicate id_mapping entry")
            result[kind][identifier] = name
        if any(not values for values in result.values()):
            raise ValueError("incomplete id_mapping")
    except (TypeError, ValueError) as exc:
        raise ValueError("malformed or duplicate id_mapping") from exc
    return result


def _provenance(text: str) -> dict[str, str]:
    result = {}
    for line in text.splitlines():
        key, separator, value = line.partition("=")
        if not separator or not key or not value or key in result:
            raise ValueError("malformed provenance")
        result[key] = value
    if result.get("profile") != "uv":
        raise ValueError("native Sigma requires UV profile")
    return result


def _edges(source, name: str) -> NDArray[np.float64]:
    try:
        result = np.asarray(source[name].member("fElements"), dtype=np.float64)
    except (KeyError, AttributeError) as exc:
        raise ValueError(f"missing {name}") from exc
    if result.ndim != 1 or len(result) < 2 or not np.isfinite(result).all() \
            or not np.all(np.diff(result) > 0):
        raise ValueError(f"invalid {name}")
    result.setflags(write=False)
    return result


def _covariance(source, name: str, size: int, *, optional: bool = False):
    if optional and name not in source:
        return None
    try:
        matrix = np.asarray(source[name].values(), dtype=np.float64)
    except (KeyError, AttributeError) as exc:
        raise ValueError(f"missing {name}") from exc
    if matrix.shape != (size, size) or not np.isfinite(matrix).all() \
            or not np.allclose(matrix, matrix.T, rtol=1e-10, atol=1e-12):
        raise ValueError(f"invalid {name} shape, finiteness or symmetry")
    return matrix


@dataclass(frozen=True)
class NativeSigmaData:
    keys: tuple[BinKey, ...]
    sigma: NDArray[np.float64]
    stat_error: NDArray[np.float64]
    tree_indices: NDArray[np.int64]
    covariance: NDArray[np.float64]
    bootstrap_covariance: NDArray[np.float64] | None
    energy_edges_gev: NDArray[np.float64]
    mass_edges_gev: dict[str, NDArray[np.float64]]
    provenance: dict[str, str]
    source_sha256: str
    status: str
    phi_bins: NDArray[np.int64] | None = None
    phi_bin_divisor: NDArray[np.float64] | None = None
    ratio_used_fallback: NDArray[np.bool_] | None = None


def load_native_sigma_root(path: Path, *, require_final: bool = False) -> NativeSigmaData:
    """Select only raw_bdt/ratio rows; preserve ROOT row order in every array."""
    import uproot

    path = Path(path)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b""):
            digest.update(chunk)
    source = uproot.open(path)
    try:
        top_keys = [key.partition(";")[0] for key in source.keys(recursive=False, cycle=True)]
        if len(top_keys) != len(set(top_keys)):
            raise ValueError("duplicate ROOT object cycles")
        maps = _mapping(source["id_mapping"].member("fTitle"))
        provenance = _provenance(source["provenance"].member("fTitle"))
        energy_edges = _edges(source, "binning/energy_edges")
        mass_edges = {pair: _edges(source, f"binning/{pair}_mass_edges") for pair in _PAIRS}
        tree = source["sigma_points"]
        columns = tree.arrays(_BRANCHES, library="np")
        size = tree.num_entries
        if any(value.shape != (size,) for value in columns.values()):
            raise ValueError("sigma_points branch length mismatch")
        sample_id = next((key for key, name in maps["sample"].items() if name == "raw_bdt"), None)
        estimator_id = next((key for key, name in maps["estimator"].items() if name == "ratio"), None)
        if sample_id is None or estimator_id is None:
            raise ValueError("raw_bdt/ratio identity missing")
        indices = np.flatnonzero((columns["sample_id"] == sample_id)
                                  & (columns["estimator_id"] == estimator_id))
        if not len(indices):
            raise ValueError("no raw_bdt/ratio points")
        # Modern production declares the finite-bin correction explicitly.
        # Legacy files without that declaration retain the old uncorrected 12-bin contract.
        phi_bins = np.full(len(indices), 12, dtype=np.int64)
        phi_divisor = np.ones(len(indices))
        fallback = np.zeros(len(indices), dtype=bool)
        if "phi_bins" in provenance or "phi_bin_correction" in provenance:
            try:
                metadata = tree.arrays(("phi_bins", "phi_bin_divisor", "used_fallback"), library="np")
            except KeyError as exc:
                raise ValueError("missing per-point phi/fallback metadata") from exc
            if any(value.shape != (size,) for value in metadata.values()):
                raise ValueError("phi metadata branch length mismatch")
            bins = metadata["phi_bins"][indices]
            divisors = metadata["phi_bin_divisor"][indices]
            used_fallback = metadata["used_fallback"][indices]
            if not np.isin(bins, (8, 12, 16)).all():
                raise ValueError("phi_bins must be 8, 12 or 16")
            approved = {8: .9003, 12: .9549, 16: .9745}
            expected = np.array([approved[int(n)] for n in bins])
            if (provenance.get("phi_bin_correction") != "ratio_only_rounded"
                    or not np.allclose(divisors, expected, rtol=0, atol=1e-12)):
                raise ValueError("phi_bin_divisor disagrees with rounded correction")
            if not np.isin(used_fallback, (0, 1)).all():
                raise ValueError("invalid ratio used_fallback")
            phi_bins = bins.astype(np.int64)
            phi_divisor = divisors.astype(np.float64)
            fallback = used_fallback.astype(bool)
        keys = []
        for index in indices:
            try:
                pair = maps["pair"][int(columns["pair_id"][index])]
                energy_bin = int(columns["energy_bin"][index])
                mass_bin = int(columns["mass_bin"][index])
                mass = mass_edges[pair]
            except (KeyError, IndexError) as exc:
                raise ValueError("invalid nominal bin identity") from exc
            if (pair not in _PAIRS or not 0 <= energy_bin < len(energy_edges)-1
                    or not 0 <= mass_bin < len(mass)-1):
                raise ValueError("nominal bin outside declared edges")
            keys.append((pair, energy_bin, mass_bin))
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate nominal bin key")
        for index, (pair, energy_bin, mass_bin) in zip(indices, keys):
            for branch, expected in (("energy_low_gev", energy_edges[energy_bin]),
                                     ("energy_high_gev", energy_edges[energy_bin+1]),
                                     ("mass_low_gev", mass_edges[pair][mass_bin]),
                                     ("mass_high_gev", mass_edges[pair][mass_bin+1])):
                if not np.isclose(columns[branch][index], expected, rtol=0, atol=1e-12):
                    raise ValueError(f"nominal {branch} disagrees with binning")
        sigma = np.asarray(columns["sigma"][indices], dtype=np.float64)
        low = np.asarray(columns["stat_low"][indices], dtype=np.float64)
        high = np.asarray(columns["stat_high"][indices], dtype=np.float64)
        if not all(np.isfinite(value).all() for value in (sigma, low, high)) \
                or np.any(low <= 0) or np.any(high <= 0):
            raise ValueError("nominal Sigma/statistical errors must be finite and positive")
        full = _covariance(source, "covariance/total", size)
        covariance = full[np.ix_(indices, indices)].copy()
        try:
            np.linalg.cholesky(covariance)
        except np.linalg.LinAlgError as exc:
            raise ValueError("selected covariance must be positive definite") from exc
        bootstrap = _covariance(source, "covariance/bootstrap_run", size, optional=True)
        if bootstrap is not None:
            bootstrap = bootstrap[np.ix_(indices, indices)].copy()
        final_input = (provenance.get("background") == "sideband-corrected"
                       and bootstrap is not None
                       and provenance.get("final_inference") != "suspended")
        if require_final and not final_input:
            raise ValueError("final data require sideband correction and run-bootstrap covariance")
        for value in (sigma, indices, covariance, bootstrap, phi_bins, phi_divisor, fallback):
            if value is not None:
                value.setflags(write=False)
        return NativeSigmaData(tuple(keys), sigma, (low+high)/2, indices, covariance,
                               bootstrap, energy_edges, mass_edges, provenance,
                               digest.hexdigest(), "final_input" if final_input else "pilot",
                               phi_bins, phi_divisor, fallback)
    finally:
        source.close()
