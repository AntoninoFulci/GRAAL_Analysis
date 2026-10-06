from pathlib import Path
import re
import subprocess

import pytest

from scripts import run_pipeline


def test_mode_config_uses_exact_test_and_production_inputs(tmp_path):
    test = run_pipeline.mode_config("test_data", tmp_path)
    production = run_pipeline.mode_config("production", tmp_path)

    assert test.preanalysis_dir == tmp_path / "test_data/pre_analyzed"
    assert test.default_output == tmp_path / "results/test_data"
    assert test.mc_events == 100_000
    assert production.preanalysis_dir == (
        tmp_path / "data/02_pre_analyzed/pre_analisi"
    )
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
    _touch(paths.preanalysis_dir / "pre_analisi_1998_uv.root")
    _touch(paths.preanalysis_dir / "pre_analisi_1999_vis.root")
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
    (paths.preanalysis_dir / "pre_analisi_1999_vis.root").unlink()

    with pytest.raises(run_pipeline.PipelineError, match="VIS.*pre-analysis"):
        run_pipeline.preflight(
            config,
            paths,
            import_module=_imports,
            which=lambda _name: "/usr/bin/root",
            manifest_validator=lambda _path: (),
        )


def test_preflight_rejects_nonempty_output_without_removing_it(tmp_path):
    config, paths = _valid_preflight_tree(tmp_path)
    sentinel = paths.output_root / "keep.txt"
    _touch(sentinel)

    with pytest.raises(run_pipeline.PipelineError, match="not empty"):
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


def test_plan_calibrates_once_then_runs_uv_vis_and_combines(tmp_path):
    _config, paths, stages = _plan(tmp_path)

    assert len(stages) == 33
    assert stages[0].name == "common:calibrate_flux"
    assert stages[-1].name == "combined:plots"
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
        model_dir = root / "bdt/artifacts/stage1"
        reco = root / "reco/reco_eta_pi0_bdt.root"
        assert str(model_dir) in train.argv
        assert str(model_dir) in bdt.argv
        assert ("--profile", profile) == bdt.argv[-2:]
        assert extract.argv.count(str(reco)) == 2
        assert str(root / "reco/reco_eta_pi0_chi2.root") in extract.argv


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
        lambda config, paths, preflight_result: (
            events.append(("plan", preflight_result.root_executable))
            or (run_pipeline.Stage("only", ("true",)),)
        ),
    )
    monkeypatch.setattr(
        run_pipeline,
        "execute_plan",
        lambda stages, paths: events.append(("execute", stages[0].name)),
    )

    code = run_pipeline.run(
        run_pipeline.build_parser().parse_args(
            ["--mode", "test_data", "--output-dir", str(tmp_path / "chosen")]
        ),
        repo_root=tmp_path,
    )

    assert code == 0
    assert events == [
        ("preflight", "test_data"),
        ("prepare", tmp_path / "chosen"),
        ("plan", "root"),
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
