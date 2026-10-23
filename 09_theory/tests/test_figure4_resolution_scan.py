"""Bounded deterministic scan used before expensive Figure 4 certification."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from graal_theory.figure4_integration import Figure4BinMoment


def _module():
    path = Path(__file__).resolve().parents[1]/"scripts"/"figure4_resolution_scan.py"
    spec = importlib.util.spec_from_file_location("figure4_resolution_scan", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_scan_records_raw_moments_at_nested_powers(monkeypatch):
    module = _module()
    calls = []
    monkeypatch.setattr(module, "_figure4_model", lambda *args: SimpleNamespace())

    def fake(model, pair, energy, mass, order, config):
        calls.append((pair, energy, mass, order, config.power, config.scramble))
        power = config.power
        return Figure4BinMoment(pair, energy, mass, energy, mass,
            np.array([energy[0]+.05]), .2*power, float(power),
            power/2, power/2, sum(mass)*power/2, .1*power, "calculated")

    monkeypatch.setattr(module, "_safe_predict", fake)
    report = module.scan_bin(0, "eta_pi0", 3)
    assert [row["power"] for row in report["moments"]] == [5, 6, 7, 8]
    assert [row["denominator"] for row in report["moments"]] == [5., 6., 7., 8.]
    assert report["mass_range_gev"] == [0.72, 0.76]
    assert report["moments"][0]["source_used_denominator"] == .5
    assert calls == [("eta_pi0", (1.1, 1.2), (.72, .76), 4, power, False)
                     for power in (5, 6, 7, 8)]


def test_scan_writes_twelve_resumable_panel_files(tmp_path, monkeypatch):
    module = _module()
    seen = []
    def fake(energy, pair, index):
        seen.append((energy, pair, index))
        return {"purpose": "deterministic_resolution_diagnostic_only",
                "energy_bin": energy, "pair": pair, "mass_bin": index,
                "energy_order": 4, "q_order": 64, "angle_order": 48,
                "mode": "grid",
                "elapsed_seconds": 0.,
                "moments": [{"power": power, "status": "calculated"}
                            for power in (5, 6, 7, 8)]}
    monkeypatch.setattr(module, "scan_bin", fake)
    assert module.main(["--output-dir", str(tmp_path), "--workers", "1"]) == 0
    assert len(seen) == 12
    assert len(list(tmp_path.glob("*.json"))) == 12
    assert json.loads((tmp_path/"e0-eta_pi0-b3.json").read_text())["pair"] == "eta_pi0"
    assert module.main(["--output-dir", str(tmp_path), "--workers", "1"]) == 0
    assert len(seen) == 12


def test_scan_refuses_to_resume_with_different_settings(tmp_path, monkeypatch):
    module = _module()
    path = tmp_path/"e0-p_pi0-b3.json"
    path.write_text(json.dumps({
        "energy_bin": 0, "pair": "p_pi0", "mass_bin": 3,
        "energy_order": 8, "q_order": 64, "angle_order": 48,
        "mode": "grid", "purpose": "deterministic_resolution_diagnostic_only",
        "moments": [{"power": power, "status": "calculated"}
                    for power in (5, 6, 7, 8)],
    }))
    monkeypatch.setattr(module, "scan_bin", lambda *args: {
        "energy_bin": args[0], "pair": args[1], "mass_bin": args[2],
        "elapsed_seconds": 0., "moments": [{"power": power, "status": "calculated"}
                                           for power in (5, 6, 7, 8)],
    })
    with pytest.raises(ValueError, match="incompatible existing scan file"):
        module.main(["--output-dir", str(tmp_path), "--workers", "1"])
