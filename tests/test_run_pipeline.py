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
