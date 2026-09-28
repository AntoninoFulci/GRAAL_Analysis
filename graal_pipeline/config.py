from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import importlib
from pathlib import Path
from types import ModuleType
from typing import Any
from dataclasses import asdict, replace


class ConfigError(ValueError):
    """Raised when pipeline configuration is missing or unsafe."""


class ProfileInputError(ConfigError):
    """Raised when a validation profile lacks its required real inputs."""


@dataclass(frozen=True)
class PathsConfig:
    raw_dir: Path
    preanalysis_dir: Path
    selected_dir: Path
    external_flux: Path
    run_manifest: Path
    results_dir: Path
    mc_data_dir: Path
    model_dir: Path
    features_file: Path
    beam_spectrum_file: Path


@dataclass(frozen=True)
class RuntimeConfig:
    python_executable: str
    root_executable: str
    input_tree: str
    signal_channel: str
    signal_prior: float
    partner: str
    mc_events: int
    grid_search_iterations: int
    use_grid_search: bool
    threads: int
    flux_progress_every_events: int
    flux_samples_per_run_strip: int
    bootstrap_replicas: int
    bootstrap_seed: int
    estimator: str


@dataclass(frozen=True)
class CheckpointConfig:
    max_age_days: int | None
    verification: str
    old_policy: str
    stale_policy: str
    untracked_policy: str


@dataclass(frozen=True)
class ProfileSettings:
    claim: str
    isolated_results: bool
    requires_real_fixture: bool


@dataclass(frozen=True)
class PipelineConfig:
    repository_root: Path
    profile: str
    paths: PathsConfig
    checkpoint: CheckpointConfig
    runtime: RuntimeConfig
    profile_settings: ProfileSettings


_DEFAULTS: dict[str, dict[str, Any]] = {
    "paths": {
        "raw_dir": "data/01_raw/graal_data",
        "preanalysis_dir": "data/02_pre_analyzed/pre_analisi",
        "selected_dir": "data/03_selected",
        "external_flux": "data/00_external/flux.root",
        "run_manifest": "config/run_manifest.csv",
        "results_dir": "results",
        "mc_data_dir": "03_mc_simulation/data",
        "model_dir": "04_bdt_training/artifacts/stage1",
        "features_file": "04_bdt_training/data/features_stage1.npz",
        "beam_spectrum_file": "04_bdt_training/data/beam_spectrum.npz",
    },
    "checkpoint": {
        "max_age_days": 30,
        "verification": "fast",
        "old_policy": "ask",
        "stale_policy": "ask",
        "untracked_policy": "ask",
    },
    "runtime": {
        "python_executable": "python",
        "root_executable": "root",
        "input_tree": "auto",
        "signal_channel": "eta_pi0",
        "signal_prior": 0.5,
        "partner": "proton",
        "mc_events": 1000000,
        "grid_search_iterations": 30,
        "use_grid_search": True,
        "threads": 1,
        "flux_progress_every_events": 1000000,
        "flux_samples_per_run_strip": 256,
        "bootstrap_replicas": 500,
        "bootstrap_seed": 1208,
        "estimator": "both",
    },
    "profile_settings": {
        "claim": "physics production",
        "isolated_results": False,
        "requires_real_fixture": False,
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
    runtime = effective["runtime"]
    profile_settings = effective["profile_settings"]
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
            mc_data_dir=resolve_within_root(root, paths["mc_data_dir"]),
            model_dir=resolve_within_root(root, paths["model_dir"]),
            features_file=resolve_within_root(root, paths["features_file"]),
            beam_spectrum_file=resolve_within_root(root, paths["beam_spectrum_file"]),
        ),
        checkpoint=CheckpointConfig(
            max_age_days=checkpoint["max_age_days"],
            verification=verification,
            old_policy=str(checkpoint["old_policy"]),
            stale_policy=str(checkpoint["stale_policy"]),
            untracked_policy=str(checkpoint["untracked_policy"]),
        ),
        runtime=RuntimeConfig(
            python_executable=str(runtime["python_executable"]),
            root_executable=str(runtime["root_executable"]),
            input_tree=str(runtime["input_tree"]),
            signal_channel=str(runtime["signal_channel"]),
            signal_prior=float(runtime["signal_prior"]),
            partner=str(runtime["partner"]),
            mc_events=int(runtime["mc_events"]),
            grid_search_iterations=int(runtime["grid_search_iterations"]),
            use_grid_search=bool(runtime["use_grid_search"]),
            threads=int(runtime["threads"]),
            flux_progress_every_events=int(runtime["flux_progress_every_events"]),
            flux_samples_per_run_strip=int(runtime["flux_samples_per_run_strip"]),
            bootstrap_replicas=int(runtime["bootstrap_replicas"]),
            bootstrap_seed=int(runtime["bootstrap_seed"]),
            estimator=str(runtime["estimator"]),
        ),
        profile_settings=ProfileSettings(
            claim=str(profile_settings["claim"]),
            isolated_results=bool(profile_settings["isolated_results"]),
            requires_real_fixture=bool(profile_settings["requires_real_fixture"]),
        ),
    )


def configuration_snapshot(config: PipelineConfig) -> dict[str, Any]:
    def normalize(value: Any) -> Any:
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, dict):
            return {str(key): normalize(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [normalize(item) for item in value]
        return value

    return normalize(asdict(config))


def validate_profile_inputs(config: PipelineConfig) -> None:
    if not config.profile_settings.requires_real_fixture:
        return
    raw_dir = config.paths.raw_dir
    fixtures = sorted(raw_dir.rglob("*.root")) if raw_dir.is_dir() else []
    if not fixtures:
        try:
            relative = raw_dir.relative_to(config.repository_root)
        except ValueError:
            relative = raw_dir
        raise ProfileInputError(
            f"profile {config.profile!r} requires reduced real ROOT fixtures under "
            f"{relative}. Create that directory and copy one or more representative "
            "detector runs from the farm dataset; synthetic physics input is not accepted."
        )


def materialize_profile_run(config: PipelineConfig, run_id: str) -> PipelineConfig:
    if not config.profile_settings.isolated_results:
        return config
    token = Path(run_id)
    if token.name != run_id or run_id in {"", ".", ".."}:
        raise ConfigError(f"invalid run ID for isolated profile: {run_id!r}")
    run_root = (config.paths.results_dir / run_id).resolve()
    base = config.paths.results_dir.resolve()
    if not run_root.is_relative_to(base):
        raise ConfigError(f"profile run root escapes validation results: {run_root}")
    paths = replace(
        config.paths,
        results_dir=run_root,
        preanalysis_dir=run_root / "data/pre_analyzed/pre_analisi",
        selected_dir=run_root / "data/selected",
        mc_data_dir=run_root / "mc",
        model_dir=run_root / "model/stage1",
        features_file=run_root / "training/features_stage1.npz",
        beam_spectrum_file=run_root / "training/beam_spectrum.npz",
    )
    return replace(config, paths=paths)
