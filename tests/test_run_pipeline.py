from pathlib import Path

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
