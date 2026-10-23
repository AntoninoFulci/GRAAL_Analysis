"""Checkpoint integrity for expensive Figure 4 basis bins."""

import json
import subprocess

import numpy as np
import pytest

from graal_theory.figure4_basis import BasisBinCertificate, BasisBinMoment
from graal_theory.figure4_fit_output import (BasisCheckpoint, basis_panels,
                                             fingerprint_inputs, write_fit_bundle)
from graal_theory.figure4_comparison import compare_figure4
from graal_theory.figure4_reference import PAIR_MASS_AXES, PublishedCurvePoint
from graal_theory.figure4_fit import FitResult


def _certificate():
    identity = np.eye(3, dtype=np.complex128)
    moment = BasisBinMoment(
        "p_pi0", (1.1, 1.2), (1.0, 1.04), "uniform", identity/4, identity,
        None, None, None, None, None, identity/8, np.array([1.15]),
        "calculated", model_fingerprint="toy", anchor_g1=-.2, anchor_g2=.3,
        proton_mass_gev=.938, mass_numerator=identity*1.02,
        accessible_energy_gev=(1.1, 1.2), accessible_mass_gev=(1.0, 1.04),
    )
    return BasisBinCertificate(moment, "calculated", (), .002,
                               np.eye(54), (moment,)*12, 8, None)


def test_checkpoint_resume_preserves_complex_moments_and_skips_valid_bin(tmp_path):
    path = tmp_path / "basis"
    keys = ((0, "p_pi0", 0), (0, "p_pi0", 1))
    checkpoint = BasisCheckpoint.open(path, target="ajaka", keys=keys,
                                      fingerprint="a"*64, resume=False)
    assert checkpoint.pending_keys() == keys
    checkpoint.write(keys[0], _certificate())
    assert checkpoint.pending_keys() == (keys[1],)
    assert json.loads((path / "manifest.json").read_text())["complete"] is False

    resumed = BasisCheckpoint.open(path, target="ajaka", keys=keys,
                                   fingerprint="a"*64, resume=True)
    assert resumed.pending_keys() == (keys[1],)
    restored = resumed.read(keys[0])
    np.testing.assert_array_equal(restored.moment.denominator,
                                  _certificate().moment.denominator)
    assert restored.moment.weighted_mass_gev([1., 0., 0.]) == pytest.approx(1.02)
    assert restored.checks[0].model_fingerprint == "toy"
    resumed.write(keys[1], _certificate())
    resumed.finish()
    assert json.loads((path / "manifest.json").read_text())["complete"] is True


def test_checkpoint_changed_fingerprint_refuses_resume(tmp_path):
    path = tmp_path / "basis"
    BasisCheckpoint.open(path, target="ajaka", keys=((0, "p_pi0", 0),),
                         fingerprint="a"*64, resume=False)
    with pytest.raises(ValueError, match="fingerprint"):
        BasisCheckpoint.open(path, target="ajaka", keys=((0, "p_pi0", 0),),
                             fingerprint="b"*64, resume=True)


def test_checkpoint_corrupt_bin_recomputed_and_never_marked_complete(tmp_path):
    path = tmp_path / "basis"
    key = (0, "p_pi0", 0)
    checkpoint = BasisCheckpoint.open(path, target="ajaka", keys=(key,),
                                      fingerprint="a"*64, resume=False)
    checkpoint.write(key, _certificate())
    (path / "bins" / "0_p_pi0_0.npz").write_bytes(b"interrupted")
    resumed = BasisCheckpoint.open(path, target="ajaka", keys=(key,),
                                   fingerprint="a"*64, resume=True)
    assert resumed.pending_keys() == (key,)
    with pytest.raises(ValueError, match="missing|corrupt"):
        resumed.finish()


def test_fingerprint_tracks_source_data_settings_and_dirty_code(tmp_path):
    reference, root, code = (tmp_path / name for name in ("parameter.json", "data.root", "code.py"))
    for path in (reference, root, code):
        path.write_text("one")
    inputs = {"parameter": reference, "root": root, "code": code}
    baseline = fingerprint_inputs("native", inputs, {"energy_rule": "native_flux", "sobol_power": 8})
    for path in inputs.values():
        path.write_text("two")
        assert fingerprint_inputs("native", inputs, {"energy_rule": "native_flux", "sobol_power": 8}) != baseline
        path.write_text("one")
    assert fingerprint_inputs("native", inputs, {"energy_rule": "uniform", "sobol_power": 8}) != baseline
    assert fingerprint_inputs("native", inputs, {"energy_rule": "native_flux", "sobol_power": 9}) != baseline


def test_sourced_discrepancy_cannot_be_promoted_by_fitted_agreement(tmp_path):
    certificates = {}
    published = []
    for energy in range(4):
        for pair, (low, high) in PAIR_MASS_AXES.items():
            edges = np.linspace(low, high, 11)
            for mass in range(10):
                center = float((edges[mass]+edges[mass+1])/2)
                identity = np.eye(3, dtype=np.complex128)
                numerator = identity*.2
                numerator[0, 1] = numerator[1, 0] = .5
                moment = BasisBinMoment(
                    pair, (1.1+.1*energy, 1.2+.1*energy),
                    (float(edges[mass]), float(edges[mass+1])), "uniform",
                    numerator, identity, None, None, None, None, None,
                    identity/8, np.array([1.15+.1*energy]), "calculated",
                    model_fingerprint="toy", anchor_g1=-.2, anchor_g2=.3,
                    proton_mass_gev=.938, mass_numerator=identity*center,
                    accessible_energy_gev=(1.1+.1*energy, 1.2+.1*energy),
                    accessible_mass_gev=(float(edges[mass]), float(edges[mass+1])),
                    vertical_normalization=identity/2,
                    horizontal_normalization=identity/2)
                certificates[energy, pair, mass] = BasisBinCertificate(
                    moment, "calculated", (), .001, None, (moment,)*12, 8, None)
            published.extend([
                PublishedCurvePoint(pair, energy,
                                    float((edges[index]+edges[index+1])/2), .29, .02)
                for index in (2, 7)
            ])
    source = basis_panels(certificates, np.array([1., 0., 0.]),
                          energy_order=2, sobol_power=4, replica_seeds=tuple(range(8)))
    fitted = basis_panels(certificates, np.array([1., .1, 0.]),
                          energy_order=2, sobol_power=4, replica_seeds=tuple(range(8)))
    source_comparison = compare_figure4(source, tuple(published))
    fitted_comparison = compare_figure4(fitted, tuple(published))
    assert source_comparison.status == "calculated_discrepant"
    assert fitted_comparison.status == "reproduced"
    assert source[(0, "p_pi0")].bins[0].sigma == pytest.approx(.2)
    assert fitted[(0, "p_pi0")].bins[0].sigma == pytest.approx((.2+.1+.002)/1.01)
    provenance = {"source_sha256": "a"*64, "parameters_sha256": "b"*64,
                  "code_sha256": "c"*64}
    fit = FitResult("fit_computed", np.array([-.1, .3]), np.array([-.0938, .2639]),
                    np.array([-.2, .3]), np.array([-.1876, .2639]),
                    np.zeros(6), 0., 4, np.array([2., 1.]), np.eye(2),
                    "d"*64, "toy", "converged", 4)
    write_fit_bundle(tmp_path/"bundle", source, fitted,
                     source_comparison, fitted_comparison, fit, provenance,
                     np.eye(6))
    manifest = json.loads((tmp_path/"bundle"/"manifest.json").read_text())
    assert manifest["sourced_status"] == "calculated_discrepant"
    assert manifest["fitted_status"] == "fitted_agreement"
    assert manifest["fit_status"] == "fit_computed"
    assert json.loads((tmp_path/"bundle"/"fit.json").read_text())["theta_internal"] == [-.1, .3]
    assert (tmp_path/"bundle"/"sourced"/"figure4_comparison.pdf").read_bytes().startswith(b"%PDF")
    assert json.loads((tmp_path/"bundle"/"sourced"/"manifest.json").read_text())["status"] == "calculated_discrepant"
    fitted_manifest = json.loads((tmp_path/"bundle"/"fitted"/"manifest.json").read_text())
    assert fitted_manifest["status"] == "fitted_agreement"
    assert fitted_manifest["claim_kind"] == "fitted"
    pdf_text = subprocess.check_output([
        "pdftotext", str(tmp_path/"bundle"/"fitted"/"figure4_comparison.pdf"), "-"
    ], text=True)
    assert "Fitted couplings" in pdf_text
