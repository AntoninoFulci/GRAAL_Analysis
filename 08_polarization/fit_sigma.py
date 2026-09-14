"""Canonical authority-only S4 fit publication CLI."""

from __future__ import annotations

import argparse
from dataclasses import replace
import shutil
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile

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
from fit_evidence import FitEvidence, validate_fit_evidence, write_fit_evidence
from response_uncertainty import propagate_response_covariance
from sigma_fit import (
    JointSigmaFitResult,
    _fit_sigma_forward_folded_core,
    bootstrap_sigma_covariance,
    fit_sigma_forward_folded,
)


CANONICAL_OUTPUT_ROOT = "results/physics/polarization_fits"
CANONICAL_BIN_SET_ID = "figure4-v1"


def _fit_release_id(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or value != value.strip()
        or "\\" in value
        or PurePosixPath(value).parts != (value,)
        or value in {".", ".."}
    ):
        raise PolarizationContractError(
            "S4 fit release ID must be one canonical path component"
        )
    return value


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
            producer_commit=producer_commit,
        )
        staged_evidence = validate_fit_evidence(
            staging,
            stable.repository_root,
            config=stable.config,
            _allow_staging=True,
        )
        if destination.exists() or destination.is_symlink():
            raise PolarizationContractError("refusing overwrite of S4 fit release")
        staging.rename(destination)
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
