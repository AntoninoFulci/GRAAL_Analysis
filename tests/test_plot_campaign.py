from pathlib import Path
from array import array
from dataclasses import replace
import warnings

import numpy as np
import pytest
import ROOT

from scripts import plot_campaign
from observable_extraction.io.root_output import RootOutputPayload, write_root_output
from observable_extraction.tests.test_figure4 import _points


def _write_reconstruction(path: Path, tree_name: str, *, fit: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    source = ROOT.TFile(str(path), "RECREATE")
    tree = ROOT.TTree(tree_name, tree_name)
    vectors = {}
    for name, energy, pz in (("eta", 0.55, 0.0), ("pi0", 0.14, 0.0),
                             ("proton", 0.94, 0.0), ("missing", 0.95, 0.0),
                             ("beam", 1.2, 1.2), ("target", 0.938, 0.0)):
        value = ROOT.TLorentzVector(0, 0, pz, energy)
        tree.Branch(name, "TLorentzVector", value)
        vectors[name] = value
    if fit:
        for name, energy in (("eta_fit", 0.548), ("pi0_fit", 0.135), ("proton_fit", 0.96)):
            value = ROOT.TLorentzVector(0, 0, 0, energy)
            tree.Branch(name, "TLorentzVector", value)
            vectors[name] = value
    scalars = {"eta_mass": array("f", [0.55]), "pi0_mass": array("f", [0.14])}
    if fit:
        scalars["fit_chi2"] = array("f", [1.0])
    for name, value in scalars.items():
        tree.Branch(name, value, f"{name}/F")
    tree.Fill()
    tree.Write()
    source.Close()


def _write_asymmetry(path: Path, profile: str) -> None:
    source_points = _points()
    if profile == "vis":
        source_points = tuple(replace(item, point=replace(item.point, energy_bin=0,
                               energy_low_gev=0.9313, energy_high_gev=1.10))
                              for item in source_points if item.point.energy_bin == 0)
    points = tuple(replace(item, sample=sample, estimator=estimator)
                   for item in source_points
                   for sample in ("raw_bdt", "raw_bdt_fit")
                   for estimator in ("ratio", "likelihood"))
    edges = (0.9313, 1.10) if profile == "vis" else (1.10, 1.20, 1.30, 1.40, 1.50)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_root_output(path, RootOutputPayload(
        points=points, energy_edges=np.asarray(edges), mass_edges={},
        covariance_total=np.eye(len(points)), systematic_covariances={},
        ratio_objects=(), provenance=f"profile={profile}",
    ))


def test_completed_campaign_root_fixture_generates_canonical_pdfs(tmp_path):
    campaign = tmp_path / "results/completed"
    original = {}
    for profile in ("uv", "vis"):
        root = campaign / profile
        for tree_name, fit in (("reco_eta_pi0_chi2", False), ("reco_eta_pi0_bdt", True)):
            path = root / "reco" / f"{tree_name}.root"
            _write_reconstruction(path, tree_name, fit=fit)
            original[path] = path.read_bytes()
        path = root / "beam_asymmetry/beam_asymmetry.root"
        _write_asymmetry(path, profile)
        original[path] = path.read_bytes()
        for name in plot_campaign.REQUIRED_STAGE7_PDFS:
            (root / "beam_asymmetry" / name).write_bytes(b"%PDF-1.4\n")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        plot_campaign.render_campaign(campaign, plot_campaign.combine_profiles.AJAKA_REFERENCE)
    assert not any("Deleting canvas with same name" in str(item.message) for item in caught)

    assert all(path.read_bytes() == contents for path, contents in original.items())
    for profile in ("uv", "vis"):
        output = campaign / profile / "plots"
        for name in ("mass_raw_fit_p_eta.pdf", "mass_raw_fit_p_pi0.pdf", "mass_raw_fit_eta_pi0.pdf",
                     "comparison_raw_fit_ratio.pdf", "comparison_raw_fit_likelihood.pdf", "dalitz_confronto.pdf"):
            assert (output / name).read_bytes().startswith(b"%PDF")
    common = campaign / "common/plots"
    for name in ("mass_uv_vis_p_eta.pdf", "comparison_raw_fit_ratio.pdf", "figure4_experimental.pdf"):
        assert (common / name).read_bytes().startswith(b"%PDF")


def test_postprocessing_publishes_all_plot_sets_without_changing_root_inputs(tmp_path, monkeypatch):
    campaign = tmp_path / "results/campaign"
    roots = []
    for profile in ("uv", "vis"):
        root = campaign / profile / "reco/reco_eta_pi0_bdt.root"
        root.parent.mkdir(parents=True)
        root.write_bytes(profile.encode())
        roots.append(root)
    monkeypatch.setattr(plot_campaign, "_read_profile", lambda campaign, profile: (profile, profile))
    monkeypatch.setattr(plot_campaign, "_render_profile", lambda campaign, profile, payload, output: (output / "plot.pdf").write_bytes(b"%PDF"))
    monkeypatch.setattr(plot_campaign, "_render_common", lambda campaign, payloads, output, reference: (output / "combined.pdf").write_bytes(b"%PDF"))

    plot_campaign.render_campaign(campaign, tmp_path / "ajaka.csv")

    assert [root.read_bytes() for root in roots] == [b"uv", b"vis"]
    for directory in (campaign / "uv/plots", campaign / "vis/plots", campaign / "common/plots"):
        assert next(directory.glob("*.pdf")).read_bytes() == b"%PDF"


def test_postprocessing_failure_keeps_previous_plot_sets(tmp_path, monkeypatch):
    campaign = tmp_path / "campaign"
    old = campaign / "uv/plots/keep.pdf"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"old")
    monkeypatch.setattr(plot_campaign, "_read_profile", lambda campaign, profile: (profile, profile))
    monkeypatch.setattr(plot_campaign, "_render_profile", lambda campaign, profile, payload, output: (_ for _ in ()).throw(RuntimeError("plot failed")))
    with pytest.raises(RuntimeError, match="plot failed"):
        plot_campaign.render_campaign(campaign, tmp_path / "ajaka.csv")
    assert old.read_bytes() == b"old"


def test_postprocessing_rejects_missing_legacy_stage7_diagnostics(tmp_path):
    root = tmp_path / "uv"
    (root / "beam_asymmetry").mkdir(parents=True)
    output = tmp_path / "staged"
    output.mkdir()
    with pytest.raises(FileNotFoundError, match="systematic_summary.pdf"):
        plot_campaign._copy_stage7_pdfs(root, output)


def test_postprocessing_rejects_corrupt_legacy_pdf(tmp_path):
    root = tmp_path / "uv"
    source = root / "beam_asymmetry"
    source.mkdir(parents=True)
    for name in plot_campaign.REQUIRED_STAGE7_PDFS:
        (source / name).write_bytes(b"%PDF-1.4\n")
    (source / "systematic_summary.pdf").write_bytes(b"broken")
    output = tmp_path / "staged"
    output.mkdir()
    with pytest.raises(ValueError, match="systematic_summary.pdf"):
        plot_campaign._copy_stage7_pdfs(root, output)
