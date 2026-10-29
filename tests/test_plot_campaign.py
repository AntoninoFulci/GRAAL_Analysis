from pathlib import Path
import json
import os
from array import array
from dataclasses import replace
import warnings

import numpy as np
import pytest
import ROOT

from scripts import plot_campaign
from observable_extraction.io.root_output import RootOutputPayload, write_root_output
from observable_extraction.tests.test_figure4 import _points


def _write_reconstruction(path: Path, tree_name: str, *, fit: bool, certified: bool = True) -> None:
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
    if not fit and certified:
        ROOT.TNamed("reconstruction_provenance", json.dumps(dict(schema=2, selection_algorithm="pairing_missing_mass"))).Write()
    source.Close()


def _write_asymmetry(
    path: Path, profile: str, *, fit: bool = False, candle: bool = False,
    estimators=("ratio", "likelihood"),
) -> None:
    source_points = _points()
    if profile == "vis":
        source_points = tuple(replace(item, point=replace(item.point, energy_bin=0,
                               energy_low_gev=0.9313, energy_high_gev=1.10))
                              for item in source_points if item.point.energy_bin == 0)
    samples = (("raw_bdt", "raw_bdt_fit") if fit else ("raw", "raw_bdt"))
    if candle:
        samples += ("raw_bdt_core", "raw_bdt_tails")
    points = tuple(replace(item, sample=sample, estimator=estimator)
                   for item in source_points
                   for sample in samples
                   for estimator in estimators)
    edges = (0.9313, 1.10) if profile == "vis" else (1.10, 1.20, 1.30, 1.40, 1.50)
    path.parent.mkdir(parents=True, exist_ok=True)
    provenance = f"profile={profile}"
    if candle:
        provenance += (
            "\ncandle_enabled=true"
            "\ncandle_eta_center_gev=0.547862"
            "\ncandle_pi0_center_gev=0.134977"
            "\ncandle_mass_half_width_gev=0.05"
            "\ncandle_geometry=rectangular"
            "\ncandle_core_logic=and"
            "\ncandle_tail_logic=or_complement"
            "\ncandle_boundary=inclusive"
            "\ncandle_baseline_event_count=100"
            "\ncandle_full_core_event_count=80"
            "\ncandle_tail_event_count=20"
            "\ncandle_balanced_core_event_count=20"
            "\ncandle_excluded_nonfinite_event_count=0"
            "\ncandle_balance_method=random_without_replacement"
            "\ncandle_balance_seed=20261024"
            "\ncandle_mass_source=raw_pre_fit"
        )
    write_root_output(path, RootOutputPayload(
        points=points, energy_edges=np.asarray(edges), mass_edges={},
        covariance_total=np.eye(len(points)), systematic_covariances={},
        ratio_objects=(), provenance=provenance,
    ))


@pytest.mark.parametrize("workers", [1, 2])
def test_completed_campaign_root_fixture_generates_canonical_pdfs(tmp_path, workers):
    campaign = tmp_path / "results/completed"
    original = {}
    for profile in ("uv", "vis"):
        root = campaign / "root" / profile
        for tree_name, fit in (("reco_eta_pi0_chi2", False), ("reco_eta_pi0_bdt", False)):
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
        plot_campaign.render_campaign(campaign, plot_campaign.combine_profiles.AJAKA_REFERENCE, workers=workers)
    assert not any("Deleting canvas with same name" in str(item.message) for item in caught)

    period = campaign / "root/uv/beam_asymmetry/periods/P1/fit_diagnostics.pdf"
    period.parent.mkdir(parents=True)
    period.write_bytes(b"%PDF-period")
    plot_campaign.render_campaign(campaign, plot_campaign.combine_profiles.AJAKA_REFERENCE, workers=workers)
    plot_campaign.render_campaign(campaign, plot_campaign.combine_profiles.AJAKA_REFERENCE, workers=workers)
    assert (campaign / "plots/uv/periods/P1/fit_diagnostics.pdf").read_bytes() == b"%PDF-period"
    assert not list((campaign / "root").rglob("*.pdf"))
    assert not list((campaign / "plots").rglob("*.root"))
    assert all(path.read_bytes() == contents for path, contents in original.items())
    for profile in ("uv", "vis"):
        output = campaign / "plots" / profile
        for name in ("comparison_reconstruction_samples.pdf", "comparison_estimators.pdf", "fit_diagnostics.pdf", "massa_eta.pdf", "massa_pi0.pdf"):
            assert (output / name).read_bytes().startswith(b"%PDF")
        for stem in ('theta_missing_proton', 'coplanarity', 'missing_mass', 'beam_energy_vs_proton_theta'):
            assert (output / f'{stem}.pdf').read_bytes().startswith(b'%PDF')
        histograms = ROOT.TFile.Open(str(campaign / "root" / profile / "istogrammi.root"))
        try:
            names = {key.GetName() for key in histograms.GetListOfKeys()
                     if key.GetClassName().startswith("TH")}
            assert not any(name.startswith(("dalitz_", "dalitz_s_", "residuo_")) for name in names)
            assert {"massa_eta_chi2", "massa_eta_bdt", "massa_pi0_chi2", "massa_pi0_bdt"} <= names
            assert {'theta_missing_proton_chi2', 'coplanarity_bdt',
                    'missing_mass_bdt', 'beam_energy_vs_proton_theta_chi2'} <= names
            quality = json.loads(histograms.Get('quality_metadata').GetTitle())
            assert quality['samples']['bdt']['eta_mass_fit']['status'] == 'insufficient_data'
            assert quality['samples']['chi2']['undefined_angles']['coplanarity_deg'] == 1
        finally:
            histograms.Close()
    common = campaign / "plots/common"
    for name in ("asymmetry_comparison.pdf",):
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
    monkeypatch.setattr(plot_campaign, "_render_common", lambda campaign, output, reference: (output / "combined.pdf").write_bytes(b"%PDF"))

    plot_campaign.render_campaign(campaign, tmp_path / "ajaka.csv")

    assert [root.read_bytes() for root in roots] == [b"uv", b"vis"]
    for directory in (campaign / "plots/uv", campaign / "plots/vis", campaign / "plots/common"):
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


def test_no_fit_campaign_generates_raw_plots_and_removes_stale_fit_pdfs(tmp_path):
    import json
    campaign = tmp_path / "baseline"
    for profile in ("uv", "vis"):
        root = campaign / profile
        for tree in ("reco_eta_pi0_chi2", "reco_eta_pi0_bdt"):
            path = root / "reco" / f"{tree}.root"
            _write_reconstruction(path, tree, fit=False)
            source = ROOT.TFile(str(path), "UPDATE")
            ROOT.TNamed("reconstruction_provenance", json.dumps({"schema": 2, "selection_algorithm": "pairing_missing_mass"})).Write()
            source.Close()
        _write_asymmetry(root / "beam_asymmetry/beam_asymmetry.root", profile, fit=False)
        for name in plot_campaign.REQUIRED_STAGE7_PDFS:
            (root / "beam_asymmetry" / name).write_bytes(b"%PDF-1.4\n")
        old = root / "plots"
        old.mkdir()
        (old / "comparison_raw_fit_ratio.pdf").write_bytes(b"%PDF-old")
        (old / "comparison_reconstruction_samples.pdf").write_bytes(b"%PDF-stale fit comparison")
    plot_campaign.render_campaign(campaign, plot_campaign.combine_profiles.AJAKA_REFERENCE)
    for profile in ("uv", "vis"):
        output = campaign / "plots" / profile
        assert not list(output.glob("dalitz*.pdf"))
        assert (output / "massa_eta.pdf").is_file()
        assert (output / "massa_pi0.pdf").is_file()
        assert not list(output.glob("massa_*_raw_confronto.pdf"))
        assert not (output / "figure4_experimental.pdf").exists()
        assert not list(output.glob("*raw_fit*"))
        assert b"stale fit" not in (output / "comparison_reconstruction_samples.pdf").read_bytes()
    assert not list((campaign / "plots/common").glob("*raw_fit*"))
    assert not list((campaign / "plots/common").glob("mass_uv_vis*"))


def test_default_postprocessing_rejects_archived_fit_campaign(tmp_path):
    _write_asymmetry(tmp_path / "uv/beam_asymmetry/beam_asymmetry.root", "uv", fit=True)
    with pytest.raises(ValueError, match="raw/raw_bdt"):
        plot_campaign._read_profile(tmp_path, "uv")


def test_postprocessing_prefers_current_stage7_diagnostics(tmp_path):
    root = tmp_path / "uv"
    (root / "plots").mkdir(parents=True)
    (root / "beam_asymmetry").mkdir()
    for name in plot_campaign.REQUIRED_STAGE7_PDFS:
        (root / "plots" / name).write_bytes(b"%PDF-old-fit-campaign")
        (root / "beam_asymmetry" / name).write_bytes(b"%PDF-current-no-fit")
    output = tmp_path / "out"
    output.mkdir()
    plot_campaign._copy_stage7_pdfs(root, output)
    assert (output / "systematic_summary.pdf").read_bytes() == b"%PDF-current-no-fit"


def test_postprocessing_refuses_diagnostics_older_than_current_extraction(tmp_path):
    import os
    root = tmp_path / "uv"
    (root / "plots").mkdir(parents=True)
    (root / "beam_asymmetry").mkdir()
    for name in plot_campaign.REQUIRED_STAGE7_PDFS:
        path = root / "plots" / name
        path.write_bytes(b"%PDF-old-fit-campaign")
        os.utime(path, (1, 1))
    (root / "beam_asymmetry/beam_asymmetry.root").touch()
    output = tmp_path / "out"
    output.mkdir()
    with pytest.raises(FileNotFoundError, match="systematic_summary.pdf"):
        plot_campaign._copy_stage7_pdfs(root, output)


@pytest.mark.parametrize(
    ("estimators", "expected"),
    [
        (("ratio", "likelihood"), {"ratio", "likelihood"}),
        (("ratio",), {"ratio"}),
        (("likelihood",), {"likelihood"}),
    ],
)
def test_candle_campaign_preserves_mass_plane_and_available_comparisons(
    tmp_path, estimators, expected
):
    campaign = tmp_path / "results/candle"
    mass_planes = {}
    for profile in ("uv", "vis"):
        root = campaign / profile
        for tree_name in ("reco_eta_pi0_chi2", "reco_eta_pi0_bdt"):
            _write_reconstruction(
                root / "reco" / f"{tree_name}.root",
                tree_name,
                fit=False,
            )
        _write_asymmetry(
            root / "beam_asymmetry/beam_asymmetry.root",
            profile,
            candle=True,
            estimators=estimators,
        )
        for name in plot_campaign.REQUIRED_STAGE7_PDFS:
            (root / "beam_asymmetry" / name).write_bytes(b"%PDF-1.4\n")
        mass_planes[profile] = f"%PDF-{profile}-raw-plane\n".encode()
        (root / "beam_asymmetry/candle_mass_plane.pdf").write_bytes(
            mass_planes[profile]
        )

    plot_campaign.render_campaign(
        campaign,
        plot_campaign.combine_profiles.AJAKA_REFERENCE,
    )

    for profile in ("uv", "vis"):
        output = campaign / "plots" / profile
        assert (output / "candle_mass_plane.pdf").read_bytes() == mass_planes[profile]
        for estimator in ("ratio", "likelihood"):
            path = output / f"comparison_candle_{estimator}.pdf"
            assert path.exists() == (estimator in expected)
            if path.exists():
                assert path.read_bytes().startswith(b"%PDF-")
    common = campaign / "plots/common"
    for estimator in ("ratio", "likelihood"):
        path = common / f"comparison_candle_{estimator}.pdf"
        assert path.exists() == (estimator in expected)
        if path.exists():
            assert path.read_bytes().startswith(b"%PDF-")


def test_postprocessing_requires_mass_plane_for_candle_points(tmp_path):
    root = tmp_path / "uv"
    source = root / "beam_asymmetry"
    source.mkdir(parents=True)
    for name in plot_campaign.REQUIRED_STAGE7_PDFS:
        (source / name).write_bytes(b"%PDF-1.4\n")
    output = tmp_path / "staged"
    output.mkdir()

    with pytest.raises(FileNotFoundError, match="candle_mass_plane.pdf"):
        plot_campaign._copy_stage7_pdfs(root, output, require_candle=True)


def test_postprocessing_rejects_candle_mass_plane_older_than_extraction(tmp_path):
    root = tmp_path / "uv"
    source = root / "beam_asymmetry"
    source.mkdir(parents=True)
    extraction = source / "beam_asymmetry.root"
    extraction.write_bytes(b"root")
    for name in plot_campaign.REQUIRED_STAGE7_PDFS:
        (source / name).write_bytes(b"%PDF-1.4\n")
    mass_plane = source / "candle_mass_plane.pdf"
    mass_plane.write_bytes(b"%PDF-1.4\n")
    old = extraction.stat().st_mtime_ns - 1_000_000_000
    os.utime(mass_plane, ns=(old, old))
    output = tmp_path / "staged"
    output.mkdir()

    with pytest.raises(ValueError, match="older than current extraction"):
        plot_campaign._copy_stage7_pdfs(root, output, require_candle=True)


def test_standalone_dalitz_rejects_uncertified_raw_tree(tmp_path):
    chi2 = tmp_path / "chi2.root"
    bdt = tmp_path / "bdt.root"
    _write_reconstruction(chi2, "reco_eta_pi0_chi2", fit=False, certified=False)
    _write_reconstruction(bdt, "reco_eta_pi0_bdt", fit=False, certified=False)
    with pytest.raises(ValueError, match="provenance"):
        plot_campaign.dalitz.main(["--chi2", str(chi2), "--bdt", str(bdt), "--out-dir", str(tmp_path / "out")])


def _certify_dalitz_fixture(path, *, empty=False, chi2_cut=10.):
    import json
    source = ROOT.TFile(str(path), 'UPDATE')
    if empty:
        key = next(k.GetName() for k in source.GetListOfKeys() if k.GetClassName() == 'TTree')
        tree = source.Get(key)
        tree.Reset()
        tree.Write('', ROOT.TObject.kOverwrite)
    ROOT.TNamed('reconstruction_provenance', json.dumps({
        'schema': 2, 'selection_algorithm': 'pairing_missing_mass', 'channel': 'eta_pi0', 'input_tree': 'h85',
        'inputs': [{'path': 'fixture.root', 'sha256': 'fixture-h85', 'size': 42}],
        'selection': {'chi2_cut': chi2_cut, 'energy_range_gev': [1.1, 1.5],
                      'chi2_resolution_relative': .08, 'missing_mass_window_gev': .06,
                      'partner_mass_gev': .938272, 'photons': 'first_four_of_at_least_four',
                      'protons': 'exactly_one'},
    })).Write('', ROOT.TObject.kOverwrite)
    source.Close()


@pytest.mark.parametrize('empty', [False, True])
def test_dalitz_root_is_self_documented_and_empty_safe(tmp_path, empty, capsys):
    import json
    chi2, bdt = tmp_path / 'chi2.root', tmp_path / 'bdt.root'
    for path, name in ((chi2, 'chi2'), (bdt, 'bdt')):
        _write_reconstruction(path, f'reco_eta_pi0_{name}', fit=False)
        _certify_dalitz_fixture(path, empty=empty)
    output = tmp_path / 'out'
    ROOT.gROOT.GetListOfCanvases().Delete()
    plot_campaign.dalitz.main(['--chi2', str(chi2), '--bdt', str(bdt),
                              '--out-dir', str(output), '--profile', 'uv'])
    source = ROOT.TFile.Open(str(output / 'istogrammi.root'))
    metadata = json.loads(source.Get('dalitz_metadata').GetTitle())
    dictionary = json.loads(source.Get('histogram_dictionary').GetTitle())
    assert metadata['samples']['chi2']['entries'] == (0 if empty else 1)
    assert metadata['samples']['chi2']['profile'] == 'uv'
    assert metadata['samples']['chi2']['input']['sha256']
    assert metadata['samples']['chi2']['reconstruction_provenance']['selection_algorithm'] == 'pairing_missing_mass'
    assert metadata['selection_comparison'] == 'matched_except_bdt_gate'
    assert metadata['masses_gev'] == {'proton': .938272, 'eta': .547862, 'pi0': .134977}
    for name in ('dalitz_s_chi2_misurato', 'dalitz_s_bdt_implicito', 'residuo_chi2_misurato'):
        assert source.Get(name).GetEntries() == (0 if empty else 1)
        assert dictionary[name]['all_bins'] == (0 if empty else 1)
    assert source.Get('massa_eta_bdt').GetXaxis().GetTitle()
    assert source.Get('massa_pi0_bdt_raw_confronto').GetXaxis().GetTitle()
    assert dictionary['dalitz_s_chi2_misurato_unit_area']['all_bins'] == (0 if empty else 1)
    assert metadata['samples']['chi2']['observed_energy_range_gev'] == (None if empty else [1.2, 1.2])
    source.Close()
    assert (output / 'dalitz_s_confronto_unit_area.pdf').read_bytes().startswith(b'%PDF')
    assert 'nan%' not in capsys.readouterr().out


def test_dalitz_rejects_comparing_different_raw_cuts(tmp_path):
    chi2, bdt = tmp_path / 'chi2.root', tmp_path / 'bdt.root'
    for path, name, cut in ((chi2, 'chi2', 10.), (bdt, 'bdt', 20.)):
        _write_reconstruction(path, f'reco_eta_pi0_{name}', fit=False)
        _certify_dalitz_fixture(path, chi2_cut=cut)
    with pytest.raises(ValueError, match='selection'):
        plot_campaign.dalitz.main(['--chi2', str(chi2), '--bdt', str(bdt), '--out-dir', str(tmp_path/'out')])
