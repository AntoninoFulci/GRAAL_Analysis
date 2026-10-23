"""Diagnostics must preserve interference, integration measure and nesting."""

import importlib.util
import json
from functools import partial
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from graal_theory.figure4_integration import (
    predict_figure4_bin, project_azimuth_averaged_moments,
)
from graal_theory.phase_space import SobolConfig


def module():
    path = Path(__file__).resolve().parents[1]/"scripts/figure4_variance_diagnostic.py"
    assert path.exists(), "event-level variance diagnostic missing"
    spec = importlib.util.spec_from_file_location("variance_diagnostic", path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class InterferingModel:
    masses = (.547862, .1349768, .93827208816)
    parameters = SimpleNamespace(proton_mass_gev=masses[2])

    def family_amplitudes(self, sample, epsilon):
        x = sample.momenta[:, 0, 1]
        scale = (1+x+1j*x) if epsilon[0] else (2-x+.3j)
        a = scale[:, None, None]*np.eye(2)[None, :, :]
        return {"first": a, "destructive": -.4*a}

    def amplitude(self, sample, epsilon):
        return np.add.reduce(tuple(self.family_amplitudes(sample, epsilon).values()))


def test_signed_family_allocation_retains_destructive_interference():
    m = module()
    identity = np.eye(2, dtype=complex)[None, :, :]
    v = np.stack([2*identity, -identity])
    h = np.stack([identity, -.5*identity])
    n, d = m.allocate_moments(np.array([0.]), v, h, np.array([1.]))
    np.testing.assert_allclose(n[:, 0], [1.5, -.75])
    np.testing.assert_allclose(d[:, 0], [2.5, -1.25])
    expected = project_azimuth_averaged_moments([0.], v.sum(0), h.sum(0), [1.])
    np.testing.assert_allclose([n.sum(), d.sum()], expected)


def test_complex_cross_polarization_allocation_recomposes_global_average():
    m = module()
    rng = np.random.default_rng(19)
    v = rng.normal(size=(7, 16, 2, 2))+1j*rng.normal(size=(7, 16, 2, 2))
    h = rng.normal(size=v.shape)+1j*rng.normal(size=v.shape)
    phi = rng.uniform(-np.pi, np.pi, 16)
    weights = rng.uniform(0, 1, 16)
    n, d = m.allocate_moments(phi, v, h, weights)
    expected = project_azimuth_averaged_moments(phi, v.sum(0), h.sum(0), weights)
    np.testing.assert_allclose([n.sum(), d.sum()], expected, atol=1e-12)


@pytest.mark.parametrize("pair,energy,mass", [
    ("eta_pi0", (1.1, 1.2), (.72, .76)),
    ("p_eta", (1.3, 1.4), (1.70, 1.80)),  # onset clips energy and mass
    ("p_pi0", (1.4, 1.5), (1.12, 1.16)),
])
@pytest.mark.parametrize("seed", [None, 2026])
def test_captured_prefixes_match_independent_integrations(pair, energy, mass, seed):
    m = module()
    model = InterferingModel()
    config = SobolConfig(5, scramble=seed is not None, seed=seed)
    report, arrays = m.diagnose_bin(model, pair, energy, mass,
                                    energy_order=3, sobol=config)
    assert report["purpose"] == "event_variance_diagnostic_only"
    for row in report["resolutions"]:
        reference = predict_figure4_bin(model, pair, energy, mass, energy_order=3,
            sobol=SobolConfig(row["power"], scramble=seed is not None, seed=seed))
        np.testing.assert_allclose([row["numerator"], row["denominator"]],
            [reference.numerator, reference.denominator], rtol=1e-12, atol=1e-12)
        for field in ("numerator", "denominator"):
            assert sum(row["families"][field]) == pytest.approx(row[field])
            for axis in row["marginals"].values():
                assert sum(axis[field]) == pytest.approx(row[field])
    assert arrays["momenta"].shape == (3, 32, 3, 4)
    assert np.all(arrays["denominator"] >= 0)
    for axis in report["refinements"][0]["marginal_drift"].values():
        assert sum(axis["denominator"]) == pytest.approx(
            report["refinements"][0]["denominator_delta"])


def test_inaccessible_bin_is_not_a_diagnostic_success():
    with pytest.raises(ValueError, match="masked_kinematic"):
        module().diagnose_bin(InterferingModel(), "p_eta", (1.1, 1.2), (2., 3.),
                              energy_order=1, sobol=SobolConfig(4))


def test_cli_records_replayable_arrays_and_refuses_overwrite(tmp_path, monkeypatch):
    m = module()
    monkeypatch.setattr(m, "_figure4_model", lambda *args: InterferingModel())
    output = tmp_path/"diagnostic"
    args = ["--mass", ".72", ".76", "--output", str(output)]
    assert m.main(args) == 0
    report = json.loads((output/"report.json").read_text())
    with np.load(output/"events.npz") as events:
        assert events["denominator"].sum() == pytest.approx(report["resolutions"][-1]["denominator"])
    assert (output/"COMPLETE").exists()
    original = (output/"report.json").read_bytes()
    with pytest.raises(FileExistsError):
        m.main(args)
    assert (output/"report.json").read_bytes() == original


def test_cli_failure_never_marks_run_complete(tmp_path, monkeypatch):
    m = module()
    monkeypatch.setattr(m, "_figure4_model", lambda *args: InterferingModel())
    output = tmp_path/"failed"
    with pytest.raises(ValueError, match="masked_kinematic"):
        m.main(["--mass", "2", "3", "--output", str(output)])
    assert (output/"failure.json").exists()
    assert not (output/"COMPLETE").exists()


def test_cli_rejects_import_from_another_checkout_before_writing_provenance(tmp_path, monkeypatch):
    import graal_theory
    m = module()
    monkeypatch.setattr(m, "_figure4_model", lambda *args: InterferingModel())
    monkeypatch.setattr(graal_theory, "__file__", str(tmp_path/"other/graal_theory/__init__.py"))
    output = tmp_path/"wrong-checkout"
    with pytest.raises(ValueError, match="checkout"):
        m.main(["--mass", ".72", ".76", "--output", str(output)])
    assert not output.exists()


def test_candidate_diagnostic_preserves_prefixes_and_restores_sampler():
    from graal_theory import figure4_integration
    from unittest.mock import patch
    m = module()
    path = Path(__file__).resolve().parents[1]/"scripts/figure4_joint_map_probe.py"
    spec = importlib.util.spec_from_file_location("joint_map", path)
    joint = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(joint)
    sampler = partial(joint.sample_delta_helicity, resonance_mass=1.232, resonance_width=.117)
    original = figure4_integration.sample_three_body_mass_window
    report, _ = m.diagnose_bin(InterferingModel(), "eta_pi0", (1.1, 1.2), (.72, .76),
        energy_order=2, sobol=SobolConfig(5), sampler=sampler, coordinate_names=joint.COORDINATES)
    assert figure4_integration.sample_three_body_mass_window is original
    with patch.object(figure4_integration, "sample_three_body_mass_window", sampler):
        reference = predict_figure4_bin(InterferingModel(), "eta_pi0", (1.1, 1.2), (.72, .76),
                                        energy_order=2, sobol=SobolConfig(4))
    assert report["resolutions"][0]["denominator"] == pytest.approx(reference.denominator)
    assert report["coordinate_names"] == list(joint.COORDINATES)
    def broken(*args, **kwargs):
        raise ValueError("candidate failed")
    with pytest.raises(ValueError, match="candidate failed"):
        m.diagnose_bin(InterferingModel(), "eta_pi0", (1.1, 1.2), (.72, .76),
                       energy_order=2, sobol=SobolConfig(4), sampler=broken)
    assert figure4_integration.sample_three_body_mass_window is original


def test_cli_candidate_records_map_source_and_actual_resonance_parameters(tmp_path, monkeypatch):
    m = module()
    monkeypatch.setattr(m, "_figure4_model", lambda *args: InterferingModel())
    monkeypatch.setattr(InterferingModel.parameters, "tree",
        SimpleNamespace(delta_mass_gev=1.232, delta_width_gev=.117), raising=False)
    output = tmp_path/"candidate"
    assert m.main(["--mass", ".72", ".76", "--sampler", "delta-helicity",
                   "--output", str(output)]) == 0
    p = json.loads((output/"provenance.json").read_text())
    r = json.loads((output/"report.json").read_text())
    assert "scripts/figure4_joint_map_probe.py" in p["sha256"]
    assert r["sampler"]["name"] == "delta-helicity"
    assert r["sampler"]["resonance_mass_gev"] == 1.232
    assert r["sampler"]["resonance_width_gev"] == .117
