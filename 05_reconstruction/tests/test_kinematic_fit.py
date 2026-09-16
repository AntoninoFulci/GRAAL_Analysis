"""Tests for the 6C kinematic fit.

The fit adjusts measured photons/proton/beam within their resolution until the
event conserves 4-momentum and the two photon pairs sit on the eta and pi0
masses. Nothing here needs ROOT: the fitter is pure numpy on [px,py,pz,E] arrays.
"""
from dataclasses import FrozenInstanceError

import numpy as np
import pytest

import reconstruction.core.kinematic_fit as kf
from graal_common.physics.channels import ETA_PI0_HYP, M_ETA, M_PI0, M_PROTON
from graal_common.physics.pairing import Pairing
from reconstruction.core.kinematic_fit import (
    _DEG,
    FitCovariance,
    FitResult,
    _covariance_diag,
    _vectors_to_params,
    confidence_level,
    fit_event,
)
from reconstruction.validate_kinematic_fit import validation_status

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


def _baseline_smeared_event():
    photons, proton, beam = _conserving_event()
    rng = np.random.default_rng(0)
    smear = photons.copy()
    smear[:, 3] *= 1.0 + rng.normal(0, 0.05, 4)
    for i in range(4):
        n3 = np.sqrt((smear[i, :3] ** 2).sum())
        smear[i, :3] *= smear[i, 3] / n3
    return smear, proton, beam


class TestFitReactionModel:
    def test_reaction_model_is_immutable(self):
        reaction = kf.FitReactionModel(target_mass=1.0, recoil_mass=2.0)

        with pytest.raises(FrozenInstanceError):
            reaction.target_mass = 3.0

    def test_target_and_recoil_masses_control_their_distinct_calculations(self):
        photons, proton, beam = _conserving_event()
        params = _vectors_to_params(photons, proton, beam)
        reaction = kf.FitReactionModel(target_mass=1.5, recoil_mass=2.0)

        converted_photons, converted_recoil, converted_beam = (
            kf._params_to_vectors(params, reaction)
        )
        constraints = kf._constraints(
            params,
            PAIRING,
            ETA_PI0_HYP.heavy_mass,
            ETA_PI0_HYP.light_mass,
            reaction,
        )
        jacobian = kf._jacobian(
            params,
            PAIRING,
            ETA_PI0_HYP.heavy_mass,
            ETA_PI0_HYP.light_mass,
            reaction,
        )

        momentum = params[12]
        expected_recoil_energy = np.sqrt(momentum**2 + 2.0**2)
        expected_energy_balance = (
            converted_beam[3]
            + 1.5
            - converted_recoil[3]
            - converted_photons[:, 3].sum()
        )
        assert converted_recoil[3] == pytest.approx(expected_recoil_energy)
        assert constraints[3] == pytest.approx(expected_energy_balance)
        assert jacobian[3, 12] == pytest.approx(
            -momentum / expected_recoil_energy,
            rel=1e-6,
        )

    def test_explicit_proton_reaction_matches_omitted_legacy_default(self):
        photons, proton, beam = _baseline_smeared_event()
        params = _vectors_to_params(photons, proton, beam)

        default_constraints = kf._constraints(
            params,
            PAIRING,
            ETA_PI0_HYP.heavy_mass,
            ETA_PI0_HYP.light_mass,
        )
        explicit_constraints = kf._constraints(
            params,
            PAIRING,
            ETA_PI0_HYP.heavy_mass,
            ETA_PI0_HYP.light_mass,
            kf.PROTON_TARGET_REACTION,
        )
        default_jacobian = kf._jacobian(
            params,
            PAIRING,
            ETA_PI0_HYP.heavy_mass,
            ETA_PI0_HYP.light_mass,
        )
        explicit_jacobian = kf._jacobian(
            params,
            PAIRING,
            ETA_PI0_HYP.heavy_mass,
            ETA_PI0_HYP.light_mass,
            kf.PROTON_TARGET_REACTION,
        )
        default_result = fit_event(
            photons,
            proton,
            beam,
            PAIRING,
            ETA_PI0_HYP,
        )
        explicit_result = fit_event(
            photons,
            proton,
            beam,
            PAIRING,
            ETA_PI0_HYP,
            FitCovariance(),
            10,
            1e-8,
            None,
            kf.PROTON_TARGET_REACTION,
        )

        np.testing.assert_array_equal(explicit_constraints, default_constraints)
        np.testing.assert_array_equal(explicit_jacobian, default_jacobian)
        assert explicit_result.converged is default_result.converged
        assert explicit_result.chi2 == default_result.chi2
        assert explicit_result.condition_number == default_result.condition_number
        assert explicit_result.failure_reason == default_result.failure_reason
        np.testing.assert_array_equal(
            explicit_result.fitted_photons,
            default_result.fitted_photons,
        )
        np.testing.assert_array_equal(
            explicit_result.fitted_proton,
            default_result.fitted_proton,
        )
        np.testing.assert_array_equal(
            explicit_result.fitted_cov,
            default_result.fitted_cov,
        )

    def test_default_reaction_preserves_numerical_baseline(self):
        photons, proton, beam = _baseline_smeared_event()
        params = _vectors_to_params(photons, proton, beam)

        constraints = kf._constraints(
            params,
            PAIRING,
            ETA_PI0_HYP.heavy_mass,
            ETA_PI0_HYP.light_mass,
        )
        jacobian = kf._jacobian(
            params,
            PAIRING,
            ETA_PI0_HYP.heavy_mass,
            ETA_PI0_HYP.light_mass,
        )
        result = fit_event(photons, proton, beam, PAIRING, ETA_PI0_HYP)

        np.testing.assert_allclose(
            constraints,
            [
                -5.3385317494273193e-03,
                -4.1633594286399850e-17,
                1.1992600340260395e-04,
                -2.3221415884280283e-03,
                -1.0813184991298463e-04,
                6.8200383355844496e-04,
            ],
            rtol=0.0,
            atol=1e-15,
        )
        np.testing.assert_allclose(
            jacobian[3],
            [
                -0.9999999999903875,
                0.0,
                0.0,
                -1.000000000231296,
                0.0,
                0.0,
                -0.9999999999160055,
                0.0,
                0.0,
                -0.9999999992527989,
                0.0,
                0.0,
                -0.3173524545870105,
                0.0,
                0.0,
                0.9999999999494541,
            ],
            rtol=0.0,
            atol=1e-15,
        )
        assert result.converged
        assert result.chi2 == pytest.approx(0.07073600149366603, abs=1e-14)
        assert result.condition_number == pytest.approx(
            4400.060298310016,
            abs=1e-10,
        )
        np.testing.assert_allclose(
            result.fitted_photons,
            [
                [0.27319026578033329, 0.0, 0.54478041905457097, 0.60944124105807207],
                [-0.27465764200889892, 0.0, 0.53838810996439734, 0.60439935246898180],
                [0.068340705242136382, 0.0, 0.001445395997158283, 0.068355988490995931],
                [-0.066646921711323887, 0.0, 0.0014085274754090144, 0.066661804080330123],
            ],
            rtol=0.0,
            atol=1e-15,
        )
        np.testing.assert_allclose(
            result.fitted_proton,
            [-2.2640730224457231e-04, 0.0, 0.31397532539573003, 0.98941139178888626],
            rtol=0.0,
            atol=1e-15,
        )
        np.testing.assert_allclose(
            result.fitted_cov,
            [
                1.4194998380519779e-03,
                1.1228045854310134e-03,
                1.4561705247991758e-03,
                1.4179419665317564e-03,
                1.1393722582606200e-03,
                1.4423251506649967e-03,
                2.3883201361417061e-05,
                5.6604121877740065e-03,
                2.6611186191224405e-03,
                2.2699066642155970e-05,
                5.7584912703266648e-03,
                2.6650564320297204e-03,
                7.9547578139372777e-05,
                2.6245480011062965e-03,
                1.2184695047578560e-03,
                4.5529401957278284e-05,
            ],
            rtol=0.0,
            atol=1e-15,
        )


class TestConfidenceLevel:
    def test_a_chi2_equal_to_ndf_gives_a_moderate_cl(self):
        cl = confidence_level(6.0, 6)
        assert 0.3 < cl < 0.6

    def test_a_huge_chi2_gives_cl_near_zero(self):
        assert confidence_level(1000.0, 6) < 1e-6

    def test_cl_is_one_at_zero_chi2(self):
        assert confidence_level(0.0, 6) == pytest.approx(1.0)


class TestValidationStatus:
    def test_closure_is_labelled_as_shared_covariance(self):
        assert "CLOSURE ONLY" in validation_status("closure", None)

    def test_calibration_requires_independent_provenance(self):
        with pytest.raises(ValueError, match="provenance"):
            validation_status("calibration", None)

    def test_calibration_reports_provenance(self):
        status = validation_status("calibration", "run-period control sample")
        assert "INDEPENDENT CALIBRATION" in status
        assert "run-period control sample" in status


class TestFitEvent:
    def test_nonpositive_photon_energy_is_rejected(self):
        photons, proton, beam = _conserving_event()
        photons[0, 3] = 0.0

        result = fit_event(photons, proton, beam, PAIRING, ETA_PI0_HYP)

        assert not result.converged
        assert result.failure_reason == "invalid_input"

    def test_max_iteration_failure_has_structured_reason(self):
        photons, proton, beam = _conserving_event()
        photons[0, 3] *= 1.05
        photons[0, :3] *= 1.05

        result = fit_event(
            photons, proton, beam, PAIRING, ETA_PI0_HYP, max_iter=1
        )

        assert not result.converged
        assert result.failure_reason == "max_iterations"

    def test_fit_does_not_use_explicit_inverse(self, monkeypatch):
        photons, proton, beam = _conserving_event()
        monkeypatch.setattr(
            np.linalg, "inv", lambda *_: pytest.fail("explicit inverse called")
        )

        result = fit_event(photons, proton, beam, PAIRING, ETA_PI0_HYP)

        assert result.converged

    def test_singular_constraint_matrix_has_structured_reason(self, monkeypatch):
        photons, proton, beam = _conserving_event()
        monkeypatch.setattr(
            kf, "_jacobian", lambda *args: np.zeros((6, 16))
        )

        result = fit_event(photons, proton, beam, PAIRING, ETA_PI0_HYP)

        assert not result.converged
        assert result.failure_reason == "singular_constraint_matrix"

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

    def test_fitted_cov_is_no_larger_than_the_measured_variance(self):
        # The fit uses the constraints to reduce, never inflate, the
        # uncertainty on the fitted parameters -- V_eta <= V, elementwise.
        photons, proton, beam = _conserving_event()
        rng = np.random.default_rng(0)
        smear = photons.copy()
        smear[:, 3] *= 1.0 + rng.normal(0, 0.05, 4)
        for i in range(4):
            n3 = np.sqrt((smear[i, :3] ** 2).sum())
            smear[i, :3] *= smear[i, 3] / n3
        res = fit_event(smear, proton, beam, PAIRING, ETA_PI0_HYP)
        assert res.converged
        assert res.fitted_cov.shape == (16,)

        measured = _covariance_diag(_vectors_to_params(smear, proton, beam), FitCovariance())
        assert np.all(res.fitted_cov >= -1e-12)          # allow tiny numerical noise
        assert np.all(res.fitted_cov <= measured + 1e-12)

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
            beam_E=2 * FitCovariance().beam_E,
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
