"""Physical four-vector oracles for the packaged three-pair geometry."""
import importlib
import importlib.util

import numpy as np
import pytest

from graal_theory.figure4_integration import PAIR_DAUGHTERS
from graal_theory.kinematics import invariant_mass

MASSES = (.547862, .1349768, .93827208816)


def geometry():
    assert importlib.util.find_spec('graal_theory.angular_geometry') is not None, 'packaged angular geometry missing'
    return importlib.import_module('graal_theory.angular_geometry')


@pytest.mark.parametrize('pair,target', [('p_eta',(1.50,1.60)),
    ('p_pi0',(1.10,1.30)),('eta_pi0',(.72,.76))])
def test_selected_mass_clipping_matches_four_vectors(pair,target):
    g = geometry()
    segments = g.mass_segments(1.75,MASSES,pair,target,thresholds=(1.60936,))
    assert segments
    for lo,hi in segments:
        z = (lo+hi)/2
        a,b = g.helicity_window(1.75,MASSES,z,pair,target)
        t = np.linspace(a,b,19)
        sample = g.fixed_mass_sample(1.75,MASSES,z,[[.6,0.,.8]]*len(t),t,.8)
        i,j = PAIR_DAUGHTERS[pair]
        measured = invariant_mass(sample.momenta[:,i]+sample.momenta[:,j])
        assert measured.min() >= target[0]-1e-12
        assert measured.max() <= target[1]+1e-12
    # All internal knots except explicit thresholds must hit a target edge.
    for z in sorted({x for interval in segments for x in interval}):
        if abs(z-1.60936)<1e-12 or not MASSES[0]+MASSES[2]<z<1.75-MASSES[1]:
            continue
        sample = g.fixed_mass_sample(1.75,MASSES,z,[[1.,0.,0.]]*2,[-1.,1.],.3)
        measured = invariant_mass(sample.momenta[:,i]+sample.momenta[:,j])
        assert np.min(abs(measured[:,None]-target)) < 1e-11


@pytest.mark.parametrize('pair',PAIR_DAUGHTERS)
def test_pair_azimuth_average_uses_actual_spectator_boost(pair):
    g = geometry()
    psi=2*np.pi*(np.arange(32768)+.5)/32768
    for c,t in ((.3,-.7),(-.4,.2),(.8,.6)):
        sample=g.fixed_mass_sample(1.9,MASSES,1.54,
            np.tile([np.sqrt(1-c*c),0.,c],(len(psi),1)),t,psi)
        i,j=PAIR_DAUGHTERS[pair]
        p=sample.momenta[:,i]+sample.momenta[:,j]
        phi=np.arctan2(p[:,2],p[:,1])
        a,b=g.spectator_cone(1.9,MASSES,1.54,t,pair)
        assert g.azimuth_cosine(a,b,c)==pytest.approx(np.mean(np.cos(2*phi)),abs=1e-10)
        assert np.mean(np.sin(2*phi))==pytest.approx(0.,abs=1e-12)


def test_empty_support_and_unknown_pair_are_explicit():
    g=geometry()
    assert g.mass_segments(1.75,MASSES,'eta_pi0',(.9,1.))==[]
    with pytest.raises(ValueError,match='pair'):
        g.mass_segments(1.75,MASSES,'invalid',(.72,.76))
