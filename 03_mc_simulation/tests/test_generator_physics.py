"""Physics invariants shared by every ROOT Monte Carlo generator."""

from pathlib import Path
import re
import shutil
import subprocess

import numpy as np
import pytest
import uproot

from graal_common import channels


GENERATOR_FILES = sorted(Path("03_mc_simulation").glob("generate_*_dataset.C"))


@pytest.mark.parametrize("path", GENERATOR_FILES, ids=lambda path: path.stem)
def test_generator_does_not_smear_beam_components_independently(path: Path):
    source = path.read_text()

    assert "rng.Gaus(Ebeam, 0.016), rng.Gaus(Ebeam, 0.016)" not in source
    assert "SmearTaggedPhoton(Ebeam, rng)" in source


def test_tagger_fwhm_is_converted_to_gaussian_sigma():
    assert getattr(channels, "TAGGER_FWHM_GEV", None) == pytest.approx(0.016)
    assert getattr(channels, "TAGGER_SIGMA_GEV", None) == pytest.approx(
        0.016 / 2.3548200450309493
    )


@pytest.mark.skipif(shutil.which("root") is None, reason="ROOT is not installed")
def test_phase_space_acceptance_tolerates_observed_root_roundoff(tmp_path: Path):
    header = Path("03_mc_simulation/smearing.h").resolve()
    macro = tmp_path / "test_weight_roundoff.C"
    macro.write_text(
        f"""
#include "{header}"
#include <TRandom3.h>

void test_weight_roundoff() {{
    TRandom3 rng(12345);
    AcceptPhaseSpaceWeight(1.0000000005940244, rng);
}}
"""
    )

    subprocess.run(
        ["root", "-l", "-b", "-q", str(macro)],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize("path", GENERATOR_FILES, ids=lambda path: path.stem)
def test_phase_space_generate_weight_is_not_ignored(path: Path):
    source = path.read_text()

    assert "GenerateUnweighted" in source
    assert not re.search(
        r"^\s*\w+(?:\[\w+\])?\.Generate\(\);\s*$", source, re.MULTILINE
    )


@pytest.mark.skipif(shutil.which("root") is None, reason="ROOT is not installed")
def test_unweighted_phase_space_matches_weighted_reference(tmp_path: Path):
    header = Path("03_mc_simulation/smearing.h").resolve()
    macro = tmp_path / "test_unweighting.C"
    macro.write_text(
        f"""
#include "{header}"
#include <TGenPhaseSpace.h>
#include <TLorentzVector.h>
#include <TRandom.h>
#include <TRandom3.h>
#include <iostream>

void test_unweighting() {{
    TLorentzVector parent(0.0, 0.0, 0.0, 2.5);
    Double_t masses[3] = {{0.938272, 0.547862, 0.134977}};
    TGenPhaseSpace decay;
    decay.SetDecay(parent, 3, masses);

    gRandom->SetSeed(12345);
    double weighted_sum = 0.0;
    double weight_sum = 0.0;
    for (int i = 0; i < 100000; ++i) {{
        const double weight = decay.Generate();
        weighted_sum += weight * decay.GetDecay(1)->E();
        weight_sum += weight;
    }}

    TRandom3 accept_rng(67890);
    double accepted_sum = 0.0;
    for (int i = 0; i < 50000; ++i) {{
        GenerateUnweighted(decay, accept_rng);
        accepted_sum += decay.GetDecay(1)->E();
    }}

    std::cout << "RESULT " << weighted_sum / weight_sum
              << " " << accepted_sum / 50000.0 << std::endl;
}}
"""
    )
    result = subprocess.run(
        ["root", "-l", "-b", "-q", str(macro)],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    match = re.search(r"RESULT\s+([0-9.eE+-]+)\s+([0-9.eE+-]+)", result.stdout)
    assert match is not None, result.stdout
    weighted_mean, accepted_mean = map(float, match.groups())

    assert accepted_mean == pytest.approx(weighted_mean, abs=2e-3)


@pytest.mark.skipif(shutil.which("root") is None, reason="ROOT is not installed")
def test_generated_tagged_beam_is_massless(tmp_path: Path):
    macro = Path("03_mc_simulation/generate_eta_pi0_dataset.C").resolve()
    subprocess.run(
        ["root", "-l", "-b", "-q", f"{macro}(50)"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )

    with uproot.open(tmp_path / "eta_pi0_mc.root")["mc"] as tree:
        beam = tree["beam"].array(library="ak")
    px = np.asarray(beam["fP"]["fX"])
    py = np.asarray(beam["fP"]["fY"])
    pz = np.asarray(beam["fP"]["fZ"])
    energy = np.asarray(beam["fE"])

    assert np.all(px == 0.0)
    assert np.all(py == 0.0)
    assert np.max(np.abs(energy**2 - pz**2)) < 1e-12
