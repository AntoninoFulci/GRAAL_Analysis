import json

import pytest
from mc_simulation import native_validation as validation
from mc_simulation.geant3_signal import signal_card


@pytest.mark.parametrize("change", ["fixed_energy", "decay", "seed", "binary"])
def test_native_contract_rejects_wrong_generation_before_reading_events(
    tmp_path, change
):
    card = signal_card(100, seed=310027, energy_range=(0.95, 1.4875))
    if change == "fixed_energy":
        card = card.replace("EWIN 0.95 1.4875\n", "")
    elif change == "decay":
        card = card.replace("ETDK 1", "ETDK 0")
    elif change == "seed":
        card = card.replace("310029", "310033")
    (tmp_path / "laggen_signal.dat").write_text(card)
    (tmp_path / "binary-sha256.txt").write_text("0" * 64 + " /build/laggen/laggen\n")
    with pytest.raises(ValueError, match="contract|binaries"):
        validation.validate_native_sample(tmp_path, tmp_path / "converted.root")


def test_bound_archive_rejects_tampering_and_missing_truth_identity(
    tmp_path, monkeypatch
):
    resource = tmp_path / "resources"
    resource.mkdir()
    contract = {
        "model": "phase-space",
        "forced_decays": ["gg"],
        "energy_range_gev": [0.95, 1.4875],
    }
    contract_path = resource / "native_campaign_contract.json"
    contract_path.write_text(json.dumps(contract))
    monkeypatch.setattr(validation, "RESOURCES", resource)
    directory = tmp_path / "reconstruction"
    directory.mkdir()
    for path in (
        directory / "matched_events.npz",
        directory / "selection_audit.json",
        tmp_path / "generated_signal.dat",
        tmp_path / "generated_decays.dat",
    ):
        path.write_text("original")
    paths = [
        directory / "matched_events.npz",
        directory / "selection_audit.json",
        tmp_path / "generated_signal.dat",
        tmp_path / "generated_decays.dat",
        contract_path,
    ]
    record = {
        **contract,
        "status": "generation_and_native_chain_contract_passed",
        "inputs": [{"path": str(p), "sha256": validation.digest(p)} for p in paths],
    }
    (directory / "validation.json").write_text(json.dumps(record))
    (directory / "matched_events.npz").write_text("changed")
    with pytest.raises(ValueError, match="input changed"):
        validation.verified_reconstruction(directory)
    record["inputs"].pop(2)
    (directory / "validation.json").write_text(json.dumps(record))
    with pytest.raises(ValueError, match="required input"):
        validation.verified_reconstruction(directory)
