import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

THEORY_ROOT = Path(__file__).resolve().parents[1]


def _run_cli(*args):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(THEORY_ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "graal_theory.cli", *args],
        cwd=THEORY_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_figure4_full_command_dispatches_explicit_numerical_settings(tmp_path, monkeypatch):
    from graal_theory import cli
    observed = []
    def fake(args):
        observed.append((args.output, args.energy_order, args.sobol_power,
                         args.replicas, args.workers, args.mode))
        return 2
    monkeypatch.setattr(cli, "_figure4_full", fake, raising=False)
    result = cli.main(["figure4-full", "--output", str(tmp_path/"run"),
                       "--energy-order", "4", "--sobol-power", "6",
                       "--replicas", "8", "--workers", "4", "--mode", "grid"])
    assert result == 2
    assert observed == [(tmp_path/"run", 4, 6, 8, 4, "grid")]


def test_figure4_full_adaptive_cli_passes_power_bounds(tmp_path, monkeypatch):
    from graal_theory import cli
    seen = []
    monkeypatch.setattr(cli, "_figure4_full", lambda args:
                        seen.append((args.adaptive_min_power, args.adaptive_max_power)) or 0)
    assert cli.main(["figure4-full", "--output", str(tmp_path/"run"),
                     "--adaptive-min-power", "5", "--adaptive-max-power", "8"]) == 0
    assert seen == [(5, 8)]


def test_basis_cli_rejects_missing_native_inputs_and_mixed_ajaka_inputs(tmp_path):
    missing = _run_cli("figure4-basis-build", "--target", "native",
                       "--output", str(tmp_path/"native"))
    assert missing.returncode == 1
    assert "reco-root" in missing.stderr
    assert not (tmp_path/"native").exists()
    mixed = _run_cli("figure4-basis-build", "--target", "ajaka",
                     "--output", str(tmp_path/"ajaka"),
                     "--data-root", str(tmp_path/"data.root"))
    assert mixed.returncode == 1
    assert "Ajaka" in mixed.stderr
    assert not (tmp_path/"ajaka").exists()


def test_fit_cli_refuses_theory_csv_and_incomplete_or_reused_basis(tmp_path):
    data = tmp_path/"theory.csv"
    data.write_text("mass,sigma\n1.1,0.2\n")
    ajaka, native = tmp_path/"ajaka", tmp_path/"native"
    ajaka.mkdir()
    native.mkdir()
    for path, target in ((ajaka, "ajaka"), (native, "native")):
        (path/"manifest.json").write_text(json.dumps({
            "version": 1, "target": target, "fingerprint": "a"*64,
            "keys": ["0_p_pi0_0.npz"], "bins": {}, "complete": False,
        }))
    common = ("--basis-native", str(native), "--basis-ajaka", str(ajaka),
              "--output", str(tmp_path/"fit"))
    csv = _run_cli("figure4-fit", "--data-root", str(data), *common)
    assert csv.returncode == 1
    assert "ROOT" in csv.stderr
    incomplete = _run_cli("figure4-fit", "--data-root", str(tmp_path/"data.root"), *common)
    assert incomplete.returncode == 1
    assert "incomplete" in incomplete.stderr
    same = _run_cli("figure4-fit", "--data-root", str(tmp_path/"data.root"),
                    "--basis-native", str(native), "--basis-ajaka", str(native),
                    "--output", str(tmp_path/"fit"))
    assert same.returncode == 1
    assert "distinct" in same.stderr


def test_ajaka_basis_cli_resumes_only_corrupt_bin(tmp_path, monkeypatch):
    import numpy as np
    from graal_theory import cli
    from graal_theory.figure4_basis import BasisBinCertificate, BasisBinMoment

    calls = []
    def fast_bin(task):
        key = task[1]
        calls.append(key)
        zero = np.zeros((3, 3), dtype=np.complex128)
        moment = BasisBinMoment(key[1], task[2], task[3], "uniform", zero, zero,
                                None, None, None, None, None, zero,
                                np.empty(0), "masked_kinematic", "toy")
        return key, BasisBinCertificate(moment, "masked_kinematic", ("toy",),
                                        float("nan"), None, (), 0, None)
    monkeypatch.setattr(cli, "_basis_bin_task", fast_bin)
    output = tmp_path/"basis"
    command = ["figure4-basis-build", "--target", "ajaka", "--output", str(output),
               "--energy-order", "2", "--sobol-power", "4"]
    assert cli.main(command) == 0
    assert len(calls) == 120
    assert json.loads((output/"manifest.json").read_text())["complete"] is True
    (output/"bins"/"0_p_pi0_0.npz").write_bytes(b"corrupt")
    calls.clear()
    assert cli.main(command+["--resume"]) == 0
    assert calls == [(0, "p_pi0", 0)]


def test_fit_cli_keeps_sourced_comparison_separate_from_successful_fit(tmp_path, monkeypatch):
    import numpy as np
    from types import SimpleNamespace
    from graal_theory import cli, figure4_fit_output, native_sigma
    from graal_theory.figure4_basis import BasisBinCertificate, BasisBinMoment, BinPrediction
    from graal_theory.figure4_reference import PAIR_MASS_AXES
    from graal_theory.native_sigma import NativeSigmaData

    mass = .93827208816
    class NativePrediction:
        def __init__(self, index):
            self.index = index
            self.moment = SimpleNamespace(anchor_g1=-.260/mass, anchor_g2=.270/mass**2,
                proton_mass_gev=mass, energy_rule="native_flux", model_fingerprint="toy-physics")
            self.status = "calculated"
            self.numerical_error_bound = 0.

        def predict(self, coefficients):
            _, x, y = coefficients
            sigma = -.08+.02*self.index+(.15+.04*self.index)*x+(.11-.025*self.index)*y
            return BinPrediction(sigma, 1., sigma, sigma, "native_flux")

    keys = tuple(("p_pi0", 0, index) for index in range(6))
    native_predictions = {key: NativePrediction(index) for index, key in enumerate(keys)}
    sigma = np.array([item.predict([1., .07, -.04]).sigma
                      for item in native_predictions.values()])
    data = NativeSigmaData(keys, sigma, np.full(6, .05), np.arange(6),
                           np.eye(6)*.0025, np.eye(6)*.001,
                           np.array([1.1, 1.2]), {"p_pi0": np.linspace(1., 1.4, 7)},
                           {"profile": "uv", "background": "sideband-corrected"},
                           "a"*64, "final_input")
    ajaka_certificates = {}
    anchor = native_predictions[data.keys[0]].moment
    for energy in range(4):
        for pair, (low, high) in PAIR_MASS_AXES.items():
            edges = np.linspace(low, high, 11)
            for mass in range(10):
                identity = np.eye(3, dtype=np.complex128)
                numerator = identity*.2
                numerator[0, 1] = numerator[1, 0] = .5
                center = float((edges[mass]+edges[mass+1])/2)
                moment = BasisBinMoment(
                    pair, (1.1+.1*energy, 1.2+.1*energy),
                    (float(edges[mass]), float(edges[mass+1])), "uniform",
                    numerator, identity, None, None, None, None, None,
                    identity/8, np.array([1.15+.1*energy]), "calculated",
                    model_fingerprint="toy-physics", anchor_g1=anchor.anchor_g1,
                    anchor_g2=anchor.anchor_g2, proton_mass_gev=anchor.proton_mass_gev,
                    mass_numerator=identity*center,
                    accessible_energy_gev=(1.1+.1*energy, 1.2+.1*energy),
                    accessible_mass_gev=(float(edges[mass]), float(edges[mass+1])),
                    vertical_normalization=identity/2,
                    horizontal_normalization=identity/2)
                ajaka_certificates[energy, pair, mass] = BasisBinCertificate(
                    moment, "calculated", (), .001, None, (moment,)*12, 8, None)
    native, ajaka = tmp_path/"native", tmp_path/"ajaka"
    native.mkdir()
    ajaka.mkdir()
    settings = {"energy_order": 2, "sobol_power": 4, "replicas": 8, "mode": "grid"}
    fingerprint = figure4_fit_output.fingerprint_inputs(
        "ajaka", cli._ajaka_basis_inputs(Path(cli._REFERENCES)), settings)
    native_manifest = {"target": "native", "complete": True,
                       "keys": [f"{energy}_{pair}_{mass}.npz" for pair, energy, mass in data.keys],
                       "code_sha256": "c"*64, "data_sha256": data.source_sha256,
                       "fingerprint": "n"*64}
    ajaka_manifest = {"target": "ajaka", "complete": True,
                      "keys": [f"{energy}_{pair}_{mass}.npz" for energy, pair, mass in ajaka_certificates],
                      "code_sha256": "c"*64, "fingerprint": fingerprint, "settings": settings}
    (native/"manifest.json").write_text(json.dumps(native_manifest))
    (ajaka/"manifest.json").write_text(json.dumps(ajaka_manifest))

    class Checkpoint:
        def __init__(self, path, manifest):
            self.manifest = manifest

        def pending_keys(self):
            return ()

        def read(self, key):
            if self.manifest["target"] == "native":
                return native_predictions[key[1], key[0], key[2]]
            return ajaka_certificates[key]

        _key_from_name = staticmethod(figure4_fit_output.BasisCheckpoint._key_from_name)

    monkeypatch.setattr(figure4_fit_output, "BasisCheckpoint", Checkpoint)
    monkeypatch.setattr(native_sigma, "load_native_sigma_root", lambda *a, **k: data)
    observed = {}
    def capture(output, sourced, fitted, source_comparison, fitted_comparison,
                fit_result, provenance, covariance):
        observed.update(status=fit_result.status,
                        sourced=source_comparison.status,
                        fitted=fitted_comparison.status,
                        source_sigma=sourced[0, "p_pi0"].bins[0].sigma,
                        fitted_sigma=fitted[0, "p_pi0"].bins[0].sigma)
    monkeypatch.setattr(figure4_fit_output, "write_fit_bundle", capture)
    result = cli.main(["figure4-fit", "--data-root", str(tmp_path/"data.root"),
                       "--basis-native", str(native), "--basis-ajaka", str(ajaka),
                       "--output", str(tmp_path/"output")])
    assert result == 2  # the synthetic source curve is not Ajaka reproduction
    assert observed["status"] == "fit_computed"
    assert observed["source_sigma"] == pytest.approx(.2)
    assert observed["fitted_sigma"] != pytest.approx(.2)


def test_figure4_bin_task_keeps_replica_checks_for_panel_assembly(monkeypatch):
    from types import SimpleNamespace
    from graal_theory import cli

    class FlatModel:
        masses = (.547862, .1349768, .93827208816)
        parameters = SimpleNamespace(proton_mass_gev=masses[2])

        def polarized_matrix_element_squared(self, sample, epsilon):
            import numpy as np
            return np.ones(len(sample.initial))

    monkeypatch.setattr(cli, "_figure4_model", lambda *args: FlatModel(), raising=False)
    key, checks = cli._figure4_bin_task((THEORY_ROOT/"references", 3, "p_eta", 5,
        1, 4, tuple(range(2026, 2034)), "direct", 64, 48))
    assert key == (3, "p_eta", 5)
    assert max(abs(a-b) for a, b in zip(checks[0].mass_range_gev, (1.6, 1.64))) < 1e-12
    assert len(checks[3]) == 8


def test_predict_cli_writes_partial_bundle(tmp_path):
    result = _run_cli(
        "predict", "--energy", "1.2", "--sobol-power", "8",
        "--output", str(tmp_path / "run"),
    )
    assert result.returncode == 0, result.stderr
    assert "partial" in result.stdout
    manifest = json.loads((tmp_path / "run" / "manifest.json").read_text())
    assert manifest["scope"] == "partial:delta1700_eta_delta_tree_eq43"


def test_predict_cli_rejects_duplicate_energies(tmp_path):
    result = _run_cli(
        "predict", "--energy", "1.2", "--energy", "1.2",
        "--output", str(tmp_path / "run"),
    )
    assert result.returncode != 0
    assert "duplicate" in result.stderr.lower()
    assert not (tmp_path / "run").exists()


def test_validate_cli_reports_scientific_failure_with_artifacts(tmp_path):
    run = tmp_path / "run"
    predicted = _run_cli(
        "predict", "--energy", "1.2", "--energy", "1.202", "--sobol-power", "8",
        "--output", str(run),
    )
    assert predicted.returncode == 0, predicted.stderr
    validated = _run_cli("validate", "--bundle", str(run))
    assert validated.returncode == 2, validated.stderr
    comparison = json.loads((run / "validation" / "comparison.json").read_text())
    assert comparison["status"] == "failed"
    assert set(comparison) >= {"figure14_tree", "factor_two_1202", "phase_space", "convergence"}
    assert (run / "validation" / "invariant_masses.pdf").is_file()
    assert (run / "validation" / "total_cross_section.pdf").is_file()
    manifest = json.loads((run / "manifest.json").read_text())
    assert manifest["validation_state"] == "failed"


def test_validate_cli_requires_both_reference_energies(tmp_path):
    run = tmp_path / "run"
    predicted = _run_cli("predict", "--energy", "1.2", "--sobol-power", "8", "--output", str(run))
    assert predicted.returncode == 0, predicted.stderr
    validated = _run_cli("validate", "--bundle", str(run))
    assert validated.returncode == 1
    assert "1.202" in validated.stderr
    assert json.loads((run / "manifest.json").read_text())["validation_state"] == "pending"


def test_validate_cli_accepts_extra_below_threshold_energy(tmp_path):
    run = tmp_path / "run"
    predicted = _run_cli(
        "predict", "--energy", "0.5", "--energy", "1.2", "--energy", "1.202",
        "--sobol-power", "8", "--output", str(run),
    )
    assert predicted.returncode == 0, predicted.stderr
    validated = _run_cli("validate", "--bundle", str(run))
    assert validated.returncode == 2, validated.stderr
    phase = json.loads((run / "validation" / "comparison.json").read_text())["phase_space"]
    assert phase["passed"]
    assert phase["energies"][0]["quadrature_volume_gev2"] == 0.0


def test_validate_cli_rejects_bundle_with_missing_source_locator(tmp_path):
    run = tmp_path / "run"
    predicted = _run_cli(
        "predict", "--energy", "1.2", "--energy", "1.202", "--sobol-power", "8",
        "--output", str(run),
    )
    assert predicted.returncode == 0, predicted.stderr
    path = run / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["parameters"]["eta_mass"]["locator"] = ""
    path.write_text(json.dumps(manifest))
    validated = _run_cli("validate", "--bundle", str(run))
    assert validated.returncode == 1
    assert "locator" in validated.stderr
    assert json.loads(path.read_text())["validation_state"] == "pending"


def test_pilot_panel5_cli_writes_labeled_partial_overlay(tmp_path):
    published = THEORY_ROOT.parent / "test_data/beam_asymmetry/ajaka2008_figure4_digitized.csv"
    output = tmp_path / "panel5"
    result = _run_cli(
        "pilot-panel5", "--published-csv", str(published),
        "--sobol-power", "14", "--energy-nodes", "9", "--output", str(output),
    )
    assert result.returncode == 0, result.stderr
    assert (output / "panel5.pdf").is_file()
    prediction = json.loads((output / "prediction.json").read_text())
    assert prediction["scope"] == "partial:delta1700_eta_delta_tree_eq43"
    assert prediction["energy_weighting"] == "uniform"
    assert prediction["beam_asymmetry_sign"] == "vertical_minus_horizontal"
    assert len(prediction["sigma"]) == 10
    assert prediction["sigma"][:2] == [None, None]
    assert len(prediction["published_points"]) == 4
    assert len(prediction["theory_parameters_sha256"]) == 64
    assert "g1_prime" in prediction["theory_parameters"]
    assert prediction["code_revision"]["commit"]
    assert prediction["published_source"]["doi"] == "10.1103/PhysRevLett.100.052003"
    assert prediction["published_source"]["uncertainties"] == "statistical only"


def test_pilot_panel5_cli_rejects_unreliable_resolution(tmp_path):
    published = THEORY_ROOT.parent / "test_data/beam_asymmetry/ajaka2008_figure4_digitized.csv"
    output = tmp_path / "panel5"
    result = _run_cli(
        "pilot-panel5", "--published-csv", str(published),
        "--sobol-power", "8", "--energy-nodes", "3", "--output", str(output),
    )
    assert result.returncode == 1
    assert "sobol-power" in result.stderr
    assert not output.exists()


def test_pilot_panel5_flux_option_requires_manifest(tmp_path):
    published = THEORY_ROOT.parent / "test_data/beam_asymmetry/ajaka2008_figure4_digitized.csv"
    result = _run_cli(
        "pilot-panel5", "--published-csv", str(published),
        "--flux-root", str(tmp_path / "flux.root"),
        "--output", str(tmp_path / "panel5"),
    )
    assert result.returncode == 1
    assert "run-manifest" in result.stderr
    assert not (tmp_path / "panel5").exists()
