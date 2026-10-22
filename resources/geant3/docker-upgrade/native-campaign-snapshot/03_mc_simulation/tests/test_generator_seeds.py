"""Nominal generators reproduce events without consuming the caller's RNG."""
from pathlib import Path

import awkward as ak
import pytest
import uproot


GENERATORS = sorted((Path(__file__).resolve().parents[1] / "generators").glob("generate_*_dataset.C"))


def _events(path):
    with uproot.open(path) as source:
        return ak.to_list(source["mc"].arrays(library="ak"))


@pytest.mark.parametrize("macro", GENERATORS, ids=lambda path: path.stem)
def test_nominal_generator_seed_controls_all_events_and_restores_rng(macro, tmp_path):
    ROOT = pytest.importorskip("ROOT")
    if not hasattr(ROOT, macro.stem):
        assert ROOT.gROOT.LoadMacro(str(macro)) == 0
    generate = getattr(ROOT, macro.stem)
    caller_rng = ROOT.gRandom
    outputs = [tmp_path / f"sample_{i}.root" for i in range(3)]
    for path, seed in zip(outputs, (71, 71, 72)):
        caller_rng.SetSeed(903)
        expected_next = caller_rng.Rndm()
        caller_rng.SetSeed(903)
        generate(30, 1.5, 1.6, str(path), seed)
        assert ROOT.gRandom == caller_rng
        assert caller_rng.Rndm() == expected_next
        with uproot.open(path) as source:
            assert source["seed"].member("fVal") == seed
            assert source["requested_seed"].member("fVal") == seed
            assert source["generator"].member("fTitle") == macro.stem
            assert source["n_generated"].member("fVal") == 30
            assert source["beam_min_gev"].member("fVal") == 1.5
            assert source["beam_max_gev"].member("fVal") == 1.6
    assert _events(outputs[0]) == _events(outputs[1])
    assert _events(outputs[0]) != _events(outputs[2])


def test_automatic_generator_seed_is_recorded_and_replayable(tmp_path):
    ROOT = pytest.importorskip("ROOT")
    macro = GENERATORS[0]
    if not hasattr(ROOT, macro.stem):
        assert ROOT.gROOT.LoadMacro(str(macro)) == 0
    generate = getattr(ROOT, macro.stem)
    original, replay = tmp_path / "auto.root", tmp_path / "replay.root"
    generate(30, 1.5, 1.6, str(original))
    with uproot.open(original) as source:
        seed = source["seed"].member("fVal")
        assert seed > 0
        assert source["requested_seed"].member("fVal") == 0
    generate(30, 1.5, 1.6, str(replay), seed)
    assert _events(original) == _events(replay)


@pytest.mark.parametrize("invalid_count", [0, -1])
def test_generator_rejects_invalid_count_before_writing(tmp_path, invalid_count):
    ROOT = pytest.importorskip("ROOT")
    macro = GENERATORS[0]
    if not hasattr(ROOT, macro.stem):
        assert ROOT.gROOT.LoadMacro(str(macro)) == 0
    output = tmp_path / "invalid.root"
    with pytest.raises(Exception, match="Nevents.*positive"):
        getattr(ROOT, macro.stem)(invalid_count, 1.5, 1.6, str(output), 71)
    assert not output.exists()


def test_generator_output_failure_restores_caller_rng(tmp_path):
    ROOT = pytest.importorskip("ROOT")
    macro = GENERATORS[0]
    if not hasattr(ROOT, macro.stem):
        assert ROOT.gROOT.LoadMacro(str(macro)) == 0
    caller_rng = ROOT.gRandom
    with pytest.raises(Exception, match="cannot create"):
        getattr(ROOT, macro.stem)(30, 1.5, 1.6, str(tmp_path / "missing" / "output.root"), 71)
    assert ROOT.gRandom == caller_rng
