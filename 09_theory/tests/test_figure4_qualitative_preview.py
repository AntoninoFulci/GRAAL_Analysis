"""Qualitative Figure 4 preview stays separate from certification."""

import csv
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from graal_theory.figure4_reference import PAIR_MASS_AXES


def _preview():
    path = Path(__file__).resolve().parents[1]/"scripts"/"figure4_qualitative_preview.py"
    assert path.exists(), "qualitative preview script is missing"
    spec = importlib.util.spec_from_file_location("figure4_qualitative_preview", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_preview_saves_resumable_raw_bins_and_labels_uncertified_output(tmp_path, monkeypatch):
    module = _preview()
    calls = []

    def synthetic_bin(energy, pair, index):
        calls.append((energy, pair, index))
        low, high = PAIR_MASS_AXES[pair]
        edges = np.linspace(low, high, 11)
        accessible = index != 0
        return {
            "energy_bin": energy, "pair": pair, "mass_bin": index,
            "energy_range_gev": [round(1.1+.1*energy, 2), round(1.2+.1*energy, 2)],
            "mass_range_gev": [float(edges[index]), float(edges[index+1])],
            "weighted_mass_gev": float((edges[index]+edges[index+1])/2) if accessible else None,
            "sigma": 0.1 if accessible else None,
            "denominator": 1.0 if accessible else 0.0,
            "status": "calculated" if accessible else "masked_kinematic",
            "reason": None if accessible else "below threshold",
        }

    monkeypatch.setattr(module, "compute_bin", synthetic_bin)
    result = module.run_preview(tmp_path/"preview", workers=1)
    assert result == 0
    assert len(calls) == 120
    output = tmp_path/"preview"
    assert (output/"preview.pdf").stat().st_size > 1000
    with (output/"preview.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 120
    assert rows[0]["status"] == "masked_kinematic"
    summary = json.loads((output/"summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "preliminary_uncertified"
    assert summary["calculated_bins"] == 108
    assert summary["kinematic_masks"] == 12
    assert "reproduced" not in json.dumps(summary)

    def no_recompute(*args):
        raise AssertionError("completed bin was recomputed")

    monkeypatch.setattr(module, "compute_bin", no_recompute)
    assert module.run_preview(output, workers=1) == 0


def test_preview_rejects_incompatible_checkpoint(tmp_path, monkeypatch):
    module = _preview()
    output = tmp_path/"preview"
    path = output/"bins"/"e0-p_pi0-b0.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"energy_bin": 3, "pair": "p_pi0", "mass_bin": 0}))
    with pytest.raises(ValueError, match="incompatible existing bin"):
        module.run_preview(output, workers=1)
