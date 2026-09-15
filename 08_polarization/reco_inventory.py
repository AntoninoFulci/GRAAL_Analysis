"""Provenance contract joining reconstruction files to Gate 0 run inventory."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from contracts import (
    COMMIT_PATTERN,
    SHA256_PATTERN,
    PolarizationContractError,
    canonical_relative_file,
    load_json,
    sha256_file,
)


@dataclass(frozen=True)
class RecoInventory:
    paths: tuple[Path, ...]
    run_numbers: frozenset[int]
    observed_event_run_numbers: frozenset[int]
    zero_selected_event_run_numbers: frozenset[int]


def _run_set(raw: object, label: str, *, allow_empty: bool) -> frozenset[int]:
    if (
        not isinstance(raw, list)
        or (not allow_empty and not raw)
        or any(
            isinstance(run, bool) or not isinstance(run, int) or run <= 0
            for run in raw
        )
    ):
        qualifier = "possibly empty" if allow_empty else "non-empty"
        raise PolarizationContractError(
            f"reconstruction {label} must be {qualifier} positive integers"
        )
    if len(set(raw)) != len(raw):
        raise PolarizationContractError(f"reconstruction {label} must be unique")
    return frozenset(raw)


def load_gate0_run_numbers(path: Path, *, target: str) -> frozenset[int]:
    """Read target run set from hash-validated observable manifest."""
    try:
        handle = Path(path).open(newline="", encoding="utf-8")
    except OSError as exc:
        raise PolarizationContractError(f"cannot read Gate 0 run manifest: {path}") from exc
    with handle:
        reader = csv.DictReader(handle)
        required = {"run_number", "target"}
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise PolarizationContractError(
                "Gate 0 run manifest missing columns: " + ", ".join(sorted(missing))
            )
        runs = []
        for row_number, row in enumerate(reader, start=2):
            if row["target"] != target:
                continue
            try:
                run = int(row["run_number"])
            except (TypeError, ValueError) as exc:
                raise PolarizationContractError(
                    f"Gate 0 run manifest row {row_number} has invalid run_number"
                ) from exc
            runs.append(run)
    if not runs or len(set(runs)) != len(runs):
        raise PolarizationContractError(
            "Gate 0 target run set must be non-empty and unique"
        )
    return frozenset(runs)


def load_processed_run_ledger(path: Path) -> frozenset[int]:
    """Require one unique `complete` record for every processed source run."""
    try:
        handle = Path(path).open(newline="", encoding="utf-8")
    except OSError as exc:
        raise PolarizationContractError(
            f"cannot read processed-run ledger: {path}"
        ) from exc
    runs = []
    with handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != ("run_number", "status"):
            raise PolarizationContractError(
                "processed-run ledger columns must be run_number,status"
            )
        for row_number, row in enumerate(reader, start=2):
            try:
                run = int(row["run_number"])
            except (TypeError, ValueError) as exc:
                raise PolarizationContractError(
                    f"processed-run ledger row {row_number} has invalid run_number"
                ) from exc
            if run <= 0 or row["status"] != "complete":
                raise PolarizationContractError(
                    "processed-run ledger requires positive runs with status complete"
                )
            runs.append(run)
    if not runs or len(set(runs)) != len(runs):
        raise PolarizationContractError(
            "processed-run ledger must contain unique non-empty runs"
        )
    return frozenset(runs)


def _inside_root_file(root: Path, raw: object) -> Path:
    return canonical_relative_file(root, raw, "reconstruction file")[1]


def load_reco_inventory(
    path: Path,
    repository_root: Path,
    *,
    expected_handoff_sha256: str,
    expected_tree: str,
    expected_vectors: str,
    expected_run_numbers: frozenset[int] | set[int],
) -> RecoInventory:
    """Validate complete-run reconstruction provenance and exact file bytes."""
    payload = load_json(path)
    if payload.get("schema_version") != 1:
        raise PolarizationContractError("reconstruction inventory schema_version must be 1")
    commit = payload.get("producer_commit")
    if not isinstance(commit, str) or COMMIT_PATTERN.fullmatch(commit) is None:
        raise PolarizationContractError(
            "reconstruction inventory producer_commit must be a Git hash"
        )
    if payload.get("complete_run_coverage") is not True:
        raise PolarizationContractError(
            "reconstruction inventory complete_run_coverage must be true"
        )
    if payload.get("gate0_handoff_sha256") != expected_handoff_sha256:
        raise PolarizationContractError("reconstruction inventory disagrees with Gate 0 hash")
    if payload.get("tree") != expected_tree or payload.get("vectors") != expected_vectors:
        raise PolarizationContractError(
            "reconstruction inventory tree/vector selection disagrees with config"
        )
    run_numbers = _run_set(payload.get("run_numbers"), "run_numbers", allow_empty=False)
    observed_runs = _run_set(
        payload.get("observed_event_run_numbers"),
        "observed_event_run_numbers",
        allow_empty=True,
    )
    zero_event_runs = _run_set(
        payload.get("zero_selected_event_run_numbers"),
        "zero_selected_event_run_numbers",
        allow_empty=True,
    )
    if observed_runs & zero_event_runs or observed_runs | zero_event_runs != run_numbers:
        raise PolarizationContractError(
            "observed and zero-selected event runs must partition run_numbers"
        )
    expected_runs = frozenset(expected_run_numbers)
    if run_numbers != expected_runs:
        missing = expected_runs - run_numbers
        extra = run_numbers - expected_runs
        raise PolarizationContractError(
            "reconstruction run inventory must equal Gate 0 target run set "
            f"(missing={len(missing)}, extra={len(extra)})"
        )
    ledger_record = payload.get("processed_run_ledger")
    if not isinstance(ledger_record, Mapping):
        raise PolarizationContractError(
            "reconstruction inventory requires processed_run_ledger"
        )
    ledger_digest = ledger_record.get("sha256")
    if (
        not isinstance(ledger_digest, str)
        or SHA256_PATTERN.fullmatch(ledger_digest) is None
    ):
        raise PolarizationContractError(
            "processed-run ledger requires lowercase SHA-256"
        )
    ledger_path = _inside_root_file(repository_root, ledger_record.get("path"))
    if sha256_file(ledger_path) != ledger_digest:
        raise PolarizationContractError("processed-run ledger SHA-256 mismatch")
    if load_processed_run_ledger(ledger_path) != run_numbers:
        raise PolarizationContractError(
            "processed-run ledger must equal reconstruction run inventory"
        )
    raw_files = payload.get("files")
    if not isinstance(raw_files, list) or not raw_files:
        raise PolarizationContractError("reconstruction inventory files must be non-empty")
    paths = []
    seen = set()
    for record in raw_files:
        if not isinstance(record, Mapping):
            raise PolarizationContractError("reconstruction file record must be an object")
        digest = record.get("sha256")
        if not isinstance(digest, str) or SHA256_PATTERN.fullmatch(digest) is None:
            raise PolarizationContractError("reconstruction file requires lowercase SHA-256")
        candidate = _inside_root_file(repository_root, record.get("path"))
        if candidate in seen:
            raise PolarizationContractError("reconstruction file paths must be unique")
        seen.add(candidate)
        actual = sha256_file(candidate)
        if actual != digest:
            raise PolarizationContractError(
                f"reconstruction file SHA-256 mismatch for {record.get('path')}"
            )
        paths.append(candidate)
    return RecoInventory(tuple(paths), run_numbers, observed_runs, zero_event_runs)
