from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import importlib
from pathlib import Path
from types import ModuleType
from typing import Any


class ConfigError(ValueError):
    """Raised when pipeline configuration is missing or unsafe."""


@dataclass(frozen=True)
class PathsConfig:
    raw_dir: Path
    preanalysis_dir: Path
    selected_dir: Path
    external_flux: Path
    run_manifest: Path
    results_dir: Path


@dataclass(frozen=True)
class CheckpointConfig:
    max_age_days: int | None
    verification: str
    old_policy: str
    stale_policy: str
    untracked_policy: str


@dataclass(frozen=True)
class PipelineConfig:
    repository_root: Path
    profile: str
    paths: PathsConfig
    checkpoint: CheckpointConfig


_DEFAULTS: dict[str, dict[str, Any]] = {
    "paths": {
        "raw_dir": "data/01_raw/graal_data",
        "preanalysis_dir": "data/02_pre_analyzed/pre_analisi",
        "selected_dir": "data/03_selected",
        "external_flux": "data/00_external/flux.root",
        "run_manifest": "config/run_manifest.csv",
        "results_dir": "results",
    },
    "checkpoint": {
        "max_age_days": 30,
        "verification": "fast",
        "old_policy": "ask",
        "stale_policy": "ask",
        "untracked_policy": "ask",
    },
}


def repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_toml_module(
    importer: Callable[[str], ModuleType] = importlib.import_module,
) -> ModuleType:
    try:
        return importer("tomllib")
    except ModuleNotFoundError:
        return importer("tomli")


def _merge(base: dict[str, Any], update: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in update.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = _merge(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


def _nested_overrides(values: Mapping[str, Any]) -> dict[str, Any]:
    nested: dict[str, Any] = {}
    for dotted_key, value in values.items():
        parts = dotted_key.split(".")
        if len(parts) != 2:
            raise ConfigError(f"invalid CLI override: {dotted_key}")
        nested.setdefault(parts[0], {})[parts[1]] = value
    return nested


def resolve_within_root(root: Path, value: str | Path) -> Path:
    root = root.resolve()
    candidate = Path(value).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    resolved = (root / candidate).resolve()
    if not resolved.is_relative_to(root):
        raise ConfigError(f"relative path escapes repository root: {value}")
    return resolved


def load_config(
    path: str | Path | None = None,
    *,
    profile: str = "production",
    cli_overrides: Mapping[str, Any] | None = None,
    repo_root: str | Path | None = None,
) -> PipelineConfig:
    root = Path(repo_root).resolve() if repo_root is not None else repository_root()
    config_path = Path(path).resolve() if path is not None else root / "config/pipeline.toml"
    document: Mapping[str, Any] = {}
    if config_path.exists():
        parser = _load_toml_module()
        with config_path.open("rb") as stream:
            document = parser.load(stream)

    effective = _merge(_DEFAULTS, {k: v for k, v in document.items() if k != "profiles"})
    profiles = document.get("profiles", {})
    if profile in profiles:
        effective = _merge(effective, profiles[profile])
    elif profile != "production":
        raise ConfigError(f"unknown profile: {profile}")
    if cli_overrides:
        effective = _merge(effective, _nested_overrides(cli_overrides))

    paths = effective["paths"]
    checkpoint = effective["checkpoint"]
    verification = str(checkpoint["verification"])
    if verification not in {"fast", "full"}:
        raise ConfigError(f"invalid verification mode: {verification}")

    return PipelineConfig(
        repository_root=root,
        profile=profile,
        paths=PathsConfig(
            raw_dir=resolve_within_root(root, paths["raw_dir"]),
            preanalysis_dir=resolve_within_root(root, paths["preanalysis_dir"]),
            selected_dir=resolve_within_root(root, paths["selected_dir"]),
            external_flux=resolve_within_root(root, paths["external_flux"]),
            run_manifest=resolve_within_root(root, paths["run_manifest"]),
            results_dir=resolve_within_root(root, paths["results_dir"]),
        ),
        checkpoint=CheckpointConfig(
            max_age_days=checkpoint["max_age_days"],
            verification=verification,
            old_policy=str(checkpoint["old_policy"]),
            stale_policy=str(checkpoint["stale_policy"]),
            untracked_policy=str(checkpoint["untracked_policy"]),
        ),
    )
