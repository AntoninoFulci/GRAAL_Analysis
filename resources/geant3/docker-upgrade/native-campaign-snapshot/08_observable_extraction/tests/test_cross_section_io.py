import copy
import json
from array import array

import numpy as np
import pytest
import ROOT
from calibration.run_manifest import RunRecord, write_manifest
from observable_extraction.cross_sections import main
from observable_extraction.io.cross_section import (
    prepare_analysis,
    selection_signature,
    write_result,
)


@pytest.fixture
def campaign(tmp_path):
    phi_edges = np.linspace(0, 2 * np.pi, 9).tolist()
    metadata = {
        "do_fit": False,
        "selection": {"energy_range_gev": [1.1, 1.2], "bdt_threshold": None},
        "beam_profile": "uv",
        "bdt_domain": None,
        "model_inputs": [],
        "source_files": [
            {"path": "/repo/05_reconstruction/core.py", "sha256": "a" * 64}
        ],
        "counts_by_run_state": [
            {"run": r, "polarization": s, "input": 100}
            for r in (811, 812)
            for s in (1, 2)
        ],
    }
    f = ROOT.TFile(str(tmp_path / "reco.root"), "RECREATE")
    tree = ROOT.TTree("reco", "reco")
    ints = {
        name: array("i", [value])
        for name, value in [
            ("RunNumber", 811),
            ("Polarization", 1),
            ("n_photons_input", 4),
        ]
    }
    floats = {
        name: array("f", [value])
        for name, value in [("Xstrip", 1), ("eta_mass", 0.548), ("pi0_mass", 0.135)]
    }
    for name, value in ints.items():
        tree.Branch(name, value, f"{name}/I")
    for name, value in floats.items():
        tree.Branch(name, value, f"{name}/F")
    vectors = {
        name: ROOT.TLorentzVector()
        for name in ("beam", "eta", "pi0", "proton", "missing")
    }
    for name, vector in vectors.items():
        tree.Branch(name, "TLorentzVector", vector)
    for state in (1, 2):
        ints["Polarization"][0] = state
        for phi in (np.array(phi_edges[:-1]) + np.array(phi_edges[1:])) / 2:
            vectors["beam"].SetPxPyPzE(0, 0, 1.15, 1.15)
            vectors["eta"].SetPxPyPzE(0.1 * np.cos(phi), 0.1 * np.sin(phi), 0, 0.6)
            vectors["pi0"].SetPxPyPzE(0.1 * np.cos(phi), 0.1 * np.sin(phi), 0, 0.2)
            vectors["proton"].SetPxPyPzE(0, 0, 0, 0.938)
            vectors["missing"].SetPxPyPzE(0, 0, 0, 0.938)
            for _ in range(10):
                tree.Fill()
    tree.Write()
    ROOT.TNamed("reconstruction_provenance", json.dumps(metadata)).Write()
    f.Close()
    flux = ROOT.TFile(str(tmp_path / "flux.root"), "RECREATE")
    for run in (811, 812):
        for state in ("POL1", "POL2", "BREM"):
            h = ROOT.TH1D(f"run{run}_{state}", "", 128, 1.1, 1.2)
            # 80 photons * 1e30 protons/cm2 * 1e-30 cm2/ub = 80 /ub.
            h.SetBinContent(1, 80)
            # Positive in every strip so existing atomic exposure contract is satisfied.
            for j in range(2, 129):
                h.SetBinContent(j, 1e-12)
            h.Write()
    flux.Close()
    write_manifest(
        [
            RunRecord(
                run, "1999_uv", "P", "UV", "P_UV", "manual", f"1999_uv/run{run}.root"
            )
            for run in (811, 812)
        ],
        tmp_path / "manifest.csv",
    )
    grid = {
        "energy_edges_gev": [1.1, 1.2],
        "phi_edges_rad": phi_edges,
        "observable": "total",
        "mass_edges_gev": None,
    }
    response = {
        "schema_version": 1,
        "grid": grid,
        "generated": [10000] * 8,
        "selected": (np.eye(8) * 5000).tolist(),
        "sample_id": "independent-test-mc",
        "selection_signature": selection_signature(metadata),
        "provenance": {
            "simulator": "synthetic_closure",
            "geometry": "test",
            "independent_of_training": True,
            "decays": "forced_gamma_gamma",
            "generated_complete": True,
            "migration_domain": "closed",
            "validation": "synthetic test",
        },
    }
    (tmp_path / "response.json").write_text(json.dumps(response))
    config = {
        "schema_version": 1,
        "analysis_kind": "synthetic_closure",
        "grid": grid,
        "branching": {"value": 1, "relative_uncertainty": 0.01, "source": "synthetic"},
        "flux_file": "flux.root",
        "run_manifest": "manifest.csv",
        "samples": [
            {
                "reconstructed": "reco.root",
                "tree": "reco",
                "profile": "uv",
                "period": "1999_uv",
                "response": "response.json",
                "target": {
                    "areal_density_cm2": 1e30,
                    "relative_uncertainty": 0.02,
                    "source": "synthetic",
                    "correlation_group": "target",
                },
                "flux_scale": {
                    "relative_uncertainty": None,
                    "source": "unknown",
                    "correlation_group": "flux",
                },
                "background": {
                    "mode": "none_diagnostic",
                    "reason": "synthetic closure",
                },
            }
        ],
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config))
    return path, config, response


def test_full_root_chain_keeps_zero_yield_run_and_writes_covariances(
    campaign, tmp_path
):
    path, _config, _response = campaign
    result = prepare_analysis(path)
    assert result["values"][0] == pytest.approx(1, rel=1e-7)
    assert result["audit"]["samples"][0]["runs"] == [811, 812]
    assert result["audit"]["samples"][0]["zero_yield_runs"] == [812]
    assert "flux:flux" in result["audit"]["missing_uncertainties"]
    assert result["audit"]["status"] == "conditional"
    assert np.sqrt(result["components"]["target:target"][0, 0]) == pytest.approx(
        0.02, rel=1e-7
    )
    write_result(result, tmp_path / "out")
    output = ROOT.TFile.Open(str(tmp_path / "out/cross_sections.root"))
    assert output.Get("cross_section_points").GetEntries() == 1
    assert output.Get("covariance/known_total")
    assert output.Get("provenance")
    output.Close()
    assert (tmp_path / "out/cross_sections.pdf").stat().st_size > 1000


@pytest.mark.parametrize(
    "mutation,match",
    [
        (
            lambda c: c["samples"][0]["target"].update(areal_density_cm2=None),
            "areal_density",
        ),
        (lambda c: c["samples"][0].pop("background"), "background"),
        (lambda c: c["samples"].append(copy.deepcopy(c["samples"][0])), "overlap"),
    ],
)
def test_invalid_config_does_not_publish(campaign, tmp_path, mutation, match):
    path, config, _ = campaign
    mutation(config)
    path.write_text(json.dumps(config))
    with pytest.raises((ValueError, KeyError), match=match):
        main(["--config", str(path), "--output-dir", str(tmp_path / "bad")])
    assert not (tmp_path / "bad").exists()


def test_response_selection_mismatch_fails(campaign):
    path, _, response = campaign
    response["selection_signature"] = "b" * 64
    (path.parent / "response.json").write_text(json.dumps(response))
    with pytest.raises(ValueError, match="selection"):
        prepare_analysis(path)


def test_grid_mismatch_fails_before_fit(campaign):
    path, _, response = campaign
    response["grid"]["energy_edges_gev"] = [1.1, 1.3]
    (path.parent / "response.json").write_text(json.dumps(response))
    with pytest.raises(ValueError, match="grid"):
        prepare_analysis(path)


def test_selection_signature_ignores_input_path_but_includes_model_and_cuts():
    original = {
        "do_fit": False,
        "selection": {"chi2_cut": 10},
        "source_files": [{"path": "/a/05_reconstruction/core.py", "sha256": "a" * 64}],
        "model_inputs": [],
    }
    moved = copy.deepcopy(original)
    moved["source_files"][0]["path"] = "/b/05_reconstruction/core.py"
    moved["inputs"] = ["different sample"]
    assert selection_signature(original) == selection_signature(moved)
    moved["selection"]["chi2_cut"] = 9
    assert selection_signature(original) != selection_signature(moved)


def test_observations_do_not_need_calibration_or_background(campaign):
    path, config, _ = campaign
    config.pop("branching")
    for key in ("target", "response", "background", "flux_scale"):
        config["samples"][0].pop(key)
    path.write_text(json.dumps(config))
    result = prepare_analysis(path, observations_only=True)
    assert result["audit"]["status"] == "observations_only"
    assert sum(result["audit"]["samples"][0]["raw_counts"]) == 160
    assert len(result["audit"]["samples"][0]["observation_signature"]) == 64
    assert "values" not in result


def test_net_background_full_covariance(campaign):
    path, config, _ = campaign
    first = prepare_analysis(path, observations_only=True)["audit"]["samples"][0]
    covariance = np.eye(16) * 10 + np.ones((16, 16)) * 2
    data = {
        "schema_version": 1,
        "source": "synthetic correlated control",
        "status": "provisional_model_inadequate",
        "observation_signature": first["observation_signature"],
        "observed_counts": first["raw_counts"],
        "net_yields": [8] * 16,
        "covariance": covariance.tolist(),
    }
    (path.parent / "background.json").write_text(json.dumps(data))
    config["samples"][0]["background"] = {
        "mode": "net_yields",
        "path": "background.json",
    }
    path.write_text(json.dumps(config))
    result = prepare_analysis(path)
    assert result["values"][0] == pytest.approx(0.8, rel=1e-7)
    assert np.array_equal(result["yield_covariance"], covariance)
    assert (
        "background_status:provisional_model_inadequate"
        in result["audit"]["limitations"]
    )
    data["observation_signature"] = "bad"
    (path.parent / "background.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="signature"):
        prepare_analysis(path)


def test_synthetic_response_forbidden_for_experiment(campaign):
    path, config, _ = campaign
    config["analysis_kind"] = "experimental"
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="synthetic response"):
        prepare_analysis(path)


@pytest.mark.parametrize(
    "decays,expected", [("inclusive", 1), ("forced_gamma_gamma", 2)]
)
def test_branching_applied_once(campaign, decays, expected):
    path, config, response = campaign
    config["branching"]["value"] = 0.5
    response["provenance"]["decays"] = decays
    path.write_text(json.dumps(config))
    (path.parent / "response.json").write_text(json.dumps(response))
    result = prepare_analysis(path)
    assert result["values"][0] == pytest.approx(expected, rel=1e-7)
    assert ("branching" in result["components"]) == (decays == "forced_gamma_gamma")


def test_differential_root_chain(campaign, tmp_path):
    path, config, response = campaign
    config["grid"].update(observable="eta_pi0", mass_edges_gev=[0.7, 0.8])
    response["grid"] = config["grid"]
    path.write_text(json.dumps(config))
    (path.parent / "response.json").write_text(json.dumps(response))
    result = prepare_analysis(path)
    assert result["values"][0] == pytest.approx(0.01, rel=1e-7)
    write_result(result, tmp_path / "differential")
    output = ROOT.TFile.Open(str(tmp_path / "differential/cross_sections.root"))
    assert output.Get("units").GetTitle() == "ub/MeV"
    output.Close()
    with pytest.raises(FileExistsError):
        write_result(result, tmp_path / "differential")


def test_shared_mc_and_target_correlate_across_periods(campaign):
    path, config, _ = campaign
    combined = prepare_analysis(path)
    write_manifest(
        [
            RunRecord(
                run, period, "P", "UV", "P_UV", "manual", f"{period}/run{run}.root"
            )
            for run, period in [(811, "1999_uv"), (812, "2000_uv")]
        ],
        path.parent / "manifest.csv",
    )
    second = copy.deepcopy(config["samples"][0])
    second["period"] = "2000_uv"
    config["samples"].append(second)
    path.write_text(json.dumps(config))
    split = prepare_analysis(path)
    # Different Poisson weights for empty/data-rich periods change the GLS estimate;
    # common relative scale still remains correlated, not reduced by sqrt(2).
    assert np.sqrt(split["components"]["target:target"][0, 0]) == pytest.approx(
        0.02 * abs(split["values"][0])
    )
    assert len([key for key in split["components"] if key.startswith("mc:")]) == 1
    assert combined["audit"]["samples"][0]["runs"] == [811, 812]


def test_multiple_background_samples_need_independence_declaration(campaign):
    path, config, _ = campaign
    config["samples"][0]["background"] = {"mode": "net_yields", "path": "pending.json"}
    config["samples"].append(copy.deepcopy(config["samples"][0]))
    path.write_text(json.dumps(config))
    with pytest.raises(
        ValueError, match="independent background_cross_sample_covariance"
    ):
        prepare_analysis(path)


def test_reference_overlay_is_recorded(campaign, tmp_path):
    path, config, _ = campaign
    (tmp_path / "points.csv").write_text("energy_gev,sigma_ub,error_ub\n1.15,1,0.1\n")
    reference = {
        "schema_version": 1,
        "observable": "total",
        "units": "ub",
        "energy_units": "GeV",
        "figure": 2,
        "errors": "published_total_including_systematics",
        "energy_bins": "centers_only",
        "source": "synthetic",
        "label": "Synthetic reference fixture",
        "extraction": "synthetic",
        "digitization_uncertainty_ub": 0,
        "data": "points.csv",
    }
    (tmp_path / "reference.json").write_text(json.dumps(reference))
    config["reference"] = "reference.json"
    path.write_text(json.dumps(config))
    result = prepare_analysis(path)
    write_result(result, tmp_path / "overlay")
    assert result["audit"]["reference"]["sigma_ub"] == [1.0]
    assert "visual overlay only" in result["audit"]["reference_comparison"]


def test_missing_exposure_event_losses_are_persisted(campaign):
    path, _, _ = campaign
    flux = ROOT.TFile(str(path.parent / "flux.root"), "UPDATE")
    histogram = flux.Get("run811_POL1")
    histogram.SetBinContent(1, 0)
    histogram.Write("", ROOT.TObject.kOverwrite)
    flux.Close()
    audit = prepare_analysis(path, observations_only=True)["audit"]["samples"][0]
    assert audit["event_selection"]["missing_exposure_events"] == 160
    assert audit["event_selection"]["missing_exposure_strata"] == [
        {"run": 811, "strip": 1, "events": 160}
    ]
    assert audit["event_selection"]["eligible_events"] == 160
    assert audit["selected_events"] == 0
    assert audit["zero_yield_runs"] == [812]


def test_real_digitization_missing_errors_plots(campaign, tmp_path):
    path, config, _ = campaign
    reference = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "references/ajaka2008_figure2_manifest.json"
    )
    config["reference"] = str(reference)
    path.write_text(json.dumps(config))
    result = prepare_analysis(path)
    assert result["reference"]["error_ub"][0] is None
    write_result(result, tmp_path / "real_reference")
    assert (tmp_path / "real_reference/cross_sections.pdf").stat().st_size > 1000


def test_joint_yield_covariance_keeps_shared_fit_correlations(tmp_path):
    from observable_extraction.io.cross_section import joint_yield_covariance

    diagonal = np.array([2.0, 3.0, 4.0, 5.0])
    factors = np.array([[1.0], [2.0], [3.0], [4.0]])
    expected = np.diag(diagonal) + factors @ factors.T * 0.1
    np.savez(
        tmp_path / "joint.npz",
        diagonal=diagonal,
        factors=factors,
        kernel=np.array([[0.1]]),
    )
    manifest = {
        "schema_version": 1,
        "source": "shared mass fit",
        "observation_signatures": ["a", "b"],
        "row_counts": [2, 2],
        "covariance_npz": "joint.npz",
    }
    (tmp_path / "joint.json").write_text(json.dumps(manifest))
    paths = set()
    actual = joint_yield_covariance(
        {"path": "joint.json"},
        ["a", "b"],
        [expected[:2, :2], expected[2:, 2:]],
        tmp_path,
        paths,
    )
    np.testing.assert_allclose(actual, expected)
    assert len(paths) == 2
    with pytest.raises(ValueError, match="signature"):
        joint_yield_covariance(
            {"path": "joint.json"},
            ["b", "a"],
            [expected[:2, :2], expected[2:, 2:]],
            tmp_path,
            set(),
        )
    with pytest.raises(ValueError, match="marginal"):
        joint_yield_covariance(
            {"path": "joint.json"}, ["a", "b"], [np.eye(2), np.eye(2)], tmp_path, set()
        )


def test_shared_background_cannot_be_declared_independent(tmp_path):
    from observable_extraction.io.cross_section import _background

    data = {
        "schema_version": 1,
        "source": "shared shape fit",
        "observation_signature": "a",
        "observed_counts": [10],
        "net_yields": [9],
        "covariance": [[10]],
        "joint_covariance": "joint.json",
    }
    (tmp_path / "bg.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="shared.*joint"):
        _background(
            {"mode": "net_yields", "path": "bg.json"},
            np.array([10]),
            "a",
            tmp_path,
            set(),
            allow_shared_covariance=False,
        )
    result = _background(
        {"mode": "net_yields", "path": "bg.json"},
        np.array([10]),
        "a",
        tmp_path,
        set(),
        allow_shared_covariance=True,
    )
    assert result[0].tolist() == [9]
