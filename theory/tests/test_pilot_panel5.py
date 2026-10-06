from pathlib import Path

import matplotlib.figure
import numpy as np
import pytest

from graal_theory.beam_asymmetry import BeamAsymmetryPrediction
from graal_theory.models.eta_pi0_p import EtaPi0PModel
from graal_theory.phase_space import SobolConfig
from graal_theory.pilot_panel5 import write_pilot_panel5

PUBLISHED = (
    Path(__file__).resolve().parents[2]
    / "test_data/beam_asymmetry/ajaka2008_figure4_digitized.csv"
)


def test_failed_pdf_save_leaves_no_pilot_output(tmp_path, monkeypatch):
    prediction = BeamAsymmetryPrediction(
        "eta_p", (1.20, 1.30), np.linspace(1.40, 1.80, 11),
        np.full(10, -0.5), np.array([1.25]), SobolConfig(power=4),
    )

    def fail_savefig(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(matplotlib.figure.Figure, "savefig", fail_savefig)
    output = tmp_path / "panel5"
    references = Path(__file__).resolve().parents[1] / "references"
    model = EtaPi0PModel.from_files(
        references / "central_parameters.json", references / "sources.json"
    )
    with pytest.raises(OSError, match="disk full"):
        write_pilot_panel5(output, prediction, PUBLISHED, model)
    assert not output.exists()
    assert list(tmp_path.iterdir()) == []


def test_pilot_rejects_unreviewed_digitization_under_ajaka_label(tmp_path):
    modified = tmp_path / "edited.csv"
    modified.write_text(PUBLISHED.read_text().replace("-0.5386", "-0.1000"), encoding="utf-8")
    references = Path(__file__).resolve().parents[1] / "references"
    model = EtaPi0PModel.from_files(
        references / "central_parameters.json", references / "sources.json"
    )
    prediction = BeamAsymmetryPrediction(
        "eta_p", (1.20, 1.30), np.linspace(1.40, 1.80, 11),
        np.full(10, -0.5), np.array([1.25]), SobolConfig(power=4),
    )
    output = tmp_path / "panel5"
    with pytest.raises(ValueError, match="digitization checksum"):
        write_pilot_panel5(output, prediction, modified, model)
    assert not output.exists()


def test_flux_pilot_records_both_estimators_and_source_coverage(tmp_path):
    from graal_theory.photon_flux import FluxSpectrum, PhotonExposure
    from graal_theory.pilot_panel5 import write_pilot_panel5
    references = Path(__file__).resolve().parents[1] / "references"
    model = EtaPi0PModel.from_files(
        references / "central_parameters.json", references / "sources.json"
    )
    root = tmp_path / "flux.root"
    root.write_bytes(b"ROOT fixture")
    manifest = tmp_path / "manifest.csv"
    manifest.write_text("manifest fixture")
    spectrum = FluxSpectrum(
        (1.20, 1.30), (PhotonExposure(1.25, 2.0, 3.0, 0.9, 0.8),),
        2, 1, 4, root, manifest,
    )
    prediction = BeamAsymmetryPrediction(
        "eta_p", (1.20, 1.30), np.linspace(1.40, 1.80, 11),
        np.full(10, -0.5), np.array([1.25]), SobolConfig(power=4),
        "measured_P_UV_flux", np.full(10, -0.47),
    )
    output = tmp_path / "panel5"
    write_pilot_panel5(output, prediction, PUBLISHED, model, flux_spectrum=spectrum)
    import json
    payload = json.loads((output / "prediction.json").read_text())
    assert payload["sigma_phi_fit"] == pytest.approx([-0.47] * 10)
    assert payload["flux_source"]["selected_runs"] == 2
    assert payload["flux_source"]["complete_runs"] == 1
    assert payload["flux_source"]["exposures"] == 1
    assert len(payload["flux_source"]["root_sha256"]) == 64
    assert "uniform photon-energy weighting" not in payload["limitations"]


def test_flux_pilot_rejects_source_from_different_energy_interval(tmp_path):
    references = Path(__file__).resolve().parents[1] / "references"
    model = EtaPi0PModel.from_files(
        references / "central_parameters.json", references / "sources.json"
    )
    from graal_theory.photon_flux import FluxSpectrum, PhotonExposure
    spectrum = FluxSpectrum(
        (1.10, 1.20), (PhotonExposure(1.15, 1.0, 1.0, 0.8, 0.8),),
        1, 1, 0, tmp_path / "wrong.root", tmp_path / "runs.csv",
    )
    prediction = BeamAsymmetryPrediction(
        "eta_p", (1.20, 1.30), np.linspace(1.40, 1.80, 11),
        np.full(10, -0.5), np.array([1.25]), SobolConfig(power=4),
        "measured_P_UV_flux", np.full(10, -0.47),
    )
    with pytest.raises(ValueError, match="flux source energy interval"):
        write_pilot_panel5(tmp_path / "panel5", prediction, PUBLISHED, model, flux_spectrum=spectrum)
    assert not (tmp_path / "panel5").exists()
