from pathlib import Path
import os
import re
import subprocess
import numpy as np
import uproot

import pytest

from scripts import run_pipeline


def test_mode_config_uses_exact_test_and_production_inputs(tmp_path):
    test = run_pipeline.mode_config("test_data", tmp_path)
    production = run_pipeline.mode_config("production", tmp_path)

    assert test.preanalysis_dir == tmp_path / "test_data/02_pre_analyzed"
    assert test.default_output == tmp_path / "results/test_data"
    assert test.mc_events == 100_000
    assert production.preanalysis_dir == tmp_path / "data/02_pre_analyzed"
    assert production.default_output == tmp_path / "results/production"
    assert production.mc_events == 1_000_000


def test_unknown_mode_is_rejected(tmp_path):
    with pytest.raises(run_pipeline.PipelineError, match="unknown mode"):
        run_pipeline.mode_config("farm", tmp_path)


def test_output_override_replaces_only_output_root(tmp_path):
    config = run_pipeline.mode_config("production", tmp_path)
    paths = run_pipeline.build_paths(config, tmp_path / "campaign 01")

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
    config = run_pipeline.mode_config("test_data", tmp_path)
    paths = run_pipeline.build_paths(config)
    for path in run_pipeline.required_repository_files(paths):
        _touch(path)
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
    with pytest.raises(run_pipeline.PipelineError, match="Python 3.10"):
        run_pipeline.preflight(
            config,
            paths,
            import_module=_imports,
            which=lambda _name: "/usr/bin/root",
            manifest_validator=lambda _path: (),
            python_version=(3, 9),
        )


def test_preflight_rejects_missing_root_executable(tmp_path):
    config, paths = _valid_preflight_tree(tmp_path)
    with pytest.raises(run_pipeline.PipelineError, match="root executable"):
        run_pipeline.preflight(
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

    with pytest.raises(run_pipeline.PipelineError, match="cannot import ROOT"):
        run_pipeline.preflight(
            config,
            paths,
            import_module=fail_root,
            which=lambda _name: "/usr/bin/root",
            manifest_validator=lambda _path: (),
        )


def test_preflight_rejects_missing_vis_input(tmp_path):
    config, paths = _valid_preflight_tree(tmp_path)
    (paths.preanalysis_dir / "pre_analisi_1998_vis.root").unlink()

    with pytest.raises(run_pipeline.PipelineError, match="VIS.*pre-analysis"):
        run_pipeline.preflight(
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

    run_pipeline.preflight(
        config,
        paths,
        import_module=_imports,
        which=lambda _name: "/usr/bin/root",
        manifest_validator=lambda _path: (),
    )
    assert sentinel.is_file()


def test_preflight_accepts_complete_minimal_inputs(tmp_path):
    config, paths = _valid_preflight_tree(tmp_path)
    result = run_pipeline.preflight(
        config,
        paths,
        import_module=_imports,
        which=lambda _name: "/opt/root/bin/root",
        manifest_validator=lambda _path: (),
    )
    assert result == run_pipeline.PreflightResult("/opt/root/bin/root")
    assert not paths.output_root.exists()


def test_preflight_rejects_invalid_h80_and_warns_only_for_old_input(tmp_path, capsys):
    config, paths = _valid_preflight_tree(tmp_path)
    uv = next(paths.preanalysis_dir.glob("*uv.root"))
    with uproot.recreate(uv) as output:
        output["h80"] = {"RunNumber": np.array([1])}
    with pytest.raises(run_pipeline.PipelineError, match="missing branches"):
        run_pipeline.preflight(config, paths, import_module=_imports, which=lambda _: "root", manifest_validator=lambda _: ())
    with uproot.recreate(uv) as output:
        output["h80"] = {key: np.array([1]) for key in ("gammas", "fcharged_theta", "RunNumber", "Polarization", "Xstrip")}
    old = uv.stat().st_mtime - 11 * 86400
    import os
    os.utime(uv, (old, old))
    run_pipeline.preflight(config, paths, import_module=_imports, which=lambda _: "root", manifest_validator=lambda _: ())
    assert "10 days" not in capsys.readouterr().out  # disposable test data has no age warning


def test_production_preflight_collects_old_h80_for_separate_warning_table(tmp_path, capsys):
    _, test_paths = _valid_preflight_tree(tmp_path)
    config = run_pipeline.mode_config("production", tmp_path)
    paths = run_pipeline.build_paths(config)
    paths.preanalysis_dir.mkdir(parents=True)
    for profile in ("uv", "vis"):
        source = test_paths.preanalysis_dir / f"pre_analisi_1998_{profile}.root"
        (paths.preanalysis_dir / source.name).write_bytes(source.read_bytes())
    old_uv = paths.preanalysis_dir / "pre_analisi_1998_uv.root"
    old_time = old_uv.stat().st_mtime - 11 * 86400
    os.utime(old_uv, (old_time, old_time))

    checked = run_pipeline.preflight(
        config, paths, import_module=_imports, which=lambda _: "root",
        manifest_validator=lambda _: (),
    )

    assert checked.old_preanalysis_inputs == (old_uv,)
    assert capsys.readouterr().out == ""
    run_pipeline.print_preflight_warnings(checked)
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
    config = run_pipeline.mode_config(mode, tmp_path)
    paths = run_pipeline.build_paths(config, tmp_path / "out with spaces")
    result = run_pipeline.PreflightResult("/opt/root/bin/root")
    stages = run_pipeline.build_pipeline_plan(
        config, paths, result, python_executable="/venv/bin/python"
    )
    return config, paths, stages


def _stage(stages, name: str):
    return next(item for item in stages if item.name == name)


@pytest.mark.parametrize("mode", ["production", "test_data"])
@pytest.mark.parametrize("phi_bins", [8, 12, 16])
def test_launch_phi_binning_reaches_both_extractions_only(tmp_path, mode, phi_bins):
    args = run_pipeline.build_parser().parse_args(
        ["--mode", mode, "--phi-bins", str(phi_bins)]
    )
    config = run_pipeline.mode_config(mode, tmp_path)
    paths = run_pipeline.build_paths(config)
    checked = run_pipeline.PreflightResult("/usr/bin/root")
    stages = run_pipeline.build_pipeline_plan(config, paths, checked, phi_bins=args.phi_bins)
    default_stages = run_pipeline.build_pipeline_plan(config, paths, checked)
    assert len(stages) == len(default_stages)
    for stage, default in zip(stages, default_stages):
        if stage.name.endswith(":extract"):
            assert stage.argv[stage.argv.index("--phi-bins") + 1] == str(phi_bins)
            assert default.argv[default.argv.index("--phi-bins") + 1] == "12"
        else:
            assert stage == default


def test_launch_phi_bins_default_and_invalid_choice():
    assert run_pipeline.build_parser().parse_args(["--mode", "production"]).phi_bins == 12
    with pytest.raises(SystemExit):
        run_pipeline.build_parser().parse_args(["--mode", "production", "--phi-bins", "10"])


def test_plan_calibrates_once_then_runs_uv_vis_and_combines(tmp_path):
    _config, paths, stages = _plan(tmp_path)

    assert len(stages) == 33
    assert stages[0].name == "common:calibrate_flux"
    assert stages[-1].name == "campaign:plots"
    assert sum(stage.name == "common:calibrate_flux" for stage in stages) == 1
    assert sum(stage.name.endswith(":extract") for stage in stages) == 2
    calibration = stages[0].argv
    assert "--output" not in calibration
    assert calibration[-2:] == ("--output-dir", str(paths.output_root / "common"))
    assert calibration[calibration.index("--target") + 1] == "P"
    assert _stage(stages, "uv:extract").argv[-2:] == (
        "--bootstrap-replicas",
        "0",
    )
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
        run_pipeline.UV_CHANNELS
    )
    assert [s.name.removeprefix("vis:generate:") for s in vis_generators] == list(
        run_pipeline.VIS_CHANNELS
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
        assert extract.argv.count(str(reco)) == 2
        assert str(root / "reco/reco_eta_pi0_chi2.root") in extract.argv


@pytest.mark.parametrize("mode,root", [("production", "data"), ("test_data", "test_data")])
def test_intermediates_live_under_mode_data_root(tmp_path, mode, root):
    config = run_pipeline.mode_config(mode, tmp_path)
    paths = run_pipeline.build_paths(config)
    for profile in ("uv", "vis"):
        assert paths.selected_dir(profile) == tmp_path / root / "03_selected" / profile
        assert paths.mc_dir(profile) == tmp_path / root / "04_mc" / profile
        assert paths.bdt_dir(profile) == tmp_path / root / "05_bdt" / profile
    assert paths.combined_dir == paths.output_root / "common/plots"


def test_root_macro_argument_preserves_spaces_and_rejects_metacharacters(tmp_path):
    macro = tmp_path / "generator folder/generate_eta_pi0_dataset.C"
    output = tmp_path / "output folder/eta_pi0_mc.root"
    call = run_pipeline.root_macro_call(macro, 100, 1.1, 1.5, output)
    assert str(macro) in call
    assert f'"{output}"' in call

    with pytest.raises(run_pipeline.PipelineError, match="ROOT macro path"):
        run_pipeline.root_macro_call(macro, 100, 1.1, 1.5, Path('bad"name.root'))
    with pytest.raises(run_pipeline.PipelineError, match="ROOT macro path"):
        run_pipeline.root_macro_call(macro, 100, 1.1, 1.5, Path("bad\nname.root"))
    with pytest.raises(run_pipeline.PipelineError, match="ROOT macro path"):
        run_pipeline.root_macro_call(macro, 100, 1.1, 1.5, Path(r"bad\name.root"))


def test_executor_stops_after_failure_and_logs_exit(tmp_path):
    config = run_pipeline.mode_config("test_data", tmp_path)
    paths = run_pipeline.build_paths(config, tmp_path / "out")
    run_pipeline.prepare_output_dirs(paths)
    stages = (
        run_pipeline.Stage("one", ("tool", "one")),
        run_pipeline.Stage("two", ("tool", "two")),
        run_pipeline.Stage("three", ("tool", "three")),
    )
    calls = []

    def runner(argv, *, cwd, check, shell):
        calls.append((tuple(argv), cwd, check, shell))
        code = 7 if argv[-1] == "two" else 0
        return subprocess.CompletedProcess(argv, code)

    ticks = iter((10.0, 12.5, 20.0, 24.0))
    with pytest.raises(run_pipeline.PipelineError, match="two.*exit 7"):
        run_pipeline.execute_plan(
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
    config = run_pipeline.mode_config("test_data", tmp_path)
    paths = run_pipeline.build_paths(config, tmp_path / "out")

    run_pipeline.prepare_output_dirs(paths)

    with pytest.raises(run_pipeline.PipelineError, match="already claimed"):
        run_pipeline.prepare_output_dirs(paths)
    assert paths.command_log.is_file()


def test_executor_shell_quotes_display_only(tmp_path, capsys):
    config = run_pipeline.mode_config("test_data", tmp_path)
    paths = run_pipeline.build_paths(config, tmp_path / "out")
    run_pipeline.prepare_output_dirs(paths)
    stage = run_pipeline.Stage("spaced", ("tool", "path with spaces"))
    seen = []

    def runner(argv, **kwargs):
        seen.append((tuple(argv), kwargs))
        return subprocess.CompletedProcess(argv, 0)

    run_pipeline.execute_plan(
        (stage,), paths, runner=runner, monotonic=iter((0.0, 1.0)).__next__
    )

    assert seen[0][0] == ("tool", "path with spaces")
    assert "'path with spaces'" in capsys.readouterr().out


def test_parser_accepts_only_two_modes():
    parser = run_pipeline.build_parser()
    assert parser.parse_args(["--mode", "test_data"]).mode == "test_data"
    assert parser.parse_args(["--mode", "production"]).mode == "production"
    with pytest.raises(SystemExit):
        parser.parse_args(["--mode", "farm"])


def test_documented_script_entrypoint_imports_launcher_dependencies():
    script = Path(__file__).parents[1] / "scripts/run_pipeline.py"
    result = subprocess.run(["python", str(script), "--help"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_run_calls_preflight_prepare_plan_and_execute_in_order(tmp_path, monkeypatch):
    events = []
    result = run_pipeline.PreflightResult("root")
    monkeypatch.setattr(
        run_pipeline,
        "preflight",
        lambda config, paths: events.append(("preflight", config.name)) or result,
    )
    monkeypatch.setattr(
        run_pipeline,
        "prepare_output_dirs",
        lambda paths: events.append(("prepare", paths.output_root)),
    )
    monkeypatch.setattr(
        run_pipeline,
        "build_pipeline_plan",
        lambda config, paths, preflight_result, *, phi_bins: (
            events.append(("plan", preflight_result.root_executable, phi_bins))
            or (run_pipeline.Stage("only", ("true",)),)
        ),
    )
    monkeypatch.setattr(
        run_pipeline,
        "execute_cached_plan",
        lambda stages, config, paths, **kwargs: events.append(("execute", stages[0].name)),
    )
    monkeypatch.setattr("builtins.input", lambda _prompt: "yes")

    code = run_pipeline.run(
        run_pipeline.build_parser().parse_args(
            ["--mode", "test_data", "--output-dir", str(tmp_path / "results/test_chosen"),
             "--phi-bins", "16"]
        ),
        repo_root=tmp_path,
    )

    assert code == 0
    assert events == [
        ("preflight", "test_data"),
        ("plan", "root", 16),
        ("prepare", tmp_path / "results/test_chosen"),
        ("execute", "only"),
    ]


def test_main_reports_pipeline_error_without_traceback(monkeypatch, capsys):
    monkeypatch.setattr(
        run_pipeline,
        "run",
        lambda _args: (_ for _ in ()).throw(run_pipeline.PipelineError("broken")),
    )
    assert run_pipeline.main(["--mode", "test_data"]) == 1
    assert capsys.readouterr().err.strip() == "ERROR: broken"


def test_main_reports_keyboard_interrupt(monkeypatch, capsys):
    monkeypatch.setattr(
        run_pipeline,
        "run",
        lambda _args: (_ for _ in ()).throw(KeyboardInterrupt()),
    )
    assert run_pipeline.main(["--mode", "test_data"]) == 130
    assert capsys.readouterr().err.strip() == "ERROR: pipeline interrupted"


def test_test_campaign_replacement_is_confined_to_test_namespace(tmp_path):
    config = run_pipeline.mode_config("test_data", tmp_path)
    safe = run_pipeline.build_paths(config, tmp_path / "results/test_trial")
    run_pipeline.validate_test_output(safe)
    for unsafe in (tmp_path / "results/production", tmp_path / "elsewhere/test_trial"):
        with pytest.raises(run_pipeline.PipelineError, match="test_"):
            run_pipeline.validate_test_output(run_pipeline.build_paths(config, unsafe))


def test_test_campaign_rejects_symlinked_results_parent(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "results").symlink_to(outside, target_is_directory=True)
    paths = run_pipeline.build_paths(run_pipeline.mode_config("test_data", tmp_path))
    with pytest.raises(run_pipeline.PipelineError, match="symlink"):
        run_pipeline.validate_test_output(paths)


def test_production_campaign_must_live_in_results_namespace(tmp_path):
    config = run_pipeline.mode_config("production", tmp_path)
    run_pipeline.validate_production_output(run_pipeline.build_paths(config, tmp_path / "results/october"))
    for unsafe in (tmp_path / "data/04_mc/uv", tmp_path / "results/test_trial"):
        with pytest.raises(run_pipeline.PipelineError, match="production output"):
            run_pipeline.validate_production_output(run_pipeline.build_paths(config, unsafe))


def test_launcher_lock_refuses_competing_run(tmp_path):
    with run_pipeline.pipeline_lock(tmp_path):
        with pytest.raises(run_pipeline.PipelineError, match="lock"):
            with run_pipeline.pipeline_lock(tmp_path):
                pass


def test_cached_stage_skips_valid_output_and_force_rebuilds(tmp_path):
    paths = run_pipeline.build_paths(run_pipeline.mode_config("production", tmp_path))
    run_pipeline.prepare_output_dirs(paths)
    destination = paths.selected_dir("uv")
    stage = run_pipeline.Stage("uv:select", ("produce", str(destination)))
    item = run_pipeline.cache.CacheItem("selected:uv", destination.parent / "uv.manifest.json", (destination,), {"input": "v1"})
    calls = []

    def runner(argv, **_kwargs):
        calls.append(argv)
        Path(argv[-1]).mkdir(parents=True, exist_ok=True)
        (Path(argv[-1]) / "selected.root").write_bytes(b"valid")
        return subprocess.CompletedProcess(argv, 0)

    validate = lambda directory: (_ for _ in ()).throw(ValueError("missing")) if not (directory / "selected.root").is_file() else None
    run_pipeline.run_cached_stages((stage,), paths, item, destination, validate, production=True, runner=runner)
    run_pipeline.run_cached_stages((stage,), paths, item, destination, validate, production=True, runner=runner)
    assert len(calls) == 1
    run_pipeline.run_cached_stages((stage,), paths, item, destination, validate, production=True, force=True, runner=runner)
    assert len(calls) == 2
    assert "SKIP" in paths.command_log.read_text()
    assert "force" in paths.command_log.read_text()


def test_production_selection_reuses_across_campaigns_and_force_rebuilds(tmp_path):
    config = run_pipeline.mode_config("production", tmp_path)
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
        paths = run_pipeline.build_paths(config, tmp_path / "results" / campaign)
        run_pipeline.prepare_output_dirs(paths)
        stage = run_pipeline.Stage("uv:select", ("selector", "--output-dir", str(paths.selected_dir("uv"))))
        run_pipeline.execute_cached_plan((stage,), config, paths, force_selected=force, runner=runner)
    assert len(calls) == 2
    assert "SKIP" in (tmp_path / "results/second/pipeline_commands.log").read_text()
    assert "RUN" in (tmp_path / "results/forced/pipeline_commands.log").read_text()


def test_failed_rebuild_preserves_last_valid_selected_directory(tmp_path):
    paths = run_pipeline.build_paths(run_pipeline.mode_config("production", tmp_path))
    run_pipeline.prepare_output_dirs(paths)
    destination = paths.selected_dir("uv")
    destination.mkdir(parents=True)
    (destination / "keep.root").write_bytes(b"old")
    stage = run_pipeline.Stage("uv:select", ("broken", str(destination)))
    item = run_pipeline.cache.CacheItem("selected:uv", destination.parent / "uv.manifest.json", (destination,), {})
    run_pipeline.cache.record_cache(item, lambda: None)
    with pytest.raises(run_pipeline.PipelineError, match="exit 7"):
        run_pipeline.run_cached_stages((stage,), paths, item, destination, lambda _: None,
                                       production=True, force=True,
                                       runner=lambda argv, **kwargs: subprocess.CompletedProcess(argv, 7))
    assert (destination / "keep.root").read_bytes() == b"old"
    assert run_pipeline.cache.cache_status(item, lambda: None)[0]


def test_invalid_staged_output_reports_pipeline_error_and_keeps_cache(tmp_path):
    paths = run_pipeline.build_paths(run_pipeline.mode_config("production", tmp_path))
    run_pipeline.prepare_output_dirs(paths)
    destination = paths.selected_dir("uv")
    destination.mkdir(parents=True)
    (destination / "keep.root").write_bytes(b"old")
    item = run_pipeline.cache.CacheItem("selected:uv", destination.parent / "uv.manifest.json", (destination,), {})
    run_pipeline.cache.record_cache(item, lambda: None)
    stage = run_pipeline.Stage("uv:select", ("broken", str(destination)))
    with pytest.raises(run_pipeline.PipelineError, match="invalid staged output"):
        run_pipeline.run_cached_stages((stage,), paths, item, destination,
                                       lambda path: (_ for _ in ()).throw(ValueError("invalid staged output"))
                                       if path != destination else None,
                                       production=True, force=True,
                                       runner=lambda argv, **kwargs: subprocess.CompletedProcess(argv, 0))
    assert (destination / "keep.root").read_bytes() == b"old"


def test_two_test_campaign_runs_replace_results_without_touching_production(tmp_path, monkeypatch):
    production = tmp_path / "results/production/keep.root"
    production.parent.mkdir(parents=True)
    production.write_bytes(b"production")
    test_root = tmp_path / "results/test_repeat"
    run_numbers = []
    monkeypatch.setattr(run_pipeline, "preflight", lambda config, paths: run_pipeline.PreflightResult("root"))
    monkeypatch.setattr(run_pipeline, "build_pipeline_plan", lambda config, paths, checked, *, phi_bins: ())

    def fake_execute(stages, config, paths, **kwargs):
        run_numbers.append(len(run_numbers) + 1)
        (paths.output_root / "run.txt").write_text(str(run_numbers[-1]))

    monkeypatch.setattr(run_pipeline, "execute_cached_plan", fake_execute)
    monkeypatch.setattr("builtins.input", lambda _prompt: "s")
    args = run_pipeline.build_parser().parse_args(["--mode", "test_data", "--output-dir", str(test_root)])
    run_pipeline.run(args, repo_root=tmp_path)
    (test_root / "obsolete.txt").write_text("old")
    run_pipeline.run(args, repo_root=tmp_path)
    assert (test_root / "run.txt").read_text() == "2"
    assert not (test_root / "obsolete.txt").exists()
    assert production.read_bytes() == b"production"


@pytest.mark.parametrize("answer", ["n", "", "maybe", None])
def test_confirmation_refusal_preserves_test_results_and_skips_execution(
    tmp_path, monkeypatch, capsys, answer
):
    output = tmp_path / "results/test_repeat"
    output.mkdir(parents=True)
    marker = output / "keep.txt"
    marker.write_text("previous campaign")
    monkeypatch.setattr(run_pipeline, "preflight", lambda *_: run_pipeline.PreflightResult("root"))
    monkeypatch.setattr(run_pipeline, "build_pipeline_plan", lambda *_, phi_bins: (run_pipeline.Stage("uv:select", ("selector",)),))
    monkeypatch.setattr(
        run_pipeline,
        "execute_cached_plan",
        lambda *_args, **_kwargs: pytest.fail("pipeline ran without confirmation"),
    )

    def reply(_prompt):
        if answer is None:
            raise EOFError
        return answer

    monkeypatch.setattr("builtins.input", reply)
    args = run_pipeline.build_parser().parse_args(
        ["--mode", "test_data", "--output-dir", str(output)]
    )
    assert run_pipeline.run(args, repo_root=tmp_path) == 0
    assert marker.read_text() == "previous campaign"
    assert not (output / "pipeline_commands.log").exists()
    summary = capsys.readouterr().out
    assert "uv:select" in summary
    assert "test_data/03_selected/uv" in summary
    assert "100000" in summary
    assert "sempre rigenerati" in summary
    assert "Sovrascrittura" in summary


def test_summary_shows_settings_and_all_planned_stages_before_prompt(
    tmp_path, monkeypatch, capsys
):
    prompts = []
    executed = []
    monkeypatch.setattr(
        run_pipeline.shutil, "get_terminal_size",
        lambda **_: os.terminal_size((240, 24)),
    )
    stale = tmp_path / "data/02_pre_analyzed/pre_analisi_2002_uv2.root"
    monkeypatch.setattr(
        run_pipeline, "preflight",
        lambda *_: run_pipeline.PreflightResult("root", (stale,)),
    )

    def approve(prompt):
        prompts.append((prompt, capsys.readouterr().out))
        return "s"

    monkeypatch.setattr("builtins.input", approve)
    monkeypatch.setattr(
        run_pipeline, "execute_cached_plan",
        lambda stages, *_args, **_kwargs: executed.append(tuple(stage.name for stage in stages)),
    )
    args = run_pipeline.build_parser().parse_args(
        ["--mode", "production", "--output-dir", str(tmp_path / "results/october"), "--force-mc"]
    )
    assert run_pipeline.run(args, repo_root=tmp_path) == 0
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
    monkeypatch.setattr(run_pipeline.shutil, "get_terminal_size", lambda **_: os.terminal_size((columns, 24)))
    monkeypatch.setattr(run_pipeline, "_use_color", lambda: False)
    config = run_pipeline.mode_config("production", tmp_path)
    paths = run_pipeline.build_paths(config)
    args = run_pipeline.build_parser().parse_args(["--mode", "production"])
    run_pipeline.print_run_summary(config, paths, args, (run_pipeline.Stage("uv:generate:eta_pi0", ()),))

    output = capsys.readouterr().out
    assert all(len(line) <= columns for line in output.splitlines())
    compact = re.sub(r"[\s│╭╮╰╯─┬┴┼├┤]+", "", output)
    assert "07_observable_extraction/references/ajaka2008_figure4_digitized.csv" in compact


def test_summary_uses_color_only_when_enabled(tmp_path, monkeypatch, capsys):
    config = run_pipeline.mode_config("test_data", tmp_path)
    paths = run_pipeline.build_paths(config)
    args = run_pipeline.build_parser().parse_args(["--mode", "test_data"])
    monkeypatch.setattr(run_pipeline, "_use_color", lambda: True)
    run_pipeline.print_run_summary(config, paths, args, ())
    assert "\x1b[" in capsys.readouterr().out
    monkeypatch.setattr(run_pipeline, "_use_color", lambda: False)
    run_pipeline.print_run_summary(config, paths, args, ())
    assert "\x1b[" not in capsys.readouterr().out


def test_color_detection_respects_tty_and_no_color(monkeypatch):
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr(run_pipeline.sys.stdout, "isatty", lambda: True)
    assert run_pipeline._use_color()
    monkeypatch.setenv("NO_COLOR", "1")
    assert not run_pipeline._use_color()
    monkeypatch.delenv("NO_COLOR")
    monkeypatch.setattr(run_pipeline.sys.stdout, "isatty", lambda: False)
    assert not run_pipeline._use_color()


def test_pipeline_documentation_names_current_launcher_and_handoff():
    root = Path(__file__).parents[1]
    required = (
        root / "README.md",
        root / "docs/runbooks/full-pipeline.md",
        root / "wiki/workflow.md",
        root / "wiki/commands-and-configuration.md",
        root / "wiki/data-and-artifacts.md",
        root / "wiki/known-limitations.md",
        root / "wiki/07-observable-extraction.md",
    )
    for path in required:
        text = path.read_text(encoding="utf-8")
        assert "scripts/run_pipeline.py" in text, path
    corpus = "\n".join(path.read_text(encoding="utf-8") for path in required)
    assert "adapter pending" not in corpus.lower()
    assert "still expects a legacy exposure CSV" not in corpus
    assert "run_pipeline.sh" not in corpus


def test_vis_runbook_combines_its_stage7_output():
    text = (
        Path(__file__).parents[1] / "docs/runbooks/vis-local-analysis.md"
    ).read_text(encoding="utf-8")
    extraction = re.search(
        r"python 07_observable_extraction/beam_asymmetry\.py \\\n(.*?)\n```",
        text,
        flags=re.DOTALL,
    )
    combination = re.search(
        r"python -m observable_extraction\.combine_profiles \\\n(.*?)\n```",
        text,
        flags=re.DOTALL,
    )
    assert extraction is not None
    assert combination is not None
    output_dir = re.search(r"--output-dir\s+(\S+)", extraction.group(1))
    vis_root = re.search(r"--vis-root\s+(\S+)", combination.group(1))
    assert output_dir is not None
    assert vis_root is not None
    assert Path(vis_root.group(1)) == Path(output_dir.group(1)) / "beam_asymmetry.root"
