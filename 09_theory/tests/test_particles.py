import pytest

from graal_theory.particles import Particle
from graal_theory.sources import SourceRef


SOURCE = SourceRef("paper", "10.1/example", "Table I")


def test_particle_rejects_nonphysical_mass():
    with pytest.raises(ValueError, match="mass_gev"):
        Particle("bad", 0.0, 0.0, SOURCE)


def test_particle_rejects_negative_width():
    with pytest.raises(ValueError, match="width_gev"):
        Particle("bad", 1.0, -0.1, SOURCE)


def test_particle_preserves_physical_properties():
    particle = Particle("p", 0.938, 0.0, SOURCE)
    assert particle.mass_gev == 0.938
    assert particle.source.locator == "Table I"
