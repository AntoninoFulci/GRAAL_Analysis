"""Random transport seeds stay nonzero, recorded and explicitly reproducible."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[1]/"03_mc_simulation/geant4/run.py"


def api():
    spec = importlib.util.spec_from_file_location("g4_seeds", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_entropy_seed_avoids_generator_seed(monkeypatch):
    module = api()
    values = iter([40, 90])
    monkeypatch.setattr(module.secrets, "randbelow", lambda bound: next(values))
    assert module.transport_seed(None, excluded={41}) == (91, "os_entropy")
    assert module.transport_seed(41, excluded={41}) == (41, "explicit")


@pytest.mark.parametrize("seed", [0, -1, 2**31, True, 1.5])
def test_invalid_seed_rejected(seed):
    with pytest.raises(ValueError, match="seed"):
        api().transport_seed(seed)


@pytest.mark.parametrize("explicit", [None, 123])
def test_seed_recorded_before_build_and_forwarded_to_conditions(tmp_path, monkeypatch, explicit):
    module = api()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module.secrets, "randbelow", lambda bound: 456)
    class Conditions:
        @staticmethod
        def load_period(*args): return {"period": "test"}
        @staticmethod
        def validate_period_truth(*args): pass
        @staticmethod
        def write_inputs(period, path, snapshot, seed):
            assert seed == (explicit or 457)
            (path/"period.json").write_text(json.dumps({"seed":seed}))
            (path/"geometry.g3").write_text("fixture")
            return {"seed":seed}
    monkeypatch.setitem(sys.modules, "period_conditions", Conditions)
    monkeypatch.setattr(module, "find_geant4", lambda _: tmp_path/"prefix/lib/cmake/Geant4")
    work = tmp_path/"work"
    def stop_at_build(*args, **kwargs):
        record=json.loads((work/"run.json").read_text())
        assert record["seed"] == (explicit or 457)
        assert record["seed_policy"] == ("explicit" if explicit else "os_entropy")
        raise RuntimeError("checked before build")
    monkeypatch.setattr(module.subprocess, "run", stop_at_build)
    argv=[str(SCRIPT),"geometry","--period","test","--work-dir",str(work)]
    if explicit: argv += ["--seed",str(explicit)]
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(RuntimeError, match="checked before build"):
        module.main()
