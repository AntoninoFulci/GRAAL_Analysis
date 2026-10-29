"""Execute stages and certify reusable artifacts."""
from __future__ import annotations

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from itertools import groupby
from pathlib import Path
import json
import os
import shlex
import subprocess
import tempfile
import time

from calibration.run_quality import load_run_quality
from graal_common.io.filesystem import atomic_output_directory
from graal_common.parallel import validate_workers
from . import artifact_manifest as cache
from . import logging as console
from .models import ModeConfig, PipelineError, PipelinePaths, Stage, ArtifactGroup, PipelinePlan, flatten_stages, PROFILE_PATTERNS
from .resources import installed_package_sources


def _log_stage(path: Path, stage: Stage, exit_code: int, duration: float) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(
            f"{stage.name}\texit={exit_code}\tduration={duration:.3f}s\t"
            f"command={shlex.join(stage.argv)}\n"
        )


def _log_decision(path: Path, name: str, action: str, reason: str) -> None:
    line = f"{name}\t{action}\treason={reason}\n"
    console.emit(line.strip(), "detail" if action == "SKIP" else "info")
    with path.open("a", encoding="utf-8") as stream:
        stream.write(line)


def run_cached_stages(
    stages: Sequence[Stage],
    paths: PipelinePaths,
    item: cache.CacheItem,
    destination: Path,
    validate: Callable[[Path], None],
    *,
    production: bool,
    force: bool = False,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> dict:
    """Run a cache unit against staging, then publish validated output."""
    if production and not force:
        reusable, reason = cache.cache_status(item, lambda: validate(destination))
        if reusable:
            _log_decision(paths.command_log, item.name, "SKIP", reason)
            return {"name": item.name, "action": "SKIP", "reason": reason, "manifest": str(item.manifest), "signature": item.signature}
    else:
        reason = "force" if force else "test data always rebuilds"
    _log_decision(paths.command_log, item.name, "RUN", reason)

    def execute_at(staged: Path) -> None:
        def rewrite_output(argument: str) -> str:
            source, target = str(destination), str(staged)
            if argument == source or argument.startswith(source + os.sep):
                return target + argument[len(source):]
            if destination.suffix == '.root' and '.C(' in argument:
                return argument.replace(f'"{source}"', f'"{target}"')
            return argument

        rewritten = tuple(
            replace(stage, argv=tuple(rewrite_output(arg) for arg in stage.argv))
            for stage in stages
        )
        execute_plan(rewritten, paths, runner=runner)
        validate(staged)

    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.suffix == ".root":
            fd, temporary = tempfile.mkstemp(prefix=f".{destination.stem}.", suffix=".root", dir=destination.parent)
            os.close(fd)
            staged = Path(temporary)
            try:
                execute_at(staged)
                staged.replace(destination)
            finally:
                staged.unlink(missing_ok=True)
        else:
            with atomic_output_directory(destination) as staged:
                execute_at(staged)
        if production:
            cache.record_cache(item, lambda: validate(destination))
    except PipelineError:
        raise
    except Exception as exc:
        raise PipelineError(f"artifact {item.name} failed: {exc}") from exc
    return {"name": item.name, "action": "RUN", "reason": reason, "manifest": str(item.manifest) if production else None, "signature": item.signature if production else None}


def execute_plan(
    stages: PipelinePlan,
    paths: PipelinePaths,
    *,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    monotonic: Callable[[], float] = time.monotonic,
) -> None:
    commands = flatten_stages(stages)
    for index, stage in enumerate(commands, start=1):
        console.emit(f"\n[{index}/{len(commands)}] {stage.name}", "info")
        console.emit(f"$ {shlex.join(stage.argv)}", "detail")
        started = monotonic()
        result = runner(
            stage.argv,
            cwd=paths.repo_root,
            check=False,
            shell=False,
        )
        duration = monotonic() - started
        _log_stage(paths.command_log, stage, result.returncode, duration)
        console.emit(
            f"[{stage.name}] exit={result.returncode} duration={duration:.1f}s",
            "success" if result.returncode == 0 else "error",
        )
        if result.returncode != 0:
            raise PipelineError(
                f"stage {stage.name} failed with exit {result.returncode}"
            )


def _source_files(paths: PipelinePaths, component: str) -> tuple[Path, ...]:
    packages = {"02_event_selector": "event_selector", "03_mc_simulation": "mc_simulation",
                "04_bdt_training": "bdt_training", "08_observable_extraction": "observable_extraction"}
    files = tuple(path for package in ("graal_workflow", "graal_common", packages[component])
                  for path in installed_package_sources(package))
    if component == "08_observable_extraction":
        files += (paths.quality_path,
                  *installed_package_sources("calibration"))
    if component == "03_mc_simulation":
        native = paths.repo_root / "03_mc_simulation/generators"
        macros, headers = tuple(native.glob("*.C")), tuple(native.glob("*.h"))
        if not macros or not headers:
            raise PipelineError(f"native source inventory is empty: {native}")
        files += (*macros, *headers)
    return tuple(files)


def _stage_sources(paths: PipelinePaths, stages: PipelinePlan) -> tuple[Path, ...]:
    """Record installed modules and explicit checkout drivers actually dispatched."""
    sources = set(installed_package_sources("graal_workflow"))
    sources.update(installed_package_sources("graal_common"))
    common = paths.repo_root / "config/support/common_inputs.json"
    if common.is_file():
        sources.add(common)
    driver_packages = {"build_strip_energy_flux.py": ("calibration",),
                       "beam_asymmetry.py": ("observable_extraction", "calibration"),
                       "plot_campaign.py": ("plots", "observable_extraction", "reconstruction")}
    # These are caller-supplied configuration inputs. In contrast,
    # --calibration-qa is produced by the preceding calibration stage.
    static_options = {"--manifest", "--run-manifest", "--hyperparams",
                      "--published-csv", "--run-metadata", "--run-quality"}
    for stage in flatten_stages(stages):
        if stage.kind == 'preanalysis':
            native = paths.repo_root / '01_pre_analysis'
            sources.update(native / name for name in ('PreAnalysis.C', 'PreAnalysis.h', 'RawTrackContract.h', 'CutManager.h'))
            cuts = (Path(stage.argv[stage.argv.index('--cuts-dir') + 1])
                    if '--cuts-dir' in stage.argv else native / 'cuts')
            sources.update(cuts.glob('*.cpp'))
        for option, value in zip(stage.argv, stage.argv[1:]):
            if option in static_options:
                path = Path(value)
                sources.add(path if path.is_absolute() else paths.repo_root / path)
        if "-m" in stage.argv:
            module = stage.argv[stage.argv.index("-m") + 1]
            sources.update(installed_package_sources(module.split(".")[0]))
            if module.startswith("flux_studies."):
                sources.update(installed_package_sources("calibration"))
        for arg in stage.argv:
            if arg.endswith(".py") and Path(arg).is_absolute():
                sources.add(Path(arg))
                for package in driver_packages.get(Path(arg).name, ()):
                    sources.update(installed_package_sources(package))
                if Path(arg).name in {"build_strip_energy_flux.py", "beam_asymmetry.py"}:
                    sources.add(paths.quality_path)
            elif ".C(" in arg:
                macro = Path(arg.split(".C(", 1)[0] + ".C")
                sources.add(macro)
                headers = tuple(macro.parent.glob("*.h"))
                if not headers:
                    raise PipelineError(f"native header inventory is empty: {macro.parent}")
                sources.update(headers)
    return tuple(sorted(sources))


def _revision(repo_root: Path) -> str:
    result = subprocess.run(
        ("git", "rev-parse", "HEAD"), cwd=repo_root, capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _write_campaign_artifacts(paths: PipelinePaths, outcomes: list[dict], sources: list[dict]) -> None:
    preanalysis = {
        profile: cache.inventory(sorted(paths.preanalysis_dir.glob(pattern)))
        for profile, pattern in PROFILE_PATTERNS.items()
    }
    target = paths.command_log.parent / "pipeline_artifacts.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps({"source_revision": _revision(paths.repo_root), "preanalysis": preanalysis,
                    "source_files": sources,
                    "run_quality": load_run_quality(paths.quality_path),
                    "calibration": (json.loads((paths.calibrated_flux.parent / "calibration_reuse.json").read_text())
                                    if (paths.calibrated_flux.parent / "calibration_reuse.json").is_file() else None),
                    "cache": outcomes}, indent=2) + "\n",
        encoding="utf-8",
    )


def artifact_cache_item(group: ArtifactGroup, stages: PipelinePlan, paths: PipelinePaths):
    """Build a content signature and validator from the actual bound command inputs."""
    profile, destination = group.profile, group.destination

    def option(stage, flag, default):
        return stage.argv[stage.argv.index(flag) + 1] if flag in stage.argv else default

    if group.kind == "selected":
        stage = group.stages[0]
        directory = Path(option(stage, "--input-dir", paths.preanalysis_dir))
        pattern = option(stage, "--pattern", PROFILE_PATTERNS[profile])
        inputs = tuple(sorted(directory.glob(pattern)))
        item = cache.CacheItem(
            f"selected:{profile}", destination.parent / f"{profile}.manifest.json", (destination,),
            {"inputs": cache.inventory(inputs), "options": stage.argv,
             "source": cache.source_fingerprint(_source_files(paths, "02_event_selector"))},
        )
        return item, lambda directory: cache.validate_selected(directory, inputs)
    if group.kind == "mc":
        item = cache.CacheItem(
            f"mc:{profile}:{group.channel}", destination.with_suffix(".manifest.json"), (destination,),
            {"options": group.stages[0].argv,
             "source": cache.source_fingerprint(_source_files(paths, "03_mc_simulation"))},
        )
        return item, lambda path: cache.validate_mc(path, group.channel)
    if group.inputs:
        selected, mc = group.inputs[:1], group.inputs[1:]
    else:
        selected = tuple(entry.destination for entry in stages
                         if isinstance(entry, ArtifactGroup) and entry.kind == "selected" and entry.profile == profile)
        mc = tuple(entry.destination for entry in stages
                   if isinstance(entry, ArtifactGroup) and entry.kind == "mc" and entry.profile == profile)
    if len(selected) != 1 or not mc:
        raise PipelineError(f"incomplete {profile} BDT upstream artifact groups")
    hyperparams = Path(option(group.stages[-1], "--hyperparams", paths.hyperparams))
    item = cache.CacheItem(
        f"bdt:{profile}", destination.parent / f"{profile}.manifest.json", (destination,),
        {"selected": cache.inventory(selected), "mc": cache.inventory(mc),
         "options": [entry.argv for entry in group.stages],
         "hyperparams": cache.source_fingerprint((hyperparams,)),
         "source": cache.source_fingerprint(_source_files(paths, "04_bdt_training"))},
    )
    return item, lambda directory: cache.validate_bdt(directory, profile, energy_range=group.energy_range)


def execute_cached_plan(
    stages: PipelinePlan,
    config: ModeConfig,
    paths: PipelinePaths,
    *,
    force_selected: bool = False,
    force_mc: bool = False,
    force_bdt: bool = False,
    cpus: int = 1,
    before_entry: Callable[[Stage | ArtifactGroup], None] | None = None,
    write_legacy_metadata: bool = True,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> list[dict]:
    validate_workers(cpus)
    cache_kinds = {"select", "generate", "beam_spectrum", "features", "train"}
    for entry in stages:
        if isinstance(entry, Stage) and entry.kind in cache_kinds:
            raise PipelineError(f"stage kind {entry.kind} requires an artifact group")
    production = config.name == "production"
    outcomes: list[dict] = []
    sources = cache.inventory(_stage_sources(paths, stages))

    def run_group(group: ArtifactGroup) -> dict:
        if before_entry is not None:
            before_entry(group)
        item, validator = artifact_cache_item(group, stages, paths)
        force = group.force if group.force is not None else {"selected": force_selected, "mc": force_mc, "bdt": force_bdt}[group.kind]
        return run_cached_stages(group.stages, paths, item, group.destination, validator,
                                 production=production, force=force, runner=runner)

    # Only consecutive MC units share a pool. Every group still owns one output;
    # the ordered common/profile/plot phases remain unchanged.
    def batch_key(entry: Stage | ArtifactGroup) -> tuple[bool, str | None]:
        is_mc = isinstance(entry, ArtifactGroup) and entry.kind == "mc"
        return is_mc, entry.profile if is_mc else None

    for (parallel_mc, _profile), entries in groupby(stages, key=batch_key):
        if parallel_mc:
            batch = tuple(entries)
            with ThreadPoolExecutor(max_workers=min(cpus, len(batch))) as pool:
                outcomes.extend(pool.map(run_group, batch))
            if production and write_legacy_metadata:
                _write_campaign_artifacts(paths, outcomes, sources)
            continue
        for entry in entries:
            if isinstance(entry, ArtifactGroup):
                outcomes.append(run_group(entry))
                if production and write_legacy_metadata:
                    _write_campaign_artifacts(paths, outcomes, sources)
            else:
                if before_entry is not None:
                    before_entry(entry)
                _log_decision(paths.command_log, entry.name, "RUN", "campaign stage" if production else "test data always rebuilds")
                execute_plan((entry,), paths, runner=runner)
    return outcomes
