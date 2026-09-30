import numpy as np
from types import SimpleNamespace

from graal_theory.convergence import compare_resolutions
from graal_theory.observables import HistogramSpec, predict_energy
from graal_theory.phase_space import SobolConfig, sample_three_body

MASSES = (0.547862, 0.1349768, 0.93827208816)


class ConstantModel:
    masses = MASSES
    parameters = SimpleNamespace(proton_mass_gev=MASSES[-1])

    def matrix_element_squared(self, sample):
        return np.ones(len(sample.momenta))


def test_nested_resolution_prediction_converges_for_constant_matrix_element():
    low_sample = sample_three_body(2.0, MASSES, SobolConfig(power=12))
    high_sample = sample_three_body(2.0, MASSES, SobolConfig(power=13))
    np.testing.assert_array_equal(low_sample.momenta, high_sample.momenta[:len(low_sample.momenta)])
    low = predict_energy(1.2, ConstantModel(), SobolConfig(power=12), HistogramSpec(bins=4))
    high = predict_energy(1.2, ConstantModel(), SobolConfig(power=13), HistogramSpec(bins=4))
    report = compare_resolutions(low, high)
    assert report.passed
    assert report.cross_section_relative_change < 0.01
    assert report.max_populated_bin_relative_change < 0.03
