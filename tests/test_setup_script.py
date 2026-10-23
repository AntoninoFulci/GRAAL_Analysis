"""First-install repository setup contract."""

from pathlib import Path
import os
import shutil
import subprocess


ROOT = Path(__file__).parents[1]
SETUP = ROOT / "scripts/setup.sh"


def _sandbox_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    shutil.copy2(SETUP, repo / "scripts/setup.sh")
    (repo / "04_bdt_training").mkdir()
    (repo / "04_bdt_training/requirements.txt").write_text("pytest\n")
    (repo / "pyproject.toml").write_text("[project]\nname='fixture'\nversion='0'\n")
    return repo


def _fake_python(tmp_path: Path) -> Path:
    executable = tmp_path / "fake-python"
    executable.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "-m" && "${2:-}" == "venv" ]]; then
    destination="${@: -1}"
    mkdir -p "$destination/bin"
    cp "$0" "$destination/bin/python"
    chmod +x "$destination/bin/python"
    exit 0
fi
if [[ "${1:-}" == "-m" && "${2:-}" == "pip" ]]; then
    printf '%s\\n' "$*" >> "${SETUP_TEST_LOG:?}"
    exit 0
fi
if [[ "${1:-}" == "-c" ]]; then
    if [[ "$2" == *"site.ENABLE_USER_SITE"* ]]; then
        exit "${SETUP_TEST_USER_SITE_STATUS:-0}"
    fi
    exit 0
fi
exit 91
"""
    )
    executable.chmod(0o755)
    return executable


def test_setup_help_describes_local_and_farm_modes():
    result = subprocess.run(
        ["bash", str(SETUP), "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert "--mode local" in result.stdout
    assert "--mode farm" in result.stdout
    assert "--raw-target" in result.stdout
    assert "--pre-target" not in result.stdout
    assert "--python" in result.stdout


def test_local_setup_builds_environment_and_empty_data_layout(tmp_path):
    repo = _sandbox_repo(tmp_path)
    python = _fake_python(tmp_path)
    log = tmp_path / "pip.log"
    env = os.environ.copy()
    env["SETUP_TEST_LOG"] = str(log)

    result = subprocess.run(
        [str(repo / "scripts/setup.sh"), "--mode", "local", "--python", str(python)],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert (repo / ".venv/bin/python").is_file()
    for relative in (
        "data/00_external",
        "data/01_raw",
        "data/02_pre_analyzed",
        "results/_cache/03_selected",
    ):
        assert (repo / relative).is_dir()
    assert not (repo / "data/01_raw/graal_data").exists()
    assert not (repo / "data/02_pre_analyzed/pre_analisi").exists()
    commands = log.read_text()
    assert "-m pip install -r" not in commands
    assert "-m pip install -e" in commands
    assert f"source {repo}/.venv/bin/activate" in result.stdout
    assert (
        f"{repo}/.venv/bin/python "
        f"{repo}/06_calibration/build_strip_energy_flux.py --help"
        in result.stdout
    )


def test_farm_setup_links_raw_and_keeps_preanalysis_directory(tmp_path):
    repo = _sandbox_repo(tmp_path)
    python = _fake_python(tmp_path)
    raw_target = tmp_path / "farm/graal_data"
    raw_target.mkdir(parents=True)
    log = tmp_path / "pip.log"
    env = os.environ.copy()
    env["SETUP_TEST_LOG"] = str(log)
    command = [
        str(repo / "scripts/setup.sh"),
        "--mode",
        "farm",
        "--python",
        str(python),
        "--raw-target",
        str(raw_target),
    ]

    first = subprocess.run(command, cwd=tmp_path, env=env, text=True, capture_output=True)
    second = subprocess.run(command, cwd=tmp_path, env=env, text=True, capture_output=True)

    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 0, second.stdout + second.stderr
    raw_link = repo / "data/01_raw/graal_data"
    pre_dir = repo / "data/02_pre_analyzed"
    assert raw_link.is_symlink()
    assert pre_dir.is_dir()
    assert not pre_dir.is_symlink()
    assert raw_link.resolve() == raw_target.resolve()


def test_farm_setup_refuses_to_replace_existing_data_path(tmp_path):
    repo = _sandbox_repo(tmp_path)
    python = _fake_python(tmp_path)
    raw_target = tmp_path / "farm/graal_data"
    raw_target.mkdir(parents=True)
    conflicting = repo / "data/01_raw/graal_data"
    conflicting.mkdir(parents=True)
    marker = conflicting / "keep.txt"
    marker.write_text("do not delete")
    env = os.environ.copy()
    env["SETUP_TEST_LOG"] = str(tmp_path / "pip.log")

    result = subprocess.run(
        [
            str(repo / "scripts/setup.sh"),
            "--mode",
            "farm",
            "--python",
            str(python),
            "--raw-target",
            str(raw_target),
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "path exists" in result.stderr
    assert marker.read_text() == "do not delete"


def test_user_setup_installs_outside_venv_and_can_be_repeated(tmp_path):
    repo = _sandbox_repo(tmp_path)
    python = _fake_python(tmp_path)
    log = tmp_path / "pip.log"
    env = os.environ.copy()
    env["SETUP_TEST_LOG"] = str(log)
    command = [
        str(repo / "scripts/setup.sh"),
        "--mode", "local", "--python", str(python), "--install", "user",
    ]

    for _ in range(2):
        result = subprocess.run(command, cwd=tmp_path, env=env, text=True, capture_output=True)
        assert result.returncode == 0, result.stdout + result.stderr

    assert not (repo / ".venv").exists()
    assert (repo / "data/02_pre_analyzed").is_dir()
    commands = log.read_text().splitlines()
    assert len(commands) == 2
    assert all("--user" in command for command in commands)
    assert not any("requirements.txt" in command for command in commands)
    assert any(f"-e {repo}" in command for command in commands)
    assert "bin/activate" not in result.stdout
    assert f"{python} {repo}/06_calibration/build_strip_energy_flux.py --help" in result.stdout


def test_user_setup_refuses_interpreter_without_visible_user_site(tmp_path):
    repo = _sandbox_repo(tmp_path)
    python = _fake_python(tmp_path)
    log = tmp_path / "pip.log"
    env = os.environ.copy()
    env["SETUP_TEST_LOG"] = str(log)
    env["SETUP_TEST_USER_SITE_STATUS"] = "1"

    result = subprocess.run(
        [str(repo / "scripts/setup.sh"), "--mode", "local", "--python", str(python),
         "--install", "user"],
        cwd=tmp_path, env=env, text=True, capture_output=True,
    )

    assert result.returncode == 1
    assert "outside a virtual environment" in result.stderr
    assert not log.exists()
    assert not (repo / ".venv").exists()


def test_farm_setup_links_explicit_preanalysis_and_refuses_replacement(tmp_path):
    repo = _sandbox_repo(tmp_path)
    python = _fake_python(tmp_path)
    raw = tmp_path / 'raw'; raw.mkdir()
    pre = tmp_path / 'h80'; pre.mkdir()
    env = {**os.environ, 'SETUP_TEST_LOG': str(tmp_path / 'pip.log')}
    command = [str(repo / 'scripts/setup.sh'), '--mode', 'farm', '--raw-target', str(raw), '--preanalysis-target', str(pre), '--python', str(python)]
    first = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    link = repo / 'data/02_pre_analyzed'
    assert link.is_symlink() and link.resolve() == pre
    other = tmp_path / 'other'; other.mkdir()
    command[command.index('--preanalysis-target') + 1] = str(other)
    second = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True, text=True)
    assert second.returncode != 0
    assert link.resolve() == pre
