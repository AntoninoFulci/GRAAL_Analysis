from __future__ import annotations

import pytest

from build_figure4_comparison import main, publish_new_directory
from contracts import PolarizationContractError


def test_cli_checks_gate0_before_reco_and_leaves_no_output(tmp_path, capsys):
    output = tmp_path / "bundle"
    result = main(
        [
            "--repository-root", str(tmp_path),
            "--reco-inventory", "missing-inventory.json",
            "--output-dir", str(output),
        ]
    )
    assert result == 1
    assert "HANDOFF does not exist" in capsys.readouterr().err
    assert not output.exists()


def test_atomic_directory_publish_cleans_stage_on_failure_and_never_overwrites(tmp_path):
    output = tmp_path / "bundle"

    def failing_writer(stage):
        (stage / "partial.csv").write_text("partial")
        raise PolarizationContractError("injected publication failure")

    with pytest.raises(PolarizationContractError, match="injected"):
        publish_new_directory(output, failing_writer)
    assert not output.exists()
    assert list(tmp_path.iterdir()) == []

    output.mkdir()
    with pytest.raises(PolarizationContractError, match="refusing overwrite"):
        publish_new_directory(output, lambda stage: None)
