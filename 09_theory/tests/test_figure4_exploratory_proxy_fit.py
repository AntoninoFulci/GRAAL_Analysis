"""A reused pilot basis must expose and limit its flux mismatch."""

from dataclasses import replace
import importlib
import json
from pathlib import Path
import shutil
import subprocess

import numpy as np
import pytest

from graal_theory.figure4_basis import BasisBinCertificate, BasisBinMoment, BinPrediction
from graal_theory.figure4_fit_output import BasisCheckpoint
from graal_theory.native_sigma import NativeSigmaData
from graal_theory.photon_flux import FluxSpectrum, PhotonExposure


def _script(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/"scripts"))
    return importlib.import_module("figure4_exploratory_proxy_fit")


def _data(size=6):
    keys = tuple(("p_pi0", 0, index) for index in range(size))
    return NativeSigmaData(
        keys, np.array([-.08+.02*i for i in range(size)]),
        np.full(size, .05), np.arange(size), np.eye(size)*.0025,
        None, np.array([1.1, 1.2]),
        {"p_pi0": np.linspace(1., 1.+.04*size, size+1)},
        {"profile": "uv", "phi_bins": "12", "background": "uncorrected",
         "phi_bin_correction": "ratio_only_rounded", "phi_bin_divisor": "0.9549"},
        "b"*64, "pilot",
    )


def _moment(index):
    eye = np.eye(3, dtype=np.complex128)
    return BasisBinMoment(
        "p_pi0", (1.1, 1.2), (1.+.04*index, 1.04+.04*index),
        "native_flux", eye/4, eye,
        np.zeros((2, 12, 3, 3), dtype=np.complex128),
        1., 1., .5, .5, eye/8, np.array([1.15]),
        "calculated", model_fingerprint="toy", anchor_g1=-.2,
        anchor_g2=.3, proton_mass_gev=.938,
        accessible_energy_gev=(1.1, 1.2),
    )


def _checkpoint(path, size=3):
    keys = tuple((0, "p_pi0", i) for i in range(size))
    checkpoint = BasisCheckpoint.open(path, target="native", keys=keys,
                                      fingerprint="a"*64, resume=False)
    checkpoint.manifest.update(policy="preliminary_uncertified_p6",
                               data_sha256="a"*64)
    checkpoint._write_manifest()
    for index in range(size):
        checkpoint.write(keys[index], BasisBinCertificate(
            _moment(index), "preliminary_uncertified",
            ("p6_only_no_convergence_check",), float("nan"), None, (), 0, None))
    return checkpoint


def test_proxy_accepts_matching_bins_and_small_recorded_flux_change(tmp_path, monkeypatch):
    module = _script(monkeypatch)
    checkpoint = _checkpoint(tmp_path/"basis")
    data = _data(3)
    spectrum = FluxSpectrum((1.1, 1.2),
                            (PhotonExposure(1.15, 1.001, 1.001, .5, .5),),
                            1, 1, 0, tmp_path/"flux.root", tmp_path/"manifest.csv",
                            "new-flux")
    monkeypatch.setattr(module, "native_flux_spectrum", lambda *args: spectrum)
    moments, audit = module.load_proxy_basis(
        checkpoint.path, data, tmp_path/"flux.root", tmp_path/"reco.root",
        tmp_path/"manifest.csv")
    assert len(moments) == 3
    assert audit["basis_original_data_sha256"] == "a"*64
    assert audit["fit_data_sha256"] == "b"*64
    assert audit["max_relative_flux_change"] == pytest.approx(.001)
    assert audit["max_energy_node_shift_gev"] == 0.
    assert audit["flux_source_fingerprint"] == "new-flux"


def test_proxy_rejects_large_flux_change_or_different_bins(tmp_path, monkeypatch):
    module = _script(monkeypatch)
    checkpoint = _checkpoint(tmp_path/"basis")
    spectrum = FluxSpectrum((1.1, 1.2),
                            (PhotonExposure(1.15, 1.02, 1., .5, .5),),
                            1, 1, 0, tmp_path/"flux.root", tmp_path/"manifest.csv",
                            "changed")
    monkeypatch.setattr(module, "native_flux_spectrum", lambda *args: spectrum)
    with pytest.raises(ValueError, match="flux change"):
        module.load_proxy_basis(checkpoint.path, _data(3), "flux", "reco", "manifest")
    data = replace(_data(3), mass_edges_gev={"p_pi0": np.array([1., 1.05, 1.09, 1.12])})
    with pytest.raises(ValueError, match="bin identity"):
        module.load_proxy_basis(checkpoint.path, data, "flux", "reco", "manifest")


def test_proxy_prediction_uses_stage07_finite_phi_bin_correction(monkeypatch):
    module = _script(monkeypatch)
    raw = ToyMoment(0).evaluate([1., 0., 0.]).ratio_sigma
    corrected = module.CorrectedRatioMoment(ToyMoment(0), .9549)
    assert corrected.evaluate([1., 0., 0.]).ratio_sigma == pytest.approx(raw/.9549)
    assert corrected.evaluate([1., 0., 0.]).sigma == pytest.approx(raw/.9549)


def test_proxy_rejects_wrong_experimental_ratio_convention(tmp_path, monkeypatch):
    module = _script(monkeypatch)
    checkpoint = _checkpoint(tmp_path/"basis")
    data = _data(3)
    data = replace(data, provenance={**data.provenance,
                                     "phi_bin_correction": "none"})
    with pytest.raises(ValueError, match="corrected 12-phi"):
        module.load_proxy_basis(checkpoint.path, data, "flux", "reco", "manifest")


class ToyMoment:
    def __init__(self, index):
        self.index = index
        self.status = "calculated"
        self.reason = None
        self.energy_rule = "native_flux"
        self.anchor_g1 = -.2
        self.anchor_g2 = .3
        self.proton_mass_gev = .938
        self.model_fingerprint = "toy"

    def evaluate(self, coefficients):
        _, x, y = coefficients
        sigma = -.08+.02*self.index+(.08+.02*self.index)*x+(.13-.015*self.index)*y
        return BinPrediction(sigma, 1., sigma, sigma, "native_flux")


def test_proxy_report_marks_mixed_inputs_and_uses_current_pilot_data(tmp_path, monkeypatch):
    module = _script(monkeypatch)
    data = _data()
    moments = {key: ToyMoment(i) for i, key in enumerate(data.keys)}
    monkeypatch.setattr(module, "load_native_sigma_root", lambda path: data)
    monkeypatch.setattr(module, "load_proxy_basis", lambda *args: (
        moments, {"basis_original_data_sha256": "a"*64,
                  "fit_data_sha256": data.source_sha256,
                  "max_relative_flux_change": .0019,
                  "max_energy_node_shift_gev": 5.8e-6,
                  "max_polarization_change": 3e-6,
                  "flux_source_fingerprint": "new-flux"}))
    monkeypatch.setattr(module, "_plot_proxy", lambda path, rows: Path(path).write_bytes(b"%PDF-1.4\n"))
    output = tmp_path/"fit"
    assert module.fit_proxy(output, "data.root", "basis", "flux", "reco", "manifest") == 0
    report = json.loads((output/"fit.json").read_text())
    assert report["status"] == "exploratory_pilot_proxy"
    assert report["included_bins"] == 6
    assert report["data_sha256"] == "b"*64
    assert report["proxy_audit"]["basis_original_data_sha256"] == "a"*64
    assert report["proxy_audit"]["max_relative_flux_change"] == .0019
    assert "uncertified" in " ".join(report["limitations"])
    assert (output/"native_comparison.csv").is_file()
    assert (output/"native_comparison.pdf").is_file()


@pytest.mark.skipif(shutil.which("pdftotext") is None, reason="pdftotext unavailable")
def test_proxy_pdf_has_visible_proxy_label(tmp_path, monkeypatch):
    module = _script(monkeypatch)
    row = {"energy_bin": 0, "pair": "p_pi0", "mass_center_gev": 1.02,
           "measured_sigma": .1, "stat_error": .05,
           "source_sigma": .08, "fitted_sigma": .11}
    path = tmp_path/"proxy.pdf"
    module._plot_proxy(path, [row])
    extracted = subprocess.run(["pdftotext", str(path), "-"], check=True,
                               capture_output=True, text=True).stdout
    assert "EXPLORATORY PROXY FIT" in extracted
