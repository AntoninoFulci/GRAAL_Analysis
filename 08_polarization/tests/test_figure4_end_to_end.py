from __future__ import annotations

from array import array
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
import numpy as np
import pytest

matplotlib.use("Agg")

ROOT = pytest.importorskip("ROOT")

from build_figure4_comparison import main
from contracts import sha256_file
from inventory_builder import build_reco_inventory


CANONICAL_BUNDLE = (
    "run_manifest_observables.csv",
    "run_quality.csv",
    "strip_energy_lookup.csv",
    "flux_by_run_energy.csv",
    "flux_by_group_energy.csv",
    "observable_run_qa.json",
)


def write_root(path, injected_sigma):
    output = ROOT.TFile(str(path), "RECREATE")
    tree = ROOT.TTree("reco_eta_pi0_chi2", "reco_eta_pi0_chi2")
    run = array("i", [7])
    state = array("i", [1])
    xstrip = array("f", [42.0])
    converged = array("i", [1])
    tree.Branch("RunNumber", run, "RunNumber/I")
    tree.Branch("Polarization", state, "Polarization/I")
    tree.Branch("Xstrip", xstrip, "Xstrip/F")
    tree.Branch("fit_converged", converged, "fit_converged/I")
    beam = ROOT.TLorentzVector()
    proton = ROOT.TLorentzVector()
    eta = ROOT.TLorentzVector()
    pi0 = ROOT.TLorentzVector()
    tree.Branch("beam", "TLorentzVector", beam)
    tree.Branch("proton_fit", "TLorentzVector", proton)
    tree.Branch("eta_fit", "TLorentzVector", eta)
    tree.Branch("pi0_fit", "TLorentzVector", pi0)
    width = np.pi / 12.0
    bin_average = np.sin(width) / width
    for index in range(12):
        phi = (index + 0.5) * width
        modulation = bin_average * np.cos(2.0 * phi)
        counts = {
            2: round(140 * (1.0 + 0.8 * injected_sigma * modulation)),
            1: round(140 * (1.0 - 0.8 * injected_sigma * modulation)),
        }
        for code, count in counts.items():
            state[0] = code
            for _ in range(count):
                momentum = 0.08
                px = momentum * np.cos(phi)
                py = momentum * np.sin(phi)
                beam.SetPxPyPzE(0.0, 0.0, 1.15, 1.15)
                proton.SetPxPyPzE(
                    px, py, 0.0, np.sqrt(0.938272**2 + momentum**2)
                )
                eta.SetPxPyPzE(0.01, -0.02, 0.0, np.sqrt(0.547862**2 + 0.0005))
                pi0.SetPxPyPzE(0.0, 0.0, 0.0, 0.134977)
                tree.Fill()
    tree.Write()
    output.Close()


def write_gate0(root):
    manifest = root / "config" / "run_manifest.csv"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("run_number,target\n7,P\n")
    bundle = root / "results" / "observable_runs"
    bundle.mkdir(parents=True)
    (bundle / "run_manifest_observables.csv").write_text(
        "run_number,source_period,target,beam_type,group,classification_source,source_file\n"
        "7,synthetic,P,UV,P_UV,synthetic,run7.root\n"
    )
    (bundle / "run_quality.csv").write_text("run_number,status\n7,good\n")
    (bundle / "strip_energy_lookup.csv").write_text(
        "run_number,xstrip,energy_median_gev\n7,42,1.15\n"
    )
    flux_fields = [
        "binning", "run_number", "source_period", "target", "beam_type",
        "group", "energy_low_gev", "energy_high_gev", "pol1", "brem",
        "pol2", "pol1_net", "pol2_net", "total_net", "status",
    ]
    with (bundle / "flux_by_run_energy.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=flux_fields)
        writer.writeheader()
        for low in (1.1, 1.2, 1.3, 1.4):
            writer.writerow(
                {
                    "binning": "ajaka_sigma", "run_number": 7,
                    "source_period": "synthetic", "target": "P",
                    "beam_type": "UV", "group": "P_UV",
                    "energy_low_gev": low, "energy_high_gev": low + 0.1,
                    "pol1": 100001, "brem": 1, "pol2": 100001,
                    "pol1_net": 100000, "pol2_net": 100000,
                    "total_net": 200000, "status": "valid",
                }
            )
    (bundle / "flux_by_group_energy.csv").write_text("status\nvalid\n")
    (bundle / "observable_run_qa.json").write_text(json.dumps({"valid": True}))
    records = []
    for name in CANONICAL_BUNDLE:
        path = bundle / name
        records.append(
            {
                "path": f"results/observable_runs/{name}",
                "sha256": sha256_file(path),
            }
        )
    qa_hash = sha256_file(bundle / "observable_run_qa.json")
    handoff = {
        "schema_version": 1,
        "producer_commit": "a" * 40,
        "manifest_path": "config/run_manifest.csv",
        "manifest_sha256": sha256_file(manifest),
        "files": records,
        "observable_run_qa_path": "results/observable_runs/observable_run_qa.json",
        "observable_run_qa_sha256": qa_hash,
        "observable_run_qa_valid": True,
        "energy_binning_mev": [1100, 1200, 1300, 1400, 1500],
        "created_at_utc": "2026-09-10T00:00:00Z",
    }
    handoff_path = bundle / "HANDOFF.json"
    handoff_path.write_text(json.dumps(handoff))
    return handoff_path


def write_config(root):
    authority = root / "authority"
    authority.mkdir()
    state_source = authority / "state.json"
    compton_source = authority / "compton.json"
    state_source.write_text("{}")
    compton_source.write_text("{}")

    def source(path):
        return {
            "path": str(path.relative_to(root)), "sha256": sha256_file(path),
            "authority": "synthetic-test", "approval_id": "fixture",
            "reviewers": ["test-a", "test-b"],
        }

    config = {
        "sign_convention": {
            "status": "approved",
            "approval_id": "fixture-sign",
            "reviewers": ["test-a", "test-b"],
            "orientation_signs": {"parallel": -1, "perpendicular": 1},
        },
        "figure4_comparison": {
            "energy_edges_gev": [1.1, 1.2, 1.3, 1.4, 1.5],
            "mass_bins": 10, "phi_bins": 12, "target": "P",
            "tree": "reco_eta_pi0_chi2", "vectors": "kinematic_fit",
        },
        "state_mapping": {
            "status": "ready", "source": source(state_source),
            "intervals": [
                {
                    "run_start": 7, "run_end": 7, "state_code": 1,
                    "orientation": "parallel", "source_period": "synthetic",
                    "flux_component": "pol1_net",
                },
                {
                    "run_start": 7, "run_end": 7, "state_code": 2,
                    "orientation": "perpendicular", "source_period": "synthetic",
                    "flux_component": "pol2_net",
                },
            ],
        },
        "compton_polarization": {
            "status": "ready",
            "periods": [
                {
                    "source_period": "synthetic", "source": source(compton_source),
                    "energies_mev": [1100, 1500], "polarization": [0.8, 0.8],
                    "covariance": [[0.0001, 0.0], [0.0, 0.0001]],
                }
            ],
        },
    }
    path = root / "config" / "physics" / "polarization_v1.json"
    path.parent.mkdir()
    path.write_text(json.dumps(config))
    return path


@pytest.mark.parametrize("injected", [-0.45, 0.0, 0.4])
def test_framework_figure4_cli_recovers_injected_sigma_from_root(tmp_path, injected):
    handoff = write_gate0(tmp_path)
    config = write_config(tmp_path)
    reco = tmp_path / "reco.root"
    write_root(reco, injected)
    ledger = tmp_path / "processed.csv"
    ledger.write_text("run_number,status\n7,complete\n")
    inventory = tmp_path / "inventory.json"
    build_reco_inventory(
        repository_root=tmp_path, output_path=inventory, reco_paths=[reco],
        processed_run_ledger=ledger, gate0_handoff_sha256=sha256_file(handoff),
        gate0_run_numbers={7}, observed_event_run_numbers={7},
        tree="reco_eta_pi0_chi2", vectors="kinematic_fit",
        producer_commit="b" * 40,
    )
    output = tmp_path / "comparison"
    result = main(
        [
            "--repository-root", str(tmp_path), "--config", str(config),
            "--handoff", str(handoff), "--reco-inventory", str(inventory),
            "--output-dir", str(output), "--producer-commit", "d" * 40,
        ]
    )
    assert result == 0
    with (output / "figure4_comparison.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    fitted = [
        float(row["sigma"])
        for row in rows
        if row["pair"] == "p_pi0" and row["valid"] == "true"
    ]
    assert fitted == pytest.approx([injected], abs=0.015)
    qa = json.loads((output / "figure4_comparison_qa.json").read_text())
    assert qa["published_data_used"] is False
    assert qa["points_total"] == 120
    assert qa["schema_version"] == 2
    assert qa["producer"]["commit"] == "d" * 40
    assert qa["producer"]["command"][0:2] == [
        "python", "08_polarization/build_figure4_comparison.py"
    ]
    assert qa["artifact_role"] == "diagnostic_qa"
    assert "not release physics" in qa["allowed_use"]
    assert qa["polarization_energy_weighting"]["panels"][0][
        "vertical_polarization_variance"
    ] == pytest.approx(0.000078125)
    input_records = [
        qa["config"], qa["handoff"], qa["reconstruction_inventory"], qa["flux"],
        *qa["reconstruction"], *qa["state_mapping_sources"], *qa["compton_sources"],
    ]
    for record in input_records:
        assert not Path(record["path"]).is_absolute()
        assert record["bytes"] > 0
        assert record["role"]
        assert record["allowed_use"]
    for record in qa["outputs"].values():
        assert record["bytes"] > 0
        assert record["role"]
        assert "not release physics" in record["allowed_use"]


def test_framework_figure4_rejects_observed_run_mismatch_with_inventory(
    tmp_path, capsys
):
    handoff = write_gate0(tmp_path)
    config = write_config(tmp_path)
    reco = tmp_path / "reco.root"
    write_root(reco, 0.2)
    ledger = tmp_path / "processed.csv"
    ledger.write_text("run_number,status\n7,complete\n")
    inventory = tmp_path / "inventory.json"
    build_reco_inventory(
        repository_root=tmp_path, output_path=inventory, reco_paths=[reco],
        processed_run_ledger=ledger, gate0_handoff_sha256=sha256_file(handoff),
        gate0_run_numbers={7}, observed_event_run_numbers=set(),
        tree="reco_eta_pi0_chi2", vectors="kinematic_fit",
        producer_commit="b" * 40,
    )
    assert main(
        [
            "--repository-root", str(tmp_path), "--config", str(config),
            "--handoff", str(handoff), "--reco-inventory", str(inventory),
            "--output-dir", str(tmp_path / "comparison"),
            "--producer-commit", "d" * 40,
        ]
    ) == 1
    assert "observed run set" in capsys.readouterr().err
