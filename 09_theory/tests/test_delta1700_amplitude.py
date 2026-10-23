from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from graal_theory.amplitudes.delta1700 import tree_amplitude
from graal_theory.models.eta_pi0_p import EtaPi0PModel
from graal_theory.phase_space import SobolConfig, sample_three_body


REFERENCES = Path(__file__).resolve().parents[1] / "references"


@pytest.fixture(scope="module")
def model():
    return EtaPi0PModel.from_files(REFERENCES / "central_parameters.json", REFERENCES / "sources.json")


@pytest.fixture(scope="module")
def sample(model):
    return sample_three_body(1.77, model.masses, SobolConfig(power=6))


def test_zero_eta_delta_coupling_gives_zero_amplitude(sample, model):
    zeroed = replace(model.parameters, g_eta_delta=0j)
    assert np.all(tree_amplitude(sample, np.array([1.0, 0.0, 0.0]), zeroed) == 0j)


def test_tree_amplitude_is_finite_spin_matrix_per_event(sample, model):
    amplitude = tree_amplitude(sample, np.array([1.0, 0.0, 0.0]), model.parameters)
    assert amplitude.shape == (len(sample.momenta), 2, 2)
    assert np.all(np.isfinite(amplitude))
