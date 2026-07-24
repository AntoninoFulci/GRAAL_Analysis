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
from typing import Protocol

import numpy as np
from scipy.stats import chi2 as _chi2dist

from graal_common.channels import M_PROTON, TAGGER_SIGMA_GEV, Hypothesis
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
    beam_E: float = TAGGER_SIGMA_GEV

    def covariance_diag(self, measured_params: np.ndarray) -> np.ndarray:
        """Diagonal measurement covariance for one event."""
        v = np.zeros(16)
        for i in range(4):
            energy = measured_params[3 * i]
            v[3 * i] = (self.photon_E_rel * energy) ** 2
            v[3 * i + 1] = self.photon_theta ** 2
            v[3 * i + 2] = self.photon_phi ** 2
        momentum = measured_params[12]
        v[12] = (self.proton_P_rel * momentum) ** 2
        v[13] = self.proton_theta ** 2
        v[14] = self.proton_phi ** 2
        v[15] = self.beam_E ** 2
        return v


class ResolutionModel(Protocol):
    """Measurement-resolution boundary for future calibrated models."""

    def covariance_diag(self, measured_params: np.ndarray) -> np.ndarray:
        """Return 16 variances in fitter parameter order."""


@dataclass(frozen=True)
class FitOptions:
    max_iter: int = 10
    constraint_tol: float = 1e-8
    chi2_abs_tol: float = 1e-8
    chi2_rel_tol: float = 1e-8
    max_condition_number: float = 1e14


@dataclass
class FitResult:
    fitted_photons: np.ndarray   # (4, 4) [px, py, pz, E]
    fitted_proton: np.ndarray    # (4,)
    chi2: float
    ndf: int
    converged: bool
    fitted_cov: np.ndarray       # (16,) diagonal of V_eta, same param order as V
    failure_reason: str | None = None
    condition_number: float = np.nan


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


def _canonicalize_angles(p: np.ndarray) -> None:
    """Normalize spherical coordinates in place without changing 4-vectors."""
    for theta_index, phi_index in ((1, 2), (4, 5), (7, 8), (10, 11), (13, 14)):
        theta = p[theta_index] % (2.0 * np.pi)
        if theta > np.pi:
            theta = 2.0 * np.pi - theta
            p[phi_index] += np.pi
        p[theta_index] = theta
        p[phi_index] = (p[phi_index] + np.pi) % (2.0 * np.pi) - np.pi


def _covariance_diag(p: np.ndarray, cov: FitCovariance) -> np.ndarray:
    """Diagonal of V, in the same order as the params, evaluated at measured p."""
    return cov.covariance_diag(p)


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
              cov: ResolutionModel = FitCovariance(),
              max_iter: int = 10, tol: float = 1e-8,
              options: FitOptions | None = None) -> FitResult:
    """Fit one event onto 4-momentum conservation and the two pair masses."""
    options = options or FitOptions(max_iter=max_iter, constraint_tol=tol)
    m_heavy, m_light = hypothesis.heavy_mass, hypothesis.light_mass
    y = _vectors_to_params(photons, proton, beam)
    V = cov.covariance_diag(y)                         # diagonal, fixed at measured

    valid_input = (
        photons.shape == (4, 4)
        and proton.shape == (4,)
        and beam.shape == (4,)
        and np.all(np.isfinite(photons))
        and np.all(np.isfinite(proton))
        and np.all(np.isfinite(beam))
        and np.all(photons[:, 3] > 0.0)
        and beam[3] > 0.0
        and np.all(np.isfinite(V))
        and np.all(V > 0.0)
    )
    if not valid_input:
        return FitResult(
            photons.copy(), proton.copy(), 1e12, 6, False, V.copy(),
            failure_reason="invalid_input",
        )

    eta = y.copy()
    chi2 = 1e12
    previous_chi2 = np.inf
    converged = False
    condition_number = np.nan
    scales = np.array([1.0, 1.0, 1.0, 1.0, m_heavy**2, m_light**2])

    for _ in range(options.max_iter):
        f = _constraints(eta, pairing, m_heavy, m_light)
        F = _jacobian(eta, pairing, m_heavy, m_light)
        S = F @ (V[:, None] * F.T)                     # F V F^T, V diagonal
        if float(np.max(np.abs(f) / scales)) < options.constraint_tol:
            chi2 = 0.0 if np.array_equal(eta, y) else chi2
            condition_number = float(np.linalg.cond(S))
            converged = True
            break
        r = f + F @ (y - eta)
        condition_number = float(np.linalg.cond(S))
        if (
            not np.isfinite(condition_number)
            or condition_number > options.max_condition_number
        ):
            fp, pr, _ = _params_to_vectors(eta)
            return FitResult(
                fp, pr, 1e12, 6, False, V.copy(),
                failure_reason="singular_constraint_matrix",
                condition_number=condition_number,
            )
        try:
            lam = np.linalg.solve(S, r)
        except np.linalg.LinAlgError:
            fp, pr, _ = _params_to_vectors(eta)
            return FitResult(
                fp, pr, 1e12, 6, False, V.copy(),
                failure_reason="singular_constraint_matrix",
                condition_number=condition_number,
            )
        eta = y - V * (F.T @ lam)
        chi2 = float(r @ lam)
        constraints = _constraints(eta, pairing, m_heavy, m_light)
        scaled_residual = float(np.max(np.abs(constraints) / scales))
        chi2_stable = (
            np.isfinite(previous_chi2)
            and abs(chi2 - previous_chi2)
            <= options.chi2_abs_tol
            + options.chi2_rel_tol * max(1.0, abs(previous_chi2))
        )
        if scaled_residual < options.constraint_tol and chi2_stable:
            converged = True
            break
        previous_chi2 = chi2

    fitted_photons, fitted_proton, _ = _params_to_vectors(eta)
    fitted_params_valid = (
        np.all(np.isfinite(eta))
        and np.all(eta[[0, 3, 6, 9, 15]] > 0.0)
        and eta[12] >= 0.0
    )
    if converged and not fitted_params_valid:
        return FitResult(
            fitted_photons, fitted_proton, 1e12, 6, False, V.copy(),
            failure_reason="invalid_fitted_parameters",
            condition_number=condition_number,
        )
    if not converged:
        chi2 = max(chi2, 1e3)          # keep it clear of any sane CL cut

    # Fitted covariance V_eta = V - V F^T S^-1 F V, at the converged eta/F/Sinv.
    # Store the raw diagonal (may hold tiny numerical negatives); clipping
    # before any sqrt is the caller's job (the validator does it).
    VFt = V[:, None] * F.T                          # (16, 6)
    try:
        solved = np.linalg.solve(S, VFt.T)
    except np.linalg.LinAlgError:
        return FitResult(
            fitted_photons, fitted_proton, 1e12, 6, False, V.copy(),
            failure_reason="singular_constraint_matrix",
            condition_number=condition_number,
        )
    V_eta = np.diag(V) - VFt @ solved
    fitted_cov = np.diag(V_eta)
    covariance_tolerance = 1e-12
    if (
        not np.all(np.isfinite(fitted_cov))
        or np.any(fitted_cov < -covariance_tolerance)
    ):
        return FitResult(
            fitted_photons, fitted_proton, 1e12, 6, False, fitted_cov,
            failure_reason="invalid_fitted_covariance",
            condition_number=condition_number,
        )
    fitted_cov = np.maximum(fitted_cov, 0.0)

    return FitResult(
        fitted_photons,
        fitted_proton,
        chi2,
        6,
        converged,
        fitted_cov,
        failure_reason=None if converged else "max_iterations",
        condition_number=condition_number,
    )
