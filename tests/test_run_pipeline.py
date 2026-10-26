from pathlib import Path
import os
import re
import subprocess
import sys
import numpy as np
import uproot

import pytest

from graal_common.physics.energy_binning import EnergyBinning
from graal_workflow import cli, execution, models, paths as workflow_paths, planning


def test_mode_config_uses_exact_test_and_production_inputs(tmp_path):
    test = workflow_paths.mode_config("test_data", tmp_path)
    production = workflow_paths.mode_config("production", tmp_path)

    assert test.preanalysis_dir == tmp_path / "data_test/sample"
    assert test.default_output == tmp_path / "results_test/test_data"
    assert test.mc_events == 100_000
    assert production.preanalysis_dir == tmp_path / "data/02_pre_analyzed"
    assert production.default_output == tmp_path / "results/production"
    assert production.mc_events == 1_000_000


def test_unknown_mode_is_rejected(tmp_path):
    with pytest.raises(models.PipelineError, match="unknown mode"):
        workflow_paths.mode_config("farm", tmp_path)


def test_output_override_replaces_only_output_root(tmp_path):
    config = workflow_paths.mode_config("production", tmp_path)
    paths = workflow_paths.build_paths(config, tmp_path / "campaign 01")

    assert paths.output_root == tmp_path / "campaign 01"
    assert paths.preanalysis_dir == config.preanalysis_dir
    assert paths.calibrated_flux == (
        tmp_path / "campaign 01/common/flux_calibrated.root"
    )
    assert paths.profile_root("uv") == tmp_path / "campaign 01/uv"
    assert paths.profile_root("vis") == tmp_path / "campaign 01/vis"


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()


def _valid_preflight_tree(tmp_path: Path):
    config = workflow_paths.mode_config("test_data", tmp_path)
    paths = workflow_paths.build_paths(config)
    for path in workflow_paths.required_repository_files(paths):
        _touch(path)
    from calibration.run_quality import DEFAULT_RUN_QUALITY_PATH
    (tmp_path / "config/run_quality_exclusions.json").write_bytes(DEFAULT_RUN_QUALITY_PATH.read_bytes())
    import json
    from calibration.calibration_qa import sha256_file
    from calibration.run_manifest import RunRecord, write_manifest
    write_manifest([RunRecord(1, 'fixture_uv', 'P', 'UV', 'P_UV', 'manual', 'fixture_uv/run1.root')], paths.manifest)
    references = {name: dict(root='checkout', path=str(path.relative_to(tmp_path)), sha256=sha256_file(path))
                  for name, path in {'run_catalog': paths.manifest, 'run_quality': paths.quality_path, 'raw_flux': paths.raw_flux}.items()}
    (tmp_path / 'config/common_inputs.json').write_text(json.dumps(dict(schema_version=1, inputs=references,
        bundles=dict(calibration=dict(root='cache', path='06_calibration', schema_version=1), inclusive_counts={}))))
    for profile in ("uv", "vis"):
        root = paths.preanalysis_dir / f"pre_analisi_1998_{profile}.root"
        root.parent.mkdir(parents=True, exist_ok=True)
        with uproot.recreate(root) as output:
            output["h80"] = {key: np.array([1]) for key in ("gammas", "fcharged_theta", "RunNumber", "Polarization", "Xstrip")}
    return config, paths


def _imports(_name: str):
    return object()


def test_preflight_rejects_old_python(tmp_path):
    config, paths = _valid_preflight_tree(tmp_path)
    with pytest.raises(models.PipelineError, match="Python 3.10"):
        workflow_paths.preflight(
            config,
            paths,
            import_module=_imports,
            which=lambda _name: "/usr/bin/root",
            manifest_validator=lambda _path: (),
            python_version=(3, 9),
        )


def test_preflight_rejects_missing_root_executable(tmp_path):
    config, paths = _valid_preflight_tree(tmp_path)
    with pytest.raises(models.PipelineError, match="root executable"):
        workflow_paths.preflight(
            config,
            paths,
            import_module=_imports,
            which=lambda _name: None,
            manifest_validator=lambda _path: (),
        )
    assert not paths.output_root.exists()


def test_preflight_rejects_pyroot_import_failure(tmp_path):
    config, paths = _valid_preflight_tree(tmp_path)

    def fail_root(name: str):
        if name == "ROOT":
            raise ImportError("ABI mismatch")
        return object()

    with pytest.raises(models.PipelineError, match="cannot import ROOT"):
        workflow_paths.preflight(
            config,
            paths,
            import_module=fail_root,
            which=lambda _name: "/usr/bin/root",
            manifest_validator=lambda _path: (),
        )


def test_preflight_rejects_missing_vis_input(tmp_path):
    config, paths = _valid_preflight_tree(tmp_path)
    (paths.preanalysis_dir / "pre_analisi_1998_vis.root").unlink()

    with pytest.raises(models.PipelineError, match="VIS.*pre-analysis"):
        workflow_paths.preflight(
            config,
            paths,
            import_module=_imports,
            which=lambda _name: "/usr/bin/root",
            manifest_validator=lambda _path: (),
        )


def test_test_preflight_allows_existing_output_until_locked_replacement(tmp_path):
    config, paths = _valid_preflight_tree(tmp_path)
    sentinel = paths.output_root / "keep.txt"
    _touch(sentinel)

    workflow_paths.preflight(
        config,
        paths,
        import_module=_imports,
        which=lambda _name: "/usr/bin/root",
        manifest_validator=lambda _path: (),
    )
    assert sentinel.is_file()


def test_preflight_accepts_complete_minimal_inputs(tmp_path):
    config, paths = _valid_preflight_tree(tmp_path)
    result = workflow_paths.preflight(
        config,
        paths,
        import_module=_imports,
        which=lambda _name: "/opt/root/bin/root",
        manifest_validator=lambda _path: (),
    )
    assert result == models.PreflightResult("/opt/root/bin/root")
    assert not paths.output_root.exists()


def test_preflight_rejects_invalid_h80_and_warns_only_for_old_input(tmp_path, capsys):
    config, paths = _valid_preflight_tree(tmp_path)
    uv = next(paths.preanalysis_dir.glob("*uv.root"))
    with uproot.recreate(uv) as output:
        output["h80"] = {"RunNumber": np.array([1])}
    with pytest.raises(models.PipelineError, match="missing branches"):
        workflow_paths.preflight(config, paths, import_module=_imports, which=lambda _: "root", manifest_validator=lambda _: ())
    with uproot.recreate(uv) as output:
        output["h80"] = {key: np.array([1]) for key in ("gammas", "fcharged_theta", "RunNumber", "Polarization", "Xstrip")}
    old = uv.stat().st_mtime - 11 * 86400
    import os
    os.utime(uv, (old, old))
    workflow_paths.preflight(config, paths, import_module=_imports, which=lambda _: "root", manifest_validator=lambda _: ())
    assert "10 days" not in capsys.readouterr().out  # disposable test data has no age warning


def test_production_preflight_collects_old_h80_for_separate_warning_table(tmp_path, capsys):
    _, test_paths = _valid_preflight_tree(tmp_path)
    config = workflow_paths.mode_config("production", tmp_path)
    paths = workflow_paths.build_paths(config)
    paths.preanalysis_dir.mkdir(parents=True)
    for profile in ("uv", "vis"):
        source = test_paths.preanalysis_dir / f"pre_analisi_1998_{profile}.root"
        (paths.preanalysis_dir / source.name).write_bytes(source.read_bytes())
    old_uv = paths.preanalysis_dir / "pre_analisi_1998_uv.root"
    old_time = old_uv.stat().st_mtime - 11 * 86400
    os.utime(old_uv, (old_time, old_time))

    checked = workflow_paths.preflight(
        config, paths, import_module=_imports, which=lambda _: "root",
        manifest_validator=lambda _: (),
    )

    assert checked.old_preanalysis_inputs == (old_uv,)
    assert capsys.readouterr().out == ""
    cli.print_preflight_warnings(checked)
    warning_table = capsys.readouterr().out
    assert "Avvisi pre-analisi" in warning_table
    warning_values = "".join(
        line.split("│")[2].strip()
        for line in warning_table.splitlines()
        if line.startswith("│")
    )
    assert str(old_uv) in warning_values
    assert "10 giorni" in warning_table
    assert "pre_analisi_1998_vis.root" not in warning_table


def _plan(tmp_path: Path, mode: str = "test_data"):
    config = workflow_paths.mode_config(mode, tmp_path)
    paths = workflow_paths.build_paths(config, tmp_path / "out with spaces")
    result = models.PreflightResult("/opt/root/bin/root")
    stages = planning.build_pipeline_plan(
        config, paths, result, python_executable="/venv/bin/python"
    )
    return config, paths, models.flatten_stages(stages)


def _stage(stages, name: str):
    return next(item for item in models.flatten_stages(stages) if item.name == name)


@pytest.mark.parametrize("mode", ["production", "test_data"])
@pytest.mark.parametrize("phi_bins", [8, 12, 16])
def test_launch_phi_binning_reaches_both_extractions_only(tmp_path, mode, phi_bins):
    args = cli.build_parser().parse_args(
        ["--mode", mode, "--phi-bins", str(phi_bins)]
    )
    config = workflow_paths.mode_config(mode, tmp_path)
    paths = workflow_paths.build_paths(config)
    checked = models.PreflightResult("/usr/bin/root")
    stages = planning.build_pipeline_plan(config, paths, checked, phi_bins=args.phi_bins)
    default_stages = planning.build_pipeline_plan(config, paths, checked)
    assert len(stages) == len(default_stages)
    for stage, default in zip(models.flatten_stages(stages), models.flatten_stages(default_stages)):
        if stage.name.endswith(":extract"):
            assert stage.argv[stage.argv.index("--phi-bins") + 1] == str(phi_bins)
            assert default.argv[default.argv.index("--phi-bins") + 1] == "12"
        else:
            assert stage == default


def test_launch_phi_bins_default_and_invalid_choice():
    assert cli.build_parser().parse_args(["--mode", "production"]).phi_bins == 12
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["--mode", "production", "--phi-bins", "10"])


def test_best_binning_changes_only_extraction_commands(tmp_path):
    args = cli.build_parser().parse_args(["--mode", "production", "--best-binning"])
    config = workflow_paths.mode_config("production", tmp_path)
    paths = workflow_paths.build_paths(config)
    checked = models.PreflightResult("/usr/bin/root")
    before = planning.build_pipeline_plan(config, paths, checked)
    after = planning.build_pipeline_plan(config, paths, checked, best_binning=args.best_binning)
    for fixed, best in zip(models.flatten_stages(before), models.flatten_stages(after), strict=True):
        if best.name.endswith(":extract"):
            assert best.argv == (*fixed.argv, "--best-binning")
        else:
            assert best == fixed


def test_plan_enables_reproducible_candle_test_for_both_profiles(tmp_path):
    config = workflow_paths.mode_config("test_data", tmp_path)
    paths = workflow_paths.build_paths(config)
    checked = models.PreflightResult("/usr/bin/root")
    energy_binnings = {
        "uv": EnergyBinning((1.10, 1.30, 1.50)),
        "vis": EnergyBinning((0.9313, 1.10)),
    }

    stages = planning.build_pipeline_plan(
        config,
        paths,
        checked,
        energy_binnings=energy_binnings,
        best_binning=True,
    )

    for profile, edges in (("uv", (1.10, 1.30, 1.50)), ("vis", (0.9313, 1.10))):
        command = _stage(stages, f"{profile}:extract").argv
        assert command.count("--candle-mass-half-width") == 1
        assert command[command.index("--candle-mass-half-width") + 1] == "0.05"
        assert command.count("--candle-balance-seed") == 1
        assert command[command.index("--candle-balance-seed") + 1] == "20261024"
        start = command.index("--energy-edges") + 1
        assert command[start:start + len(edges)] == tuple(str(edge) for edge in edges)
        assert command[-1] == "--best-binning"


def test_plan_calibrates_once_then_runs_uv_vis_and_combines(tmp_path):
    _config, paths, stages = _plan(tmp_path)

    assert len(stages) == 33
    assert stages[0].name == "common:calibrate_flux"
    assert stages[-1].name == "campaign:plots"
    assert sum(stage.name == "common:calibrate_flux" for stage in stages) == 1
    assert sum(stage.name.endswith(":extract") for stage in stages) == 2
    calibration = stages[0].argv
    assert "--output" not in calibration
    assert calibration[calibration.index("--output-dir") + 1] == str(paths.output_root / "common")
    assert calibration[calibration.index("--cache-root") + 1] == str(paths.artifact_root / "06_calibration")
    assert calibration[calibration.index("--cache-scope") + 1] == "diagnostic"
    assert calibration[calibration.index("--target") + 1] == "P"
    uv_extract = _stage(stages, "uv:extract").argv
    assert uv_extract[uv_extract.index("--bootstrap-replicas") + 1] == "0"
    assert str(paths.calibrated_flux) in _stage(stages, "uv:extract").argv
    assert str(paths.calibrated_flux) in _stage(stages, "vis:extract").argv
    assert str(paths.profile_root("uv") / "plots") in _stage(stages, "uv:extract").argv
    assert _stage(stages, "campaign:plots").argv[-2:] == ("--published-csv", str(paths.ajaka_reference))
    assert stages.index(_stage(stages, "uv:extract")) < stages.index(
        _stage(stages, "vis:select")
    )


def test_plan_uses_exact_profile_patterns_channels_and_energy_ranges(tmp_path):
    config, _paths, stages = _plan(tmp_path)

    uv_select = _stage(stages, "uv:select")
    vis_select = _stage(stages, "vis:select")
    assert uv_select.argv[-2:] == ("--pattern", "pre_analisi_*uv*.root")
    assert vis_select.argv[-2:] == ("--pattern", "pre_analisi_*vis*.root")

    uv_generators = [s for s in stages if s.name.startswith("uv:generate:")]
    vis_generators = [s for s in stages if s.name.startswith("vis:generate:")]
    assert [s.name.removeprefix("uv:generate:") for s in uv_generators] == list(
        models.UV_CHANNELS
    )
    assert [s.name.removeprefix("vis:generate:") for s in vis_generators] == list(
        models.VIS_CHANNELS
    )
    assert len(uv_generators) == 9
    assert len(vis_generators) == 6
    assert f"({config.mc_events},1.1,1.5," in uv_generators[0].argv[-1]
    assert f"({config.mc_events},0.9313,1.1," in vis_generators[0].argv[-1]


def test_plan_trains_and_reconstructs_with_profile_local_artifacts(tmp_path):
    _config, paths, stages = _plan(tmp_path)

    for profile in ("uv", "vis"):
        root = paths.profile_root(profile)
        train = _stage(stages, f"{profile}:train")
        bdt = _stage(stages, f"{profile}:reconstruct_bdt")
        extract = _stage(stages, f"{profile}:extract")
        model_dir = paths.bdt_dir(profile) / "artifacts/stage1"
        reco = root / "reco/reco_eta_pi0_bdt.root"
        assert str(model_dir) in train.argv
        assert str(model_dir) in bdt.argv
        assert str(paths.selected_dir(profile)) in _stage(stages, f"{profile}:select").argv
        assert str(paths.mc_dir(profile)) in _stage(stages, f"{profile}:mc_status").argv
        assert str(paths.bdt_dir(profile) / "features_stage1.npz") in _stage(stages, f"{profile}:features").argv
        assert ("--profile", profile) == bdt.argv[-2:]
        assert extract.argv.count(str(reco)) == 1
        assert "--raw-bdt-fit" not in extract.argv
        assert "--by-period" in extract.argv
        assert "--no-fit" not in bdt.argv
        chi2 = _stage(stages, f"{profile}:reconstruct_chi2")
        assert "--no-fit" not in chi2.argv
        assert chi2.argv[-2:] == ("--profile", profile)
        assert str(root / "reco/reco_eta_pi0_chi2.root") in extract.argv


@pytest.mark.parametrize("mode,root", [("production", "results/_cache"), ("test_data", "results_test/test_data/artifacts")])
def test_intermediates_live_under_mode_data_root(tmp_path, mode, root):
    config = workflow_paths.mode_config(mode, tmp_path)
    paths = workflow_paths.build_paths(config)
    for profile in ("uv", "vis"):
        assert paths.selected_dir(profile) == tmp_path / root / "03_selected" / profile
        assert paths.mc_dir(profile) == tmp_path / root / "04_mc" / profile
        assert paths.bdt_dir(profile) == tmp_path / root / "05_bdt" / profile
    assert paths.combined_dir == paths.output_root / "common/plots"


def test_root_macro_argument_preserves_spaces_and_rejects_metacharacters(tmp_path):
    macro = tmp_path / "generator folder/generate_eta_pi0_dataset.C"
    output = tmp_path / "output folder/eta_pi0_mc.root"
    call = planning.root_macro_call(macro, 100, 1.1, 1.5, output)
    assert str(macro) in call
    assert f'"{output}"' in call

    with pytest.raises(models.PipelineError, match="ROOT macro path"):
        planning.root_macro_call(macro, 100, 1.1, 1.5, Path('bad"name.root'))
    with pytest.raises(models.PipelineError, match="ROOT macro path"):
        planning.root_macro_call(macro, 100, 1.1, 1.5, Path("bad\nname.root"))
    with pytest.raises(models.PipelineError, match="ROOT macro path"):
        planning.root_macro_call(macro, 100, 1.1, 1.5, Path(r"bad\name.root"))


def test_executor_stops_after_failure_and_logs_exit(tmp_path):
    config = workflow_paths.mode_config("test_data", tmp_path)
    paths = workflow_paths.build_paths(config, tmp_path / "out")
    workflow_paths.prepare_output_dirs(paths)
    stages = (
        models.Stage("one", ("tool", "one")),
        models.Stage("two", ("tool", "two")),
        models.Stage("three", ("tool", "three")),
    )
    calls = []

    def runner(argv, *, cwd, check, shell):
        calls.append((tuple(argv), cwd, check, shell))
        code = 7 if argv[-1] == "two" else 0
        return subprocess.CompletedProcess(argv, code)

    ticks = iter((10.0, 12.5, 20.0, 24.0))
    with pytest.raises(models.PipelineError, match="two.*exit 7"):
        execution.execute_plan(
            stages,
            paths,
            runner=runner,
            monotonic=lambda: next(ticks),
        )

    assert [call[0][-1] for call in calls] == ["one", "two"]
    assert all(call[1] == paths.repo_root for call in calls)
    assert all(call[2:] == (False, False) for call in calls)
    log = paths.command_log.read_text()
    assert "one" in log and "exit=0" in log and "duration=2.500s" in log
    assert "two" in log and "exit=7" in log and "duration=4.000s" in log
    assert "three" not in log


def test_prepare_output_dirs_exclusively_claims_campaign(tmp_path):
    config = workflow_paths.mode_config("test_data", tmp_path)
    paths = workflow_paths.build_paths(config, tmp_path / "out")

    workflow_paths.prepare_output_dirs(paths)

    with pytest.raises(models.PipelineError, match="already claimed"):
        workflow_paths.prepare_output_dirs(paths)
    assert paths.command_log.is_file()


def test_executor_shell_quotes_display_only(tmp_path, capsys):
    config = workflow_paths.mode_config("test_data", tmp_path)
    paths = workflow_paths.build_paths(config, tmp_path / "out")
    workflow_paths.prepare_output_dirs(paths)
    stage = models.Stage("spaced", ("tool", "path with spaces"))
    seen = []

    def runner(argv, **kwargs):
        seen.append((tuple(argv), kwargs))
        return subprocess.CompletedProcess(argv, 0)

    execution.execute_plan(
        (stage,), paths, runner=runner, monotonic=iter((0.0, 1.0)).__next__
    )

    assert seen[0][0] == ("tool", "path with spaces")
    assert "'path with spaces'" in capsys.readouterr().out


def test_parser_accepts_only_two_modes():
    parser = cli.build_parser()
    assert parser.parse_args(["--mode", "test_data"]).mode == "test_data"
    assert parser.parse_args(["--mode", "production"]).mode == "production"
    with pytest.raises(SystemExit):
        parser.parse_args(["--mode", "farm"])


def test_documented_script_entrypoint_imports_launcher_dependencies():
    script = Path(__file__).parents[1] / "scripts/run_pipeline.py"
    result = subprocess.run([sys.executable, str(script), "--help"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_run_calls_preflight_prepare_plan_and_execute_in_order(tmp_path, monkeypatch):
    events = []
    result = models.PreflightResult("root")
    monkeypatch.setattr(
        cli,
        "preflight",
        lambda config, paths: events.append(("preflight", config.name)) or result,
    )
    monkeypatch.setattr(
        cli,
        "prepare_output_dirs",
        lambda paths: events.append(("prepare", paths.output_root)),
    )
    monkeypatch.setattr(
        cli,
        "build_pipeline_plan",
        lambda config, paths, preflight_result, *, phi_bins, energy_binnings=None, best_binning=False, flux_study="off", flux_study_metadata=None: (
            events.append(("plan", preflight_result.root_executable, phi_bins))
            or (models.Stage("only", ("true",)),)
        ),
    )
    monkeypatch.setattr(
        cli,
        "execute_cached_plan",
        lambda stages, config, paths, **kwargs: events.append(("execute", stages[0].name)),
    )
    monkeypatch.setattr("builtins.input", lambda _prompt: "yes")

    code = cli.run(
        cli.build_parser().parse_args(
            ["--mode", "test_data", "--output-dir", str(tmp_path / "results_test/test_chosen"),
             "--phi-bins", "16"]
        ),
        repo_root=tmp_path,
    )

    assert code == 0
    assert events == [
        ("preflight", "test_data"),
        ("plan", "root", 16),
        ("prepare", tmp_path / "results_test/test_chosen"),
        ("execute", "only"),
    ]


def test_main_reports_pipeline_error_without_traceback(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "run",
        lambda _args: (_ for _ in ()).throw(models.PipelineError("broken")),
    )
    assert cli.main(["--mode", "test_data"]) == 1
    assert capsys.readouterr().err.strip() == "ERROR: broken"


def test_main_reports_keyboard_interrupt(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "run",
        lambda _args: (_ for _ in ()).throw(KeyboardInterrupt()),
    )
    assert cli.main(["--mode", "test_data"]) == 130
    assert capsys.readouterr().err.strip() == "ERROR: pipeline interrupted"


def test_test_campaign_replacement_is_confined_to_test_namespace(tmp_path):
    config = workflow_paths.mode_config("test_data", tmp_path)
    safe = workflow_paths.build_paths(config, tmp_path / "results_test/test_trial")
    workflow_paths.validate_test_output(safe)
    for unsafe in (tmp_path / "results/production", tmp_path / "elsewhere/test_trial"):
        with pytest.raises(models.PipelineError, match="results_test"):
            workflow_paths.validate_test_output(workflow_paths.build_paths(config, unsafe))


def test_test_campaign_rejects_symlinked_results_parent(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "results_test").symlink_to(outside, target_is_directory=True)
    paths = workflow_paths.build_paths(workflow_paths.mode_config("test_data", tmp_path))
    with pytest.raises(models.PipelineError, match="symlink"):
        workflow_paths.validate_test_output(paths)


def test_production_campaign_must_live_in_results_namespace(tmp_path):
    config = workflow_paths.mode_config("production", tmp_path)
    workflow_paths.validate_production_output(workflow_paths.build_paths(config, tmp_path / "results/october"))
    for unsafe in (tmp_path / "data/04_mc/uv", tmp_path / "results_test/test_trial"):
        with pytest.raises(models.PipelineError, match="production output"):
            workflow_paths.validate_production_output(workflow_paths.build_paths(config, unsafe))


def test_launcher_lock_refuses_competing_run(tmp_path):
    with workflow_paths.pipeline_lock(tmp_path):
        with pytest.raises(models.PipelineError, match="lock"):
            with workflow_paths.pipeline_lock(tmp_path):
                pass


def test_cached_stage_skips_valid_output_and_force_rebuilds(tmp_path):
    paths = workflow_paths.build_paths(workflow_paths.mode_config("production", tmp_path))
    workflow_paths.prepare_output_dirs(paths)
    destination = paths.selected_dir("uv")
    stage = models.Stage("uv:select", ("produce", str(destination)))
    item = execution.cache.CacheItem("selected:uv", destination.parent / "uv.manifest.json", (destination,), {"input": "v1"})
    calls = []

    def runner(argv, **_kwargs):
        calls.append(argv)
        Path(argv[-1]).mkdir(parents=True, exist_ok=True)
        (Path(argv[-1]) / "selected.root").write_bytes(b"valid")
        return subprocess.CompletedProcess(argv, 0)

    validate = lambda directory: (_ for _ in ()).throw(ValueError("missing")) if not (directory / "selected.root").is_file() else None
    execution.run_cached_stages((stage,), paths, item, destination, validate, production=True, runner=runner)
    execution.run_cached_stages((stage,), paths, item, destination, validate, production=True, runner=runner)
    assert len(calls) == 1
    execution.run_cached_stages((stage,), paths, item, destination, validate, production=True, force=True, runner=runner)
    assert len(calls) == 2
    assert "SKIP" in paths.command_log.read_text()
    assert "force" in paths.command_log.read_text()


def test_production_selection_reuses_across_campaigns_and_force_rebuilds(tmp_path):
    from dataclasses import replace
    from calibration.run_quality import DEFAULT_RUN_QUALITY_PATH
    policy = tmp_path / "config/run_quality_exclusions.json"
    policy.parent.mkdir()
    policy.write_bytes(DEFAULT_RUN_QUALITY_PATH.read_bytes())
    config = workflow_paths.mode_config("production", tmp_path)
    inputs = []
    for profile in ("uv", "vis"):
        path = config.preanalysis_dir / f"pre_analisi_{profile}.root"
        path.parent.mkdir(parents=True, exist_ok=True)
        with uproot.recreate(path) as output:
            output["h80"] = {key: np.array([1]) for key in ("gammas", "fcharged_theta", "RunNumber", "Polarization", "Xstrip")}
        inputs.append(path)
    calls = []

    def runner(argv, **_kwargs):
        calls.append(argv)
        destination = Path(argv[argv.index("--output-dir") + 1])
        destination.mkdir(parents=True, exist_ok=True)
        with uproot.recreate(destination / "analisi_uv.root") as output:
            output["h85"] = {key: np.array([1]) for key in ("gammas", "fcharged_theta", "RunNumber", "Polarization", "Xstrip")}
        return subprocess.CompletedProcess(argv, 0)

    for campaign, force in (("first", False), ("second", False), ("forced", True)):
        paths = workflow_paths.build_paths(config, tmp_path / "results" / campaign)
        workflow_paths.prepare_output_dirs(paths)
        stage = models.Stage("uv:select", ("selector", "--output-dir", str(paths.selected_dir("uv"))))
        group = models.ArtifactGroup("selected", "uv", (replace(stage, kind="select", profile="uv"),), paths.selected_dir("uv"))
        execution.execute_cached_plan((group,), config, paths, force_selected=force, runner=runner)
    assert len(calls) == 2
    assert "SKIP" in (tmp_path / "results/second/pipeline_commands.log").read_text()
    assert "RUN" in (tmp_path / "results/forced/pipeline_commands.log").read_text()


def test_failed_rebuild_preserves_last_valid_selected_directory(tmp_path):
    paths = workflow_paths.build_paths(workflow_paths.mode_config("production", tmp_path))
    workflow_paths.prepare_output_dirs(paths)
    destination = paths.selected_dir("uv")
    destination.mkdir(parents=True)
    (destination / "keep.root").write_bytes(b"old")
    stage = models.Stage("uv:select", ("broken", str(destination)))
    item = execution.cache.CacheItem("selected:uv", destination.parent / "uv.manifest.json", (destination,), {})
    execution.cache.record_cache(item, lambda: None)
    with pytest.raises(models.PipelineError, match="exit 7"):
        execution.run_cached_stages((stage,), paths, item, destination, lambda _: None,
                                       production=True, force=True,
                                       runner=lambda argv, **kwargs: subprocess.CompletedProcess(argv, 7))
    assert (destination / "keep.root").read_bytes() == b"old"
    assert execution.cache.cache_status(item, lambda: None)[0]


def test_invalid_staged_output_reports_pipeline_error_and_keeps_cache(tmp_path):
    paths = workflow_paths.build_paths(workflow_paths.mode_config("production", tmp_path))
    workflow_paths.prepare_output_dirs(paths)
    destination = paths.selected_dir("uv")
    destination.mkdir(parents=True)
    (destination / "keep.root").write_bytes(b"old")
    item = execution.cache.CacheItem("selected:uv", destination.parent / "uv.manifest.json", (destination,), {})
    execution.cache.record_cache(item, lambda: None)
    stage = models.Stage("uv:select", ("broken", str(destination)))
    with pytest.raises(models.PipelineError, match="invalid staged output"):
        execution.run_cached_stages((stage,), paths, item, destination,
                                       lambda path: (_ for _ in ()).throw(ValueError("invalid staged output"))
                                       if path != destination else None,
                                       production=True, force=True,
                                       runner=lambda argv, **kwargs: subprocess.CompletedProcess(argv, 0))
    assert (destination / "keep.root").read_bytes() == b"old"


def test_two_test_campaign_runs_replace_results_without_touching_production(tmp_path, monkeypatch):
    production = tmp_path / "results/production/keep.root"
    production.parent.mkdir(parents=True)
    production.write_bytes(b"production")
    test_root = tmp_path / "results_test/test_repeat"
    run_numbers = []
    monkeypatch.setattr(cli, "preflight", lambda config, paths: models.PreflightResult("root"))
    monkeypatch.setattr(cli, "build_pipeline_plan", lambda config, paths, checked, *, phi_bins, energy_binnings=None, best_binning=False, flux_study="off", flux_study_metadata=None: ())

    def fake_execute(stages, config, paths, **kwargs):
        run_numbers.append(len(run_numbers) + 1)
        (paths.output_root / "run.txt").write_text(str(run_numbers[-1]))

    monkeypatch.setattr(cli, "execute_cached_plan", fake_execute)
    monkeypatch.setattr("builtins.input", lambda _prompt: "s")
    args = cli.build_parser().parse_args(["--mode", "test_data", "--output-dir", str(test_root)])
    cli.run(args, repo_root=tmp_path)
    (test_root / "obsolete.txt").write_text("old")
    cli.run(args, repo_root=tmp_path)
    assert (test_root / "run.txt").read_text() == "2"
    assert not (test_root / "obsolete.txt").exists()
    assert production.read_bytes() == b"production"


@pytest.mark.parametrize("answer", ["n", "", "maybe", None])
def test_confirmation_refusal_preserves_test_results_and_skips_execution(
    tmp_path, monkeypatch, capsys, answer
):
    output = tmp_path / "results_test/test_repeat"
    output.mkdir(parents=True)
    marker = output / "keep.txt"
    marker.write_text("previous campaign")
    (output / "pipeline_commands.log").write_text("previous command log")
    monkeypatch.setattr(cli, "preflight", lambda *_: models.PreflightResult("root"))
    monkeypatch.setattr(cli, "build_pipeline_plan", lambda *_, phi_bins, energy_binnings=None, best_binning=False, flux_study="off", flux_study_metadata=None: (models.Stage("uv:select", ("selector",)),))
    monkeypatch.setattr(
        cli,
        "execute_cached_plan",
        lambda *_args, **_kwargs: pytest.fail("pipeline ran without confirmation"),
    )

    def reply(_prompt):
        if answer is None:
            raise EOFError
        return answer

    monkeypatch.setattr("builtins.input", reply)
    args = cli.build_parser().parse_args(
        ["--mode", "test_data", "--output-dir", str(output)]
    )
    assert cli.run(args, repo_root=tmp_path) == 0
    assert marker.read_text() == "previous campaign"
    assert (output / "pipeline_commands.log").read_text() == "previous command log"
    summary = capsys.readouterr().out
    assert "uv:select" in summary
    assert "results_test/test_repeat/artifacts/03_selected/uv" in summary
    assert "100000" in summary
    assert "sempre rigenerati" in summary
    assert "Sovrascrittura" in summary


def test_summary_shows_settings_and_all_planned_stages_before_prompt(
    tmp_path, monkeypatch, capsys
):
    prompts = []
    executed = []
    monkeypatch.setattr(
        cli.shutil, "get_terminal_size",
        lambda **_: os.terminal_size((240, 24)),
    )
    stale = tmp_path / "data/02_pre_analyzed/pre_analisi_2002_uv2.root"
    monkeypatch.setattr(
        cli, "preflight",
        lambda *_: models.PreflightResult("root", (stale,)),
    )

    def approve(prompt):
        prompts.append((prompt, capsys.readouterr().out))
        return "s"

    monkeypatch.setattr("builtins.input", approve)
    monkeypatch.setattr(
        cli, "execute_cached_plan",
        lambda stages, *_args, **_kwargs: executed.append(tuple(stage.name for stage in models.flatten_stages(stages))),
    )
    args = cli.build_parser().parse_args(
        ["--mode", "production", "--output-dir", str(tmp_path / "results/october"), "--force-mc"]
    )
    assert cli.run(args, repo_root=tmp_path) == 0
    summary = prompts[0][1]
    assert "production" in summary
    assert str(tmp_path) in summary
    assert "data/02_pre_analyzed" in summary
    assert "results/october" in summary
    assert "1000000" in summary or "1,000,000" in summary
    assert "10 giorni" in summary
    assert "force-mc" in summary
    assert "uv:select" in summary
    assert "vis:train" in summary
    assert "campaign:plots" in summary
    assert summary.index("Riepilogo pipeline") < summary.index("Avvisi pre-analisi")
    assert "pre_analisi_2002_uv2.root" in summary
    assert "WARNING:" not in summary
    assert len(executed) == 1
    assert all(stage in summary for stage in executed[0])
    assert "[s/N]" in prompts[0][0]


@pytest.mark.parametrize("columns", [42, 22])
def test_summary_wraps_inside_terminal_width_without_losing_long_paths(
    tmp_path, monkeypatch, capsys, columns
):
    monkeypatch.setattr(cli.shutil, "get_terminal_size", lambda **_: os.terminal_size((columns, 24)))
    monkeypatch.setattr(cli, "_use_color", lambda: False)
    config = workflow_paths.mode_config("production", tmp_path)
    paths = workflow_paths.build_paths(config)
    args = cli.build_parser().parse_args(["--mode", "production"])
    cli.print_run_summary(config, paths, args, (models.Stage("uv:generate:eta_pi0", ()),))

    output = capsys.readouterr().out
    assert all(len(line) <= columns for line in output.splitlines())
    compact = re.sub(r"[\s│╭╮╰╯─┬┴┼├┤]+", "", output)
    assert "08_observable_extraction/references/ajaka2008_figure4_digitized.csv" in compact


def test_summary_uses_color_only_when_enabled(tmp_path, monkeypatch, capsys):
    config = workflow_paths.mode_config("test_data", tmp_path)
    paths = workflow_paths.build_paths(config)
    args = cli.build_parser().parse_args(["--mode", "test_data"])
    monkeypatch.setattr(cli, "_use_color", lambda: True)
    cli.print_run_summary(config, paths, args, ())
    assert "\x1b[" in capsys.readouterr().out
    monkeypatch.setattr(cli, "_use_color", lambda: False)
    cli.print_run_summary(config, paths, args, ())
    assert "\x1b[" not in capsys.readouterr().out


def test_color_detection_respects_tty_and_no_color(monkeypatch):
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr(cli.sys.stdout, "isatty", lambda: True)
    assert cli._use_color()
    monkeypatch.setenv("NO_COLOR", "1")
    assert not cli._use_color()
    monkeypatch.delenv("NO_COLOR")
    monkeypatch.setattr(cli.sys.stdout, "isatty", lambda: False)
    assert not cli._use_color()


def test_pipeline_documentation_names_current_launcher_and_retirement():
    root = Path(__file__).parents[1]
    for relative in ("README.md", "wiki/workflow.md", "wiki/commands-and-configuration.md"):
        assert "scripts/run_pipeline.py" in (root / relative).read_text()
    workflow = (root / "wiki/workflow.md").read_text()
    assert "[Stage 09](09-theory) is retired" in workflow
    assert "theory[09:" not in workflow
    assert "results/_cache/" in workflow and "results_test/test_data" in workflow


def test_manual_extraction_example_combines_its_actual_output():
    import shlex
    from observable_extraction.beam_asymmetry import build_parser as extraction_parser
    from observable_extraction.combine_profiles import build_parser as combination_parser

    text = (Path(__file__).parents[1] / "wiki/commands-and-configuration.md").read_text()
    commands = re.findall(r"```bash\n(.*?)\n```", text, flags=re.DOTALL)
    extraction = next(c for c in commands if c.startswith("python 08_observable_extraction/beam_asymmetry.py "))
    combination = next(c for c in commands if c.startswith("python -m observable_extraction.combine_profiles "))
    extract_args = extraction_parser().parse_args(shlex.split(extraction.replace("\\\n", " "))[2:])
    combine_args = combination_parser().parse_args(shlex.split(combination.replace("\\\n", " "))[3:])
    assert combine_args.vis_root == extract_args.output_dir / "beam_asymmetry.root"
    assert str(extract_args.output_dir).startswith("results_test/")
    assert extract_args.profile == "vis" and extract_args.phi_bins == 16


def test_flux_audit_is_opt_in_and_after_calibration(tmp_path):
    config=workflow_paths.mode_config('production',tmp_path)
    paths=workflow_paths.build_paths(config)
    checked=models.PreflightResult('/usr/bin/root')
    default=planning.build_pipeline_plan(config,paths,checked)
    enabled=planning.build_pipeline_plan(config,paths,checked,flux_study='audit')
    assert not any(s.name.startswith('common:flux_') for s in models.flatten_stages(default))
    assert enabled[0]==default[0]
    assert enabled[1].name=='common:flux_audit'
    assert enabled[2:]==default[1:]
    study=planning.build_pipeline_plan(config,paths,checked,flux_study='study',flux_study_metadata=tmp_path/'metadata with spaces.json')
    assert 'flux_studies.study_missing_flux' in study[1].argv
    assert str(tmp_path/'metadata with spaces.json') in study[1].argv
    assert _stage(study,'uv:extract')==_stage(default,'uv:extract')


def test_flux_study_default_and_invalid_mode():
    parser=cli.build_parser()
    assert parser.parse_args(['--mode','production']).flux_study=='off'
    with pytest.raises(SystemExit):parser.parse_args(['--mode','production','--flux-study','automatic'])


def test_test_and_production_locks_are_distinct(tmp_path):
    with workflow_paths.pipeline_lock(tmp_path):
        with workflow_paths.pipeline_lock(tmp_path, mode='test_data'):
            with pytest.raises(models.PipelineError, match='lock'):
                with workflow_paths.pipeline_lock(tmp_path, mode='test_data'):
                    pass


def test_production_flux_study_uses_diagnostic_output(tmp_path):
    config = workflow_paths.mode_config('production', tmp_path)
    paths = workflow_paths.build_paths(config, tmp_path / 'results/october')
    stages = planning.build_pipeline_plan(config, paths, models.PreflightResult('root'), flux_study='audit')
    stage = next(s for s in models.flatten_stages(stages) if s.name == 'common:flux_audit')
    assert stage.argv[stage.argv.index('--output-dir') + 1] == str(tmp_path / 'results_test/diagnostics/october/missing_flux')
    assert stage.argv[stage.argv.index('--calibrated-flux') + 1] == str(paths.calibrated_flux)


def test_production_rejects_embedded_diagnostic_sample_without_sidecar(tmp_path):
    from dataclasses import replace
    config, paths = _valid_preflight_tree(tmp_path)
    config = replace(config, name='production')
    with uproot.update(next(paths.preanalysis_dir.glob('*uv*'))) as output:
        output['sample_provenance'] = '{"diagnostic_only": true}'
    with pytest.raises(models.PipelineError, match='diagnostic'):
        workflow_paths.preflight(config, paths, import_module=_imports, which=lambda _: 'root', manifest_validator=lambda _: ())


def test_test_output_cannot_alias_input_or_production(tmp_path):
    config = workflow_paths.mode_config('test_data', tmp_path)
    for root in ['data', 'data_test', 'results']:
        target = tmp_path / root
        target.mkdir()
        alias = tmp_path / 'results_test'
        alias.symlink_to(target, target_is_directory=True)
        with pytest.raises(models.PipelineError):
            workflow_paths.validate_test_output(workflow_paths.build_paths(config))
        alias.unlink()


def test_test_campaign_accepts_unprefixed_name(tmp_path):
    config = workflow_paths.mode_config('test_data', tmp_path)
    workflow_paths.validate_test_output(workflow_paths.build_paths(config, tmp_path / 'results_test/smoke'))


def test_artifact_directory_symlink_is_rejected(tmp_path):
    config = workflow_paths.mode_config('test_data', tmp_path)
    paths = workflow_paths.build_paths(config)
    paths.output_root.mkdir(parents=True)
    target = tmp_path / 'results/_cache'; target.mkdir(parents=True)
    paths.artifact_root.symlink_to(target, target_is_directory=True)
    with pytest.raises(models.PipelineError, match='artifact'):
        workflow_paths.validate_test_output(paths)


def test_failed_test_campaign_restores_previous_outputs_and_inputs(tmp_path, monkeypatch):
    config = workflow_paths.mode_config('test_data', tmp_path)
    paths = workflow_paths.build_paths(config)
    paths.output_root.mkdir(parents=True)
    (paths.output_root / 'valid.txt').write_text('previous result')
    paths.command_log.write_text('previous command log')
    paths.preanalysis_dir.mkdir(parents=True)
    source = paths.preanalysis_dir / 'input.root'; source.write_bytes(b'original')
    monkeypatch.setattr(cli, 'preflight', lambda *_: models.PreflightResult('root'))
    monkeypatch.setattr(cli, 'build_pipeline_plan', lambda *_, **__: ())
    monkeypatch.setattr('builtins.input', lambda _: 's')
    def fail(*_, **__): raise RuntimeError('stage failure')
    monkeypatch.setattr(cli, 'execute_cached_plan', fail)
    args = cli.build_parser().parse_args(['--mode', 'test_data'])
    with pytest.raises(RuntimeError, match='stage failure'):
        cli.run(args, repo_root=tmp_path)
    assert (paths.output_root / 'valid.txt').read_text() == 'previous result'
    assert source.read_bytes() == b'original'


def test_input_alias_into_test_output_is_rejected(tmp_path):
    config = workflow_paths.mode_config('test_data', tmp_path)
    paths = workflow_paths.build_paths(config)
    paths.output_root.mkdir(parents=True)
    paths.preanalysis_dir.parent.mkdir(parents=True)
    paths.preanalysis_dir.symlink_to(paths.output_root, target_is_directory=True)
    with pytest.raises(models.PipelineError, match='input'):
        workflow_paths.validate_test_output(paths)


@pytest.mark.parametrize('name', ['archive', 'repository-refactor-20261023', 'unrelated-study'])
def test_shared_test_namespaces_are_preserved_before_replacement(tmp_path, name):
    config = workflow_paths.mode_config('test_data', tmp_path)
    paths = workflow_paths.build_paths(config, tmp_path / 'results_test' / name)
    sentinel = paths.output_root / 'nested/frozen-proof.root'
    sentinel.parent.mkdir(parents=True)
    sentinel.write_bytes(b'irreplaceable scientific evidence')
    if name == 'archive':
        # A log inside the reserved archive cannot turn it into a campaign.
        paths.command_log.write_text('historical log')
    with pytest.raises(models.PipelineError):
        with workflow_paths._replace_test_output(paths):
            pytest.fail('protected output reached replacement')
    assert sentinel.read_bytes() == b'irreplaceable scientific evidence'
    assert not list(paths.output_root.parent.glob(f'.{name}.backup-*'))


def test_production_write_summary_names_actual_cache(tmp_path, capsys):
    config = workflow_paths.mode_config('production', tmp_path)
    paths = workflow_paths.build_paths(config)
    args = cli.build_parser().parse_args(['--mode', 'production'])
    cli.print_run_summary(config, paths, args, ())
    text = capsys.readouterr().out
    assert 'intermedi persistenti in results/_cache/' in text
    assert 'intermedi persistenti in data/' not in text


def test_preflight_rejects_changed_common_identity(tmp_path):
    config, paths = _valid_preflight_tree(tmp_path)
    paths.raw_flux.write_bytes(b'new raw flux')
    with pytest.raises(models.PipelineError, match='common input identity mismatch'):
        workflow_paths.preflight(config, paths, import_module=_imports, which=lambda _: 'root',
                                 manifest_validator=lambda _: ())


def test_configured_policy_is_exact_extraction_and_provenance_input(tmp_path):
    from dataclasses import replace
    from calibration.run_quality import DEFAULT_RUN_QUALITY_PATH
    config = workflow_paths.mode_config('production', tmp_path)
    policy = tmp_path / 'explicit-policy.json'
    policy.write_bytes(DEFAULT_RUN_QUALITY_PATH.read_bytes())
    locations = replace(workflow_paths.build_paths(config), run_quality=policy)
    stages = planning.build_pipeline_plan(config, locations, models.PreflightResult('root'))
    for stage in models.flatten_stages(stages):
        if stage.kind == 'extract':
            assert stage.argv[stage.argv.index('--run-quality') + 1] == str(policy)
    assert policy in execution._source_files(locations, '08_observable_extraction')


def test_common_cache_reference_uses_test_campaign_root_during_planning(tmp_path):
    import json
    config, original = _valid_preflight_tree(tmp_path)
    common_path = tmp_path / 'config/common_inputs.json'
    common = json.loads(common_path.read_text())
    common['inputs']['raw_flux'].update(root='cache', path='raw/flux.root')
    common_path.write_text(json.dumps(common))
    planned = workflow_paths.build_paths(config)
    assert planned.raw_flux == original.output_root / 'artifacts/raw/flux.root'
    assert not planned.raw_flux.is_relative_to(tmp_path / 'results')


@pytest.mark.parametrize('kind', ['file', 'directory'])
def test_linked_external_inputs_reach_preflight_plan_and_summary(tmp_path, monkeypatch, kind):
    from dataclasses import replace
    config, original = _valid_preflight_tree(tmp_path / 'checkout')
    farm = tmp_path / 'farm'; farm.mkdir()
    raw = farm / 'flux.root'
    original.raw_flux.rename(raw)
    if kind == 'file':
        original.raw_flux.symlink_to(raw)
    else:
        original.raw_flux.parent.rmdir()
        original.raw_flux.parent.symlink_to(farm, target_is_directory=True)
    source = farm / 'preanalysis'
    original.preanalysis_dir.rename(source)
    original.preanalysis_dir.symlink_to(source, target_is_directory=True)
    config = replace(config, preanalysis_dir=source)
    locations = workflow_paths.build_paths(config)
    checked = workflow_paths.preflight(config, locations, import_module=_imports,
                                       which=lambda _: '/usr/bin/root')
    assert locations.raw_flux == raw
    stages = planning.build_pipeline_plan(config, locations, checked)
    calibration = models.flatten_stages(stages)[0]
    assert str(raw) in calibration.argv and str(source) in calibration.argv
    displayed = []
    monkeypatch.setattr(cli, '_print_table', lambda title, rows: displayed.extend(rows))
    args = cli.build_parser().parse_args(['--mode', 'test_data'])
    cli.print_run_summary(config, locations, args, stages)
    assert ('Flux input', str(raw)) in displayed
    assert ('Input h80', str(source)) in displayed
    workflow_paths.validate_test_output(locations)
    with pytest.raises(models.PipelineError, match='overlap input through aliases'):
        workflow_paths.validate_test_output(replace(locations, output_root=farm))
    with pytest.raises(models.PipelineError, match='without symlinks'):
        workflow_paths.validate_test_output(replace(locations, output_root=tmp_path / 'external-output'))
