"""Small handoff command for measured adaptive Figure 4 control bins."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from graal_theory.figure4_integration import AdaptiveBinChecks, Figure4BinMoment


def test_pilot_writes_selected_power_and_gate_result(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[1]/"scripts"/"figure4_adaptive_pilot.py"
    spec = importlib.util.spec_from_file_location("figure4_adaptive_pilot", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    seen = []
    monkeypatch.setattr(module, "_figure4_model", lambda *args: SimpleNamespace(strong_grid=None))

    def fake(model, pair, energy_range, mass_range, **settings):
        seen.append((pair, energy_range, mass_range, settings))
        base = Figure4BinMoment(pair, energy_range, mass_range,
            energy_range, mass_range, np.array([1.15]), .2, 1., .5, .5,
            sum(mass_range)/2, 0., "calculated")
        replicas = tuple(base for _ in settings["replica_seeds"])
        return AdaptiveBinChecks((base, base, base, replicas, base), 5,
                                 confirmation=base)

    monkeypatch.setattr(module, "adaptive_figure4_bin_checks", fake)
    output = tmp_path/"pilot.json"
    assert module.main(["--control", "lower", "--output", str(output)]) == 0
    report = json.loads(output.read_text())
    assert report["status"] == "calculated"
    assert report["selected_power"] == 5
    assert report["confirmation_power"] == 7
    assert report["resolution_policy"] == "two_nested_refinements_and_span"
    assert report["replica_seeds"] == list(range(2026, 2034))
    assert report["checks"]["sobol_total_relative"] == 0
    assert seen[0][1:3] == ((1.1, 1.2), (1.52, 1.56))
    assert seen[0][3]["min_power"] == 5
    assert seen[0][3]["max_power"] == 8
