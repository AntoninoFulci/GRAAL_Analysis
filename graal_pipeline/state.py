from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import tempfile
from datetime import datetime, timezone
from typing import Any

from .model import (
    ArtifactState,
    ArtifactStatus,
    CheckpointScope,
    ValidationResult,
    StageInvocation,
)


Fingerprint = dict[str, Any]
CHECKPOINT_SCHEMA_VERSION = 1


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class DigestCache:
    def __init__(self) -> None:
        self._entries: dict[tuple[str, int, int], str] = {}
        self.hits = 0
        self.misses = 0

    def digest(self, path: Path, *, size: int, mtime_ns: int) -> str:
        key = (str(path.resolve()), size, mtime_ns)
        if key in self._entries:
            self.hits += 1
            return self._entries[key]
        self.misses += 1
        value = _sha256_file(path)
        self._entries[key] = value
        return value


def _file_fingerprint(
    path: Path,
    *,
    mode: str,
    small_file_limit: int,
    cache: DigestCache,
    root_metadata_reader: Callable[[Path], Mapping[str, Any]] | None,
    include_path: bool = True,
) -> Fingerprint:
    stat = path.stat()
    result: Fingerprint = {
        "kind": "file",
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }
    if include_path:
        result["path"] = str(path.resolve())
    if mode == "full" or stat.st_size <= small_file_limit:
        result["sha256"] = cache.digest(
            path, size=stat.st_size, mtime_ns=stat.st_mtime_ns
        )
    if path.suffix.lower() == ".root" and root_metadata_reader is not None:
        result["root"] = dict(root_metadata_reader(path))
    return result


def fingerprint_path(
    path: str | Path,
    *,
    mode: str = "fast",
    small_file_limit: int = 1024 * 1024,
    cache: DigestCache | None = None,
    root_metadata_reader: Callable[[Path], Mapping[str, Any]] | None = None,
) -> Fingerprint:
    if mode not in {"fast", "full"}:
        raise ValueError(f"unknown fingerprint mode: {mode}")
    candidate = Path(path)
    if not candidate.exists():
        return {"kind": "missing", "path": str(candidate.resolve())}
    digest_cache = cache or DigestCache()
    if candidate.is_file():
        return _file_fingerprint(
            candidate,
            mode=mode,
            small_file_limit=small_file_limit,
            cache=digest_cache,
            root_metadata_reader=root_metadata_reader,
        )
    if not candidate.is_dir():
        return {"kind": "unsupported", "path": str(candidate.resolve())}

    entries: list[Fingerprint] = []
    for child in sorted(
        (item for item in candidate.rglob("*") if item.is_file()),
        key=lambda item: item.relative_to(candidate).as_posix(),
    ):
        entry = _file_fingerprint(
            child,
            mode=mode,
            small_file_limit=small_file_limit,
            cache=digest_cache,
            root_metadata_reader=root_metadata_reader,
            include_path=False,
        )
        entry["name"] = child.relative_to(candidate).as_posix()
        entries.append(entry)
    return {"kind": "directory", "path": str(candidate.resolve()), "entries": entries}


def fingerprint_mismatch_reasons(
    expected: Mapping[str, Any], current: Mapping[str, Any]
) -> tuple[str, ...]:
    reasons: list[str] = []

    def compare(left: Any, right: Any, prefix: str) -> None:
        if isinstance(left, Mapping) and isinstance(right, Mapping):
            for key in sorted(set(left) | set(right)):
                field = f"{prefix}.{key}" if prefix else str(key)
                if key not in left:
                    reasons.append(f"{field}: added {right[key]!r}")
                elif key not in right:
                    reasons.append(f"{field}: expected {left[key]!r}, found missing")
                else:
                    compare(left[key], right[key], field)
            return
        if left != right:
            reasons.append(f"{prefix}: expected {left!r}, found {right!r}")

    compare(expected, current, "")
    return tuple(reasons)


def _responsible_file_hashes(paths: Iterable[Path], root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in sorted((item.resolve() for item in paths), key=str):
        try:
            label = path.relative_to(root).as_posix()
        except ValueError:
            label = str(path)
        if path.is_file():
            hashes[label] = _sha256_file(path)
        elif path.is_dir():
            children = sorted(item for item in path.rglob("*") if item.is_file())
            if not children:
                hashes[f"{label}/"] = "<empty>"
            for child in children:
                try:
                    child_label = child.relative_to(root).as_posix()
                except ValueError:
                    child_label = str(child)
                hashes[child_label] = _sha256_file(child)
        else:
            hashes[label] = "<missing>"
    return hashes


def responsible_code_fingerprint(
    paths: Iterable[str | Path],
    repository: str | Path,
    *,
    git_executable: str = "git",
) -> Fingerprint:
    root = Path(repository).resolve()
    resolved_paths = tuple(
        (root / Path(item)).resolve() if not Path(item).is_absolute() else Path(item).resolve()
        for item in paths
    )
    fallback = {
        "git_commit": None,
        "dirty": True,
        "files": _responsible_file_hashes(resolved_paths, root),
    }
    try:
        commit = subprocess.run(
            [git_executable, "-C", str(root), "rev-parse", "HEAD"],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return fallback
    if commit.returncode != 0:
        return fallback

    relative_paths: list[str] = []
    for path in resolved_paths:
        try:
            relative_paths.append(path.relative_to(root).as_posix())
        except ValueError:
            return fallback
    status = subprocess.run(
        [
            git_executable,
            "-C",
            str(root),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
            *relative_paths,
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if status.returncode != 0:
        return fallback
    dirty = bool(status.stdout.strip())
    return {
        "git_commit": commit.stdout.strip(),
        "dirty": dirty,
        "files": _responsible_file_hashes(resolved_paths, root) if dirty else {},
    }


def make_checkpoint(
    *,
    stage: str,
    completed_at: datetime,
    inputs: Mapping[str, Any],
    outputs: Mapping[str, Any],
    configuration: Mapping[str, Any],
    code: Mapping[str, Any],
    run_id: str,
    final_state: str | None = None,
    observable: str | None = None,
    profile: str = "production",
    provenance: str = "produced",
    provenance_confident: bool = True,
    command: Iterable[str] = (),
    working_directory: str | None = None,
    validator: str | None = None,
    verification: str = "fast",
) -> Fingerprint:
    timestamp = completed_at.astimezone(timezone.utc).isoformat()
    return {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "stage": stage,
        "final_state": final_state,
        "observable": observable,
        "profile": profile,
        "completed_at": timestamp,
        "run_id": run_id,
        "inputs": dict(inputs),
        "outputs": dict(outputs),
        "configuration": dict(configuration),
        "code": dict(code),
        "provenance": provenance,
        "provenance_confident": provenance_confident,
        "command": list(command),
        "working_directory": working_directory,
        "validator": validator,
        "verification": verification,
    }


def invocation_configuration(invocation: StageInvocation) -> Fingerprint:
    """Return only configuration that can change this stage's artifact."""
    return {
        "commands": [list(command) for command in invocation.commands],
        "working_directory": str(invocation.working_directory),
        "validator": invocation.validator,
        "output_kind": invocation.output_kind,
    }


def adopt_artifact_checkpoint(
    checkpoint: Mapping[str, Any], *, provenance_confident: bool
) -> Fingerprint:
    adopted = json.loads(canonical_json(checkpoint))
    adopted["provenance"] = "adopted_legacy_output"
    adopted["provenance_confident"] = provenance_confident
    return adopted


def classify_artifact(
    *,
    exists: bool,
    validation: ValidationResult,
    checkpoint: Mapping[str, Any] | None,
    current_inputs: Mapping[str, Any],
    current_outputs: Mapping[str, Any],
    current_configuration: Mapping[str, Any],
    current_code: Mapping[str, Any],
    max_age_days: int | None,
    now: datetime | None = None,
) -> ArtifactStatus:
    if not exists:
        return ArtifactStatus(
            ArtifactState.MISSING, ("required output is missing",)
        )
    if not validation.valid:
        return ArtifactStatus(
            ArtifactState.INVALID,
            validation.reasons or ("artifact validation failed",),
        )
    if checkpoint is None:
        return ArtifactStatus(
            ArtifactState.UNTRACKED,
            ("valid output has no compatible checkpoint",),
        )
    schema = checkpoint.get("schema_version")
    if schema != CHECKPOINT_SCHEMA_VERSION:
        return ArtifactStatus(
            ArtifactState.STALE,
            (
                f"checkpoint schema {schema} is unsupported "
                f"(expected {CHECKPOINT_SCHEMA_VERSION})",
            ),
        )
    if (
        checkpoint.get("provenance") == "adopted_legacy_output"
        and not checkpoint.get("provenance_confident", False)
    ):
        return ArtifactStatus(
            ArtifactState.STALE,
            ("legacy configuration provenance is uncertain",),
        )

    expected = {
        "inputs": checkpoint.get("inputs", {}),
        "outputs": checkpoint.get("outputs", {}),
        "configuration": checkpoint.get("configuration", {}),
        "code": checkpoint.get("code", {}),
    }
    current = {
        "inputs": dict(current_inputs),
        "outputs": dict(current_outputs),
        "configuration": dict(current_configuration),
        "code": dict(current_code),
    }
    reasons = fingerprint_mismatch_reasons(expected, current)
    if reasons:
        return ArtifactStatus(ArtifactState.STALE, reasons)

    completed_at = datetime.fromisoformat(str(checkpoint["completed_at"]))
    reference = now or datetime.now(timezone.utc)
    if completed_at.tzinfo is None:
        completed_at = completed_at.replace(tzinfo=timezone.utc)
    age_days = (reference.astimezone(timezone.utc) - completed_at).total_seconds() / 86400
    if max_age_days is not None and age_days > max_age_days:
        return ArtifactStatus(
            ArtifactState.OLD,
            (
                f"checkpoint is {age_days:.1f} days old "
                f"(limit {max_age_days} days)",
            ),
            age_days=age_days,
        )
    return ArtifactStatus(ArtifactState.FRESH, age_days=age_days)


class CheckpointStore:
    def __init__(self, state_directory: str | Path) -> None:
        self.state_directory = Path(state_directory)

    def path_for(
        self,
        stage: str,
        scope: CheckpointScope,
        *,
        final_state: str | None = None,
        observable: str | None = None,
    ) -> Path:
        base = self.state_directory / "checkpoints"
        if scope is CheckpointScope.SHARED:
            return base / "shared" / f"{stage}.json"
        if final_state is None:
            raise ValueError(f"final_state is required for {scope.value} checkpoint")
        if scope is CheckpointScope.FINAL_STATE:
            return base / final_state / f"{stage}.json"
        if observable is None:
            raise ValueError("observable is required for observable checkpoint")
        return base / final_state / observable / f"{stage}.json"

    def read(self, path: str | Path) -> Fingerprint | None:
        candidate = Path(path)
        if not candidate.exists():
            return None
        with candidate.open(encoding="utf-8") as stream:
            return json.load(stream)

    def write(self, path: str | Path, checkpoint: Mapping[str, Any]) -> None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=destination.parent,
                prefix=f".{destination.name}.",
                suffix=".tmp",
                delete=False,
            ) as stream:
                temporary_name = stream.name
                json.dump(checkpoint, stream, sort_keys=True, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, destination)
            temporary_name = None
        finally:
            if temporary_name is not None:
                Path(temporary_name).unlink(missing_ok=True)


def inspect_invocation_status(
    invocation: StageInvocation,
    *,
    checkpoint_store: CheckpointStore,
    configuration: Mapping[str, Any],
    repository_root: str | Path,
    final_state: str,
    observable: str | None,
    max_age_days: int | None,
    verification: str = "fast",
    validator: Callable[[str, StageInvocation], ValidationResult],
    now: datetime | None = None,
) -> ArtifactStatus:
    del configuration
    exists = bool(invocation.outputs) and all(path.exists() for path in invocation.outputs)
    if not exists:
        return ArtifactStatus(
            ArtifactState.MISSING, ("required output is missing",)
        )
    validation = validator(invocation.stage_key, invocation)
    if not validation.valid:
        return ArtifactStatus(ArtifactState.INVALID, validation.reasons)
    inputs = {
        str(path): fingerprint_path(path, mode=verification)
        for path in invocation.inputs
    }
    outputs = {
        str(path): fingerprint_path(path, mode=verification)
        for path in invocation.outputs
    }
    code = responsible_code_fingerprint(
        invocation.responsible_paths,
        repository_root,
    )
    checkpoint_path = checkpoint_store.path_for(
        invocation.stage_key,
        invocation.scope,
        final_state=final_state,
        observable=observable or "beam_asymmetry",
    )
    return classify_artifact(
        exists=True,
        validation=validation,
        checkpoint=checkpoint_store.read(checkpoint_path),
        current_inputs=inputs,
        current_outputs=outputs,
        current_configuration=invocation_configuration(invocation),
        current_code=code,
        max_age_days=max_age_days,
        now=now,
    )
