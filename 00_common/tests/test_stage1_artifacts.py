"""Contract tests for the stage-1 runtime artifact bundle."""

import subprocess
import sys

import pytest

from graal_common.stage1.artifacts import (
    METRICS_FILE,
    MODEL_FILE,
    PROVENANCE_FILE,
    THRESHOLD_FILE,
    Stage1ArtifactPaths,
    Stage1Provenance,
)


PROVENANCE_JSON = """{
  "signal_channel": "eta_pi0",
  "hypothesis": "eta_pi0",
  "signal_prior": 0.5,
  "beam_reweighted": true,
  "phase_space_sampling": "accept-reject-unweighted",
  "tagger_resolution_fwhm_gev": 0.016,
  "tagger_resolution_sigma_gev": 0.006794574402304153,
  "detector_covariance_status": "legacy-uncalibrated",
  "feature_names": [
    "mass",
    "energy"
  ]
}
"""


def test_artifact_paths_preserve_runtime_filenames(tmp_path):
    paths = Stage1ArtifactPaths.from_directory(tmp_path)

    assert MODEL_FILE == "bdt_stage1.json"
    assert THRESHOLD_FILE == "stage1_threshold.txt"
    assert PROVENANCE_FILE == "stage1_provenance.json"
    assert METRICS_FILE == "stage1_metrics.txt"
    assert paths.model == tmp_path / "bdt_stage1.json"
    assert paths.threshold == tmp_path / "stage1_threshold.txt"
    assert paths.provenance == tmp_path / "stage1_provenance.json"
    assert paths.metrics == tmp_path / "stage1_metrics.txt"


def test_provenance_serialization_preserves_exact_json_bytes():
    provenance = Stage1Provenance(
        signal_channel="eta_pi0",
        hypothesis="eta_pi0",
        signal_prior=0.5,
        beam_reweighted=True,
        phase_space_sampling="accept-reject-unweighted",
        tagger_resolution_fwhm_gev=0.016,
        tagger_resolution_sigma_gev=0.006794574402304153,
        detector_covariance_status="legacy-uncalibrated",
        feature_names=("mass", "energy"),
    )

    assert provenance.to_json() == PROVENANCE_JSON


def test_provenance_parser_round_trips_all_values():
    provenance = Stage1Provenance.from_json(PROVENANCE_JSON)

    assert provenance.signal_channel == "eta_pi0"
    assert provenance.hypothesis == "eta_pi0"
    assert provenance.signal_prior == 0.5
    assert provenance.beam_reweighted is True
    assert provenance.phase_space_sampling == "accept-reject-unweighted"
    assert provenance.tagger_resolution_fwhm_gev == 0.016
    assert provenance.tagger_resolution_sigma_gev == 0.006794574402304153
    assert provenance.detector_covariance_status == "legacy-uncalibrated"
    assert provenance.feature_names == ("mass", "energy")
    assert provenance.to_json() == PROVENANCE_JSON


@pytest.mark.parametrize(
    ("fragment", "message"),
    [
        ('  "hypothesis": "eta_pi0",\n', "missing keys: hypothesis"),
        ('  "unexpected": 1,\n', "unexpected keys: unexpected"),
        ('  "signal_prior": "0.5",\n', "signal_prior must be a number or null"),
        ('  "beam_reweighted": 1,\n', "beam_reweighted must be a boolean or null"),
        ('  "feature_names": "mass",\n', "feature_names must be an array of strings"),
    ],
)
def test_provenance_parser_rejects_schema_drift(fragment, message):
    if fragment.startswith('  "hypothesis"'):
        malformed = PROVENANCE_JSON.replace(fragment, "")
    elif fragment.startswith('  "unexpected"'):
        malformed = PROVENANCE_JSON.replace("{\n", "{\n" + fragment)
    elif fragment.startswith('  "signal_prior"'):
        malformed = PROVENANCE_JSON.replace('  "signal_prior": 0.5,\n', fragment)
    elif fragment.startswith('  "beam_reweighted"'):
        malformed = PROVENANCE_JSON.replace('  "beam_reweighted": true,\n', fragment)
    else:
        start = '  "feature_names": [\n'
        end = '  ]\n'
        before, remainder = PROVENANCE_JSON.split(start, 1)
        _, after = remainder.split(end, 1)
        malformed = before + fragment.rstrip(",\n") + "\n" + after

    with pytest.raises(ValueError, match=message):
        Stage1Provenance.from_json(malformed)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_provenance_parser_rejects_non_finite_numbers(value):
    malformed = PROVENANCE_JSON.replace("0.016", value, 1)

    with pytest.raises(ValueError, match="tagger_resolution_fwhm_gev must be finite"):
        Stage1Provenance.from_json(malformed)


def test_importing_artifact_contract_does_not_import_numeric_or_model_packages():
    script = """
import sys
import graal_common.stage1.artifacts

loaded = sorted(
    name for name in sys.modules
    if name == "numpy" or name.startswith("xgboost")
)
if loaded:
    raise SystemExit(f"unexpected dependencies loaded: {loaded}")
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
