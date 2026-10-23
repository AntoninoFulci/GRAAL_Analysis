"""Covariance-aware two-coupling objective and identifiable toy recovery."""

from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from graal_theory.figure4_basis import BinPrediction
from graal_theory.figure4_fit import build_exploratory_gls, build_gls, fit_delta_em
from graal_theory.native_sigma import NativeSigmaData


class ToyCertificate:
    def __init__(self, index, *, rank_one=False, status="calculated", error=0.):
        proton = .93827208816
        self.moment = SimpleNamespace(anchor_g1=-.260/proton,
                                      anchor_g2=.270/proton**2,
                                      proton_mass_gev=proton,
                                      energy_rule="native_flux",
                                      model_fingerprint="toy-physics")
        self.index = index
        self.rank_one = rank_one
        self.status = status
        self.numerical_error_bound = error
        self.fit_precision_limit = .01

    def predict(self, coefficients):
        _, x, y = coefficients
        a = .15+.04*self.index
        b = 2*a if self.rank_one else .11-.025*self.index
        sigma = -.08+.02*self.index+a*x+b*y+(0. if self.rank_one else .05*x*y)
        return BinPrediction(sigma, 1., sigma, sigma, "native_flux")


def toy_data(*, rank_one=False):
    keys = tuple(("p_pi0", 0, index) for index in range(6))
    predictions = {key: ToyCertificate(index, rank_one=rank_one)
                   for index, key in enumerate(keys)}
    anchor = predictions[keys[0]].moment
    truth = np.array([anchor.anchor_g1+.07, anchor.anchor_g2-.04])
    coeff = np.array([1., truth[0]-anchor.anchor_g1, truth[1]-anchor.anchor_g2])
    sigma = np.array([predictions[key].predict(coeff).sigma for key in keys])
    factor = np.eye(6)*.05+np.tril(np.ones((6, 6)), -1)*.004
    covariance = factor @ factor.T
    data = NativeSigmaData(keys, sigma, np.full(6, .05), np.arange(6), covariance,
                           covariance/2, np.array([1.1, 1.2]),
                           {"p_pi0": np.linspace(1.05, 1.35, 7)},
                           {"profile": "uv", "background": "sideband-corrected"},
                           "a"*64, "final_input")
    return data, predictions, truth


def test_gls_residuals_use_ordered_cholesky_whitening():
    data, predictions, truth = toy_data()
    objective = build_gls(data, predictions)
    theta = truth+np.array([.02, -.01])
    c = np.array([1., theta[0]-objective.anchor_g1, theta[1]-objective.anchor_g2])
    expected_prediction = np.array([predictions[key].predict(c).sigma for key in data.keys])
    expected = np.linalg.solve(np.linalg.cholesky(data.covariance), data.sigma-expected_prediction)
    np.testing.assert_allclose(objective.residuals(theta), expected, rtol=1e-13, atol=1e-13)
    np.testing.assert_allclose(objective.residuals(truth), 0., atol=1e-13)


def test_gls_rejects_missing_masked_or_imprecise_theory():
    data, predictions, _ = toy_data()
    with pytest.raises(ValueError, match="keys"):
        build_gls(data, {key: item for key, item in predictions.items() if key != data.keys[-1]})
    predictions[data.keys[0]].status = "masked_nonconverged"
    with pytest.raises(ValueError, match="certif"):
        build_gls(data, predictions)
    predictions[data.keys[0]].status = "calculated"
    predictions[data.keys[0]].numerical_error_bound = .02
    with pytest.raises(ValueError, match="numerical"):
        build_gls(data, predictions)


def test_gls_rejects_invalid_covariance_and_denominator():
    data, predictions, truth = toy_data()
    data.covariance[0, 0] = 0.
    with pytest.raises(ValueError, match="covariance"):
        build_gls(data, predictions)
    data, predictions, truth = toy_data()
    objective = build_gls(data, predictions)
    def zero_denominator(coefficients):
        return BinPrediction(0., 0., 0., 0., "native_flux")
    predictions[data.keys[0]].predict = zero_denominator
    with pytest.raises(ValueError, match="denominator"):
        objective.residuals(truth)


def test_gls_rejects_nonfinite_measured_sigma():
    data, predictions, _ = toy_data()
    data.sigma[2] = np.nan
    with pytest.raises(ValueError, match="Sigma"):
        build_gls(data, predictions)


def test_fit_recovers_injected_couplings_and_source_units():
    data, predictions, truth = toy_data()
    objective = build_gls(data, predictions)
    result = fit_delta_em(objective, np.array([objective.anchor_g1, objective.anchor_g2]))
    assert result.status == "fit_computed"
    np.testing.assert_allclose(result.theta_internal, truth, atol=1e-8)
    np.testing.assert_allclose(result.theta_source_units,
                               [truth[0]*objective.proton_mass_gev,
                                truth[1]*objective.proton_mass_gev**2], atol=1e-8)
    assert result.chi_square == pytest.approx(0., abs=1e-15)
    assert result.degrees_of_freedom == 4
    assert result.parameter_covariance is not None


def test_rank_one_sensitivity_is_not_identifiable():
    data, predictions, _ = toy_data(rank_one=True)
    objective = build_gls(data, predictions)
    result = fit_delta_em(objective, np.array([objective.anchor_g1, objective.anchor_g2]))
    assert result.status == "not_identifiable"
    assert result.parameter_covariance is None


def _pilot_moments(predictions):
    return {key: SimpleNamespace(**vars(certificate.moment),
                                 status="calculated", reason=None,
                                 evaluate=certificate.predict)
            for key, certificate in predictions.items()}


def test_exploratory_gls_keeps_all_computed_bins_and_slices_full_covariance():
    data, predictions, truth = toy_data()
    data = replace(data, status="pilot")
    moments = _pilot_moments(predictions)
    omitted = data.keys[1]
    moments[omitted].status = "masked_nonconverged"
    moments[omitted].reason = "inner quadrature"
    objective = build_exploratory_gls(data, moments)
    indices = [0, 2, 3, 4, 5]
    assert objective.data.keys == tuple(data.keys[i] for i in indices)
    assert objective.excluded == ((omitted, "inner quadrature"),)
    np.testing.assert_allclose(objective.data.covariance,
                               data.covariance[np.ix_(indices, indices)])
    np.testing.assert_allclose(objective.residuals(truth), 0., atol=1e-13)
    result = fit_delta_em(objective, np.array([objective.anchor_g1, objective.anchor_g2]))
    assert result.status == "exploratory_pilot"
    np.testing.assert_allclose(result.theta_internal, truth, atol=1e-8)
    with pytest.raises(ValueError, match="uncertified"):
        build_gls(data, {key: SimpleNamespace(moment=moment,
                    status="preliminary_uncertified", numerical_error_bound=np.nan)
                    for key, moment in moments.items()})


def test_exploratory_gls_rejects_missing_key_or_inconsistent_anchor():
    data, predictions, _ = toy_data()
    moments = _pilot_moments(predictions)
    with pytest.raises(ValueError, match="pilot data"):
        build_exploratory_gls(data, moments)
    data = replace(data, status="pilot")
    with pytest.raises(ValueError, match="keys"):
        build_exploratory_gls(data, {key: value for key, value in moments.items()
                                     if key != data.keys[-1]})
    moments[data.keys[1]].anchor_g1 += .1
    with pytest.raises(ValueError, match="anchor"):
        build_exploratory_gls(data, moments)


def test_exploratory_fit_checks_each_trial_and_preserves_selected_phi_metadata():
    data,predictions,truth=toy_data()
    data=replace(data,status='pilot',phi_bins=np.array([8,12,16,8,12,16]),
                 phi_bin_divisor=np.array([.9003,.9549,.9745]*2),
                 ratio_used_fallback=np.array([True,False]*3))
    moments=_pilot_moments(predictions)
    for index,key in enumerate(data.keys):
        moments[key].state_phi=np.zeros((2,int(data.phi_bins[index]),3,3),complex)
        moments[key].phi_bin_divisor=float(data.phi_bin_divisor[index])
        moments[key].ratio_used_fallback=bool(data.ratio_used_fallback[index])
    moments[data.keys[1]].status='masked_nonconverged'
    checks={}
    calls=[]
    for key in data.keys:
        def predict(c,key=key):
            calls.append(key)
            if abs(c[1]) > .09:
                raise ValueError('refinement unresolved at trial')
            return predictions[key].predict(c)
        checks[key]=SimpleNamespace(moment=moments[key],status='diagnostic_converged',predict=predict)
    objective=build_exploratory_gls(data,moments,checks=checks)
    assert objective.data.phi_bins.tolist() == [8,16,8,12,16]
    result=fit_delta_em(objective,np.array([objective.anchor_g1,objective.anchor_g2]))
    assert result.status == 'exploratory_pilot'
    np.testing.assert_allclose(result.theta_internal,truth,atol=1e-8)
    assert len(calls) > 10
    with pytest.raises(ValueError,match='refinement'):
        objective.residuals(truth+[.1,0.])
