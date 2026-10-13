"""Physical and publication contracts for the optional charged truth sample."""

from pathlib import Path
import shutil
import subprocess

import numpy as np
import pytest
import uproot


MACRO = Path(__file__).resolve().parents[1] / "studies/generate_pip_pim_truth.C"
pytestmark = pytest.mark.skipif(shutil.which("root") is None, reason="ROOT required")


def generate(path, *, events=300, low=0.95, high=1.10, seed=12345):
    return subprocess.run(
        ["root", "-l", "-b", "-q", f'{MACRO}({events},{low},{high},"{path}",{seed})'],
        capture_output=True, text=True, timeout=60,
    )


def vectors(tree, name):
    a = tree[name].array(library="ak")
    return np.column_stack(
        [np.asarray(a["fP"][axis]) for axis in ("fX", "fY", "fZ")]
        + [np.asarray(a["fE"])]
    )


def test_charged_truth_conserves_four_momentum_and_has_no_fake_photons(tmp_path):
    output = tmp_path / "charged.root"
    result = generate(output)
    assert result.returncode == 0, result.stdout + result.stderr
    with uproot.open(output) as f:
        tree = f["mc_truth"]
        assert tree.num_entries == 300
        beam = vectors(tree, "beam_true")
        target = vectors(tree, "target_true")
        proton = vectors(tree, "proton_true")
        plus = vectors(tree, "pi_plus_true")
        minus = vectors(tree, "pi_minus_true")
        np.testing.assert_allclose(proton + plus + minus, beam + target, atol=2e-12)
        for p, mass in ((proton, 0.938272), (plus, 0.13957039), (minus, 0.13957039)):
            np.testing.assert_allclose(p[:, 3] ** 2 - (p[:, :3] ** 2).sum(axis=1), mass**2, atol=2e-12)
        assert np.all((beam[:, 3] >= 0.95) & (beam[:, 3] < 1.10))
        np.testing.assert_array_equal(tree["event_id"].array(library="np"), np.arange(300))
        assert np.all(tree["n_true_gamma"].array(library="np") == 0)
        assert "mc" not in f  # Cannot accidentally feed the neutral MC loader.
        assert "truth-only" in f["sample_kind"].member("fTitle")


def test_charged_truth_reproduces_seed_in_same_root_process(tmp_path):
    import ROOT

    assert ROOT.gROOT.LoadMacro(str(MACRO)) == 0
    before = ROOT.gRandom
    outputs = [tmp_path / f"sample_{i}.root" for i in range(3)]
    for path, seed in zip(outputs, (71, 71, 72)):
        ROOT.generate_pip_pim_truth(80, 0.95, 1.1, str(path), seed)
        assert ROOT.gRandom == before
    samples = []
    for path in outputs:
        with uproot.open(path) as f:
            samples.append(vectors(f["mc_truth"], "pi_plus_true"))
    np.testing.assert_array_equal(samples[0], samples[1])
    assert not np.array_equal(samples[0], samples[2])


@pytest.mark.parametrize("kwargs", [
    {"events": 0}, {"seed": 0}, {"low": 0.1, "high": 0.2},
    {"low": 1.1, "high": 1.0},
])
def test_invalid_charged_request_does_not_publish(tmp_path, kwargs):
    output = tmp_path / "invalid.root"
    result = generate(output, **kwargs)
    assert result.returncode != 0
    assert not output.exists()


def test_charged_generator_preserves_existing_output(tmp_path):
    output = tmp_path / "existing.root"
    output.write_bytes(b"previous result")
    result = generate(output)
    assert result.returncode != 0
    assert output.read_bytes() == b"previous result"
