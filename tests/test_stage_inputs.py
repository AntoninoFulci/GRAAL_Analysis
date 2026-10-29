"""External products are checked without modifying scientific artifacts."""
from array import array
import json
from pathlib import Path

import pytest

from graal_workflow.models import PipelineError, PipelinePaths


@pytest.fixture
def config():
    return {
        "campaign": {"mode": "test_data"},
        "profiles": {"uv": {"energy_edges_gev": [1.1, 1.2, 1.3, 1.4, 1.5]}},
        "stages": {
            "monte_carlo": {"uv": {"channels": ["eta_pi0"]}},
            "reconstruction": {"uv": {"chi2_cut": 10., "missing_mass_window_gev": .06}},
            "extraction": {"uv": {"enabled": True, "estimator": "both", "phi_bins": 12,
                                     "best_binning": False, "mass_bins": 10}},
        },
    }


@pytest.fixture
def paths(tmp_path):
    return PipelinePaths(*(tmp_path / name for name in (
        "repo", "preanalysis", "data", "artifacts", "output", "manifest.csv", "flux.root",
        "hyperparams.json", "reference.csv")))


def validate(kind, value, config, paths, profile="uv"):
    from graal_workflow.stage_inputs import validate_product
    return validate_product(kind, value, profile=profile, config=config, paths=paths)


def root_file(path, tree, branches, metadata=None):
    import ROOT
    path.parent.mkdir(parents=True, exist_ok=True)
    output = ROOT.TFile(str(path), "RECREATE")
    events = ROOT.TTree(tree, tree)
    buffers = [array("d", [1.]) for _ in branches]
    for name, buffer in zip(branches, buffers):
        events.Branch(name, buffer, f"{name}/D")
    events.Fill()
    events.Write()
    for key, value in (metadata or {}).items():
        if isinstance(value, float):
            ROOT.TParameter("double")(key, value).Write()
        else:
            ROOT.TNamed(key, json.dumps(value)).Write()
    output.Close()
    return path


def reco_pair(tmp_path, **overrides):
    branches = ("RunNumber", "Xstrip", "Polarization", "beam", "eta", "pi0", "proton",
                "missing", "eta_mass", "pi0_mass", "n_photons_input")
    metadata = dict(schema=2, selection_algorithm="pairing_missing_mass", beam_profile="uv",
                    channel="eta_pi0", selection=dict(chi2_cut=10., missing_mass_window_gev=.06,
                                                       energy_range_gev=[1.1, 1.5]),
                    bdt_domain=dict(beam_profile="uv", energy_range_gev=[1.1, 1.5]),
                    counts_by_run_state=[dict(run=1, polarization=1, input=10)])
    metadata.update(overrides)
    return {name: root_file(tmp_path / f"{name}.root", f"reco_eta_pi0_{name}", branches,
                           {"reconstruction_provenance": metadata}) for name in ("chi2", "bdt")}


def test_missing_external_directory_is_actionable(tmp_path, config, paths):
    with pytest.raises(PipelineError, match="selected.*missing"):
        validate("selected", tmp_path / "missing", config, paths)


def test_selected_requires_actual_reconstruction_branches(tmp_path, config, paths):
    root_file(tmp_path / "selected/a.root", "h85",
              ("gammas", "fcharged_theta", "RunNumber", "Polarization", "Xstrip"))
    with pytest.raises(PipelineError, match="beam|protons|neutrons"):
        validate("selected", tmp_path / "selected", config, paths)


def test_selected_reuse_does_not_require_original_h80_or_cache_ttl(tmp_path, config, paths):
    root_file(tmp_path / "selected/a.root", "h85",
              ("gammas", "fcharged_theta", "RunNumber", "Polarization", "Xstrip",
               "beam", "protons", "neutrons"))
    path = tmp_path / "selected/a.root"
    before = path.read_bytes()
    warnings = validate("selected", path.parent, config, paths)
    assert any("cannot certify profile from metadata" in message for message in warnings)
    assert path.read_bytes() == before


def test_reconstruction_owner_contract_and_inclusive_run_universe(tmp_path, config, paths):
    products = reco_pair(tmp_path)
    before = {key: path.read_bytes() for key, path in products.items()}
    assert validate("reconstruction", products, config, paths) == []
    assert before == {key: path.read_bytes() for key, path in products.items()}


@pytest.mark.parametrize("override,match", [
    ({"schema": 1}, "schema"),
    ({"beam_profile": "vis"}, "profile"),
    ({"counts_by_run_state": []}, "inclusive"),
    ({"selection": {"chi2_cut": 10., "missing_mass_window_gev": .06,
                     "energy_range_gev": [1.2, 1.5]}}, "energy range"),
])
def test_reconstruction_incompatible_contract_blocks(tmp_path, config, paths, override, match):
    with pytest.raises(PipelineError, match=match):
        validate("reconstruction", reco_pair(tmp_path, **override), config, paths)


def test_changed_reconstruction_cut_names_requested_and_recorded_values(tmp_path, config, paths):
    config["stages"]["reconstruction"]["uv"]["chi2_cut"] = 7.
    with pytest.raises(PipelineError, match=r"chi2_cut.*7.*10"):
        validate("reconstruction", reco_pair(tmp_path), config, paths)


def test_plot_only_reuse_does_not_require_inclusive_counts(tmp_path, config, paths):
    config["stages"]["extraction"]["uv"]["enabled"] = False
    assert validate("reconstruction", reco_pair(tmp_path, counts_by_run_state=[]), config, paths) == []


def test_mc_requires_generation_domain_metadata(tmp_path, config, paths):
    from graal_common.physics.channels import get_channel
    channel = get_channel("eta_pi0")
    root_file(tmp_path / "mc" / channel.mc_filename, "mc",
              ("beam", "proton", "target", *channel.photon_branches))
    with pytest.raises(PipelineError, match="beam_min_gev|generation.*domain"):
        validate("mc", tmp_path / "mc", config, paths)


def test_mc_certified_generation_coverage(tmp_path, config, paths):
    from graal_common.physics.channels import get_channel
    channel = get_channel("eta_pi0")
    root_file(tmp_path / "mc" / channel.mc_filename, "mc",
              ("beam", "proton", "target", *channel.photon_branches),
              {"beam_min_gev": 1.1, "beam_max_gev": 1.5})
    assert validate("mc", tmp_path / "mc", config, paths) == []


def test_production_rejects_diagnostic_selected_marker(tmp_path, config, paths):
    config["campaign"]["mode"] = "production"
    root_file(tmp_path / "selected/a.root", "h85",
              ("gammas", "fcharged_theta", "RunNumber", "Polarization", "Xstrip",
               "beam", "protons", "neutrons"), {"sample_provenance": {"diagnostic_only": True}})
    with pytest.raises(PipelineError, match="diagnostic"):
        validate("selected", tmp_path / "selected", config, paths)


def calibration_pair(tmp_path, paths):
    import ROOT
    from calibration.calibration_qa import write_calibration_qa, sha256_file
    paths.manifest.write_text("fixture catalog")
    paths.raw_flux.write_bytes(b"fixture raw flux")
    root = tmp_path / "calibrated.root"
    output = ROOT.TFile(str(root), "RECREATE")
    for state in ("POL1", "POL2", "BREM"):
        ROOT.TH1D(f"run1_{state}", "", 128, 1.1, 1.5).Write()
    output.Close()
    qa = root.with_suffix(".qa.json")
    write_calibration_qa(qa, root,
        inputs=dict(manifest=sha256_file(paths.manifest), raw_flux=sha256_file(paths.raw_flux),
                    h80=[["/archived/source/h80.root", 100, 1, "a" * 64]]),
        coverage=[dict(run_number=1, state=state, accepted=True, h80_present=True)
                  for state in ("POL1", "POL2", "BREM")], diagnostics={})
    return dict(root=root, qa=qa)


def test_calibration_reuse_authenticates_pair_without_original_h80(tmp_path, config, paths):
    products = calibration_pair(tmp_path, paths)
    assert validate("calibration", products, config, paths, profile=None) == []
    paths.manifest.write_text("different catalog")
    with pytest.raises(PipelineError, match="identity mismatch"):
        validate("calibration", products, config, paths, profile=None)


def test_calibration_rejects_changed_root_bytes(tmp_path, config, paths):
    products = calibration_pair(tmp_path, paths)
    with products["root"].open("ab") as stream:
        stream.write(b"modified")
    with pytest.raises(PipelineError, match="identity mismatch"):
        validate("calibration", products, config, paths, profile=None)


def extraction_file(tmp_path, *, profile="uv", divisor=.9549, estimator="both", candle=False):
    import ROOT
    from observable_extraction.core.binning import PAIR_NAMES, pair_mass_edges, phi_edges_rad
    path = tmp_path / "beam_asymmetry.root"
    output = ROOT.TFile(str(path), "RECREATE")
    binning = output.mkdir("binning")
    binning.cd()
    vectors = {"energy_edges": [1.1, 1.2, 1.3, 1.4, 1.5], "phi_edges": phi_edges_rad()}
    vectors.update({f"{pair}_mass_edges": pair_mass_edges(pair) for pair in PAIR_NAMES})
    for name, values in vectors.items():
        vector = ROOT.TVectorD(len(values), array("d", values))
        vector.Write(name)
    output.cd()
    provenance = f"profile={profile}\nestimator={estimator}\nphi_bins=12\n" + (f"phi_bin_divisor={divisor}\n" if divisor is not None else "")
    if candle:
        fields = dict(enabled="true", eta_center_gev=.547862, pi0_center_gev=.134977,
                      mass_half_width_gev=.05, geometry="rectangular", core_logic="and",
                      tail_logic="or_complement", boundary="inclusive", baseline_event_count=4,
                      full_core_event_count=2, tail_event_count=2, balanced_core_event_count=2,
                      excluded_nonfinite_event_count=0, balance_method="random_without_replacement",
                      balance_seed=20261024, mass_source="raw_pre_fit")
        provenance += "".join(f"candle_{key}={value}\n" for key, value in fields.items())
    ROOT.TNamed("provenance", provenance).Write()
    # A certified non-estimable result is still a valid comparison input.
    ROOT.TTree("sigma_points", "sigma_points").Write()
    ROOT.TNamed("extraction_metadata", json.dumps({"status": "not_estimable"})).Write()
    output.Close()
    return path


def test_extraction_contract_accepts_certified_nominal_grid(tmp_path, config, paths):
    assert validate("extraction", extraction_file(tmp_path), config, paths) == []


@pytest.mark.parametrize("overrides,match", [
    ({"profile": "vis"}, "profile"),
    ({"divisor": None}, "phi_bin_divisor"),
    ({"estimator": "ratio"}, "estimator"),
])
def test_extraction_contract_blocks_incompatible_metadata(tmp_path, config, paths, overrides, match):
    with pytest.raises(PipelineError, match=match):
        validate("extraction", extraction_file(tmp_path, **overrides), config, paths)


def bdt_bundle(tmp_path):
    import numpy as np
    import xgboost as xgb
    model = xgb.XGBClassifier(n_estimators=1, max_depth=1, n_jobs=1)
    model.fit(np.zeros((4, 26)), np.array([0, 1, 0, 1]))
    model.save_model(tmp_path / "bdt_stage1.json")
    (tmp_path / "stage1_threshold.txt").write_text("0.5")
    source = Path(__file__).resolve().parents[1] / "04_bdt_training/artifacts/stage1/stage1_provenance.json"
    payload = json.loads(source.read_text())
    payload.update(beam_profile="uv", energy_min_gev=1.1, energy_max_gev=1.5)
    (tmp_path / "stage1_provenance.json").write_text(json.dumps(payload))
    return tmp_path


def test_bdt_reuse_needs_only_certified_model_bundle(tmp_path, config, paths):
    assert validate("bdt", bdt_bundle(tmp_path), config, paths) == []


def test_bdt_reuse_rejects_reordered_features(tmp_path, config, paths):
    directory = bdt_bundle(tmp_path)
    path = directory / "stage1_provenance.json"
    payload = json.loads(path.read_text())
    payload["feature_names"].reverse()
    path.write_text(json.dumps(payload))
    with pytest.raises(PipelineError, match="feature_names"):
        validate("bdt", directory, config, paths)


def test_compatible_wider_reconstruction_domain_is_visible(tmp_path, config, paths):
    config["profiles"]["uv"]["energy_edges_gev"] = [1.2, 1.3, 1.4]
    warnings = validate("reconstruction", reco_pair(tmp_path), config, paths)
    assert len(warnings) == 2
    assert all("energy_range_gev" in warning and "1.2" in warning and "1.1" in warning
               for warning in warnings)


def test_reuse_checks_preanalysis_selector_branches(tmp_path, config, paths):
    root_file(tmp_path / "pre/pre_analisi_uv_1.root", "h80",
              ("gammas", "fcharged_theta", "RunNumber", "Polarization", "Xstrip"))
    with pytest.raises(PipelineError, match="pions_theta|protons"):
        validate("preanalysis", tmp_path / "pre", config, paths)


def test_invalid_acquisition_metadata_in_selected_blocks_early(tmp_path, config, paths):
    root_file(tmp_path / "selected/a.root", "h85",
              ("gammas", "fcharged_theta", "RunNumber", "Polarization", "Xstrip", "beam", "protons", "neutrons"),
              {"preanalysis_provenance": {"input_run_states": [{"run": "bad"}]}})
    with pytest.raises(PipelineError, match="input_run_states"):
        validate("selected", tmp_path / "selected", config, paths)


def test_calibration_reports_changed_recorded_quality_threshold(tmp_path, config, paths):
    products = calibration_pair(tmp_path, paths)
    payload = json.loads(products["qa"].read_text())
    payload["diagnostics"] = {"pre_write": {"thresholds": {"min_events_per_strip": 3}}}
    products["qa"].write_text(json.dumps(payload))
    config["stages"]["calibration"] = {"min_events_per_strip": 10}
    with pytest.raises(PipelineError, match="min_events_per_strip.*10.*3"):
        validate("calibration", products, config, paths, profile=None)


@pytest.mark.parametrize("kind,tree", [("selected", "h85"), ("preanalysis", "h80")])
def test_acquisition_profile_rejects_positive_embedded_mismatch(tmp_path, config, paths, kind, tree):
    root_file(tmp_path / "input/pre_analisi_uv_1.root", tree,
              ("gammas", "fcharged_theta", "RunNumber", "Polarization", "Xstrip", "beam", "protons", "neutrons", "pions_theta"),
              {"preanalysis_provenance": {"beam_profile": "vis"}})
    with pytest.raises(PipelineError, match="beam_profile.*uv.*vis"):
        validate(kind, tmp_path / "input", config, paths)


@pytest.mark.parametrize("target,beam,classification,expected", [
    ("P", "VIS", "manual", "reject"), ("D", "UV", "manual", "reject"),
    ("P", "UV", "manual", "certified"), ("P", "UV", "automatic", "warning"),
])
def test_selected_profile_uses_manual_run_catalog(tmp_path, config, paths, target, beam, classification, expected):
    paths.manifest.write_text("run_number,source_period,target,beam_type,group,classification_source,source_file\n"
                              f"42,period,{target},{beam},{target}_{beam},{classification},period/run42.root\n")
    root_file(tmp_path / "selected/a.root", "h85",
              ("gammas", "fcharged_theta", "RunNumber", "Polarization", "Xstrip", "beam", "protons", "neutrons"),
              {"preanalysis_provenance": {"input_run_states": [
                  dict(run=42, polarization=1, input=1, skipped_no_tagger=0)]}})
    if expected == "reject":
        with pytest.raises(PipelineError, match="target|beam_type"):
            validate("selected", tmp_path / "selected", config, paths)
    else:
        warnings = validate("selected", tmp_path / "selected", config, paths)
        assert bool(warnings) == (expected == "warning")
        assert all("cannot certify profile from metadata" in warning for warning in warnings)


def test_published_calibration_receipt_still_enforces_diagnostic_scope(tmp_path, config, paths):
    products = calibration_pair(tmp_path, paths)
    qa_dir = tmp_path / "metadata/common"
    qa_dir.mkdir(parents=True)
    products["qa"] = products["qa"].rename(qa_dir / products["qa"].name)
    (qa_dir / "calibration_reuse.json").write_text(json.dumps({"scope": "diagnostic"}))
    config["campaign"]["mode"] = "production"
    with pytest.raises(PipelineError, match="diagnostic"):
        validate("calibration", products, config, paths, profile=None)


@pytest.mark.parametrize("key,value,candle", [
    ("candle_enabled", True, False), ("candle_enabled", False, True),
    ("candle_mass_half_width_gev", .06, True), ("candle_balance_seed", 7, True),
])
def test_extraction_candle_settings_match_owner_contract(tmp_path, config, paths, key, value, candle):
    config["stages"]["extraction"]["uv"][key] = value
    with pytest.raises(PipelineError, match=key):
        validate("extraction", extraction_file(tmp_path, candle=candle), config, paths)


def test_extraction_warns_for_settings_without_reuse_contract(tmp_path, config, paths):
    config["stages"]["extraction"]["uv"].update(enabled=False, by_period=True, bootstrap_replicas=10, bootstrap_seed=17)
    warnings = validate("extraction", extraction_file(tmp_path), config, paths)
    for key in ("by_period", "bootstrap_replicas", "bootstrap_seed"):
        assert any(key in warning and "cannot certify" in warning for warning in warnings)


def test_new_extraction_uses_current_invocation_for_nonpersisted_settings(tmp_path, config, paths):
    config['stages']['extraction']['uv'].update(enabled=True, by_period=True, bootstrap_replicas=10, bootstrap_seed=17)
    assert validate('extraction', extraction_file(tmp_path), config, paths) == []
