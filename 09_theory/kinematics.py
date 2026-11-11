"""Canonical three-body kinematics, metric (+---), energies/masses in GeV.

The invariant phase-space convention is independent of the still-unresolved
normalization of the Fix amplitudes. See fix2010-derivation.md for derivation.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
from graal_common.physics.channels import M_ETA, M_PI0, M_PROTON

MASS_BOUNDARY_TOLERANCE_GEV = 1e-12
FourVector = tuple[float, float, float, float]


@dataclass(frozen=True)
class Masses:
    proton: float = M_PROTON
    pi0: float = M_PI0
    eta: float = M_ETA

    def __post_init__(self):
        if not all(math.isfinite(m) and m > 0 for m in (self.proton,self.pi0,self.eta)):
            raise ValueError('stable masses must be positive finite GeV values')


@dataclass(frozen=True)
class PhaseSpacePoint:
    egamma_gev: float
    w_gev: float
    omega_gamma_gev: float
    m_pi_p_gev: float
    cos_theta_eta: float
    cos_theta_pi_star: float
    phi_pi_star_rad: float
    masses: Masses
    eta: FourVector
    pi: FourVector
    proton: FourVector
    pi_star: FourVector
    # Order: pi_p, eta_p, pi_eta; units GeV².
    pair_mass_squared: tuple[float, float, float]


def boost(vector: FourVector, beta: tuple[float,float,float]) -> FourVector:
    """Active rotation-free boost: rest vector gains momentum +gamma*m*beta."""
    if len(vector) != 4 or len(beta) != 3 or not all(math.isfinite(x) for x in (*vector,*beta)):
        raise ValueError('boost requires finite four-vector and three-velocity')
    b2=sum(b*b for b in beta)
    if b2 >= 1: raise ValueError('boost velocity must be subluminal')
    if b2 == 0: return tuple(vector)
    gamma=1/math.sqrt(1-b2)
    bp=sum(b*p for b,p in zip(beta,vector[1:]))
    # (gamma-1)/beta² = gamma²/(gamma+1), stable for tiny beta.
    factor=gamma*vector[0]+gamma*gamma/(gamma+1)*bp
    return (gamma*(vector[0]+bp),*(p+factor*b for p,b in zip(vector[1:],beta)))


def two_body_momentum(parent: float, first: float, second: float) -> float:
    """Physical breakup momentum; no unstable-isobar nominal threshold imposed."""
    if not all(math.isfinite(v) for v in (parent,first,second)) or parent <= 0 or min(first,second)<0:
        raise ValueError('invalid two-body masses')
    threshold=first+second
    if parent < threshold-MASS_BOUNDARY_TOLERANCE_GEV:
        raise ValueError('below physical two-body threshold')
    if parent <= threshold: return 0.
    product=(parent-threshold)*(parent+threshold)*(parent-first+second)*(parent+first-second)
    return math.sqrt(product)/(2*parent)


def _pair_squared(a,b):
    return (a[0]+b[0])**2-sum((x+y)**2 for x,y in zip(a[1:],b[1:]))


def make_point(egamma_gev, m_pi_p_gev, cos_theta_eta, cos_theta_pi_star,
               phi_pi_star_rad, *, masses: Masses) -> PhaseSpacePoint:
    """Build eta+(pi p) in K frame; y parallel eta×beam, eta_x <= 0.

    Phi_eta is fixed by rotational choice. At collinear configurations use
    the limiting axes. Pair-rest pion angles refer to these same canonical axes.
    Only mass roundoff <=1e-12 GeV is reconciled, explicitly in returned mass.
    """
    values=(egamma_gev,m_pi_p_gev,cos_theta_eta,cos_theta_pi_star,phi_pi_star_rad)
    if not all(math.isfinite(x) for x in values): raise ValueError('nonfinite coordinate')
    if not 1 <= egamma_gev <= 1.4: raise ValueError('energy outside [1.0,1.4] GeV')
    if abs(cos_theta_eta)>1 or abs(cos_theta_pi_star)>1: raise ValueError('unphysical cosine')
    W=math.sqrt(masses.proton**2+2*masses.proton*egamma_gev)
    lower=masses.proton+masses.pi0; upper=W-masses.eta
    if upper < lower: raise ValueError('below three-body threshold')
    if m_pi_p_gev < lower-MASS_BOUNDARY_TOLERANCE_GEV or m_pi_p_gev > upper+MASS_BOUNDARY_TOLERANCE_GEV:
        raise ValueError('pair mass outside Dalitz support')
    m=min(upper,max(lower,m_pi_p_gev))
    q=two_body_momentum(W,masses.eta,m)
    # Compute endpoint momentum as exact zero instead of sqrt(roundoff).
    if m == upper: q=0.
    p=two_body_momentum(m,masses.pi0,masses.proton)
    qvec=(-q*math.sqrt(1-cos_theta_eta**2),0.,q*cos_theta_eta)
    eta=(math.hypot(masses.eta,q),*qvec)
    pair_energy=math.hypot(m,q)
    beta=tuple(-a/pair_energy for a in qvec)
    st=math.sqrt(1-cos_theta_pi_star**2)
    pvec=(p*st*math.cos(phi_pi_star_rad),p*st*math.sin(phi_pi_star_rad),p*cos_theta_pi_star)
    pi_star=(math.hypot(masses.pi0,p),*pvec)
    proton_star=(math.hypot(masses.proton,p),*(-v for v in pvec))
    pi=boost(pi_star,beta); proton=boost(proton_star,beta)
    invariants=(_pair_squared(pi,proton),_pair_squared(eta,proton),_pair_squared(pi,eta))
    return PhaseSpacePoint(egamma_gev,W,(W*W-masses.proton**2)/(2*W),m,
                           cos_theta_eta,cos_theta_pi_star,phi_pi_star_rad,masses,
                           eta,pi,proton,pi_star,invariants)


def phase_space_density(point: PhaseSpacePoint) -> float:
    """dΦ3/(dm dcosTheta_eta dcosTheta_pi* dphi_pi*), in GeV.

    Overall eta azimuth already integrated (2π). Use only when the integrand
    is invariant under that rotation, including any polarization axes.
    """
    q=math.sqrt(sum(v*v for v in point.eta[1:]))
    p=math.sqrt(sum(v*v for v in point.pi_star[1:]))
    return q*p/(128*math.pi**4*point.w_gev)
