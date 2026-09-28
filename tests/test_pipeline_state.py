from __future__ import annotations

from datetime import datetime, timedelta, timezone


NOW = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)


def _validation(valid: bool = True, *reasons: str):
    from graal_pipeline.model import ValidationResult

    return ValidationResult(valid=valid, validator="test", reasons=tuple(reasons))


def _checkpoint(**changes):
    from graal_pipeline.state import make_checkpoint

    values = {
        "stage": "example",
        "completed_at": NOW - timedelta(days=1),
        "inputs": {"raw": {"size": 3}},
        "outputs": {"product": {"size": 5}},
        "configuration": {"mode": "standard"},
        "code": {"git_commit": "abc", "dirty": False, "files": {}},
        "run_id": "run-1",
    }
    values.update(changes)
    return make_checkpoint(**values)


def _classify(*, checkpoint=None, exists=True, validation=None, max_age_days=30, **changes):
    from graal_pipeline.state import classify_artifact

    values = {
        "exists": exists,
        "validation": validation or _validation(),
        "checkpoint": checkpoint,
        "current_inputs": {"raw": {"size": 3}},
        "current_outputs": {"product": {"size": 5}},
        "current_configuration": {"mode": "standard"},
        "current_code": {"git_commit": "abc", "dirty": False, "files": {}},
        "max_age_days": max_age_days,
        "now": NOW,
    }
    values.update(changes)
    return classify_artifact(**values)


def test_missing_and_invalid_outputs_are_never_reused():
    from graal_pipeline.model import ArtifactState

    missing = _classify(exists=False)
    invalid = _classify(validation=_validation(False, "ROOT file is corrupt"))

    assert missing.state is ArtifactState.MISSING
    assert missing.reasons == ("required output is missing",)
    assert invalid.state is ArtifactState.INVALID
    assert invalid.reasons == ("ROOT file is corrupt",)


def test_valid_output_without_checkpoint_is_untracked_after_crash_window():
    from graal_pipeline.model import ArtifactState

    status = _classify(checkpoint=None)

    assert status.state is ArtifactState.UNTRACKED
    assert status.reasons == ("valid output has no compatible checkpoint",)


def test_matching_checkpoint_is_fresh():
    from graal_pipeline.model import ArtifactState

    status = _classify(checkpoint=_checkpoint())

    assert status.state is ArtifactState.FRESH
    assert status.reasons == ()


def test_semantic_change_is_stale_even_when_checkpoint_is_new():
    from graal_pipeline.model import ArtifactState

    status = _classify(
        checkpoint=_checkpoint(completed_at=NOW - timedelta(minutes=1)),
        current_inputs={"raw": {"size": 4}},
    )

    assert status.state is ArtifactState.STALE
    assert status.reasons == ("inputs.raw.size: expected 3, found 4",)


def test_age_is_measured_from_completion_and_disabled_for_sources():
    from graal_pipeline.model import ArtifactState

    checkpoint = _checkpoint(completed_at=NOW - timedelta(days=31))

    old = _classify(checkpoint=checkpoint, max_age_days=30)
    source = _classify(checkpoint=checkpoint, max_age_days=None)

    assert old.state is ArtifactState.OLD
    assert old.age_days == 31
    assert old.reasons == ("checkpoint is 31.0 days old (limit 30 days)",)
    assert source.state is ArtifactState.FRESH


def test_unknown_checkpoint_schema_is_stale():
    from graal_pipeline.model import ArtifactState

    checkpoint = _checkpoint()
    checkpoint["schema_version"] = 99

    status = _classify(checkpoint=checkpoint)

    assert status.state is ArtifactState.STALE
    assert status.reasons == ("checkpoint schema 99 is unsupported (expected 1)",)


def test_uncertain_legacy_adoption_never_claims_fresh():
    from graal_pipeline.model import ArtifactState
    from graal_pipeline.state import adopt_artifact_checkpoint

    uncertain = adopt_artifact_checkpoint(
        _checkpoint(), provenance_confident=False
    )
    confident = adopt_artifact_checkpoint(_checkpoint(), provenance_confident=True)

    uncertain_status = _classify(checkpoint=uncertain)
    confident_status = _classify(checkpoint=confident)

    assert uncertain_status.state is ArtifactState.STALE
    assert uncertain_status.reasons == ("legacy configuration provenance is uncertain",)
    assert confident_status.state is ArtifactState.FRESH
    assert confident["provenance"] == "adopted_legacy_output"


def test_checkpoint_store_uses_scope_and_atomic_json(tmp_path):
    from graal_pipeline.model import CheckpointScope
    from graal_pipeline.state import CheckpointStore

    store = CheckpointStore(tmp_path)
    shared = store.path_for("preanalysis", CheckpointScope.SHARED)
    final_state = store.path_for(
        "reco_bdt_fit", CheckpointScope.FINAL_STATE, final_state="eta_pi0"
    )
    observable = store.path_for(
        "beam_asymmetry_full",
        CheckpointScope.OBSERVABLE,
        final_state="eta_pi0",
        observable="beam_asymmetry",
    )

    assert shared == tmp_path / "checkpoints/shared/preanalysis.json"
    assert final_state == tmp_path / "checkpoints/eta_pi0/reco_bdt_fit.json"
    assert observable == (
        tmp_path
        / "checkpoints/eta_pi0/beam_asymmetry/beam_asymmetry_full.json"
    )

    checkpoint = _checkpoint()
    store.write(observable, checkpoint)

    assert store.read(observable) == checkpoint
    assert list(observable.parent.glob("*.tmp")) == []
