from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from graal_theory.beam_asymmetry import (
    asymmetry_from_polarized_weights,
    predict_beam_asymmetry,
)
from graal_theory.models.eta_pi0_p import EtaPi0PModel
from graal_theory.phase_space import SobolConfig, ThreeBodySample
from graal_theory.photon_flux import FluxSpectrum, PhotonExposure

REFERENCES = Path(__file__).resolve().parents[1] / "references"


def test_vertical_minus_horizontal_harmonic_has_experimental_sign():
    # Y_V - Y_H = Sigma cos(2 phi) * (Y_V + Y_H) for fully polarized beams.
    phi = np.array([0.0, np.pi / 4, np.pi / 2, 3 * np.pi / 4])
    cosine = np.cos(2 * phi)
    sigma = -0.4
    vertical = 1.0 + sigma * cosine
    horizontal = 1.0 - sigma * cosine
    mass = np.full(4, 1.50)
    result = asymmetry_from_polarized_weights(
        mass, phi, vertical, horizontal, np.array([1.48, 1.52, 1.56])
    )
    assert result[0] == pytest.approx(sigma)
    assert np.isnan(result[1])


def test_pilot_panel_has_no_curve_below_physical_p_eta_threshold():
    model = EtaPi0PModel.from_files(
        REFERENCES / "central_parameters.json", REFERENCES / "sources.json"
    )
    prediction = predict_beam_asymmetry(
        1.20, 1.30, "eta_p", np.linspace(1.40, 1.80, 11),
        model, SobolConfig(power=14, scramble=True, seed=2026), energy_nodes=9,
    )
    assert prediction.pair == "eta_p"
    assert prediction.sigma.shape == (10,)
    assert np.isnan(prediction.sigma[:2]).all()
    assert prediction.sigma[3] < -0.2
    assert prediction.energy_weighting == "uniform"


def test_energy_interval_must_have_positive_width():
    model = EtaPi0PModel.from_files(
        REFERENCES / "central_parameters.json", REFERENCES / "sources.json"
    )
    with pytest.raises(ValueError, match="energy interval"):
        predict_beam_asymmetry(
            1.20, 1.20, "eta_p", np.linspace(1.40, 1.80, 11),
            model, SobolConfig(power=4), energy_nodes=3,
        )


def test_reachable_but_unsampled_edge_bin_is_not_called_unphysical():
    model = EtaPi0PModel.from_files(
        REFERENCES / "central_parameters.json", REFERENCES / "sources.json"
    )
    with pytest.raises(ValueError, match="reachable mass bin 7.*no sampled weight"):
        predict_beam_asymmetry(
            1.20, 1.30, "eta_p", np.linspace(1.40, 1.80, 11),
            model, SobolConfig(power=8, scramble=True, seed=2026), energy_nodes=3,
        )


def test_low_resolution_unphysical_sigma_is_rejected():
    model = EtaPi0PModel.from_files(
        REFERENCES / "central_parameters.json", REFERENCES / "sources.json"
    )
    with pytest.raises(ValueError, match=r"mass bin 7.*outside \[-1, 1\]"):
        predict_beam_asymmetry(
            1.20, 1.30, "eta_p", np.linspace(1.40, 1.80, 11),
            model, SobolConfig(power=8, scramble=True, seed=2026), energy_nodes=9,
        )


def test_nonfinite_polarized_amplitude_names_energy_and_event(monkeypatch):
    model = EtaPi0PModel.from_files(
        REFERENCES / "central_parameters.json", REFERENCES / "sources.json"
    )
    original = EtaPi0PModel.polarized_matrix_element_squared

    def nonfinite_vertical(self, sample, polarization):
        values = original(self, sample, polarization)
        if polarization[1] == 1.0:
            values[3] = np.nan
        return values

    monkeypatch.setattr(EtaPi0PModel, "polarized_matrix_element_squared", nonfinite_vertical)
    with pytest.raises(ValueError, match=r"vertical.*E_gamma=.*event=3"):
        predict_beam_asymmetry(
            1.20, 1.30, "eta_p", np.linspace(1.40, 1.80, 11),
            model, SobolConfig(power=4), energy_nodes=3,
        )


def test_energy_nodes_sum_cross_sections_before_forming_sigma(monkeypatch):
    from graal_theory import beam_asymmetry

    phi = np.arange(4) * np.pi / 4.0
    momentum = np.column_stack(
        (np.full(4, np.sqrt(1.5**2 + 0.1**2)), 0.1 * np.cos(phi), 0.1 * np.sin(phi), np.zeros(4))
    )

    def toy_sample(sqrt_s, masses, config):
        momenta = np.zeros((4, 3, 4))
        momenta[:, 0] = momentum
        initial = np.tile([sqrt_s, 0.0, 0.0, 0.0], (4, 1))
        return ThreeBodySample(initial, momenta, np.ones(4), masses, np.zeros(4), config)

    class ToyModel:
        parameters = SimpleNamespace(proton_mass_gev=0.938)
        masses = (0.548, 0.135, 0.938)

        def polarized_matrix_element_squared(self, sample, polarization):
            lower_node = sample.initial[0, 0] < np.sqrt(0.938**2 + 2 * 0.938 * 1.25)
            sigma, cross_section_scale = (0.5, 1.0) if lower_node else (-0.25, 4.0)
            flux = sample.initial[0, 0] ** 2 - 0.938**2
            sign = 1.0 if polarization[1] == 1.0 else -1.0
            return flux * cross_section_scale * (1.0 + sign * sigma * np.cos(2 * phi))

    monkeypatch.setattr(beam_asymmetry, "sample_three_body", toy_sample)
    result = predict_beam_asymmetry(
        1.20, 1.30, "eta_p", np.array([1.48, 1.52]),
        ToyModel(), SobolConfig(power=4), energy_nodes=2,
    )
    # Unequal node cross sections, 1:4: (0.5 + 4*(-0.25)) / 5 = -0.1.
    assert result.sigma[0] == pytest.approx(-0.1, abs=1e-12)


def test_flux_prediction_uses_separate_state_spectra_before_phi_fit(monkeypatch):
    from graal_theory import beam_asymmetry

    phi = (np.arange(12) + 0.5) * np.pi / 6.0
    momentum = np.column_stack((
        np.full(12, np.sqrt(1.5**2 + 0.1**2)),
        0.1 * np.cos(phi), 0.1 * np.sin(phi), np.zeros(12),
    ))

    def toy_sample(sqrt_s, masses, config):
        momenta = np.zeros((12, 3, 4))
        momenta[:, 0] = momentum
        initial = np.tile([sqrt_s, 0.0, 0.0, 0.0], (12, 1))
        return ThreeBodySample(initial, momenta, np.ones(12), masses, np.zeros(12), config)

    class ToyModel:
        parameters = SimpleNamespace(proton_mass_gev=0.938)
        masses = (0.548, 0.135, 0.938)

        def polarized_matrix_element_squared(self, sample, polarization):
            lower = sample.initial[0, 0] < np.sqrt(0.938**2 + 2 * 0.938 * 1.25)
            scale = 1.0 if lower else 3.0
            sign = 1.0 if polarization[1] == 1.0 else -1.0
            return (sample.initial[0, 0]**2 - 0.938**2) * scale * (1 - sign * 0.5 * np.cos(2 * phi))

    monkeypatch.setattr(beam_asymmetry, "sample_three_body", toy_sample)
    spectrum = FluxSpectrum(
        (1.20, 1.30),
        (PhotonExposure(1.22, 3.0, 1.0, 1.0, 1.0), PhotonExposure(1.28, 1.0, 3.0, 1.0, 1.0)),
        2, 2, 0, Path("flux.root"), Path("manifest.csv"),
    )
    result = beam_asymmetry.predict_flux_weighted_asymmetry(
        spectrum, "eta_p", np.array([1.48, 1.52]), ToyModel(), SobolConfig(power=4), energy_bins=2,
    )
    assert result.sigma[0] == pytest.approx(-0.5, abs=1e-12)
    assert result.sigma_phi_fit is not None
    # Unequal energy spectra create a nonzero ratio offset; center-only fit differs from intrinsic moment.
    assert result.sigma_phi_fit[0] != pytest.approx(-0.5, abs=0.01)
    assert result.energy_weighting == "measured_P_UV_flux"
