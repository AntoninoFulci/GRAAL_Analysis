"""Publication behavior for event-selection outputs."""

from pathlib import Path
import sys

import pytest

from event_selector import select_events


def test_cli_defaults_follow_numbered_data_layout(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["select_events"])

    args = select_events.parse_args()

    assert args.input_dir == "data/02_pre_analyzed/pre_analisi"
    assert args.output_dir == "data/03_selected"


def test_successful_selection_replaces_stale_output_dataset(tmp_path, monkeypatch):
    input_dir = tmp_path / "pre_analisi"
    input_dir.mkdir()
    (input_dir / "pre_analisi_1998_uv.root").touch()
    (input_dir / "pre_analisi_2002_vis1.root").touch()

    output_dir = tmp_path / "selected"
    output_dir.mkdir()
    (output_dir / "analisi_obsoleta.root").write_text("stale")

    def select_file(input_path: Path, output_path: Path) -> None:
        output_path.write_text(input_path.name)

    monkeypatch.setattr(select_events, "_select_file", select_file)

    select_events.run(input_dir, output_dir)

    assert sorted(path.name for path in output_dir.iterdir()) == [
        "analisi_1998_uv.root",
        "analisi_2002_vis1.root",
    ]


def test_failed_selection_preserves_previous_output_dataset(tmp_path, monkeypatch):
    input_dir = tmp_path / "pre_analisi"
    input_dir.mkdir()
    (input_dir / "pre_analisi_1998_uv.root").touch()
    (input_dir / "pre_analisi_2002_vis1.root").touch()

    output_dir = tmp_path / "selected"
    output_dir.mkdir()
    sentinel = output_dir / "analisi_verificata.root"
    sentinel.write_text("previous complete dataset")

    def fail_on_second_file(input_path: Path, output_path: Path) -> None:
        if input_path.name == "pre_analisi_2002_vis1.root":
            raise RuntimeError("broken ROOT input")
        output_path.write_text(input_path.name)

    monkeypatch.setattr(select_events, "_select_file", fail_on_second_file)

    with pytest.raises(RuntimeError, match="broken ROOT input"):
        select_events.run(input_dir, output_dir)

    assert sorted(path.name for path in output_dir.iterdir()) == [sentinel.name]
    assert sentinel.read_text() == "previous complete dataset"
