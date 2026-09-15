"""Canonical authority-only S4 fit publication CLI."""

from __future__ import annotations

import argparse
import ctypes
from dataclasses import replace
import errno
import hashlib
import os
import shutil
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from azimuth_counts import (
    CANONICAL_GATE0_PATH,
    CountAuthority,
    _authority_fingerprint,
    _reload_count_authority,
    build_azimuth_counts,
    load_count_authority,
)
from contracts import PolarizationContractError
from fit_evidence import (
    FIT_EVIDENCE_FILENAMES,
    FitEvidence,
    validate_fit_evidence,
    write_fit_evidence,
)
from response_uncertainty import propagate_response_covariance
from nuisance_uncertainty import (
    propagate_compton_covariance,
    propagate_flux_exposure_covariance,
)
from sigma_fit import (
    JointSigmaFitResult,
    _fit_sigma_forward_folded_core,
    bootstrap_sigma_covariance,
    fit_sigma_forward_folded,
)
from scripts.s4_release_id import validate_fit_release_id


CANONICAL_OUTPUT_ROOT = "results/physics/polarization_fits"
CANONICAL_BIN_SET_ID = "figure4-v1"


def _rename_directory_no_replace(source: Path, destination: Path) -> None:
    """Atomically publish one directory without replacing any destination.

    POSIX ``rename`` may replace an empty directory.  Linux ``renameat2`` and
    macOS ``renamex_np`` supply kernel-enforced no-replace semantics.  Other
    POSIX kernels fail closed; Windows ``os.rename`` already refuses an
    existing destination.
    """
    source_bytes = os.fsencode(source)
    destination_bytes = os.fsencode(destination)
    if sys.platform == "darwin":
        libc = ctypes.CDLL(None, use_errno=True)
        operation = libc.renamex_np
        operation.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint)
        operation.restype = ctypes.c_int
        result = operation(source_bytes, destination_bytes, 0x00000004)
    elif sys.platform.startswith("linux"):
        libc = ctypes.CDLL(None, use_errno=True)
        try:
            operation = libc.renameat2
        except AttributeError as exc:
            raise PolarizationContractError(
                "atomic no-replace directory publication is unsupported"
            ) from exc
        operation.argtypes = (
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        )
        operation.restype = ctypes.c_int
        result = operation(-100, source_bytes, -100, destination_bytes, 1)
    elif os.name == "nt":
        try:
            os.rename(source, destination)
        except FileExistsError as exc:
            raise PolarizationContractError(
                "refusing overwrite of S4 fit release"
            ) from exc
        return
    else:
        raise PolarizationContractError(
            "atomic no-replace directory publication is unsupported"
        )
    if result != 0:
        error = ctypes.get_errno()
        if error in {errno.EEXIST, errno.ENOTEMPTY}:
            raise PolarizationContractError(
                "refusing overwrite of S4 fit release"
            )
        raise OSError(error, os.strerror(error), str(destination))


def _fit_release_id(value: object) -> str:
    try:
        return validate_fit_release_id(value)
    except ValueError as exc:
        raise PolarizationContractError(str(exc)) from exc


def _snapshot_staged_triplet(directory: Path) -> tuple[tuple[str, int, str], ...]:
    """Hash exact stable bytes, detecting replacement or mutation while read."""
    entries = tuple(directory.iterdir())
    if {entry.name for entry in entries} != FIT_EVIDENCE_FILENAMES:
        raise PolarizationContractError("staged S4 evidence changed during publication")
    snapshots = []
    identities = {}
    for name in sorted(FIT_EVIDENCE_FILENAMES):
        path = directory / name
        if path.is_symlink() or not path.is_file():
            raise PolarizationContractError(
                "staged S4 evidence changed during publication"
            )
        with path.open("rb") as stream:
            before = os.fstat(stream.fileno())
            payload = stream.read()
            after = os.fstat(stream.fileno())
        identity_before = (
            before.st_dev, before.st_ino, before.st_size,
            before.st_mtime_ns, before.st_ctime_ns,
        )
        identity_after = (
            after.st_dev, after.st_ino, after.st_size,
            after.st_mtime_ns, after.st_ctime_ns,
        )
        if identity_before != identity_after or len(payload) != after.st_size:
            raise PolarizationContractError(
                "staged S4 evidence changed during publication"
            )
        identities[name] = identity_after
        snapshots.append((name, len(payload), hashlib.sha256(payload).hexdigest()))
    if {entry.name for entry in directory.iterdir()} != FIT_EVIDENCE_FILENAMES:
        raise PolarizationContractError(
            "staged S4 evidence changed during publication"
        )
    for name, identity in identities.items():
        current = (directory / name).stat(follow_symlinks=False)
        if (
            current.st_dev, current.st_ino, current.st_size,
            current.st_mtime_ns, current.st_ctime_ns,
        ) != identity:
            raise PolarizationContractError(
                "staged S4 evidence changed during publication"
            )
    return tuple(snapshots)


def _same_fit(left: JointSigmaFitResult, right: JointSigmaFitResult) -> bool:
    scalar = (
        left.bin_keys == right.bin_keys
        and left.nuisance_keys == right.nuisance_keys
        and left.row_keys == right.row_keys
        and left.deviance == right.deviance
        and left.ndof == right.ndof
        and left.converged == right.converged
        and left.rank == right.rank
        and left.replica_id == right.replica_id
    )
    arrays = (
        "sigma", "log_yield", "hessian_covariance", "expected", "residuals",
        "deviance_contributions",
    )
    return scalar and all(
        np.array_equal(getattr(left, name), getattr(right, name)) for name in arrays
    )


def _canonical_output_directory(
    authority: CountAuthority, output_root: Path
) -> tuple[Path, Path]:
    repository = authority.repository_root.resolve(strict=True)
    raw = Path(output_root)
    if raw.is_absolute():
        try:
            relative = raw.relative_to(repository).as_posix()
        except ValueError as exc:
            raise PolarizationContractError(
                "S4 output root must stay inside repository"
            ) from exc
    else:
        relative = raw.as_posix()
    if (
        relative != CANONICAL_OUTPUT_ROOT
        or PurePosixPath(relative).as_posix() != relative
        or any(part in {"", ".", ".."} for part in PurePosixPath(relative).parts)
    ):
        raise PolarizationContractError(
            f"S4 output root must be {CANONICAL_OUTPUT_ROOT}"
        )
    parent = repository / relative
    cursor = repository
    for part in PurePosixPath(relative).parts:
        cursor = cursor / part
        if cursor.exists() and cursor.is_symlink():
            raise PolarizationContractError("S4 output path cannot contain symlinks")
    parent.mkdir(parents=True, exist_ok=True)
    if parent.is_symlink() or not parent.is_dir() or parent.resolve() != parent:
        raise PolarizationContractError("S4 output root is not canonical")
    destination = parent / authority.fit_release_id
    return parent, destination


def publish_fit_release(
    *,
    authority: CountAuthority,
    output_root: Path,
    producer_commit: str,
) -> FitEvidence:
    """Run full authority-bound S4 analysis and atomically publish evidence."""
    if type(authority) is not CountAuthority:
        raise PolarizationContractError(
            "S4 publication requires authenticated CountAuthority"
        )
    _fit_release_id(authority.fit_release_id)
    original = _authority_fingerprint(authority)
    fresh = _reload_count_authority(authority)
    if _authority_fingerprint(fresh) != original:
        raise PolarizationContractError("S4 authority changed before fitting")
    parent, destination = _canonical_output_directory(fresh, output_root)
    if destination.exists() or destination.is_symlink():
        raise PolarizationContractError("refusing overwrite of S4 fit release")

    counts = build_azimuth_counts(authority=fresh)
    public_nominal = fit_sigma_forward_folded(authority=fresh, replica_id=0)
    replay_nominal = _fit_sigma_forward_folded_core(
        counts, fresh.response, config=fresh.config, replica_id=0
    )
    if not _same_fit(public_nominal, replay_nominal):
        raise PolarizationContractError(
            "authority-only nominal fit disagrees with serialized count replay"
        )
    successful_ids = []
    failed_ids = []
    vectors = []
    replicas = fresh.config.bootstrap.replicas
    if type(replicas) is not int:
        raise PolarizationContractError("S4 bootstrap replica authority is absent")
    for replica_id in range(1, replicas + 1):
        try:
            result = _fit_sigma_forward_folded_core(
                counts,
                fresh.response,
                config=fresh.config,
                replica_id=replica_id,
            )
        except PolarizationContractError:
            failed_ids.append(replica_id)
            continue
        if result.bin_keys != public_nominal.bin_keys or result.replica_id != replica_id:
            raise PolarizationContractError(
                "bootstrap fit returned noncanonical global Sigma order"
            )
        successful_ids.append(replica_id)
        vectors.append(np.asarray(result.sigma, dtype=float))
    matrix = np.asarray(vectors, dtype=float)
    if not vectors:
        matrix = np.empty((0, len(public_nominal.bin_keys)), dtype=float)
    statistical = bootstrap_sigma_covariance(
        matrix,
        public_nominal.bin_keys,
        replica_ids=successful_ids,
        failed_replica_ids=failed_ids,
        config=fresh.config,
        hessian_covariance=public_nominal.hessian_covariance,
    )
    response = propagate_response_covariance(
        counts,
        fresh.response,
        config=fresh.config,
        covariance_scope=fresh.response_covariance_scope,
    )
    compton = propagate_compton_covariance(
        counts,
        fresh.response,
        config=fresh.config,
        authority=fresh,
    )
    flux_exposure = propagate_flux_exposure_covariance(
        counts,
        fresh.response,
        config=fresh.config,
        authority=fresh,
    )
    stable = _reload_count_authority(fresh)
    if _authority_fingerprint(stable) != original:
        raise PolarizationContractError("S4 authority changed during fitting")

    staging = Path(
        tempfile.mkdtemp(prefix=f".{fresh.fit_release_id}.staging-", dir=parent)
    )
    renamed = False
    try:
        write_fit_evidence(
            staging,
            authority=stable,
            counts=counts,
            nominal=public_nominal,
            statistical_covariance=statistical,
            bootstrap_sigma_vectors=matrix,
            successful_replica_ids=successful_ids,
            failed_replica_ids=failed_ids,
            response_propagation=response,
            compton_propagation=compton,
            flux_exposure_propagation=flux_exposure,
            producer_commit=producer_commit,
        )
        written_snapshot = _snapshot_staged_triplet(staging)
        staged_evidence = validate_fit_evidence(
            staging,
            stable.repository_root,
            config=stable.config,
            _allow_staging=True,
        )
        final_authority = _reload_count_authority(stable)
        if _authority_fingerprint(final_authority) != original:
            raise PolarizationContractError(
                "S4 authority changed before atomic publication"
            )
        if _snapshot_staged_triplet(staging) != written_snapshot:
            raise PolarizationContractError(
                "staged S4 evidence changed before atomic publication"
            )
        _rename_directory_no_replace(staging, destination)
        renamed = True
    finally:
        if not renamed and staging.exists():
            shutil.rmtree(staging)
    return replace(staged_evidence, directory=destination)


def _producer_commit(repository_root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repository_root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise PolarizationContractError("cannot determine S4 producer commit") from exc


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--acceptance-handoff", required=True)
    parser.add_argument("--reco-inventory", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--fit-release-id", required=True)
    parser.add_argument("--output-root", required=True)
    try:
        arguments = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)
    try:
        root = Path.cwd().resolve(strict=True)
        if arguments.output_root != CANONICAL_OUTPUT_ROOT:
            raise PolarizationContractError(
                f"S4 output root must be {CANONICAL_OUTPUT_ROOT}"
            )
        authority = load_count_authority(
            repository_root=root,
            config_path=arguments.config,
            gate0_handoff_path=CANONICAL_GATE0_PATH,
            n2_inventory_path=arguments.reco_inventory,
            acceptance_handoff_path=arguments.acceptance_handoff,
            fit_release_id=arguments.fit_release_id,
            bin_set_id=CANONICAL_BIN_SET_ID,
        )
        publish_fit_release(
            authority=authority,
            output_root=Path(arguments.output_root),
            producer_commit=_producer_commit(root),
        )
    except (PolarizationContractError, OSError, RuntimeError, ValueError) as exc:
        print(f"S4 publication failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
