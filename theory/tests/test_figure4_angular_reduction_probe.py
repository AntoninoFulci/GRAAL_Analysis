"""Checks for diagnostic angular reconstruction and its phase-space measure."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from scipy.integrate import quad

from graal_theory.kinematics import invariant_mass, kallen, validate_final_state
from graal_theory.models.eta_pi0_p_full import FAMILY_NAMES
from graal_theory.constants import GEV2_TO_MICROBARN

MASSES = (.547862, .1349768, .93827208816)


def module():
    path = Path(__file__).resolve().parents[1]/"scripts/figure4_angular_reduction_probe.py"
    assert path.exists(), "angular reduction diagnostic missing"
    spec = importlib.util.spec_from_file_location("angular_probe", path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_fixed_mass_samples_preserve_invariants_and_helicity_angle():
    m = module()
    directions = np.array([[1., 0., 0.], [0., 1., 0.], [0., 0., 1.], [.6, 0., -.8]])
    chi = np.array([-.7, -.2, .1, .8])
    sample = m.fixed_mass_sample(1.9, MASSES, 1.54, directions, chi, .37)
    validate_final_state(sample.initial, sample.momenta, MASSES, atol=1e-12)
    np.testing.assert_allclose(invariant_mass(sample.momenta[:, 0]+sample.momenta[:, 2]), 1.54, atol=1e-12)
    pion = sample.momenta[:, 1, 1:]
    np.testing.assert_allclose(pion/np.linalg.norm(pion, axis=1)[:, None], directions, atol=1e-12)
    s = 1.54**2
    ep = (s+MASSES[2]**2-MASSES[0]**2)/(2*1.54)
    epi = (1.9**2-s-MASSES[1]**2)/(2*1.54)
    a = MASSES[2]**2+MASSES[1]**2+2*ep*epi
    b = np.sqrt(kallen(s,MASSES[2]**2,MASSES[0]**2)*kallen(1.9**2,s,MASSES[1]**2))/(2*s)
    actual = invariant_mass(sample.momenta[:, 1]+sample.momenta[:, 2])**2
    np.testing.assert_allclose(actual, a-b*chi, atol=1e-12)


def test_fixed_mass_density_agrees_with_independent_phase_space_integral():
    m = module()
    nodes, weights = np.polynomial.legendre.leggauss(24)
    lo, hi = 1.52**2, 1.56**2
    total = 0.
    for x, weight in zip(nodes, weights):
        sample = m.fixed_mass_sample(1.9, MASSES, np.sqrt((lo+hi+(hi-lo)*x)/2),
                                    [[1.,0.,0.]], 0., 0.)
        full_span = (1.9-MASSES[1])**2-(MASSES[0]+MASSES[2])**2
        total += sample.weights_gev2[0]/full_span*weight*(hi-lo)/2
    def density(s):
        return np.sqrt(kallen(1.9**2,s,MASSES[1]**2)*kallen(s,MASSES[2]**2,MASSES[0]**2))/(128*np.pi**3*1.9**2*s)
    assert total == pytest.approx(quad(density,lo,hi,epsabs=1e-13)[0], rel=1e-11)


def test_reconstruction_retains_complex_linear_terms_and_external_recoil_factor():
    m = module()
    anchors = m.fixed_mass_sample(1.9, MASSES, 1.54, np.eye(3), .2, .4)
    directions = np.array([[.36, .48, -.8], [-.6, 0., .8]])
    target = m.fixed_mass_sample(1.9, MASSES, 1.54, directions, -.3, 1.2)
    matrices = np.array([[[1, 2j],[3,4]], [[-1j,2],[.4,3j]], [[2,1],[-3j,.7]]])
    families = {name:matrices.copy() for name in FAMILY_NAMES}
    families["chiral_contact"][:] = matrices[0]
    # Independently form the recoil factor in Eq. 24.
    def recoil(sample):
        k = (1.9**2-MASSES[2]**2)/(2*1.9)
        pion = sample.momenta[:, 1]
        eout = np.sqrt(MASSES[2]**2+np.sum((pion[:,1:]+[0,0,k])**2,axis=1))
        return 1/(eout*(np.sqrt(MASSES[2]**2+k*k)-pion[:,0]-eout))
    families["external_pi0"] *= recoil(anchors)[:,None,None]
    actual = m.reconstruct_families(anchors, families, target, MASSES[2])
    expected = directions[:,0,None,None]*matrices[0]+directions[:,1,None,None]*matrices[1]+directions[:,2,None,None]*matrices[2]
    for name, value in actual.items():
        want = (np.broadcast_to(matrices[0], expected.shape) if name == "chiral_contact"
                else expected*recoil(target)[:,None,None] if name == "external_pi0" else expected)
        np.testing.assert_allclose(value, want, rtol=1e-12, atol=1e-12)
    assert "eq43_tree" not in actual
    other_mass = m.fixed_mass_sample(1.9, MASSES, 1.55, directions, .2, .4)
    with pytest.raises(ValueError, match="invariant"):
        m.reconstruct_families(anchors, families, other_mass, MASSES[2])


class InterferingConstantModel:
    masses = MASSES
    parameters = SimpleNamespace(proton_mass_gev=MASSES[2])

    def family_amplitudes(self, sample, epsilon):
        result = {name:np.zeros((len(sample.momenta),2,2),complex) for name in FAMILY_NAMES}
        result["chiral_contact"][:] = (1 if epsilon[0] else 2)*np.eye(2)
        result["eq43_tree"] = -.5*result["chiral_contact"]
        return result

    def selected_amplitude(self, sample, epsilon, families):
        assert families == ("eq43_tree",)
        return self.family_amplitudes(sample,epsilon)["eq43_tree"]


@pytest.mark.parametrize("energy,mass", [((1.1,1.2),(1.52,1.56)),((1.3,1.4),(1.70,1.80))])
def test_reduced_bin_preserves_flux_onset_and_coherent_interference(energy,mass):
    m = module()
    assert hasattr(m,"integrate_bin"), "reduced bin quadrature missing"
    model = InterferingConstantModel()
    rows = m.integrate_bin(model,energy,mass,energy_order=16,mass_order=16,angular_orders=(4,8))
    mp, meta, mpi = MASSES[2],MASSES[0],MASSES[1]
    onset = max(energy[0],((max(mass[0],mp+meta)+mpi)**2-mp**2)/(2*mp))
    def energy_density(e):
        s = mp*mp+2*mp*e
        lo,hi = max(mass[0],mp+meta)**2,min(mass[1],np.sqrt(s)-mpi)**2
        def density(z2):
            return np.sqrt(kallen(s,z2,mpi*mpi)*kallen(z2,mp*mp,meta*meta))/(128*np.pi**3*s*z2)
        return quad(density,lo,hi,epsabs=1e-12)[0]*GEV2_TO_MICROBARN*4*mp*mp/(2*(s-mp*mp))/(energy[1]-energy[0])
    measure = quad(energy_density,onset,energy[1],epsabs=1e-10)[0]
    for row in rows:
        assert row["denominator"] == pytest.approx(1.25*measure,rel=5e-5)
        assert row["numerator"] == pytest.approx(.75*measure,rel=5e-5)
        assert row["sigma"] == pytest.approx(.6,abs=1e-12)
    with pytest.raises(ValueError,match="1.80"):
        m.integrate_bin(model,(1.5,1.6),(1.79,1.82),energy_order=4,mass_order=4,angular_orders=(4,))
