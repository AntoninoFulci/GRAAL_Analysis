"""6C kinematic fit for gamma p -> p eta pi0.

The reconstruction measures four photons, the recoil proton, and the tagged
beam energy, each with a resolution. The event should conserve 4-momentum and
the two photon pairs should sit exactly on the eta and pi0 masses; measured, it
never quite does. This fit finds the smallest adjustment -- in units of the
resolution -- that makes it, by minimising

    chi2 = (y - eta)^T V^-1 (y - eta)   subject to   f(eta) = 0

with y the measured parameters, V their (diagonal) covariance, and f the six
constraints. It returns the adjusted 4-vectors and the fit chi2, whose value on
true signal follows chi2(6) -- the basis of the confidence-level cut that
replaces the missing-mass window.

Pure numpy: the parametrisation is (E, theta, phi) per photon, (P, theta, phi)
for the proton (E = sqrt(P^2 + m_p^2)), and E for the beam (along z). That keeps
the covariance diagonal and equal to the smearing model in smearing.h.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import chi2 as _chi2dist

from graal_common.channels import M_PROTON, Hypothesis
from graal_common.pairing import Pairing

_DEG = np.pi / 180.0


@dataclass(frozen=True)
class FitCovariance:
    """Per-measurement sigmas, straight from smearing.h.

    photon_E_rel and proton_P_rel are relative (sigma = rel * value); the angular
    sigmas are absolute [rad]; beam_E is absolute [GeV].
    """

    photon_E_rel: float = 0.10
    photon_theta: float = 5 * _DEG
    photon_phi: float = 3 * _DEG
    proton_P_rel: float = 0.04
    proton_theta: float = 3 * _DEG
    proton_phi: float = 2 * _DEG
    beam_E: float = 0.016


@dataclass
class FitResult:
    fitted_photons: np.ndarray   # (4, 4) [px, py, pz, E]
    fitted_proton: np.ndarray    # (4,)
    chi2: float
    ndf: int
    converged: bool
    fitted_cov: np.ndarray       # (16,) diagonal of V_eta, same param order as V


def confidence_level(chi2_value: float, ndf: int) -> float:
    """Probability that a correct fit would give a chi2 this large or larger."""
    return float(_chi2dist.sf(chi2_value, ndf))


# --- parameter <-> 4-vector conversions ---------------------------------------
# params layout (16,): [E,theta,phi] x4 photons, [P,theta,phi] proton, [E] beam.

def _vectors_to_params(photons: np.ndarray, proton: np.ndarray,
                       beam: np.ndarray) -> np.ndarray:
    p = np.zeros(16)
    for i in range(4):
        px, py, pz, E = photons[i]
        p[3 * i] = E
        p[3 * i + 1] = np.arccos(np.clip(pz / max(E, 1e-12), -1, 1))
        p[3 * i + 2] = np.arctan2(py, px)
    P = np.sqrt((proton[:3] ** 2).sum())
    p[12] = P
    p[13] = np.arccos(np.clip(proton[2] / max(P, 1e-12), -1, 1))
    p[14] = np.arctan2(proton[1], proton[0])
    p[15] = beam[3]
    return p


def _params_to_vectors(p: np.ndarray):
    photons = np.zeros((4, 4))
    for i in range(4):
        E, th, ph = p[3 * i], p[3 * i + 1], p[3 * i + 2]
        s = np.sin(th)
        photons[i] = [E * s * np.cos(ph), E * s * np.sin(ph), E * np.cos(th), E]
    P, thp, php = p[12], p[13], p[14]
    Ep = np.sqrt(P ** 2 + M_PROTON ** 2)
    s = np.sin(thp)
    proton = np.array([P * s * np.cos(php), P * s * np.sin(php), P * np.cos(thp), Ep])
    Eb = p[15]
    beam = np.array([0.0, 0.0, Eb, Eb])
    return photons, proton, beam


def _covariance_diag(p: np.ndarray, cov: FitCovariance) -> np.ndarray:
    """Diagonal of V, in the same order as the params, evaluated at measured p."""
    v = np.zeros(16)
    for i in range(4):
        E = p[3 * i]
        v[3 * i] = (cov.photon_E_rel * E) ** 2
        v[3 * i + 1] = cov.photon_theta ** 2
        v[3 * i + 2] = cov.photon_phi ** 2
    P = p[12]
    v[12] = (cov.proton_P_rel * P) ** 2
    v[13] = cov.proton_theta ** 2
    v[14] = cov.proton_phi ** 2
    v[15] = cov.beam_E ** 2
    return v


def _constraints(p: np.ndarray, pairing: Pairing,
                 m_heavy: float, m_light: float) -> np.ndarray:
    photons, proton, beam = _params_to_vectors(p)
    target = np.array([0.0, 0.0, 0.0, M_PROTON])
    balance = (beam + target) - (proton + photons.sum(axis=0))   # (4,) px,py,pz,E
    gh = photons[pairing.heavy[0]] + photons[pairing.heavy[1]]
    gl = photons[pairing.light[0]] + photons[pairing.light[1]]
    m2h = gh[3] ** 2 - (gh[:3] ** 2).sum()
    m2l = gl[3] ** 2 - (gl[:3] ** 2).sum()
    return np.array([balance[0], balance[1], balance[2], balance[3],
                     m2h - m_heavy ** 2, m2l - m_light ** 2])


def _jacobian(p: np.ndarray, pairing: Pairing,
              m_heavy: float, m_light: float) -> np.ndarray:
    """d f / d p, 6 x 16, by central differences."""
    n = p.size
    F = np.zeros((6, n))
    for j in range(n):
        step = max(abs(p[j]) * 1e-6, 1e-8)
        pp = p.copy(); pp[j] += step
        pm = p.copy(); pm[j] -= step
        F[:, j] = (_constraints(pp, pairing, m_heavy, m_light)
                   - _constraints(pm, pairing, m_heavy, m_light)) / (2 * step)
    return F


def fit_event(photons: np.ndarray, proton: np.ndarray, beam: np.ndarray,
              pairing: Pairing, hypothesis: Hypothesis,
              cov: FitCovariance = FitCovariance(),
              max_iter: int = 10, tol: float = 1e-8) -> FitResult:
    """Fit one event onto 4-momentum conservation and the two pair masses."""
    m_heavy, m_light = hypothesis.heavy_mass, hypothesis.light_mass
    y = _vectors_to_params(photons, proton, beam)
    V = _covariance_diag(y, cov)                       # diagonal, fixed at measured
    eta = y.copy()
    chi2 = 1e12
    converged = False

    for _ in range(max_iter):
        f = _constraints(eta, pairing, m_heavy, m_light)
        F = _jacobian(eta, pairing, m_heavy, m_light)
        r = f + F @ (y - eta)
        S = F @ (V[:, None] * F.T)                     # F V F^T, V diagonal
        try:
            Sinv = np.linalg.inv(S)
        except np.linalg.LinAlgError:
            fp, pr, _ = _params_to_vectors(eta)
            return FitResult(fp, pr, 1e12, 6, False, V.copy())
        lam = Sinv @ r
        eta = y - V * (F.T @ lam)
        chi2 = float(r @ Sinv @ r)
        if np.max(np.abs(_constraints(eta, pairing, m_heavy, m_light))) < tol:
            converged = True
            break

    fitted_photons, fitted_proton, _ = _params_to_vectors(eta)
    if not converged:
        chi2 = max(chi2, 1e3)          # keep it clear of any sane CL cut

    # Fitted covariance V_eta = V - V F^T S^-1 F V, at the converged eta/F/Sinv.
    # Store the raw diagonal (may hold tiny numerical negatives); clipping
    # before any sqrt is the caller's job (the validator does it).
    VFt = V[:, None] * F.T                          # (16, 6)
    V_eta = np.diag(V) - VFt @ Sinv @ VFt.T
    fitted_cov = np.diag(V_eta)

    return FitResult(fitted_photons, fitted_proton, chi2, 6, converged, fitted_cov)
