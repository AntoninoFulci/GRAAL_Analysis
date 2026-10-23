"""Angular basis against independent phase space and complete complex amplitudes."""
from dataclasses import dataclass, replace
from types import SimpleNamespace
from pathlib import Path

import numpy as np
import pytest

from graal_theory.constants import GEV2_TO_MICROBARN
from graal_theory.models.eta_pi0_p_full import FAMILY_NAMES
from graal_theory.phase_space import SobolConfig, sample_three_body_mass_window
from graal_theory.photon_flux import FluxSpectrum, PhotonExposure


@dataclass(frozen=True)
class Toy:
    g1: float = .2
    g2: float = -.1
    masses = (.547862, .1349768, .93827208816)

    @property
    def parameters(self):
        return SimpleNamespace(proton_mass_gev=self.masses[2],
            tree=SimpleNamespace(g1_prime=self.g1,g2_prime=self.g2),
            strong=SimpleNamespace(meson_masses_gev=(),baryon_masses_gev=()))

    def family_amplitudes(self, sample, epsilon):
        result = {name:np.zeros((len(sample.momenta),2,2),complex) for name in FAMILY_NAMES}
        # Source/offset interference and H/V interference both survive.
        result['chiral_contact'][:] = (1+self.g1+.3j*self.g2)*(1 if epsilon[0] else 2)*np.eye(2)
        result['eq43_tree'] = self.selected_amplitude(sample,epsilon,('eq43_tree',))
        return result

    def selected_amplitude(self,sample,epsilon,families):
        assert families == ('eq43_tree',)
        value = (-.3+.2j+.4*self.g2)*(1 if epsilon[0] else 1.5)*np.eye(2)
        return np.broadcast_to(value,(len(sample.momenta),2,2)).copy()


@pytest.fixture
def angular(monkeypatch):
    from graal_theory import angular_basis as module
    monkeypatch.setattr(module, '_basis_models', lambda m: (m,replace(m,g1=m.g1+1),replace(m,g2=m.g2+1)))
    monkeypatch.setattr(module, '_fingerprint', lambda *args: 'toy-fixed')
    return module


@pytest.mark.parametrize('pair,target', [('p_pi0',(1.12,1.16)),('p_eta',(1.52,1.56)),('eta_pi0',(.72,.76))])
def test_complete_angular_basis_measure_matches_independent_sobol(angular,pair,target):
    from graal_theory.figure4_integration import PAIR_DAUGHTERS, project_azimuth_averaged_moments
    model = Toy()
    result = angular.integrate_angular_basis_bin(model,pair,(1.1,1.2),target,
        energy_rule='uniform',energy_order=4,mass_order=12,angular_order=12)
    en,ew = np.polynomial.legendre.leggauss(4)
    for shifts in [(0.,0.),(.08,-.04)]:
        candidate = replace(model,g1=model.g1+shifts[0],g2=model.g2+shifts[1])
        n=d=0.
        for e,weight in zip(1.15+.05*en,ew/2):
            s=model.masses[2]**2+2*model.masses[2]*e
            sample=sample_three_body_mass_window(np.sqrt(s),model.masses,PAIR_DAUGHTERS[pair],target,
                SobolConfig(15),reduce_global_azimuth=True)
            # The noncovariant toy is defined in the pion-azimuth-zero frame.
            # Rotate the independent selected-pair Sobol sample into that frame.
            pion_phi = np.arctan2(sample.momenta[:,1,2],sample.momenta[:,1,1])
            momenta = sample.momenta.copy()
            x,y = sample.momenta[:,:,1], sample.momenta[:,:,2]
            momenta[:,:,1] = np.cos(pion_phi)[:,None]*x+np.sin(pion_phi)[:,None]*y
            momenta[:,:,2] = -np.sin(pion_phi)[:,None]*x+np.cos(pion_phi)[:,None]*y
            sample = replace(sample,momenta=momenta)
            pair_p=sample.momenta[:,PAIR_DAUGHTERS[pair][0]]+sample.momenta[:,PAIR_DAUGHTERS[pair][1]]
            phi=np.arctan2(pair_p[:,2],pair_p[:,1])
            v,h=[np.add.reduce(tuple(candidate.family_amplitudes(sample,np.array(eps)).values()))
                 for eps in ([0.,1.,0.],[1.,0.,0.])]
            measure=sample.weights_gev2*GEV2_TO_MICROBARN*4*model.masses[2]**2/(2*(s-model.masses[2]**2)*len(phi))
            a,b=project_azimuth_averaged_moments(phi,v,h,measure)
            n+=weight*a; d+=weight*b
        prediction=result.evaluate([1.,*shifts])
        assert prediction.denominator == pytest.approx(d,rel=4e-4)
        assert prediction.intrinsic_sigma == pytest.approx(n/d,abs=8e-4)
        assert target[0] < result.weighted_mass_gev([1.,*shifts]) < target[1]


def test_angular_native_counts_preserve_full_exposure_below_onset(angular):
    model=Toy()
    spectrum=FluxSpectrum((1.1,1.2),(
        PhotonExposure(1.11,100.,150.,.6,.4),PhotonExposure(1.19,200.,250.,.7,.5)),2,2,0,Path("flux"),Path("manifest"))
    target=(1.62,1.64)
    result=angular.integrate_angular_basis_bin(model,'p_eta',(1.1,1.2),target,
        energy_rule='native_flux',energy_order=2,mass_order=8,angular_order=4,
        flux_spectrum=spectrum,phi_bins=8,phi_bin_divisor=.9003)
    assert result.flux_vertical == 300.
    assert result.flux_horizontal == 400.
    assert result.state_phi.shape == (2,8,3,3)
    assert result.energy_nodes_gev == pytest.approx([1.19])
    assert np.isfinite(result.evaluate([1.,.08,-.04]).sigma)


def test_full_domain_guard_precedes_amplitudes(angular,monkeypatch):
    monkeypatch.setattr(Toy,'family_amplitudes',lambda *args:pytest.fail('amplitudes evaluated before domain guard'))
    result=angular.integrate_angular_basis_bin(Toy(),'p_eta',(1.5,1.6),(1.79,1.82),
        energy_rule='uniform',energy_order=2,mass_order=2,angular_order=2)
    assert result.status == 'masked_unsupported_domain'


def test_physical_angular_basis_matches_direct_off_source_amplitudes():
    from graal_theory.angular_basis import AngularBasisIntegrator
    from graal_theory.angular_geometry import fixed_mass_sample
    from graal_theory.cli import _figure4_model
    references=Path(__file__).resolve().parents[1]/'references'
    model=_figure4_model(references,'direct',64,48)
    integrator=AngularBasisIntegrator(model)
    # Distinct polar directions and internal azimuths at the same invariant mass.
    sample=fixed_mass_sample(1.82,model.masses,1.54,[[.6,0.,.8],[.8,0.,-.6]],[-.4,.7],[.3,1.8])
    v,h=integrator.event_basis(1.82,1.54,sample)
    for shifts in ((0.,0.),(.04,-.03)):
        candidate=replace(model,parameters=replace(model.parameters,tree=replace(model.parameters.tree,
            g1_prime=model.parameters.tree.g1_prime+shifts[0],
            g2_prime=model.parameters.tree.g2_prime+shifts[1])))
        for basis,epsilon in zip((v,h),([0.,1.,0.],[1.,0.,0.])):
            direct=candidate.amplitude(sample,np.asarray(epsilon))
            actual=np.einsum('a,anij->nij',[1.,*shifts],basis)
            np.testing.assert_allclose(actual,direct,rtol=2e-9,atol=2e-10)
