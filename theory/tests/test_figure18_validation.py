"""Independent fixed-energy mass-density check for PRC73 Figure 18."""

from types import SimpleNamespace

import numpy as np
import pytest
from scipy.integrate import quad

from graal_theory.constants import GEV2_TO_MICROBARN
from graal_theory.figure18_reference import Figure18Point
from graal_theory.figure18_validation import (
    compare_figure18_point, predict_figure18_density,
)
from graal_theory.kinematics import kallen
from graal_theory.phase_space import SobolConfig


class ConstantModel:
    masses = (.547862, .1349768, .93827208816)
    parameters = SimpleNamespace(proton_mass_gev=masses[2])

    def matrix_element_squared(self, sample):
        return np.ones(len(sample.momenta))


def test_fixed_energy_density_has_unpolarized_flux_and_mass_jacobian():
    model = ConstantModel()
    low, high = 1.60, 1.64
    proton, eta, pion = model.masses[2], model.masses[0], model.masses[1]
    s = proton**2+2*proton*1.7
    flux = GEV2_TO_MICROBARN*4*proton**2/(2*(s-proton**2))

    def independent_density(s_pair):
        first = np.sqrt(kallen(s, s_pair, pion**2, atol=1e-12))
        second = np.sqrt(kallen(s_pair, eta**2, proton**2, atol=1e-12))
        return first*second/(128*np.pi**3*s*s_pair)

    expected = flux*quad(independent_density, low**2, high**2,
                         epsabs=1e-12)[0]/(high-low)
    actual = predict_figure18_density(model, (low, high), SobolConfig(10))
    assert actual == pytest.approx(expected, rel=.005)


def test_coherent_model_eliminates_redundant_global_azimuth():
    class CoherentConstantModel(ConstantModel):
        def amplitude(self, sample, epsilon):
            return np.broadcast_to(np.eye(2, dtype=complex),
                                   (len(sample.momenta), 2, 2))

        def matrix_element_squared(self, sample):
            self.sample = sample
            return super().matrix_element_squared(sample)

    model = CoherentConstantModel()
    predict_figure18_density(model, (1.60, 1.64), SobolConfig(4))
    spectator = model.sample.momenta[:, 1]
    assert np.allclose(spectator[:, 2], 0., rtol=0, atol=1e-14)


def test_source_ceiling_and_independent_reading_bound_are_enforced():
    with pytest.raises(ValueError, match="1.80"):
        predict_figure18_density(ConstantModel(), (1.79, 1.81), SobolConfig(4))
    point = Figure18Point(1.65, 16.0, 2.0)
    assert compare_figure18_point(point, 17.0, .5) == "compatible"
    assert compare_figure18_point(point, 19.0, .5) == "discrepant"
    assert compare_figure18_point(point, None, None) == "masked"
