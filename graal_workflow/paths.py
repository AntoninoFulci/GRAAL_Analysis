"""Repository paths, preflight checks, locks and campaign publication."""
from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from pathlib import Path
import fcntl
import importlib
import json
import os
import shutil
import sys
import tempfile

from calibration.run_manifest import validate_manifest
from calibration.common_inputs import load_common_inputs
from calibration.run_quality import load_run_quality
from .artifact_manifest import validate_preanalysis
from .models import ModeConfig, PipelineError, PipelinePaths, PreflightResult, PROFILE_PATTERNS

RUNTIME_MODULES = (
    "ROOT",
    "numpy",
    "uproot",
    "awkward",
    "xgboost",
    "sklearn",
    "matplotlib",
)


def resolve_repo_root(explicit: Path | None) -> Path:
    """Resolve native resources only from an explicitly validated checkout.

    The implicit location is useful in editable installs; wheels must supply
    --repo-root. Neither the working directory nor site-packages is a resource
    root, even if unrelated files happen to have matching names.
    """
    root = (Path(explicit).expanduser().resolve() if explicit is not None
            else Path(__file__).resolve().parents[1])
    if explicit is None and any(part in {"site-packages", "dist-packages"} for part in root.parts):
        raise PipelineError("installed workflow requires --repo-root PATH to a GRAAL checkout")
    required = (
        "pyproject.toml", "config/run_manifest.csv", "config/run_quality_exclusions.json",
        "01_pre_analysis/PreAnalysis.C", "scripts/plot_campaign.py",
        "06_calibration/build_strip_energy_flux.py", "08_observable_extraction/beam_asymmetry.py",
    )
    missing = [str(root / name) for name in required if not (root / name).is_file()]
    generators = root / "03_mc_simulation/generators"
    from .models import UV_CHANNELS
    missing.extend(str(generators / f"generate_{name}_dataset.C") for name in UV_CHANNELS
                   if not (generators / f"generate_{name}_dataset.C").is_file())
    missing.extend(str(generators / name) for name in ("smearing.h", "beam_window.h", "generator_runtime.h")
                   if not (generators / name).is_file())
    if missing:
        raise PipelineError(f"invalid repository root {root}: required resources missing: " + ", ".join(missing))
    return root



def mode_config(mode: str, repo_root: Path | None = None) -> ModeConfig:
    repo_root = resolve_repo_root(None) if repo_root is None else Path(repo_root).resolve()
    values = {
        "test_data": ("data_test/sample", "results_test/test_data", 100_000),
        "production": (
            "data/02_pre_analyzed",
            "results/production",
            1_000_000,
        ),
    }
    try:
        preanalysis, output, events = values[mode]
    except KeyError:
        raise PipelineError(f"unknown mode: {mode}") from None
    return ModeConfig(
        name=mode,
        repo_root=repo_root,
        preanalysis_dir=repo_root / preanalysis,
        default_output=repo_root / output,
        mc_events=events,
    )


def build_paths(
    config: ModeConfig, output_override: Path | None = None
) -> PipelinePaths:
    output = (
        config.default_output
        if output_override is None
        else Path(output_override).expanduser().absolute()
    )
    artifact_root = config.repo_root / "results/_cache" if config.name == "production" else output / "artifacts"
    common_path = config.repo_root / "config/common_inputs.json"
    common = (load_common_inputs(config.repo_root, path=common_path, cache=artifact_root, verify=False)["inputs"]
              if common_path.is_file() else {})
    return PipelinePaths(
        repo_root=config.repo_root,
        preanalysis_dir=config.preanalysis_dir,
        data_root=config.repo_root / ("data" if config.name == "production" else "data_test"),
        artifact_root=artifact_root,
        output_root=output,
        manifest=common.get("run_catalog", config.repo_root / "config/run_manifest.csv"),
        run_quality=common.get("run_quality", config.repo_root / "config/run_quality_exclusions.json"),
        raw_flux=common.get("raw_flux", config.repo_root / "data/00_external/flux.root"),
        hyperparams=(
            config.repo_root
            / "04_bdt_training/artifacts/stage1/best_hyperparams.json"
        ),
        ajaka_reference=(
            config.repo_root
            / "08_observable_extraction/references/ajaka2008_figure4_digitized.csv"
        ),
    )


def required_repository_files(paths: PipelinePaths) -> tuple[Path, ...]:
    generator_dir = paths.repo_root / "03_mc_simulation/generators"
    generators = tuple(
        generator_dir / f"generate_{name}_dataset.C"
        for name in (
            "eta_pi0",
            "pi0pi0",
            "3pi0",
            "eta_2pi0",
            "omega_pi0",
            "etaprime",
            "eta_via_3pi0",
            "4pi0",
            "eta_pi0_via_3pi0",
        )
    )
    return (
        paths.manifest,
        paths.quality_path,
        paths.repo_root / "config/common_inputs.json",
        paths.raw_flux,
        paths.hyperparams,
        paths.ajaka_reference,
        paths.repo_root / "06_calibration/build_strip_energy_flux.py",
        paths.repo_root / "08_observable_extraction/beam_asymmetry.py",
        *generators,
    )


def _writable_ancestor(path: Path) -> Path:
    candidate = path
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    return candidate


def preflight(
    config: ModeConfig,
    paths: PipelinePaths,
    *,
    import_module: Callable[[str], object] = importlib.import_module,
    which: Callable[[str], str | None] = shutil.which,
    manifest_validator: Callable[[Path], object] = validate_manifest,
    preanalysis_validator: Callable[[Sequence[Path]], None] = validate_preanalysis,
    python_version: tuple[int, int] = sys.version_info[:2],
) -> PreflightResult:
    if python_version < (3, 10):
        raise PipelineError(
            f"Python 3.10 or newer is required, got {python_version[0]}."
            f"{python_version[1]}"
        )
    if config.mc_events <= 0:
        raise PipelineError("MC event count must be positive")
    if not paths.preanalysis_dir.is_dir():
        raise PipelineError(
            f"pre-analysis directory not found: {paths.preanalysis_dir}"
        )
    if config.name == "production":
        marker = paths.preanalysis_dir / "manifest.json"
        if marker.is_file() and json.loads(marker.read_text()).get("diagnostic_only"):
            raise PipelineError("diagnostic sample is forbidden in production")
    old_preanalysis_inputs: list[Path] = []
    now = datetime.now(timezone.utc).timestamp()
    for profile, pattern in PROFILE_PATTERNS.items():
        files = sorted(path for path in paths.preanalysis_dir.glob(pattern) if path.is_file())
        if not files:
            raise PipelineError(
                f"{profile.upper()} pre-analysis files not found: {pattern}"
            )
        if config.name == "production":
            import uproot
            for path in files:
                with uproot.open(path) as source:
                    if "sample_provenance" in source:
                        obj = source["sample_provenance"]
                        payload = obj.member("fTitle") if obj.classname == "TNamed" else str(obj)
                        if json.loads(payload).get("diagnostic_only"):
                            raise PipelineError(f"diagnostic sample is forbidden in production: {path}")
        try:
            preanalysis_validator(files)
        except Exception as exc:
            raise PipelineError(f"{profile.upper()} pre-analysis invalid: {exc}") from exc
        if config.name == "production":
            for path in files:
                if now - path.stat().st_mtime > 10 * 86400:
                    old_preanalysis_inputs.append(path)
    for path in required_repository_files(paths):
        if not path.is_file():
            raise PipelineError(f"required file not found: {path}")
    if paths.output_root.exists():
        if not paths.output_root.is_dir():
            raise PipelineError(
                f"output root is not a directory: {paths.output_root}"
            )
        if config.name == "production" and any(paths.output_root.iterdir()):
            raise PipelineError(f"output root is not empty: {paths.output_root}")
    writable = _writable_ancestor(paths.output_root)
    if not writable.is_dir() or not os.access(writable, os.W_OK):
        raise PipelineError(f"output parent is not writable: {writable}")
    for name in RUNTIME_MODULES:
        try:
            import_module(name)
        except Exception as exc:
            raise PipelineError(f"cannot import {name}: {exc}") from exc
    root_executable = which("root")
    if root_executable is None:
        raise PipelineError("root executable not found on PATH")
    try:
        load_run_quality(paths.quality_path)
        common = load_common_inputs(paths.repo_root, cache=paths.artifact_root)
        if common["inputs"] != {"run_catalog": paths.manifest.resolve(),
                                "run_quality": paths.quality_path.resolve(), "raw_flux": paths.raw_flux.resolve()}:
            raise ValueError("planned common inputs differ from verified manifest")
    except (ValueError, OSError) as exc:
        raise PipelineError(f"invalid run quality policy: {exc}") from exc
    try:
        manifest_validator(paths.manifest)
    except Exception as exc:
        raise PipelineError(f"invalid run manifest: {exc}") from exc
    return PreflightResult(root_executable, tuple(old_preanalysis_inputs))


def prepare_output_dirs(paths: PipelinePaths) -> None:
    paths.output_root.mkdir(parents=True, exist_ok=True)
    try:
        paths.command_log.touch(exist_ok=False)
    except FileExistsError as exc:
        raise PipelineError(
            f"output root already claimed by another pipeline: {paths.output_root}"
        ) from exc
    except OSError as exc:
        raise PipelineError(
            f"cannot claim output root {paths.output_root}: {exc}"
        ) from exc
    unexpected = tuple(
        path for path in paths.output_root.iterdir() if path != paths.command_log
    )
    if unexpected:
        paths.command_log.unlink()
        raise PipelineError(
            f"output root changed after preflight: {paths.output_root}"
        )
    for path in (
        paths.output_root / "common",
        paths.output_root / "uv/reco",
        paths.output_root / "vis/reco",
    ):
        path.mkdir(parents=True, exist_ok=True)


def validate_test_output(paths: PipelinePaths) -> None:
    parent = paths.repo_root / "results_test"
    output = paths.output_root.resolve()
    inputs = paths.preanalysis_dir.resolve()
    if output == inputs or output.is_relative_to(inputs) or inputs.is_relative_to(output):
        raise PipelineError("test output must not overlap input through aliases")
    if parent.is_symlink():
        raise PipelineError("test output results parent must not be a symlink")
    if (paths.output_root.parent.resolve() != parent.resolve() or paths.output_root.is_symlink()
            or paths.output_root.name in {"archive", "diagnostics", "_cache"}):
        raise PipelineError("test output must be results_test/<campaign> without symlinks")
    if paths.artifact_root.is_symlink():
        raise PipelineError("test artifact root must not be a symlink")
    if paths.artifact_root != paths.output_root / "artifacts":
        raise PipelineError("test artifact root must belong to its campaign")
    # Only launcher-created campaigns are replaceable. Other populated trees
    # may contain archives, study inputs or execution evidence in this namespace.
    if paths.output_root.is_dir() and any(paths.output_root.iterdir()):
        if paths.command_log.is_symlink() or not paths.command_log.is_file():
            raise PipelineError("existing test output is not a launcher-owned campaign")


def validate_production_output(paths: PipelinePaths) -> None:
    results = paths.repo_root / "results"
    if (results.is_symlink() or paths.output_root.is_symlink() or
            paths.output_root.parent.resolve() != results.resolve() or
            paths.output_root.name.startswith("test_")):
        raise PipelineError("production output must be results/<campaign> without symlinked results paths")


@contextmanager
def pipeline_lock(repo_root: Path, *, mode: str = "production"):
    if mode not in ("production", "test_data"):
        raise PipelineError(f"unknown lock mode: {mode}")
    namespace = "results" if mode == "production" else "results_test"
    lock_path = Path(repo_root) / namespace / ".pipeline.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise PipelineError(f"pipeline lock is held: {lock_path}") from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


@contextmanager
def _replace_test_output(paths: PipelinePaths):
    """Publish a complete test campaign, restoring its previous bytes on failure."""
    validate_test_output(paths)
    backup = None
    if paths.output_root.exists():
        backup = Path(tempfile.mkdtemp(prefix=f".{paths.output_root.name}.backup-", dir=paths.output_root.parent))
        backup.rmdir()
        paths.output_root.rename(backup)
    try:
        yield
    except BaseException:
        if paths.output_root.exists():
            shutil.rmtree(paths.output_root)
        if backup is not None:
            backup.rename(paths.output_root)
        raise
    else:
        if backup is not None:
            shutil.rmtree(backup)
