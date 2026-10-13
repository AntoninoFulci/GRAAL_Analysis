"""Shared diagnostic bundles declare both coverage and training provenance."""
from dataclasses import replace
import json

import pytest

from graal_common.physics.beam_profiles import UV_PROFILE, VIS_PROFILE
from graal_common.stage1.artifacts import Stage1Provenance
from graal_common.tests.test_stage1_artifacts import PROVENANCE_JSON
from reconstruction.runtime.stage1_gate import Stage1Gate


def shared_contract():
    return dict(schema_version=1, supported_profiles={"uv": [1.1, 1.5], "vis": [.9313, 1.1]},
                profile_mixture={"uv": .5, "vis": .5}, dataset_sha256="a" * 64,
                split_sha256="b" * 64, training_seed=42,
                threshold_policy="weighted_validation_f1_single",
                validation_status="diagnostic_only")


def test_shared_bundle_round_trip_and_coverage(tmp_path):
    provenance = replace(Stage1Provenance.from_json(PROVENANCE_JSON), shared_training=shared_contract())
    restored = Stage1Provenance.from_json(provenance.to_json())
    assert restored.shared_training == shared_contract()
    gate = Stage1Gate(None, .5, supported_profiles=restored.shared_training["supported_profiles"])
    gate.check_profile(UV_PROFILE)
    gate.check_profile(VIS_PROFILE)
    gate.check_profile(UV_PROFILE, energy_range_gev=(1.2, 1.4))
    with pytest.raises(ValueError, match="cover"):
        gate.check_profile(UV_PROFILE, energy_range_gev=(1.0, 1.4))
    with pytest.raises(ValueError, match="cover"):
        gate.check_profile(VIS_PROFILE, energy_range_gev=(.93, 1.1))


@pytest.mark.parametrize("key,value", [
    ("profile_mixture", {"uv": .5, "vis": .7}),
    ("supported_profiles", {"uv": [1.5, 1.1], "vis": [.9313, 1.1]}),
    ("dataset_sha256", "unknown"),
    ("schema_version", 999),
    ("validation_status", "validated_sigma"),
])
def test_shared_contract_rejects_invalid_provenance(key, value):
    payload = json.loads(PROVENANCE_JSON)
    payload["shared_training"] = shared_contract()
    payload["shared_training"][key] = value
    with pytest.raises(ValueError):
        Stage1Provenance.from_json(json.dumps(payload))


def test_single_profile_bundle_cannot_claim_shared_training():
    legacy = Stage1Provenance.from_json(PROVENANCE_JSON)
    ambiguous = replace(legacy, beam_profile="vis", energy_min_gev=.9313, energy_max_gev=1.1,
                        shared_training=shared_contract())
    with pytest.raises(ValueError, match="single.profile"):
        ambiguous.to_json()


def test_shared_domain_survives_reconstruction_and_extraction():
    from reconstruction.runtime.provenance import stage1_domain, validate_energy_domain
    gate = Stage1Gate(None, .5, supported_profiles=shared_contract()["supported_profiles"])
    record = {"selection": {"energy_range_gev": [.9313, 1.1]}, "beam_profile": "vis",
              "bdt_domain": stage1_domain(gate)}
    validate_energy_domain(record, "vis", (.9313, 1.1), requires_bdt=True)
    record["selection"]["energy_range_gev"] = [.9313, 1.5]
    record["beam_profile"] = "uv"
    with pytest.raises(ValueError, match="BDT.*cover"):
        validate_energy_domain(record, "uv", (.9313, 1.1), requires_bdt=True, allow_legacy=True)
