"""Independent geometry and measure checks for the eta-pion projection."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from scipy.integrate import quad

from graal_theory.constants import GEV2_TO_MICROBARN
from graal_theory.figure4_integration import predict_figure4_bin
from graal_theory.kinematics import invariant_mass, kallen
from graal_theory.models.eta_pi0_p_full import FAMILY_NAMES
from graal_theory.phase_space import SobolConfig

MASSES = (.547862,.1349768,.93827208816)


def module():
    path = Path(__file__).resolve().parents[1]/"scripts/figure4_pair_projection_probe.py"
    assert path.exists(), "eta-pion angular projection missing"
    spec = importlib.util.spec_from_file_location("pair_probe",path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


@pytest.mark.parametrize("u,c",[(0.,.5),(.3,.5),(.5,.3),(.9,.3),(-.7,-.8),(.7,0.)])
def test_closed_azimuth_average_matches_explicit_uniform_azimuth(u,c):
    m = module()
    psi = 2*np.pi*(np.arange(65536)+.5)/65536
    b = np.sqrt(1-u*u)
    x = u*np.sqrt(1-c*c)+b*c*np.cos(psi)
    y = b*np.sin(psi)
    expected = np.mean((x*x-y*y)/(x*x+y*y))
    assert m.azimuth_cosine(u,b,c) == pytest.approx(expected,abs=2e-12)
    assert np.mean(2*x*y/(x*x+y*y)) == pytest.approx(0.,abs=1e-12)


def test_azimuth_average_limits_and_actual_boosted_proton():
    m = module()
    assert m.azimuth_cosine(1.,0.,.4) == pytest.approx(1.)
    assert m.azimuth_cosine(.5,.8,1.) == pytest.approx(0.)
    with pytest.raises(ValueError):
        m.azimuth_cosine(0.,0.,.4)
    for c,t in ((.3,-.7),(-.4,.2),(.8,.6)):
        psi = 2*np.pi*(np.arange(8192)+.5)/8192
        sample = m.angular.fixed_mass_sample(1.9,MASSES,1.54,
            np.tile([np.sqrt(1-c*c),0.,c],(len(psi),1)),t,psi)
        proton = sample.momenta[:,2,1:]
        phi = np.arctan2(proton[:,1],proton[:,0])
        a,b = m.proton_cone(1.9,MASSES,1.54,t)
        assert m.azimuth_cosine(a,b,c) == pytest.approx(np.mean(np.cos(2*phi)),abs=1e-10)


def test_eta_pion_clipping_and_mass_knots_preserve_support():
    m = module()
    segments = m.mass_segments(1.75,MASSES,(.72,.76),thresholds=(1.60936,))
    assert segments
    for low,high in segments:
        z = (low+high)/2
        a,b = m.helicity_window(1.75,MASSES,z,(.72,.76))
        t = np.linspace(a,b,17)
        sample = m.angular.fixed_mass_sample(1.75,MASSES,z,
                    np.tile([.6,0.,.8],(len(t),1)),t,.8)
        mass = invariant_mass(sample.momenta[:,0]+sample.momenta[:,1])
        assert np.all(mass >= .72-1e-12) and np.all(mass <= .76+1e-12)
    # The actual four-vectors at every crossing knot hit a selected mass edge.
    for z in sorted({v for segment in segments for v in segment}):
        if abs(z-1.60936) < 1e-12 or not sum((MASSES[0],MASSES[2])) < z < 1.75-MASSES[1]:
            continue
        sample = m.angular.fixed_mass_sample(1.75,MASSES,z,[[1.,0.,0.]]*2,[-1.,1.],0.)
        mass = invariant_mass(sample.momenta[:,0]+sample.momenta[:,1])
        assert min(abs(mass[:,None]-[.72,.76]).ravel()) < 1e-11
    assert m.mass_segments(1.75,MASSES,(.9,1.)) == []


class ConstantInterferenceModel:
    masses = MASSES
    parameters = SimpleNamespace(proton_mass_gev=MASSES[2],strong=SimpleNamespace(
        meson_masses_gev=(.49368,),baryon_masses_gev=(1.11568,)))

    def family_amplitudes(self,sample,epsilon):
        result = {name:np.zeros((len(sample.momenta),2,2),complex) for name in FAMILY_NAMES}
        result["chiral_contact"][:] = 2*np.eye(2)
        result["eq43_tree"][:] = -np.eye(2)
        return result

    def selected_amplitude(self,sample,epsilon,families):
        assert families == ("eq43_tree",)
        return self.family_amplitudes(sample,epsilon)["eq43_tree"]


@pytest.mark.parametrize("energy,mass",[((1.1,1.2),(.72,.76)),((1.0,1.1),(.72,.76))])
def test_projected_measure_matches_independent_eta_pion_mass_quadrature(energy,mass):
    m = module()
    assert hasattr(m,"integrate_eta_pi0"), "projected quadrature missing"
    rows = m.integrate_eta_pi0(ConstantInterferenceModel(),energy,mass,
                             energy_order=16,mass_order=12,angular_orders=(4,8))
    meta,mpi,mp = MASSES
    lo = max(mass[0],meta+mpi)
    onset = max(energy[0],((lo+mp)**2-mp*mp)/(2*mp))
    def energy_density(e):
        s = mp*mp+2*mp*e
        hi = min(mass[1],np.sqrt(s)-mp)
        def density(y):
            return np.sqrt(kallen(s,y,mp*mp)*kallen(y,meta*meta,mpi*mpi))/(128*np.pi**3*s*y)
        return quad(density,lo*lo,hi*hi,epsabs=1e-13)[0]*GEV2_TO_MICROBARN*4*mp*mp/(2*(s-mp*mp))/(energy[1]-energy[0])
    transition = ((mass[1]+mp)**2-mp*mp)/(2*mp)
    points = [transition] if onset < transition < energy[1] else None
    expected = 2*quad(energy_density,onset,energy[1],points=points,epsabs=1e-11)[0]
    for row in rows:
        assert row["denominator"] == pytest.approx(expected,rel=3e-5)
        assert row["numerator"] == pytest.approx(0.,abs=1e-14)


def test_nonzero_projected_numerator_matches_independent_eta_pion_sampling():
    class PionDipole(ConstantInterferenceModel):
        def amplitude(self, sample, epsilon):
            return (sample.momenta[:,1,1:]@epsilon)[:,None,None]*np.eye(2)

        def family_amplitudes(self, sample, epsilon):
            result = {name:np.zeros((len(sample.momenta),2,2),complex) for name in FAMILY_NAMES}
            result["internal_pi0"] = self.amplitude(sample,epsilon)
            return result

        def selected_amplitude(self, sample, epsilon, families):
            assert families == ("eq43_tree",)
            return np.zeros((len(sample.momenta),2,2),complex)

    m = module()
    model = PionDipole()
    row = m.integrate_eta_pi0(model,(1.1,1.2),(.72,.76),energy_order=4,
                             mass_order=12,angular_orders=(16,))[0]
    reference = predict_figure4_bin(model,"eta_pi0",(1.1,1.2),(.72,.76),
                                   energy_order=4,sobol=SobolConfig(17))
    assert abs(row["sigma"]) > .01
    assert row["numerator"] == pytest.approx(reference.numerator,rel=3e-4)
    assert row["denominator"] == pytest.approx(reference.denominator,rel=3e-4)


def test_unsupported_mass_domain_rejected_before_evaluating_amplitudes():
    class NoEvaluation(ConstantInterferenceModel):
        def family_amplitudes(self, *args):
            raise AssertionError("amplitudes evaluated before support guard")

    m = module()
    with pytest.raises(ValueError,match="throughout support"):
        m.integrate_eta_pi0(NoEvaluation(),(1.8,1.9),(.72,.76),
                           energy_order=2,mass_order=2,angular_orders=(2,))
    # Nearby lower energy stays within the documented eta-p ceiling.
    rows = m.integrate_eta_pi0(ConstantInterferenceModel(),(1.4,1.5),(.72,.76),
                              energy_order=2,mass_order=2,angular_orders=(2,))
    assert rows[0]["denominator"] > 0
