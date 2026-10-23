"""Pilot fit workflow never turns p6 raw moments into certificates."""

from dataclasses import replace
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from graal_theory.figure4_basis import BasisBinMoment, BinPrediction
from graal_theory.figure4_fit_output import BasisCheckpoint
from graal_theory.native_sigma import NativeSigmaData


def _workflow():
    path = Path(__file__).resolve().parents[1]/"scripts"/"figure4_exploratory_fit.py"
    assert path.exists(), "exploratory fit workflow script is missing"
    spec = importlib.util.spec_from_file_location("figure4_exploratory_fit", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _data(size=6):
    keys = tuple(("p_pi0", 0, index) for index in range(size))
    covariance = np.eye(size)*.0025+np.ones((size, size))*.0001
    return NativeSigmaData(keys, np.array([-.08+.02*i for i in range(size)]),
                           np.full(size, .05), np.arange(size), covariance,
                           None, np.array([1.1, 1.2]),
                           {"p_pi0": np.linspace(1.0, 1.4, size+1)},
                           {"profile": "uv", "background": "uncorrected"},
                           "a"*64, "pilot")


def _raw_moment(index):
    identity = np.eye(3, dtype=np.complex128)
    return BasisBinMoment("p_pi0", (1.1, 1.2), (1.+.04*index, 1.04+.04*index),
                          "native_flux", identity/4, identity,
                          np.zeros((2, 12, 3, 3), dtype=np.complex128),
                          1., 1., .5, .5, identity/8, np.array([1.15]),
                          "calculated", model_fingerprint="toy", anchor_g1=-.2,
                          anchor_g2=.3, proton_mass_gev=.938)


def test_basis_checkpoints_are_explicitly_uncertified_and_resume(tmp_path, monkeypatch):
    module = _workflow()
    files = []
    for name in ("data.root", "reco.root", "flux.root", "manifest.csv"):
        path = tmp_path/name
        path.write_bytes(name.encode())
        files.append(path)
    data = replace(_data(3), mass_edges_gev={"p_pi0": np.linspace(1., 1.12, 4)})
    monkeypatch.setattr(module, "load_native_sigma_root", lambda path: data)
    monkeypatch.setattr(module, "native_flux_spectrum", lambda *args: object())
    calls = []
    def calculate(task):
        key = task[0]
        calls.append(key)
        return key, _raw_moment(key[2])
    monkeypatch.setattr(module, "_calculate", calculate)
    output = tmp_path/"basis"
    assert module.build_pilot_basis(output, *files, workers=1) == 0
    assert len(calls) == 3
    manifest = json.loads((output/"manifest.json").read_text())
    assert manifest["complete"] is True
    assert manifest["policy"] == "preliminary_uncertified_p6"
    checkpoint = BasisCheckpoint(output, manifest)
    assert all(checkpoint.read((0, "p_pi0", i)).status == "preliminary_uncertified"
               for i in range(3))
    assert len(module._load_basis(output, data, files[0])) == 3
    with pytest.raises(ValueError, match="ROOT path differs"):
        module._load_basis(output, data, files[1])
    monkeypatch.setattr(module, "_calculate", lambda task: (_ for _ in ()).throw(
        AssertionError("completed bin recomputed")))
    assert module.build_pilot_basis(output, *files, workers=1) == 0
    altered = checkpoint.read((0, "p_pi0", 0))
    checkpoint.write((0, "p_pi0", 0), replace(
        altered, moment=replace(altered.moment, mass_range_gev=(1.01, 1.04))))
    checkpoint.finish()
    with pytest.raises(ValueError, match="bin identity mismatch"):
        module._load_basis(output, data, files[0])


class ToyMoment:
    def __init__(self, index, status="calculated"):
        self.index = index
        self.status = status
        self.reason = "inner quadrature" if status != "calculated" else None
        self.energy_rule = "native_flux"
        self.anchor_g1 = -.2
        self.anchor_g2 = .3
        self.proton_mass_gev = .938
        self.model_fingerprint = "toy"

    def evaluate(self, coefficients):
        _, x, y = coefficients
        a, b = .08+.02*self.index, .13-.015*self.index
        sigma = -.08+.02*self.index+a*x+b*y
        return BinPrediction(sigma, 1., sigma, sigma, "native_flux")


def test_fit_report_uses_pilot_label_and_lists_excluded_bins(tmp_path, monkeypatch):
    module = _workflow()
    data = _data()
    truth = np.array([-.13, .26])
    moments = {key: ToyMoment(index) for index, key in enumerate(data.keys)}
    data = replace(data, sigma=np.array([moment.evaluate([1., truth[0]+.2,
                              truth[1]-.3]).sigma for moment in moments.values()]))
    omitted = data.keys[1]
    moments[omitted] = ToyMoment(1, status="masked_nonconverged")
    monkeypatch.setattr(module, "load_native_sigma_root", lambda path: data)
    monkeypatch.setattr(module, "_load_basis", lambda path, data, data_root: moments)
    output = tmp_path/"fit"
    assert module.fit_pilot(output, tmp_path/"data.root", tmp_path/"basis") == 0
    result = json.loads((output/"fit.json").read_text())
    assert result["status"] == "exploratory_pilot"
    assert result["included_bins"] == 5
    assert result["excluded_bins"] == [{"key": list(omitted), "reason": "inner quadrature"}]
    assert result["data_status"] == "pilot"
    assert (output/"native_comparison.csv").exists()
    assert (output/"native_comparison.pdf").stat().st_size > 1000
