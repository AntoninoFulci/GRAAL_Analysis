"""Plot provenance must hash the modules actually imported by the runtime."""
import hashlib
import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from plots.core import dalitz_metadata


MODULES = (
    "plots.dalitz", "plots.core.dalitz_metadata", "plots.core.kinematics",
    "plots.core.reconstruction_data", "graal_common.physics.channels", "plots.quality",
)


def test_plot_metadata_uses_installed_module_paths(tmp_path):
    metadata = dalitz_metadata.build_metadata(
        SimpleNamespace(run_manifest=tmp_path / "absent.csv"), {}, {}, "matched", [])
    expected = {Path(importlib.import_module(name).__file__).resolve() for name in MODULES}
    assert {Path(row["path"]) for row in metadata["source_files"]} == expected
    for row in metadata["source_files"]:
        content = Path(row["path"]).read_bytes()
        assert row["size"] == len(content)
        assert row["sha256"] == hashlib.sha256(content).hexdigest()


def test_plot_metadata_rejects_missing_loaded_source(tmp_path, monkeypatch):
    channels = importlib.import_module("graal_common.physics.channels")
    missing = tmp_path / "missing_channels.py"
    monkeypatch.setattr(channels, "__file__", str(missing))
    with pytest.raises(FileNotFoundError, match="missing_channels.py"):
        dalitz_metadata.build_metadata(
            SimpleNamespace(run_manifest=tmp_path / "absent.csv"), {}, {}, "matched", [])
