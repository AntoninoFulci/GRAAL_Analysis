"""Integrity and generation contract for the frozen native 100k campaign.

This validates completion, identities and the conditional generation model;
it does not certify the historical detector configuration or physics model.
"""

import hashlib
import json
import re
from pathlib import Path

import numpy as np
from mc_simulation.geant3_signal import (
    RESOURCES,
    read_decay_truth,
    read_truth,
    signal_card,
)


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate_native_sample(pilot, converted):
    pilot, converted = Path(pilot), Path(converted)
    contract_path = RESOURCES / "native_campaign_contract.json"
    contract = json.loads(contract_path.read_text())
    card = (pilot / "laggen_signal.dat").read_text()
    count = re.search(r"^TRIG (\d+)$", card, re.MULTILINE)
    seed = re.search(r"^RNDM (\d+) (\d+)$", card, re.MULTILINE)
    if not count or not seed:
        raise ValueError("missing generation count/seeds")
    count, seed = int(count[1]), int(seed[1])
    bounds = contract["energy_range_gev"]
    if card != signal_card(count, seed=seed, energy_range=bounds):
        raise ValueError(
            "card does not match frozen uniform phase-space generation contract"
        )
    binaries = {}
    for line in (pilot / "binary-sha256.txt").read_text().splitlines():
        sha, name = line.split()
        binaries[name.removeprefix("/build/")] = sha
    if binaries != contract["binaries"]:
        raise ValueError("unrecognized native generation/digitization binaries")
    paths = [contract_path, pilot / "laggen_signal.dat", pilot / "binary-sha256.txt"]
    for name, marker in (
        ("transport_probe.log", "TRANSPORT PROBE PASS"),
        ("laggen.log", "Time of CPU Used ="),
        ("lagdig.log", "Normal termination"),
        ("prean.log", "Normal Termination"),
    ):
        path = pilot / name
        if marker not in path.read_text():
            raise ValueError(f"native execution incomplete or failed: {name}")
        paths.append(path)
    completed = {}
    for line in (pilot / "completed-sha256.txt").read_text().splitlines():
        sha, name = line.split()
        completed[name] = sha
    for name, path in (
        ("generated_signal.dat", pilot / "generated_signal.dat"),
        ("generated_decays.dat", pilot / "generated_decays.dat"),
        ("converted.root", converted),
    ):
        if digest(path) != completed.get(name):
            raise ValueError(f"native completed-output hash mismatch: {name}")
        paths.append(path)
    truth = read_truth(pilot / "generated_signal.dat", count)
    if np.any((truth[:, 4] < bounds[0]) | (truth[:, 4] > bounds[1])):
        raise ValueError("truth energy outside generation interval")
    decays = read_decay_truth(pilot / "generated_decays.dat", truth)
    dig = (pilot / "lagdig.log").read_text()
    counts = {"generated": count}
    for key, expression in (
        ("hit_written", r"NUMBER OF EVENTS\s*:\s*(\d+)"),
        ("tag_rejected", r"Events rejected by Tagging Condition\s*=\s*(\d+)"),
        ("trigger_rejected", r"Events rejected by Trigger Condition\s*=\s*(\d+)"),
        ("digitized", r"Events collected\s*=\s*(\d+)"),
    ):
        match = re.search(expression, dig)
        if not match:
            raise ValueError(f"missing native count: {key}")
        counts[key] = int(match[1])
    counts["lost_before_digitizer"] = count - counts["hit_written"]
    if (
        counts["lost_before_digitizer"] < 0
        or sum(counts[key] for key in ("tag_rejected", "trigger_rejected", "digitized"))
        != counts["hit_written"]
    ):
        raise ValueError("inconsistent native loss accounting")
    prean = (pilot / "prean.log").read_text()
    match = re.search(r"Number of events in NTUPLE:\s*(\d+)", prean)
    if not match or int(match[1]) != counts["digitized"]:
        raise ValueError("PREAN/digitizer counts differ")
    for marker in ("OLD_CYL", "GRAAL_21", "calib_3700.cal"):
        if marker not in prean:
            raise ValueError("unexpected PREAN configuration")
    result = {
        "schema_version": 1,
        "status": "generation_and_native_chain_contract_passed",
        "model": contract["model"],
        "forced_decays": contract["forced_decays"],
        "energy_range_gev": bounds,
        "seeds": [seed, seed + 2],
        "generated_sample_sha256": completed["generated_signal.dat"],
        "counts": counts,
        "decays": decays,
        "inputs": [{"path": str(p.resolve()), "sha256": digest(p)} for p in paths],
    }
    return truth, result


def bind_reconstruction(directory, validation):
    """Bind completed reconstruction to checked native inputs and truth."""
    directory = Path(directory)
    for name in ("matched_events.npz", "selection_audit.json"):
        path = directory / name
        validation["inputs"].append(
            {"path": str(path.resolve()), "sha256": digest(path)}
        )
    (directory / "validation.json").write_text(json.dumps(validation, indent=2) + "\n")


def verified_reconstruction(directory):
    """Reject changed inputs, wrong generation model, or unbound reconstruction."""
    directory = Path(directory).resolve()
    validation = json.loads((directory / "validation.json").read_text())
    contract = json.loads((RESOURCES / "native_campaign_contract.json").read_text())
    if validation["status"] != "generation_and_native_chain_contract_passed" or any(
        validation[key] != contract[key]
        for key in ("model", "forced_decays", "energy_range_gev")
    ):
        raise ValueError("MC generation contract mismatch")
    identities = {
        Path(item["path"]).resolve(): item["sha256"] for item in validation["inputs"]
    }
    required = {
        directory / "matched_events.npz",
        directory / "selection_audit.json",
        directory.parent / "generated_signal.dat",
        directory.parent / "generated_decays.dat",
        (RESOURCES / "native_campaign_contract.json").resolve(),
    }
    if not required <= identities.keys():
        raise ValueError("MC validation lacks required input identities")
    for path, sha in identities.items():
        if digest(path) != sha:
            raise ValueError(f"MC validation input changed: {path}")
    if (
        identities[directory.parent / "generated_signal.dat"]
        != validation["generated_sample_sha256"]
    ):
        raise ValueError("MC generated sample identity mismatch")
    with np.load(directory / "matched_events.npz", allow_pickle=False) as data:
        truth = read_truth(
            directory.parent / "generated_signal.dat", validation["counts"]["generated"]
        )
        for name, expected in (
            ("generated_ids", truth[:, 1]),
            ("generated_energy_gev", truth[:, 4]),
            ("generated_p4", truth[:, 8:].reshape(-1, 3, 4)),
        ):
            if not np.array_equal(data[name], expected):
                raise ValueError("matched archive differs from complete native truth")
    return validation
