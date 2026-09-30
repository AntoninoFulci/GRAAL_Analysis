from types import SimpleNamespace

import numpy as np
import pytest

from graal_theory.constants import GEV2_TO_MICROBARN
from graal_theory.kinematics import s_from_lab_photon_energy
from graal_theory.observables import HistogramSpec, predict_energy
from graal_theory.phase_space import SobolConfig, phase_space_volume_quad


MASSES = (0.547862, 0.1349768, 0.93827208816)


class ConstantModel:
    masses = MASSES
    parameters = SimpleNamespace(proton_mass_gev=MASSES[-1])

    def matrix_element_squared(self, sample):
        return np.ones(len(sample.momenta))


def test_below_threshold_returns_zero_without_sampling(monkeypatch):
    monkeypatch.setattr("graal_theory.observables.sample_three_body",
                        lambda *args, **kwargs: pytest.fail("sampler called"))
    result = predict_energy(0.90, ConstantModel(), SobolConfig(power=8), HistogramSpec(bins=8))
    assert result.partial_cross_section_microbarn == 0.0
    assert all(np.all(hist.values == 0.0) for hist in result.histograms.values())


def test_histogram_integrals_equal_partial_cross_section():
    result = predict_energy(1.2, ConstantModel(), SobolConfig(power=15), HistogramSpec(bins=12))
    for histogram in result.histograms.values():
        assert np.sum(histogram.values * np.diff(histogram.edges)) == pytest.approx(
            result.partial_cross_section_microbarn, rel=5e-3
        )


def test_constant_amplitude_cross_section_matches_independent_phase_space():
    energy = 1.2
    result = predict_energy(energy, ConstantModel(), SobolConfig(power=16), HistogramSpec(bins=12))
    s = s_from_lab_photon_energy(energy, MASSES[-1])
    expected = (
        GEV2_TO_MICROBARN * 4 * MASSES[-1] ** 2 / (2 * (s - MASSES[-1] ** 2))
        * phase_space_volume_quad(np.sqrt(s), MASSES)
    )
    assert result.partial_cross_section_microbarn == pytest.approx(expected, rel=5e-3)


def test_nonfinite_matrix_element_reports_energy_and_event():
    class BrokenModel(ConstantModel):
        def matrix_element_squared(self, sample):
            values = super().matrix_element_squared(sample)
            values[7] = np.nan
            return values

    with pytest.raises(ValueError, match=r"E_gamma=1.2 GeV, event=7"):
        predict_energy(1.2, BrokenModel(), SobolConfig(power=8), HistogramSpec(bins=8))
