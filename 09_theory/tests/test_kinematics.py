"""Conservation, analytic limits and independent Dalitz-area phase volume."""
import math
import random
import numpy as np
import pytest
from numpy.polynomial.legendre import leggauss


def invariant(v):
    return v[0]**2-sum(x*x for x in v[1:])


def test_conservation_and_invariants():
    from graal_theory.kinematics import make_point, Masses
    masses=Masses()
    rng=random.Random(1905)
    for energy in [1.,1.2,1.4]:
        W=math.sqrt(masses.proton**2+2*masses.proton*energy)
        for _ in range(20):
            m=rng.uniform(masses.pi0+masses.proton,W-masses.eta)
            point=make_point(energy,m,rng.uniform(-1,1),rng.uniform(-1,1),rng.uniform(-math.pi,math.pi),masses=masses)
            vectors=[point.eta,point.pi,point.proton]
            for p,mass in zip(vectors,[masses.eta,masses.pi0,masses.proton]):
                assert invariant(p)==pytest.approx(mass**2,abs=1e-10)
            assert np.sum(vectors,axis=0)==pytest.approx([W,0,0,0],abs=1e-10)
            assert sum(point.pair_mass_squared)==pytest.approx(W**2+masses.eta**2+masses.pi0**2+masses.proton**2,abs=1e-10)
            assert point.pair_mass_squared[0]==pytest.approx(m*m,abs=1e-10)
            # Check the published canonical boost relation (2010 Eq.7), independently.
            pstar=np.asarray(point.pi_star)
            X=-(pstar[0]+point.pi[0])/(m+W-point.eta[0])
            assert np.asarray(point.pi[1:])==pytest.approx(pstar[1:]+X*np.asarray(point.eta[1:]),abs=1e-10)
    assert W**2==pytest.approx(masses.proton**2+2*masses.proton*1.4,abs=1e-10)


def test_boost_roundtrip_and_zero():
    from graal_theory.kinematics import boost
    v=(2.,.1,.2,1.2)
    for beta in [(0,0,0),(.2,-.3,.1),(0,0,.7)]:
        b=boost(v,beta)
        assert invariant(b)==pytest.approx(invariant(v),abs=1e-10)
        assert boost(b,tuple(-x for x in beta))==pytest.approx(v,abs=1e-10)
    with pytest.raises(ValueError): boost(v,(1.,0,0))
    with pytest.raises(ValueError): boost(v,(float('nan'),0,0))


@pytest.mark.parametrize('field,value', [('egamma_gev',.99),('egamma_gev',1.41),('egamma_gev',float('nan')),('m_pi_p_gev',1.),('m_pi_p_gev',1.8),('cos_theta_eta',1.00001),('cos_theta_pi_star',-1.01),('phi_pi_star_rad',float('inf'))])
def test_invalid_point(field,value):
    from graal_theory.kinematics import make_point,Masses
    args=dict(egamma_gev=1.2,m_pi_p_gev=1.15,cos_theta_eta=.2,cos_theta_pi_star=-.3,phi_pi_star_rad=.7,masses=Masses())
    args[field]=value
    with pytest.raises(ValueError): make_point(**args)


def test_edges_and_no_stable_delta_threshold():
    from graal_theory.kinematics import make_point,Masses,phase_space_density
    masses=Masses()
    W=math.sqrt(masses.proton**2+2*masses.proton*1.)
    assert W < masses.eta+1.232
    assert phase_space_density(make_point(1.,1.1,1.,-1.,0.,masses=masses))>0
    for m in [masses.proton+masses.pi0,W-masses.eta]:
        p=make_point(1.,m,-1.,1.,0.,masses=masses)
        assert phase_space_density(p)==pytest.approx(0.,abs=1e-12)
    # Only a documented floating tolerance, never an actual nonphysical interval.
    p=make_point(1.,masses.proton+masses.pi0-1e-13,0.,0.,0.,masses=masses)
    assert p.m_pi_p_gev==masses.proton+masses.pi0
    with pytest.raises(ValueError): make_point(1.,masses.proton+masses.pi0-1e-8,0.,0.,0.,masses=masses)


def test_phase_volume_independent_dalitz_and_convergence():
    from graal_theory.kinematics import make_point,Masses,phase_space_density
    m=Masses(); E=1.2; W=math.sqrt(m.proton*m.proton+2*m.proton*E)
    lo=m.pi0+m.proton; hi=W-m.eta
    volumes=[]
    for order in [32,64,96]:
        x,w=leggauss(order)
        volume=sum(weight*phase_space_density(make_point(E,(lo+hi)/2+(hi-lo)*node/2,.3,-.2,.8,masses=m)) for node,weight in zip(x,w))*(hi-lo)/2*8*math.pi
        volumes.append(volume)
    # Independent integration in invariant s and Dalitz t extent, no density helper.
    # Endpoint substitution s=lo²+(hi²-lo²)*sin²(u) smooths square roots.
    x,w=leggauss(96); integral=0.
    for node,weight in zip(x,w):
        u=(node+1)*math.pi/4
        s=lo*lo+(hi*hi-lo*lo)*math.sin(u)**2
        Epi=(s+m.pi0**2-m.proton**2)/(2*math.sqrt(s))
        Eeta=(W**2-s-m.eta**2)/(2*math.sqrt(s))
        t_extent=4*math.sqrt(max(0,Epi**2-m.pi0**2))*math.sqrt(max(0,Eeta**2-m.eta**2))
        integral+=weight*t_extent*(hi*hi-lo*lo)*math.sin(2*u)*math.pi/4
    independent=integral/(128*math.pi**3*W**2)
    assert volumes[-1]==pytest.approx(independent,rel=1e-6)
    assert abs(volumes[-1]-independent)<abs(volumes[0]-independent)


def test_massless_phase_volume_analytic():
    from graal_theory.kinematics import two_body_momentum
    # Analytic Φ3(W;0,0,0)=W²/(256π³), using factorized angular integral.
    W=2.; x,w=leggauss(20)
    integral=0.
    for node,weight in zip(x,w):
        mass=(node+1)*W/2
        integral+=weight*two_body_momentum(W,mass,0)*two_body_momentum(mass,0,0)/(16*math.pi**3*W)*W/2
    assert integral==pytest.approx(W**2/(256*math.pi**3),rel=1e-13)
