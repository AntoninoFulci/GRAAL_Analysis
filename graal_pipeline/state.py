from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import Any


Fingerprint = dict[str, Any]


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
        hashes[label] = _sha256_file(path) if path.is_file() else "<missing>"
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
