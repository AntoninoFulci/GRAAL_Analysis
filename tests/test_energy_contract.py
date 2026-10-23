from dataclasses import replace
import json
from pathlib import Path

import numpy as np
import pytest

from graal_common.physics.beam_profiles import UV_PROFILE
from graal_common.physics.energy_binning import EnergyBinning
from graal_common.stage1.artifacts import Stage1Provenance
from graal_common.stage1.features import FEATURE_NAMES_S1
from bdt_training.dataset.stage1_dataset import Stage1Dataset, Stage1DatasetMetadata, save_stage1_dataset, load_stage1_dataset
from bdt_training.beam_spectrum import BeamSpectrum
from reconstruction.runtime.stage1_gate import Stage1Gate
from observable_extraction.plotting.figure4 import profile_energy_rows
from graal_workflow import models, paths as workflow_paths, planning


def test_low_uv_domain_survives_dataset_and_model_contract(tmp_path):
    metadata = Stage1DatasetMetadata(tuple(FEATURE_NAMES_S1), "eta_pi0", "eta_pi0",
                                     signal_prior=.5, beam_reweighted=True, beam_profile="uv", energy_min_gev=0.9313, energy_max_gev=1.1)
    dataset = Stage1Dataset(np.zeros((2, len(FEATURE_NAMES_S1))), np.array([0, 1]), np.ones(2), metadata)
    path = tmp_path / "features.npz"
    save_stage1_dataset(path, dataset)
    assert load_stage1_dataset(path).metadata == metadata
    provenance = Stage1Provenance("eta_pi0", "eta_pi0", .5, True, "accept-reject-unweighted", .016, .007,
                                 "legacy-uncalibrated", tuple(FEATURE_NAMES_S1), "uv", .9313, 1.1)
    assert Stage1Provenance.from_json(provenance.to_json()) == provenance


def test_gate_rejects_nominal_or_legacy_model_for_low_uv():
    for profile, bounds in ((None, None), ("uv", (1.1, 1.5))):
        gate = Stage1Gate(None, .5, beam_profile=profile, energy_range_gev=bounds)
        with pytest.raises(ValueError, match="energy range|legacy"):
            gate.check_profile(UV_PROFILE, energy_range_gev=(.9313, 1.1))
    Stage1Gate(None, .5, beam_profile="uv", energy_range_gev=(.9313, 1.1)).check_profile(
        UV_PROFILE, energy_range_gev=(.9313, 1.1))


def test_spectrum_includes_last_edge_once():
    spectrum = BeamSpectrum(np.array([1., 1.05, 1.1]), np.array([2., 3.]))
    np.testing.assert_equal(spectrum.pdf(np.array([.99, 1., 1.05, 1.1, 1.11])), [0, 2, 3, 3, 0])


def test_rows_use_actual_grid():
    rows = profile_energy_rows("uv", (.9313, 1.0, 1.1))
    assert [(r.low_gev, r.high_gev) for r in rows] == [(.9313, 1.), (1., 1.1)]


def test_pipeline_propagates_domain_and_skips_closed_channels(tmp_path):
    config = workflow_paths.mode_config("test_data", tmp_path)
    paths = workflow_paths.build_paths(config)
    plan = planning.build_pipeline_plan(config, paths, models.PreflightResult("root"),
        energy_binnings={"uv": EnergyBinning((.9313, 1.1))})
    stages = {s.name: s.argv for s in plan}
    assert "uv:generate:etaprime" not in stages
    assert "uv:generate:eta_pi0" in stages
    assert "0.9313,1.1" in stages["uv:generate:eta_pi0"][-1]
    for stage in ("beam_spectrum", "features", "reconstruct_chi2", "reconstruct_bdt", "extract"):
        cmd = stages[f"uv:{stage}"]
        pos = cmd.index("--energy-edges")
        assert cmd[pos+1:pos+3] == ("0.9313", "1.1")


def test_reconstruction_domain_rejects_extrapolation_and_missing_bdt_contract():
    from reconstruction.runtime.provenance import validate_energy_domain
    metadata = {"selection": {"energy_range_gev": [1.1, 1.5]}, "beam_profile": "uv"}
    with pytest.raises(ValueError, match="cover"):
        validate_energy_domain(metadata, "uv", (.9313, 1.1), requires_bdt=False)
    metadata["selection"]["energy_range_gev"] = [.9313, 1.1]
    validate_energy_domain(metadata, "uv", (.9313, 1.1), requires_bdt=False)
    with pytest.raises(ValueError, match="BDT"):
        validate_energy_domain(metadata, "uv", (.9313, 1.1), requires_bdt=True)
    metadata["bdt_domain"] = {"beam_profile": "uv", "energy_range_gev": [.9313, 1.1]}
    validate_energy_domain(metadata, "uv", (.9313, 1.1), requires_bdt=True)


def test_signal_support_rejects_partial_overlap_and_zero_weight_tails():
    from bdt_training.beam_spectrum import validate_signal_support
    target = BeamSpectrum(np.array([.9313, 1.1, 1.3, 1.5]), np.ones(3))
    with pytest.raises(ValueError, match="signal MC support"):
        validate_signal_support(np.array([1.2, 1.4]), np.ones(2), target)
    with pytest.raises(ValueError, match="signal MC support"):
        validate_signal_support(np.array([1., 1.2, 1.4]), np.array([0., 1., 1.]), target)
    validate_signal_support(np.array([1., 1.2, 1.5]), np.ones(3), target)


def test_unprofiled_default_reconstruction_keeps_nominal_compatibility():
    from reconstruction.runtime.provenance import validate_energy_domain
    metadata = {"selection": {"energy_range_gev": None}, "beam_profile": None, "bdt_domain": None}
    validate_energy_domain(metadata, "uv", (1.1, 1.5), requires_bdt=False, allow_legacy=True)
    validate_energy_domain(metadata, "uv", (1.1, 1.5), requires_bdt=True, allow_legacy=True)
    with pytest.raises(ValueError, match="missing"):
        validate_energy_domain(metadata, "uv", (.9313, 1.1), requires_bdt=False)
