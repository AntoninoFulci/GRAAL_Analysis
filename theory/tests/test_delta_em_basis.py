"""Exact Delta(1700) electromagnetic basis against the coherent model."""

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from graal_theory.models.delta_em_basis import delta_em_event_basis
from graal_theory.models.eta_pi0_p_full import EtaPi0PFullModel
from graal_theory.phase_space import SobolConfig, sample_three_body


REFERENCES = Path(__file__).resolve().parents[1] / "references"
HORIZONTAL = np.array([1.0, 0.0, 0.0])
VERTICAL = np.array([0.0, 1.0, 0.0])


@pytest.fixture(scope="module")
def model():
    return EtaPi0PFullModel.from_files(REFERENCES)


def _one_event(model, sqrt_s):
    sampled = sample_three_body(sqrt_s, model.masses, SobolConfig(4))
    chosen = np.array([7])
    return replace(sampled, initial=sampled.initial[chosen],
                   momenta=sampled.momenta[chosen],
                   weights_gev2=sampled.weights_gev2[chosen],
                   s12_gev2=sampled.s12_gev2[chosen])


@pytest.mark.parametrize("sqrt_s", [1.82, 1.90])
@pytest.mark.parametrize("polarization", [HORIZONTAL, VERTICAL], ids=["H", "V"])
def test_basis_reconstructs_direct_full_spin_matrix_off_source(model, sqrt_s, polarization):
    sample = _one_event(model, sqrt_s)
    basis = delta_em_event_basis(model, sample, polarization)
    assert basis.matrices.shape == (3, 1, 2, 2)
    assert basis.matrices.dtype == np.dtype(np.complex128)
    assert not basis.matrices.flags.writeable
    source_g1 = model.parameters.tree.g1_prime
    source_g2 = model.parameters.tree.g2_prime
    for g1, g2 in ((source_g1, source_g2),
                   (source_g1 + 0.04, source_g2 - 0.03),
                   (source_g1 - 0.06, source_g2 + 0.05)):
        parameters = replace(model.parameters, tree=replace(
            model.parameters.tree, g1_prime=g1, g2_prime=g2))
        direct = EtaPi0PFullModel(parameters).amplitude(sample, polarization)
        np.testing.assert_allclose(basis.reconstruct(g1, g2), direct,
                                   rtol=1e-10, atol=1e-10)


def test_basis_rejects_changed_fixed_physics(model):
    basis = delta_em_event_basis(model, _one_event(model, 1.82), HORIZONTAL)
    p = model.parameters
    changed_width = replace(p, tree=replace(p.tree, width_parameters=replace(
        p.tree.width_parameters, n_pi_branching_fraction=0.16)))
    changed_strong = replace(p, strong=replace(p.strong, subtraction_constants=(
        p.strong.subtraction_constants[0] + 0.001, *p.strong.subtraction_constants[1:])))
    changed_production = replace(p, production=replace(
        p.production, electric_charge=p.production.electric_charge + 0.001))
    for parameters in (changed_width, changed_strong, changed_production):
        with pytest.raises(ValueError, match="fixed|fingerprint|match"):
            basis.validate_model(EtaPi0PFullModel(parameters))
    varied_em = replace(p, tree=replace(p.tree, g1_prime=p.tree.g1_prime + 0.01))
    basis.validate_model(EtaPi0PFullModel(varied_em))
