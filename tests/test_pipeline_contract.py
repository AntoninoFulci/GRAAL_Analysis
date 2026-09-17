"""Public shell contract for top-level pipeline orchestration."""

from pathlib import Path
import os
import subprocess


ROOT = Path(__file__).parents[1]
PIPELINE = ROOT / "run_pipeline.sh"


def _write_fake_executable(path: Path, body: str) -> None:
    path.write_text(f"#!/usr/bin/env bash\nset -euo pipefail\n{body}\n")
    path.chmod(0o755)


def _run_path_probe(
    tmp_path: Path,
    *options: str,
    force_preanalysis: bool = True,
) -> subprocess.CompletedProcess[str]:
    fake_python = tmp_path / "fake-python"
    _write_fake_executable(
        fake_python,
        """
if [[ "${1:-}" == "-c" ]]; then
    exit 0
fi
if [[ "$*" == *"mc_simulation.mc_status"* ]]; then
    exit 0
fi
if [[ "$*" == *"event_selector.select_events"* ]]; then
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --input-dir) input_dir="$2"; shift 2 ;;
            --output-dir) output_dir="$2"; shift 2 ;;
            *) shift ;;
        esac
    done
    [[ -d "$input_dir" ]]
    mkdir -p "$output_dir"
    exit 0
fi
exit 97
""",
    )
    fake_root = tmp_path / "fake-root"
    _write_fake_executable(fake_root, "exit 0")

    env = os.environ.copy()
    env.update(PYTHON=str(fake_python), ROOT_EXEC=str(fake_root))
    command = [str(PIPELINE)]
    if force_preanalysis:
        command.append("--force-preanalysis")
    command.extend(
        [
            "--skip-mc",
            "--skip-features",
            "--skip-train",
            "--skip-reco",
            "--skip-plots",
            *options,
        ]
    )
    return subprocess.run(
        command,
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
    )


def test_pipeline_help_describes_all_eight_stages_and_public_flags():
    result = subprocess.run(
        [str(PIPELINE), "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    for stage in (
        "1. Pre-analisi",
        "2. Selezione eventi",
        "3. MC generation",
        "4. Build features stage-1",
        "5. Grid search",
        "6. Training BDT stage-1",
        "7. Ricostruzione",
        "8. Plot",
    ):
        assert stage in result.stdout
    for option in (
        "--test-data",
        "--raw-dir",
        "--pre-dir",
        "--selected-dir",
        "--nevents",
        "--input-tree",
        "--signal-channel",
        "--signal-prior",
        "--skip-preanalysis",
        "--force-preanalysis",
        "--skip-selection",
        "--skip-mc",
        "--force-mc",
        "--skip-features",
        "--skip-grid-search",
        "--grid-search-niter",
        "--skip-train",
        "--skip-reco",
        "--skip-plots",
    ):
        assert option in result.stdout


def test_pipeline_rejects_unknown_option_before_running_any_stage():
    result = subprocess.run(
        [str(PIPELINE), "--phase0-unknown-option"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert result.stdout.strip() == "Unknown option: --phase0-unknown-option"
    assert result.stderr == ""


def test_pipeline_defaults_follow_numbered_data_layout(tmp_path):
    run_dir = tmp_path / "data/01_raw/graal_data/1998_uv"
    run_dir.mkdir(parents=True)
    (run_dir / "run1321.root").touch()

    result = _run_path_probe(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "data/02_pre_analyzed/pre_analisi").is_dir()
    assert (tmp_path / "data/03_selected").is_dir()


def test_explicit_data_paths_override_test_data_layout(tmp_path):
    raw_dir = tmp_path / "farm/raw/graal_data"
    pre_dir = tmp_path / "farm/pre/pre_analisi"
    selected_dir = tmp_path / "local/selected"
    run_dir = raw_dir / "1998_uv"
    run_dir.mkdir(parents=True)
    (run_dir / "run1321.root").touch()

    result = _run_path_probe(
        tmp_path,
        "--test-data",
        "--raw-dir",
        str(raw_dir),
        "--pre-dir",
        str(pre_dir),
        "--selected-dir",
        str(selected_dir),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert pre_dir.is_dir()
    assert selected_dir.is_dir()
    assert not (tmp_path / "test_data/pre_analyzed").exists()
    assert not (tmp_path / "test_data/selected").exists()


def test_pipeline_reuses_preanalysis_files_through_directory_symlink(tmp_path):
    farm_pre_dir = tmp_path / "farm/pre_analisi"
    farm_pre_dir.mkdir(parents=True)
    (farm_pre_dir / "pre_analisi_2002_vis1.root").touch()
    local_pre_parent = tmp_path / "data/02_pre_analyzed"
    local_pre_parent.mkdir(parents=True)
    (local_pre_parent / "pre_analisi").symlink_to(farm_pre_dir, target_is_directory=True)

    result = _run_path_probe(tmp_path, force_preanalysis=False)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 file gia'" in result.stdout
