from __future__ import annotations

from array import array
import json
from pathlib import Path

import numpy as np
import pytest


ROOT = pytest.importorskip("ROOT")


def _write_tree(path: Path, tree_name: str, branches: tuple[str, ...]) -> None:
    output = ROOT.TFile(str(path), "RECREATE")
    tree = ROOT.TTree(tree_name, tree_name)
    values = {}
    for branch in branches:
        type_code = "i" if branch in {"RunNumber", "Polarization", "n_photons_input"} else "f"
        leaf_code = "I" if type_code == "i" else "F"
        values[branch] = array(type_code, [1])
        tree.Branch(branch, values[branch], f"{branch}/{leaf_code}")
    tree.Fill()
    tree.Write()
    output.Close()


@pytest.mark.parametrize(
    ("fixture", "expected"),
    [
        ("corrupt", "zombie or unreadable"),
        ("missing_tree", "missing TTree 'h80'"),
        ("missing_branch", "missing branches: Xstrip"),
    ],
)
def test_root_contract_rejects_corrupt_missing_tree_and_missing_branch(
    tmp_path, fixture, expected
):
    from graal_pipeline.validators import validate_root_tree

    path = tmp_path / f"{fixture}.root"
    if fixture == "corrupt":
        path.write_bytes(b"not a ROOT file")
    elif fixture == "missing_tree":
        _write_tree(path, "wrong", ("RunNumber", "Xstrip"))
    else:
        _write_tree(path, "h80", ("RunNumber",))

    result = validate_root_tree(path, "h80", ("RunNumber", "Xstrip"))

    assert result.valid is False
    assert any(expected in reason for reason in result.reasons)


def test_preanalysis_and_selected_directories_validate_expected_trees(tmp_path):
    from graal_pipeline.validators import (
        validate_preanalysis_directory,
        validate_selected_directory,
    )

    preanalysis = tmp_path / "pre"
    selected = tmp_path / "selected"
    preanalysis.mkdir()
    selected.mkdir()
    common = ("gammas", "fcharged_theta", "RunNumber", "Polarization", "Xstrip")
    _write_tree(preanalysis / "pre_run.root", "h80", common)
    _write_tree(selected / "run.root", "h85", common)

    assert validate_preanalysis_directory(preanalysis).valid is True
    assert validate_selected_directory(
        selected, expected_files=("run.root",)
    ).valid is True
    incomplete = validate_selected_directory(
        selected, expected_files=("run.root", "missing.root")
    )
    assert incomplete.valid is False
    assert incomplete.reasons == ("missing expected files: missing.root",)


def test_mc_validator_requires_mc_tree_and_generator_branches(tmp_path):
    from graal_pipeline.validators import validate_mc_file

    path = tmp_path / "eta_pi0_mc.root"
    _write_tree(path, "mc", ("beam", "proton", "eta_gamma1", "eta_gamma2"))

    valid = validate_mc_file(
        path, required_branches=("beam", "proton", "eta_gamma1", "eta_gamma2")
    )
    invalid = validate_mc_file(path, required_branches=("beam", "generator_weight"))

    assert valid.valid is True
    assert invalid.valid is False
    assert "generator_weight" in invalid.reasons[0]


def test_feature_validator_reuses_stage1_dataset_schema(tmp_path):
    from bdt_training.dataset.stage1_dataset import (
        Stage1Dataset,
        Stage1DatasetMetadata,
        save_stage1_dataset,
    )
    from graal_common.stage1.features import N_FEATURES_S1
    from graal_pipeline.validators import validate_feature_dataset

    path = tmp_path / "features.npz"
    save_stage1_dataset(
        path,
        Stage1Dataset(
            X=np.zeros((2, N_FEATURES_S1)),
            y=np.array([0, 1]),
            w=np.array([1.0, 1.0]),
            metadata=Stage1DatasetMetadata(
                feature_names=tuple(f"feature_{index}" for index in range(N_FEATURES_S1)),
                signal_channel="eta_pi0",
                hypothesis="eta_pi0",
                signal_prior=0.5,
                beam_reweighted=True,
            ),
        ),
    )

    assert validate_feature_dataset(path, "eta_pi0", "eta_pi0").valid is True
    mismatch = validate_feature_dataset(path, "2pi0", "2pi0")
    assert mismatch.valid is False
    assert "signal channel" in mismatch.reasons[0]


def test_model_validator_reuses_artifact_and_provenance_schemas(tmp_path):
    from graal_common.stage1.artifacts import Stage1ArtifactPaths, Stage1Provenance
    from graal_pipeline.validators import validate_model_bundle

    artifacts = Stage1ArtifactPaths.from_directory(tmp_path)
    artifacts.model.write_text(json.dumps({"learner": {}}))
    artifacts.threshold.write_text("0.42\n")
    artifacts.metrics.write_text("auc=0.9\n")
    artifacts.provenance.write_text(
        Stage1Provenance(
            signal_channel="eta_pi0",
            hypothesis="eta_pi0",
            signal_prior=0.5,
            beam_reweighted=True,
            phase_space_sampling="flat",
            tagger_resolution_fwhm_gev=0.016,
            tagger_resolution_sigma_gev=0.0068,
            detector_covariance_status="configured",
            feature_names=("one",),
        ).to_json()
    )

    assert validate_model_bundle(tmp_path, "eta_pi0", "eta_pi0").valid is True
    wrong = validate_model_bundle(tmp_path, "2pi0", "2pi0")
    assert wrong.valid is False
    assert "model provenance" in wrong.reasons[0]


def test_calibration_validator_requires_schema_v2_qa_and_selected_coverage(tmp_path):
    from graal_common.calibration.strip_energy_flux import (
        FLUX_SCHEMA_VERSION,
        StripExposureRecord,
        write_qa_json,
        write_strip_exposure_csv,
    )
    from graal_pipeline.validators import validate_calibration_directory

    write_qa_json(
        tmp_path / "strip_energy_flux_qa.json",
        {"schema_version": FLUX_SCHEMA_VERSION, "valid": True, "errors": []},
    )
    write_strip_exposure_csv(
        tmp_path / "flux_by_run_strip.csv",
        [
            StripExposureRecord(
                schema_version=FLUX_SCHEMA_VERSION,
                run_number=1321,
                source_period="1998_uv",
                target="H",
                beam_type="uv",
                group="A",
                xstrip=12,
                energy_median_gev=1.2,
                flux_pol1=10.0,
                flux_pol2=11.0,
                flux_brem=3.0,
                status="ok",
            )
        ],
    )

    assert validate_calibration_directory(
        tmp_path, required_selected_keys={(1321, 12)}
    ).valid is True
    missing = validate_calibration_directory(
        tmp_path, required_selected_keys={(1321, 13)}
    )
    assert missing.valid is False
    assert "missing selected run/strip exposure" in missing.reasons[0]


def test_reconstruction_validator_requires_tree_contract_and_finite_values(tmp_path):
    from graal_pipeline.validators import validate_reconstruction_file

    path = tmp_path / "reco.root"
    branches = (
        "RunNumber",
        "Polarization",
        "Xstrip",
        "beam",
        "eta",
        "pi0",
        "proton",
        "missing",
        "eta_mass",
        "pi0_mass",
        "n_photons_input",
        "bdt_score",
    )
    _write_tree(path, "reco_eta_pi0_bdt", branches)

    assert validate_reconstruction_file(
        path, "reco_eta_pi0_bdt", require_bdt=True
    ).valid is True
    missing_fit = validate_reconstruction_file(
        path, "reco_eta_pi0_bdt", require_bdt=True, require_fit=True
    )
    assert missing_fit.valid is False
    assert "eta_fit" in missing_fit.reasons[0]


def _write_beam_asymmetry_fixture(directory: Path, *, converged: int = 1) -> None:
    directory.mkdir()
    output = ROOT.TFile(str(directory / "beam_asymmetry.root"), "RECREATE")
    tree = ROOT.TTree("sigma_points", "sigma_points")
    sigma = array("d", [0.2])
    fit_converged = array("i", [converged])
    energy_bin = array("i", [0])
    tree.Branch("sigma", sigma, "sigma/D")
    tree.Branch("fit_converged", fit_converged, "fit_converged/I")
    tree.Branch("energy_bin", energy_bin, "energy_bin/I")
    tree.Fill()
    tree.Write()
    binning = output.mkdir("binning")
    binning.cd()
    edges = ROOT.TVectorD(3)
    for index, value in enumerate((1.1, 1.2, 1.3)):
        edges[index] = value
    edges.Write("energy_edges")
    covariance = output.mkdir("covariance")
    covariance.cd()
    matrix = ROOT.TH2D("total", "total", 1, 0, 1, 1, 0, 1)
    matrix.SetBinContent(1, 1, 0.04)
    matrix.Write()
    output.Close()
    for name in (
        "figure4_experimental.pdf",
        "comparison_reconstruction_samples.pdf",
        "comparison_estimators.pdf",
        "fit_diagnostics.pdf",
        "systematic_summary.pdf",
        "false_asymmetry_controls.pdf",
        "photon_multiplicity.pdf",
    ):
        (directory / name).write_bytes(b"%PDF-1.4\n")


def test_beam_asymmetry_validator_checks_objects_bins_fits_covariance_and_pdfs(tmp_path):
    from graal_pipeline.validators import validate_beam_asymmetry_directory

    valid_dir = tmp_path / "valid"
    _write_beam_asymmetry_fixture(valid_dir)

    assert validate_beam_asymmetry_directory(
        valid_dir, expected_energy_edges=(1.1, 1.2, 1.3)
    ).valid is True

    wrong_bins = validate_beam_asymmetry_directory(
        valid_dir, expected_energy_edges=(1.1, 1.25, 1.3)
    )
    assert wrong_bins.valid is False
    assert "energy edges do not match" in wrong_bins.reasons[0]

    (valid_dir / "fit_diagnostics.pdf").unlink()
    missing_pdf = validate_beam_asymmetry_directory(
        valid_dir, expected_energy_edges=(1.1, 1.2, 1.3)
    )
    assert missing_pdf.valid is False
    assert "fit_diagnostics.pdf" in missing_pdf.reasons[0]
