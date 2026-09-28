from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest


def _write_config(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    return path


def test_default_config_uses_numbered_repository_layout(monkeypatch, tmp_path):
    from graal_pipeline.config import load_config, repository_root

    monkeypatch.chdir(tmp_path)
    config = load_config()
    root = repository_root()

    assert config.paths.raw_dir == root / "data/01_raw/graal_data"
    assert config.paths.preanalysis_dir == root / "data/02_pre_analyzed/pre_analisi"
    assert config.paths.selected_dir == root / "data/03_selected"
    assert config.paths.external_flux == root / "data/00_external/flux.root"
    assert config.paths.run_manifest == root / "config/run_manifest.csv"
    assert config.paths.results_dir == root / "results"
    assert config.checkpoint.max_age_days == 30
    assert config.checkpoint.verification == "fast"


def test_config_is_immutable():
    from graal_pipeline.config import load_config

    config = load_config()

    with pytest.raises(FrozenInstanceError):
        config.profile = "farm"  # type: ignore[misc]


def test_cli_overrides_profile_which_overrides_toml(tmp_path):
    from graal_pipeline.config import load_config

    root = tmp_path / "repo"
    root.mkdir()
    config_path = _write_config(
        root / "pipeline.toml",
        """
[paths]
selected_dir = "from-toml"
results_dir = "results"

[checkpoint]
verification = "fast"

[profiles.smoke.paths]
selected_dir = "from-profile"

[profiles.smoke.checkpoint]
verification = "full"
""",
    )

    config = load_config(
        config_path,
        profile="smoke",
        cli_overrides={"paths.selected_dir": "from-cli"},
        repo_root=root,
    )

    assert config.paths.selected_dir == root / "from-cli"
    assert config.paths.results_dir == root / "results"
    assert config.checkpoint.verification == "full"
    assert config.profile == "smoke"


def test_relative_path_cannot_escape_repository(tmp_path):
    from graal_pipeline.config import ConfigError, load_config

    root = tmp_path / "repo"
    root.mkdir()
    config_path = _write_config(
        root / "pipeline.toml",
        '[paths]\nresults_dir = "../outside"\n',
    )

    with pytest.raises(ConfigError, match="escapes repository root"):
        load_config(config_path, repo_root=root)


def test_symlinked_relative_path_cannot_escape_repository(tmp_path):
    from graal_pipeline.config import ConfigError, load_config

    root = tmp_path / "repo"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "linked").symlink_to(outside, target_is_directory=True)
    config_path = _write_config(
        root / "pipeline.toml",
        '[paths]\nresults_dir = "linked/results"\n',
    )

    with pytest.raises(ConfigError, match="escapes repository root"):
        load_config(config_path, repo_root=root)


def test_declared_farm_input_symlinks_may_target_external_storage(tmp_path):
    from graal_pipeline.config import load_config

    root = tmp_path / "repo"
    farm = tmp_path / "farm"
    raw_target = farm / "graal_data"
    preanalysis_target = farm / "pre_analisi"
    flux_target = farm / "flux.root"
    raw_target.mkdir(parents=True)
    preanalysis_target.mkdir(parents=True)
    flux_target.write_bytes(b"flux")
    raw_link = root / "data/01_raw/graal_data"
    preanalysis_link = root / "data/02_pre_analyzed/pre_analisi"
    flux_link = root / "data/00_external/flux.root"
    for link in (raw_link, preanalysis_link, flux_link):
        link.parent.mkdir(parents=True, exist_ok=True)
    raw_link.symlink_to(raw_target, target_is_directory=True)
    preanalysis_link.symlink_to(preanalysis_target, target_is_directory=True)
    flux_link.symlink_to(flux_target)
    config_path = _write_config(root / "pipeline.toml", "")

    config = load_config(config_path, repo_root=root)

    assert config.paths.raw_dir == raw_link
    assert config.paths.preanalysis_dir == preanalysis_link
    assert config.paths.external_flux == flux_link


def test_absolute_farm_path_is_allowed(tmp_path):
    from graal_pipeline.config import load_config

    root = tmp_path / "repo"
    farm = tmp_path / "farm-results"
    root.mkdir()
    config_path = _write_config(
        root / "pipeline.toml",
        f'[paths]\nresults_dir = "{farm}"\n',
    )

    config = load_config(config_path, repo_root=root)

    assert config.paths.results_dir == farm


def test_python_310_falls_back_to_tomli():
    from graal_pipeline.config import _load_toml_module

    calls: list[str] = []
    sentinel = object()

    def fake_import(name: str):
        calls.append(name)
        if name == "tomllib":
            raise ModuleNotFoundError(name)
        return sentinel

    assert _load_toml_module(fake_import) is sentinel
    assert calls == ["tomllib", "tomli"]


def test_explicit_missing_config_is_rejected(tmp_path):
    from graal_pipeline.config import ConfigError, load_config

    with pytest.raises(ConfigError, match="configuration file does not exist"):
        load_config(tmp_path / "missing.toml", repo_root=tmp_path)
