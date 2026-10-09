"""Stable artifact reuse requires both identity and a validated payload."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts import artifact_manifest as pipeline_cache
import numpy as np
import uproot


def test_cache_reuses_only_matching_complete_output_within_ten_days(tmp_path):
    output = tmp_path / "artifact.root"
    output.write_bytes(b"valid")
    manifest = tmp_path / "artifact.manifest.json"
    now = datetime(2026, 10, 7, tzinfo=timezone.utc)
    item = pipeline_cache.CacheItem("mc:uv:eta_pi0", manifest, (output,), {"events": 10})
    valid = lambda: None

    assert pipeline_cache.cache_status(item, valid, now)[0] is False
    pipeline_cache.record_cache(item, valid, now)
    assert pipeline_cache.cache_status(item, valid, now + timedelta(days=10)) == (True, "valid")
    assert pipeline_cache.cache_status(item, valid, now + timedelta(days=10, microseconds=1))[0] is False
    changed = pipeline_cache.CacheItem(item.name, manifest, (output,), {"events": 11})
    assert pipeline_cache.cache_status(changed, valid, now)[0] is False
    output.write_bytes(b"changed")
    assert pipeline_cache.cache_status(item, valid, now)[0] is False


def test_cache_requires_valid_payload_and_source_fingerprint(tmp_path):
    source = tmp_path / "stage.py"
    source.write_text("v1")
    output = tmp_path / "artifact.root"
    output.write_bytes(b"valid")
    item = pipeline_cache.CacheItem("selected:uv", tmp_path / "manifest.json", (output,), {"source": pipeline_cache.source_fingerprint((source,))})
    now = datetime.now(timezone.utc)
    pipeline_cache.record_cache(item, lambda: None, now)
    assert pipeline_cache.cache_status(item, lambda: (_ for _ in ()).throw(ValueError("invalid")), now)[0] is False
    source.write_text("v2")
    changed = pipeline_cache.CacheItem(item.name, item.manifest, item.outputs, {"source": pipeline_cache.source_fingerprint((source,))})
    assert pipeline_cache.cache_status(changed, lambda: None, now)[0] is False


def test_missing_or_malformed_manifest_never_authorizes_reuse(tmp_path):
    output = tmp_path / "artifact.root"
    output.write_bytes(b"valid")
    item = pipeline_cache.CacheItem("x", tmp_path / "manifest.json", (output,), {})
    assert pipeline_cache.cache_status(item, lambda: None)[0] is False
    item.manifest.write_text("{")
    assert pipeline_cache.cache_status(item, lambda: None)[0] is False
    for malformed in ("[]", "null", '"text"'):
        item.manifest.write_text(malformed)
        assert pipeline_cache.cache_status(item, lambda: None)[0] is False


def test_cache_signature_preserves_command_argument_sequences(tmp_path):
    output = tmp_path / "artifact"
    output.write_bytes(b"valid")
    item = pipeline_cache.CacheItem("x", tmp_path / "manifest.json", (output,), {"argv": ("tool", "--flag")})
    pipeline_cache.record_cache(item, lambda: None)
    assert pipeline_cache.cache_status(item, lambda: None) == (True, "valid")


def test_background_mc_contract_uses_branches_generators_write(tmp_path):
    path = tmp_path / "pi0pi0_mc.root"
    with uproot.recreate(path) as output:
        output["mc"] = {name: np.array([1]) for name in ("beam", "proton", "n_true_gamma", "g0")}
    pipeline_cache.validate_mc(path, "pi0pi0")


def test_background_mc_requires_all_photon_branches_declared_by_tree(tmp_path):
    path = tmp_path / "pi0pi0_mc.root"
    with uproot.recreate(path) as output:
        output["mc"] = {"beam": np.array([1]), "proton": np.array([1]),
                        "n_true_gamma": np.array([2]), "g0": np.array([1])}
    import pytest
    with pytest.raises(ValueError, match="g1"):
        pipeline_cache.validate_mc(path, "pi0pi0")


def test_bdt_beam_spectrum_rejects_zero_normalization(tmp_path):
    path = tmp_path / "beam_spectrum.npz"
    np.savez(path, edges=np.array([1.1, 1.5]), density=np.array([0.0]))
    import pytest
    with pytest.raises(ValueError, match="normal"):
        pipeline_cache.validate_beam_spectrum(path, "uv")


def test_bdt_reports_require_decodable_plots_and_metrics_schema(tmp_path):
    from PIL import Image
    import pytest

    tmp_path.joinpath("stage1_metrics.txt").write_text(
        "Signal: eta_pi0\nHypothesis: eta_pi0\nAUC: 0.8\nThreshold: 0.3\n"
        "Precision: 0.8\nRecall: 0.7\nF1: 0.75\nN_train: 10\nN_val: 5\n"
    )
    for stem in ("stage1_roc", "stage1_feature_importance", "stage1_score_dist"):
        Image.new("RGB", (2, 2)).save(tmp_path / f"{stem}.png")
    pipeline_cache.validate_training_reports(tmp_path, 0.3, "eta_pi0", "eta_pi0")
    (tmp_path / "stage1_roc.png").write_bytes(b"not a PNG")
    with pytest.raises(ValueError, match="training plot"):
        pipeline_cache.validate_training_reports(tmp_path, 0.3, "eta_pi0", "eta_pi0")


def test_malformed_bdt_model_is_rejected(tmp_path):
    import pytest

    model = tmp_path / "bdt_stage1.json"
    model.write_text("{not xgboost}")
    with pytest.raises(ValueError, match="invalid BDT model"):
        pipeline_cache.validate_bdt_model(model, 10)
