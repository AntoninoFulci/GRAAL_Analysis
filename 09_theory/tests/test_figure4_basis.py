"""Bin-level phase-space and fast-moment contracts without production loops."""

from dataclasses import dataclass, replace
from types import SimpleNamespace

import numpy as np
import pytest

from graal_theory.figure4_basis import certify_basis_bin, integrate_basis_bin
from graal_theory.figure4_integration import predict_figure4_bin
from graal_theory.beam_asymmetry import fit_binned_asymmetry
from graal_theory.constants import GEV2_TO_MICROBARN
from graal_theory.kinematics import s_from_lab_photon_energy
from graal_theory.phase_space import SobolConfig, sample_three_body_mass_window
from graal_theory.photon_flux import FluxSpectrum, PhotonExposure


@dataclass(frozen=True)
class ToyModel:
    g1: float = 0.
    g2: float = 0.
    masses = (.547862, .134977, .938272)

    @property
    def parameters(self):
        return SimpleNamespace(proton_mass_gev=self.masses[2])

    def amplitude(self, sample, polarization):
        # Complex spin matrix linear in exactly the two proposed couplings.
        scale = 1 + self.g1*(.2 + .1j)*sample.momenta[:, 0, 1] \
                    + self.g2*(.1 - .2j)*sample.momenta[:, 1, 2]
        return np.broadcast_to(scale[:, None, None], (len(scale), 2, 2)).copy()


class ToyBasis:
    def __init__(self, model, sample, polarization):
        self.anchor_g1 = 0.
        self.anchor_g2 = 0.
        source_model = replace(model, g1=0., g2=0.)
        source = source_model.amplitude(sample, polarization)
        first = replace(source_model, g1=1.).amplitude(sample, polarization) - source
        second = replace(source_model, g2=1.).amplitude(sample, polarization) - source
        self.matrices = np.stack((source, first, second))

    def validate_model(self, model):
        if model.masses != ToyModel.masses:
            raise ValueError("model fingerprint mismatch")


@pytest.mark.parametrize("pair,mass_range", [
    ("p_pi0", (1.08, 1.22)), ("p_eta", (1.49, 1.63)), ("eta_pi0", (.69, .84)),
])
def test_uniform_basis_bin_matches_direct_integral(monkeypatch, pair, mass_range):
    monkeypatch.setattr("graal_theory.figure4_basis.delta_em_event_basis", ToyBasis)
    model = ToyModel()
    interval = (1.1, 1.2)
    moment = integrate_basis_bin(model, pair, interval, mass_range,
                                 energy_rule="uniform", energy_order=2, sobol=SobolConfig(4))
    assert moment.anchor_g1 == 0. and moment.anchor_g2 == 0.
    assert moment.proton_mass_gev == model.masses[2]
    for g1, g2 in ((0., 0.), (.08, -.03), (-.06, .05)):
        expected = predict_figure4_bin(replace(model, g1=g1, g2=g2), pair, interval,
                                       mass_range, energy_order=2, sobol=SobolConfig(4))
        actual = moment.evaluate([1., g1, g2])
        assert actual.numerator == pytest.approx(expected.numerator, rel=1e-12, abs=1e-12)
        assert actual.denominator == pytest.approx(expected.denominator, rel=1e-12, abs=1e-12)
        assert actual.intrinsic_sigma == pytest.approx(expected.sigma, abs=1e-12)
        assert moment.weighted_mass_gev([1., g1, g2]) == pytest.approx(expected.weighted_mass_gev, rel=1e-12)
        vertical, horizontal = moment.polarized_normalizations([1., g1, g2])
        assert vertical == pytest.approx(expected.vertical_normalization, rel=1e-12)
        assert horizontal == pytest.approx(expected.horizontal_normalization, rel=1e-12)
        assert 0. <= moment.source_used_extension_fraction([1., g1, g2]) <= 1.


def test_uniform_basis_bin_splits_onset_and_masks_kinematic(monkeypatch):
    monkeypatch.setattr("graal_theory.figure4_basis.delta_em_event_basis", ToyBasis)
    model = ToyModel()
    moment = integrate_basis_bin(model, "p_eta", (1.3, 1.4), (1.7, 1.8),
                                 energy_rule="uniform", energy_order=3, sobol=SobolConfig(4))
    onset = ((1.7+model.masses[1])**2-model.masses[2]**2)/(2*model.masses[2])
    assert moment.status == "calculated"
    assert moment.accessible_energy_gev[0] == pytest.approx(onset)
    assert moment.accessible_mass_gev == pytest.approx((1.7, min(1.8, np.sqrt(s_from_lab_photon_energy(1.4, model.masses[2]))-model.masses[1])))
    assert all(energy >= onset for energy in moment.energy_nodes_gev)
    missing = integrate_basis_bin(model, "p_eta", (1.3, 1.4), (1.8, 1.9),
                                  energy_rule="uniform", energy_order=3, sobol=SobolConfig(4))
    assert missing.status == "masked_kinematic"
    assert missing.accessible_energy_gev is None


def test_uniform_and_native_weighting_must_not_mix(monkeypatch):
    monkeypatch.setattr("graal_theory.figure4_basis.delta_em_event_basis", ToyBasis)
    with pytest.raises(ValueError):
        integrate_basis_bin(ToyModel(), "p_pi0", (1.1, 1.2), (1.08, 1.22),
                            energy_rule="uniform", energy_order=2, sobol=SobolConfig(4),
                            flux_spectrum=object())


def test_certificate_accepts_stable_matrices_and_rejects_offsource_drift(monkeypatch):
    monkeypatch.setattr("graal_theory.figure4_basis.delta_em_event_basis", ToyBasis)
    model = ToyModel()
    args = (model, "p_pi0", (1.1, 1.2), (1.08, 1.22))
    base = integrate_basis_bin(*args, energy_rule="uniform", energy_order=2, sobol=SobolConfig(4))
    def stable(*unused, **kwargs):
        return base
    monkeypatch.setattr("graal_theory.figure4_basis.integrate_basis_bin", stable)
    certificate = certify_basis_bin(*args, energy_rule="uniform", energy_order=2,
                                    sobol_power=4, replica_seeds=tuple(range(8)))
    assert certificate.status == "calculated"
    assert certificate.predict([1., .08, -.03]).sigma == pytest.approx(base.evaluate([1., .08, -.03]).sigma)
    assert certificate.matrix_covariance.shape[0] == certificate.matrix_covariance.shape[1]
    assert set(certificate.reference_deltas) == {"source", "plus", "minus"}
    assert certificate.reference_deltas["source"]["energy_denominator"] == pytest.approx(0.)
    def drift(*unused, **kwargs):
        if kwargs["energy_order"] != 4:
            return base
        altered = base.numerator.copy()
        altered[1, 1] += 1000.
        return replace(base, numerator=altered)
    monkeypatch.setattr("graal_theory.figure4_basis.integrate_basis_bin", drift)
    failed = certify_basis_bin(*args, energy_rule="uniform", energy_order=2,
                               sobol_power=4, replica_seeds=tuple(range(8)))
    assert failed.status == "masked_nonconverged"
    with pytest.raises(ValueError):
        failed.predict([1., .08, -.03])


def test_native_energy_group_splits_exact_mass_onset(monkeypatch, tmp_path):
    monkeypatch.setattr("graal_theory.figure4_basis.delta_em_event_basis", ToyBasis)
    low = PhotonExposure(1.31, 10., 10., .5, .5)
    high = PhotonExposure(1.39, 10., 10., .5, .5)
    def spectrum(exposures):
        return FluxSpectrum((1.3, 1.4), exposures, len(exposures), len(exposures), 0,
                            tmp_path / "flux.root", tmp_path / "runs.csv")
    args = (ToyModel(), "p_eta", (1.3, 1.4), (1.7, 1.8))
    full = integrate_basis_bin(*args, energy_rule="native_flux", energy_order=1,
                               sobol=SobolConfig(4), flux_spectrum=spectrum((low, high)))
    upper = integrate_basis_bin(*args, energy_rule="native_flux", energy_order=1,
                                sobol=SobolConfig(4), flux_spectrum=spectrum((high,)))
    assert full.status == upper.status == "calculated"
    np.testing.assert_allclose(full.denominator, upper.denominator/2, rtol=1e-12)
    np.testing.assert_allclose(full.state_phi, upper.state_phi, rtol=1e-12)


def test_native_ratio_transfer_matches_explicit_global_azimuth(monkeypatch, tmp_path):
    @dataclass(frozen=True)
    class PolarToy(ToyModel):
        def amplitude(self, sample, polarization):
            return super().amplitude(sample, polarization)*(1.2 if polarization[1] else .8)
    monkeypatch.setattr("graal_theory.figure4_basis.delta_em_event_basis", ToyBasis)
    model = PolarToy()
    exposure = PhotonExposure(1.16, 30., 10., .65, .42)
    spectrum = FluxSpectrum((1.1, 1.2), (exposure,), 1, 1, 0,
                            tmp_path / "flux.root", tmp_path / "runs.csv")
    moment = integrate_basis_bin(model, "p_pi0", (1.1, 1.2), (1.08, 1.22),
                                 energy_rule="native_flux", energy_order=1,
                                 sobol=SobolConfig(4), flux_spectrum=spectrum)
    prediction = moment.evaluate([1., 0., 0.])
    proton = model.masses[2]
    s = s_from_lab_photon_energy(exposure.energy_gev, proton)
    sample = sample_three_body_mass_window(np.sqrt(s), model.masses, (2, 1),
                                            (1.08, 1.22), SobolConfig(4),
                                            reduce_global_azimuth=True)
    pair = sample.momenta[:, 2]+sample.momenta[:, 1]
    phi = np.arctan2(pair[:, 2], pair[:, 1])
    v = model.amplitude(sample, np.array([0., 1., 0.]))
    h = model.amplitude(sample, np.array([1., 0., 0.]))
    v2 = np.sum(abs(v)**2, axis=(1, 2))/2
    h2 = np.sum(abs(h)**2, axis=(1, 2))/2
    cross = np.real(np.sum(h.conj()*v, axis=(1, 2)))/2
    measure = (GEV2_TO_MICROBARN*4*proton**2/(2*(s-proton**2)*len(phi))
               *sample.weights_gev2)
    edges = np.linspace(0., 2*np.pi, 13)
    counts = np.zeros((2, 12))
    for j, (lower, upper) in enumerate(zip(edges[:-1], edges[1:])):
        beta = lower+(np.arange(256)+.5)*(upper-lower)/256
        angle = beta[:, None]-phi[None, :]
        contrast = (v2-h2)[None, :]*np.cos(2*angle)-2*cross[None, :]*np.sin(2*angle)
        for state, (flux, polarization, sign) in enumerate(((30., .65, 1), (10., .42, -1))):
            density = (v2+h2)[None, :]/2+sign*polarization*contrast/2
            counts[state, j] = flux*np.sum(np.mean(density, axis=0)*measure)*(upper-lower)/(2*np.pi)
    expected = fit_binned_asymmetry(counts[0], counts[1], 30., 10., .65, .42, edges)
    assert prediction.ratio_sigma == pytest.approx(expected, rel=2e-5, abs=2e-5)
    assert prediction.sigma == prediction.ratio_sigma


def test_native_certificate_rejects_unstable_state_phi_matrix(monkeypatch, tmp_path):
    monkeypatch.setattr("graal_theory.figure4_basis.delta_em_event_basis", ToyBasis)
    model = ToyModel()
    exposure = PhotonExposure(1.16, 30., 10., .65, .42)
    spectrum = FluxSpectrum((1.1, 1.2), (exposure,), 1, 1, 0,
                            tmp_path / "flux.root", tmp_path / "runs.csv")
    args = (model, "p_pi0", (1.1, 1.2), (1.08, 1.22))
    base = integrate_basis_bin(*args, energy_rule="native_flux", energy_order=1,
                               sobol=SobolConfig(4), flux_spectrum=spectrum)
    def drift(*unused, **kwargs):
        if kwargs["energy_order"] != 2:
            return base
        state = base.state_phi.copy()
        state[0, 0, 1, 1] += .1
        return replace(base, state_phi=state)
    monkeypatch.setattr("graal_theory.figure4_basis.integrate_basis_bin", drift)
    certificate = certify_basis_bin(*args, energy_rule="native_flux", energy_order=1,
                                    sobol_power=4, replica_seeds=tuple(range(8)),
                                    flux_spectrum=spectrum, data_stat_error=.1)
    assert certificate.status == "masked_nonconverged"
    assert "energy_matrix" in certificate.reason


def test_certificate_rejects_changed_physics_fingerprint(monkeypatch):
    monkeypatch.setattr("graal_theory.figure4_basis.delta_em_event_basis", ToyBasis)
    args = (ToyModel(), "p_pi0", (1.1, 1.2), (1.08, 1.22))
    base = integrate_basis_bin(*args, energy_rule="uniform", energy_order=2,
                               sobol=SobolConfig(4))
    base = replace(base, model_fingerprint="physics-a")
    def mixed(*unused, **kwargs):
        return replace(base, model_fingerprint="physics-b") if kwargs["energy_order"] == 4 else base
    monkeypatch.setattr("graal_theory.figure4_basis.integrate_basis_bin", mixed)
    certificate = certify_basis_bin(*args, energy_rule="uniform", energy_order=2,
                                    sobol_power=4, replica_seeds=tuple(range(8)))
    assert certificate.status == "masked_nonconverged"
    assert "model_fingerprint" in certificate.reason


def test_certificate_rejects_unstable_weighted_mass_matrix(monkeypatch):
    monkeypatch.setattr("graal_theory.figure4_basis.delta_em_event_basis", ToyBasis)
    args = (ToyModel(), "p_pi0", (1.1, 1.2), (1.08, 1.22))
    base = integrate_basis_bin(*args, energy_rule="uniform", energy_order=2,
                               sobol=SobolConfig(4))
    def drift(*unused, **kwargs):
        if kwargs["energy_order"] != 4:
            return base
        mass = base.mass_numerator.copy()
        mass[1, 1] += 1000.
        return replace(base, mass_numerator=mass)
    monkeypatch.setattr("graal_theory.figure4_basis.integrate_basis_bin", drift)
    certificate = certify_basis_bin(*args, energy_rule="uniform", energy_order=2,
                                    sobol_power=4, replica_seeds=tuple(range(8)))
    assert "energy_matrix" in certificate.reason


@pytest.mark.parametrize('bins,divisor', [(8,.9003),(12,.9549),(16,.9745)])
@pytest.mark.parametrize('fallback', [False, True])
def test_native_prediction_uses_declared_bin_correction_and_frozen_fit(bins, divisor, fallback):
    from graal_theory.figure4_basis import BasisBinMoment
    edges = np.linspace(0., 2*np.pi, bins+1)
    phi = (edges[1:]+edges[:-1])/2
    cosine, sine = np.cos(2*phi), np.sin(2*phi)
    # Asymmetric exposures/offset make cosine-only and diagnostic fits distinct.
    ratio = .13 + .27*cosine - .21*sine
    v, h = 1000*(1+.6*ratio), 700*(1-.4*ratio)
    states = np.zeros((2,bins,3,3), complex)
    states[0,:,0,0], states[1,:,0,0] = v, h
    d = np.eye(3,dtype=complex)
    moment = BasisBinMoment('p_eta',(1.1,1.2),(1.5,1.54),'native_flux',.27*d,d,
        states,1000.,700.,.6,.4,np.zeros_like(d),np.array([1.15]),'calculated',
        phi_bin_divisor=divisor, ratio_used_fallback=fallback)
    yv, yh = v/1000,h/700
    denom = .4*yv+.6*yh
    variance = (yh/denom**2/1000)**2*v + (yv/denom**2/700)**2*h
    design = np.column_stack((np.ones(bins), cosine, sine)) if fallback else cosine[:,None]
    fitted = np.linalg.lstsq(design/np.sqrt(variance[:,None]), ratio/np.sqrt(variance),rcond=None)[0]
    expected = fitted[1 if fallback else 0]/divisor
    assert moment.evaluate([1.,0.,0.]).sigma == pytest.approx(expected, abs=1e-13)
