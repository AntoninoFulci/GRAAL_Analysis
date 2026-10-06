import csv

import numpy as np
import pytest
import uproot

from graal_theory.photon_flux import (
    group_flux_by_energy, load_calibrated_flux, native_flux_spectrum, selected_uv_runs,
)


def _fixture(tmp_path, *, complete=True):
    manifest = tmp_path / "runs.csv"
    with manifest.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["run_number", "target", "beam_type"])
        writer.writeheader()
        writer.writerow({"run_number": 1, "target": "P", "beam_type": "UV"})
        writer.writerow({"run_number": 2, "target": "P", "beam_type": "UV"})
    root = tmp_path / "flux.root"
    edges = np.linspace(1.0, 1.4, 129)
    vertical = np.zeros(128)
    horizontal = np.zeros(128)
    brem = np.zeros(128)
    vertical[64] = 30.0
    horizontal[64] = 10.0
    brem[64] = 5.0
    vertical[80] = 10.0
    horizontal[80] = 30.0
    brem[80] = 5.0
    with uproot.recreate(root) as out:
        out["run1_POL1"] = vertical, edges
        out["run1_POL2"] = horizontal, edges
        out["run1_BREM"] = brem, edges
        out["run2_POL1"] = vertical, edges
        out["run2_POL2"] = horizontal, edges
        if complete:
            out["run2_BREM"] = brem, edges
    return root, manifest


def test_loader_uses_only_complete_runs_and_selected_positive_strips(tmp_path):
    root, manifest = _fixture(tmp_path, complete=False)
    spectrum = load_calibrated_flux(root, manifest, (1.20, 1.30))
    assert spectrum.selected_runs == 2
    assert spectrum.complete_runs == 1
    assert len(spectrum.exposures) == 2
    assert sum(item.flux_vertical for item in spectrum.exposures) == 40.0
    assert sum(item.flux_horizontal for item in spectrum.exposures) == 40.0
    assert all(0.0 < item.polarization_vertical < 1.0 for item in spectrum.exposures)


def test_grouping_preserves_state_flux_and_separate_polarization_means(tmp_path):
    root, manifest = _fixture(tmp_path)
    spectrum = load_calibrated_flux(root, manifest, (1.20, 1.30))
    grouped = group_flux_by_energy(spectrum, 2)
    assert len(grouped) == 2
    assert [node.flux_vertical for node in grouped] == [60.0, 20.0]
    assert [node.flux_horizontal for node in grouped] == [20.0, 60.0]
    assert grouped[0].energy_gev < grouped[1].energy_gev
    assert grouped[0].polarization_vertical == pytest.approx(spectrum.exposures[0].polarization_vertical)
    assert grouped[1].polarization_horizontal == pytest.approx(spectrum.exposures[1].polarization_horizontal)


def test_loader_rejects_no_complete_flux_in_energy_bin(tmp_path):
    root, manifest = _fixture(tmp_path, complete=False)
    with pytest.raises(ValueError, match="no complete.*exposures"):
        load_calibrated_flux(root, manifest, (1.30, 1.35))


def test_native_spectrum_uses_only_runs_in_nominal_reconstruction(tmp_path):
    root, manifest = _fixture(tmp_path)
    edges = np.linspace(1.0, 1.4, 129)
    different = np.zeros(128)
    different[64] = 100.0
    with uproot.update(root) as out:
        # New run has a different spectrum; use new run ID to avoid ROOT cycles.
        for state in ("POL1", "POL2", "BREM"):
            out[f"run3_{state}"] = different, edges
    with manifest.open("a") as stream:
        stream.write("3,P,UV\n")
    reco = tmp_path / "reco.root"
    with uproot.recreate(reco) as out:
        out["reco_eta_pi0_bdt"] = {"RunNumber": np.array([1, 1, 1], dtype=np.int32)}
    assert selected_uv_runs(reco) == frozenset({1})
    selected = native_flux_spectrum(root, manifest, reco, (1.2, 1.3))
    unfiltered = load_calibrated_flux(root, manifest, (1.2, 1.3))
    assert selected.selected_runs == selected.complete_runs == 1
    assert sum(item.flux_vertical for item in selected.exposures) == 40.0
    assert sum(item.flux_vertical for item in unfiltered.exposures) == 180.0
    assert len(selected.source_fingerprint) == 64


def test_selected_run_requires_complete_triplet_and_valid_reco(tmp_path):
    root, manifest = _fixture(tmp_path, complete=False)
    with pytest.raises(ValueError, match="complete"):
        load_calibrated_flux(root, manifest, (1.2, 1.3), selected_run_numbers=frozenset({2}))
    with pytest.raises(ValueError):
        load_calibrated_flux(root, manifest, (1.2, 1.3), selected_run_numbers=frozenset())
    reco = tmp_path / "bad_reco.root"
    with uproot.recreate(reco) as out:
        out["reco_eta_pi0_bdt"] = {"SomeOtherBranch": np.array([1], dtype=np.int32)}
    with pytest.raises(ValueError, match="RunNumber"):
        selected_uv_runs(reco)


def test_native_wrapper_skips_incomplete_reco_run_like_stage07(tmp_path):
    root, manifest = _fixture(tmp_path, complete=False)
    reco = tmp_path / "reco.root"
    with uproot.recreate(reco) as out:
        out["reco_eta_pi0_bdt"] = {"RunNumber": np.array([1, 2], dtype=np.int32)}
    spectrum = native_flux_spectrum(root, manifest, reco, (1.2, 1.3))
    assert spectrum.complete_runs == 1
    assert sum(item.flux_vertical for item in spectrum.exposures) == 40.0


def test_selected_run_rejects_duplicate_flux_root_cycle(tmp_path):
    root, manifest = _fixture(tmp_path)
    edges = np.linspace(1.0, 1.4, 129)
    with uproot.update(root) as out:
        out["run1_POL1"] = np.zeros(128), edges
    with pytest.raises(ValueError, match="duplicate"):
        load_calibrated_flux(root, manifest, (1.2, 1.3), selected_run_numbers=frozenset({1}))
