"""Public shell contract for top-level pipeline orchestration."""

from pathlib import Path
import subprocess


ROOT = Path(__file__).parents[1]
PIPELINE = ROOT / "run_pipeline.sh"


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
