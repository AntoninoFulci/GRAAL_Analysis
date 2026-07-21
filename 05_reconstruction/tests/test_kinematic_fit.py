"""Tests for the 6C kinematic fit.

The fit adjusts measured photons/proton/beam within their resolution until the
event conserves 4-momentum and the two photon pairs sit on the eta and pi0
masses. Nothing here needs ROOT: the fitter is pure numpy on [px,py,pz,E] arrays.
"""
import numpy as np
import pytest

from graal_common.channels import ETA_PI0_HYP, M_ETA, M_PI0, M_PROTON
from graal_common.pairing import Pairing
from reconstruction.kinematic_fit import (
    _DEG,
    FitCovariance,
    FitResult,
    confidence_level,
    fit_event,
)

# Photons (0,1) are the eta, (2,3) the pi0 -- the pairing the fit is handed.
PAIRING = Pairing(heavy=(0, 1), light=(2, 3))


def _photon(E, theta, phi):
    return np.array([
        E * np.sin(theta) * np.cos(phi),
        E * np.sin(theta) * np.sin(phi),
        E * np.cos(theta),
        E,
    ])


def _conserving_event():
    """A gamma p -> p eta pi0 event that conserves and is on-mass, built forwards.

    Everything is placed along z so the kinematics reduce to 1D and balance
    exactly: W -> (eta pi0 system) + proton, then the system -> eta + pi0, then
    each meson -> two collinear photons. 4-momentum balances and the pair masses
    are exactly m_eta / m_pi0 by construction.
    """
    mp = M_PROTON
    Ebeam = 1.4
    beam = np.array([0.0, 0.0, Ebeam, Ebeam])
    target = np.array([0.0, 0.0, 0.0, mp])
    W = beam + target
    Wm = np.sqrt(W[3] ** 2 - (W[:3] ** 2).sum())
    betaz = W[2] / W[3]
    gamma = 1.0 / np.sqrt(1 - betaz ** 2)

    def boost_z(v, beta, g):
        px, py, pz, E = v
        return np.array([px, py, g * (pz + beta * E), g * (E + beta * pz)])

    # eta+pi0 system mass. Must sit in [m_eta+m_pi0, Wm-m_p] to be physical;
    # at Ebeam=1.4 that is [0.683, 0.935], so 0.8 works (1.1 does not -> NaN).
    Msys = 0.8
    E_sys = (Wm ** 2 + Msys ** 2 - mp ** 2) / (2 * Wm)
    p_sys = np.sqrt(E_sys ** 2 - Msys ** 2)
    E_p = Wm - E_sys
    proton = boost_z(np.array([0.0, 0.0, -p_sys, E_p]), betaz, gamma)
    sys = boost_z(np.array([0.0, 0.0, p_sys, E_sys]), betaz, gamma)

    E_eta = (Msys ** 2 + M_ETA ** 2 - M_PI0 ** 2) / (2 * Msys)
    p_eta = np.sqrt(E_eta ** 2 - M_ETA ** 2)
    E_pi0 = Msys - E_eta
    beta_s = p_sys / E_sys
    g_s = 1.0 / np.sqrt(1 - beta_s ** 2)
    eta = boost_z(np.array([0.0, 0.0, p_eta, E_eta]), beta_s, g_s)
    pi0 = boost_z(np.array([0.0, 0.0, -p_eta, E_pi0]), beta_s, g_s)
    # beta_s took eta/pi0 from the system rest frame into the CM; now the same
    # CM->lab boost betaz that proton/sys got, or the event does not conserve.
    eta = boost_z(eta, betaz, gamma)
    pi0 = boost_z(pi0, betaz, gamma)

    def two_photons(meson, mass):
        # Decay PERPENDICULAR to the boost (along x in the rest frame), so the
        # lab photons are off the z-axis (theta != 0) and the (E,theta,phi)
        # parametrisation is not singular. Boost is along z (the meson direction).
        E_g = mass / 2.0
        pmag = np.sqrt((meson[:3] ** 2).sum())
        beta = pmag / meson[3]
        g = 1.0 / np.sqrt(1 - beta ** 2)
        g1 = np.array([E_g, 0.0, g * beta * E_g, g * E_g])
        g2 = np.array([-E_g, 0.0, g * beta * E_g, g * E_g])
        return g1, g2

    e1, e2 = two_photons(eta, M_ETA)
    p1, p2 = two_photons(pi0, M_PI0)
    photons = np.stack([e1, e2, p1, p2])
    return photons, proton, beam


class TestConfidenceLevel:
    def test_a_chi2_equal_to_ndf_gives_a_moderate_cl(self):
        cl = confidence_level(6.0, 6)
        assert 0.3 < cl < 0.6

    def test_a_huge_chi2_gives_cl_near_zero(self):
        assert confidence_level(1000.0, 6) < 1e-6

    def test_cl_is_one_at_zero_chi2(self):
        assert confidence_level(0.0, 6) == pytest.approx(1.0)


class TestFitEvent:
    def test_a_conserving_on_mass_event_barely_moves(self):
        photons, proton, beam = _conserving_event()
        res = fit_event(photons, proton, beam, PAIRING, ETA_PI0_HYP)
        assert res.converged
        assert res.ndf == 6
        assert res.chi2 < 1e-2          # already satisfies the constraints
        np.testing.assert_allclose(res.fitted_photons, photons, atol=1e-3)

    def test_the_fitted_event_satisfies_the_constraints(self):
        photons, proton, beam = _conserving_event()
        rng = np.random.default_rng(0)
        smear = photons.copy()
        smear[:, 3] *= 1.0 + rng.normal(0, 0.05, 4)   # 5% energy jitter
        # rescale 3-momentum of each (massless) photon to its jittered energy
        for i in range(4):
            n3 = np.sqrt((smear[i, :3] ** 2).sum())
            smear[i, :3] *= smear[i, 3] / n3
        res = fit_event(smear, proton, beam, PAIRING, ETA_PI0_HYP)
        assert res.converged
        target = np.array([0.0, 0.0, 0.0, M_PROTON])
        total_in = beam + target
        total_out = res.fitted_proton + res.fitted_photons.sum(axis=0)
        np.testing.assert_allclose(total_out, total_in, atol=1e-4)
        gh = res.fitted_photons[0] + res.fitted_photons[1]
        gl = res.fitted_photons[2] + res.fitted_photons[3]
        mh = np.sqrt(gh[3] ** 2 - (gh[:3] ** 2).sum())
        ml = np.sqrt(gl[3] ** 2 - (gl[:3] ** 2).sum())
        assert mh == pytest.approx(M_ETA, abs=1e-3)
        assert ml == pytest.approx(M_PI0, abs=1e-3)

    def test_non_convergence_is_flagged_not_crashed(self):
        # Mesons carrying far more than the beam: conservation is unsatisfiable,
        # so the fit must flag not-converged and leave chi2 large, never raise.
        photons = np.stack([
            _photon(5.0, 0.5, 0.0), _photon(5.0, 0.6, 0.1),
            _photon(5.0, 2.0, 3.0), _photon(5.0, 2.2, 2.0),
        ])
        proton = np.array([0.0, 0.0, 0.3, np.sqrt(0.3 ** 2 + M_PROTON ** 2)])
        beam = np.array([0.0, 0.0, 1.0, 1.0])
        res = fit_event(photons, proton, beam, PAIRING, ETA_PI0_HYP, max_iter=5)
        assert res.converged is False
        assert res.chi2 > 100


class TestChi2Calibration:
    """Pin chi2's calibration: it must scale as 1/sigma^2, not 1/sigma.

    Constraint satisfaction only cares about V^-1 up to direction, so the
    fitted 4-vectors are scale-invariant under V -> k*V. But chi2 = r^T
    (F V F^T)^-1 r is NOT scale-invariant: it picks up a factor 1/k. That
    factor is exactly what turns the chi2(ndf) confidence-level cut into a
    real background rejection. A regression that plugs in sigma instead of
    sigma^2 (or drops a square somewhere) would leave every other test in
    this file green while silently gutting the CL cut -- this test is the
    only thing standing in its way.
    """

    def test_doubling_every_sigma_quarters_chi2_but_not_the_fitted_vectors(self):
        photons, proton, beam = _conserving_event()
        rng = np.random.default_rng(6)
        smear = photons.copy()
        smear[:, 3] *= 1.0 + rng.normal(0, 0.07, 4)   # 7% energy jitter
        for i in range(4):
            n3 = np.sqrt((smear[i, :3] ** 2).sum())
            smear[i, :3] *= smear[i, 3] / n3

        cov_default = FitCovariance()
        cov_2x = FitCovariance(
            photon_E_rel=0.20,
            photon_theta=10 * _DEG,
            photon_phi=6 * _DEG,
            proton_P_rel=0.08,
            proton_theta=6 * _DEG,
            proton_phi=4 * _DEG,
            beam_E=0.032,
        )

        res_default = fit_event(smear, proton, beam, PAIRING, ETA_PI0_HYP, cov=cov_default)
        res_2x = fit_event(smear, proton, beam, PAIRING, ETA_PI0_HYP, cov=cov_2x)

        assert res_default.converged and res_2x.converged
        assert res_default.chi2 > 1.0   # guard: non-trivial chi2, not ~0

        # Constraint satisfaction is scale-invariant in V -- same fitted event.
        np.testing.assert_allclose(res_2x.fitted_photons, res_default.fitted_photons, atol=1e-6)
        np.testing.assert_allclose(res_2x.fitted_proton, res_default.fitted_proton, atol=1e-6)

        # Every sigma doubled -> every variance x4 -> chi2 / 4.
        assert res_2x.chi2 == pytest.approx(res_default.chi2 / 4.0, rel=1e-3)
