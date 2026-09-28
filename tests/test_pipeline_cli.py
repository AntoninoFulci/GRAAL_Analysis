from __future__ import annotations

from pathlib import Path
import os
import subprocess
import sys


ROOT = Path(__file__).parents[1]


def test_module_help_works_outside_repository(tmp_path):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)

    result = subprocess.run(
        [sys.executable, "-m", "graal_pipeline", "--help"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert "GRAAL pipeline orchestrator" in result.stdout
    assert "--config" in result.stdout
    assert "--profile" in result.stdout


def test_pyproject_registers_console_command_and_python_310_tomli():
    try:
        import tomllib
    except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.10
        import tomli as tomllib

    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text())

    assert metadata["project"]["scripts"]["graal-pipeline"] == "graal_pipeline.cli:main"
    assert "tomli>=2; python_version < '3.11'" in metadata["project"]["dependencies"]
    assert "graal_pipeline" in metadata["tool"]["setuptools"]["packages"]
