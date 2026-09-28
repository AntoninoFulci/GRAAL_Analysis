from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest


def test_eta_pi0_exposes_reconstruction_and_beam_asymmetry():
    from graal_pipeline.registry import FINAL_STATES, capability

    final_state = FINAL_STATES["eta_pi0"]
    beam = capability("eta_pi0", "beam_asymmetry")

    assert final_state.enabled is True
    assert final_state.hypothesis == "eta_pi0"
    assert final_state.reconstruction_target == "reco_bdt_fit"
    assert beam.enabled is True
    assert beam.production_target == "beam_asymmetry_full"
    assert beam.first_pass_target == "beam_asymmetry_first_pass"


def test_cross_section_is_visible_but_disabled_for_eta_pi0():
    from graal_pipeline.registry import OBSERVABLES, capability

    observable = OBSERVABLES["cross_section"]
    entry = capability("eta_pi0", "cross_section")

    assert observable.label == "Sezione d'urto"
    assert entry.enabled is False
    assert "non ancora implementata" in entry.disabled_reason


def test_2pi0_observables_are_visible_but_disabled():
    from graal_pipeline.registry import FINAL_STATES, capability

    assert FINAL_STATES["2pi0"].reconstruction_target == "reco_2pi0"
    beam = capability("2pi0", "beam_asymmetry")
    cross_section = capability("2pi0", "cross_section")

    assert beam.enabled is False
    assert "2pi0" in beam.disabled_reason
    assert cross_section.enabled is False


def test_registry_descriptions_are_shared_user_facing_text():
    from graal_pipeline.registry import FINAL_STATES, OBSERVABLES

    assert FINAL_STATES["eta_pi0"].description == (
        "Ricostruisce lo stato finale eta pi0 con selezione chi2 e BDT."
    )
    assert OBSERVABLES["beam_asymmetry"].description == (
        "Estrae Sigma da campioni polarizzati, flusso e sideband."
    )


def test_unsupported_selection_is_rejected_before_execution():
    from graal_pipeline.registry import CapabilityError, require_capability

    with pytest.raises(CapabilityError, match="2pi0.*beam_asymmetry"):
        require_capability("2pi0", "beam_asymmetry")
    with pytest.raises(CapabilityError, match="unknown final state"):
        require_capability("omega_pi0", "beam_asymmetry")
    with pytest.raises(CapabilityError, match="unknown observable"):
        require_capability("eta_pi0", "polarization_transfer")


def test_registry_specs_are_immutable():
    from graal_pipeline.registry import FINAL_STATES

    with pytest.raises(FrozenInstanceError):
        FINAL_STATES["eta_pi0"].label = "changed"  # type: ignore[misc]


def test_stage_and_artifact_specs_have_frozen_defaults():
    from graal_pipeline.model import ArtifactSpec, CheckpointScope, StageSpec

    artifact = ArtifactSpec("selected", "Selected data", "selected_dir", "directory")
    stage = StageSpec(
        key="event_selection",
        description="Select events",
        outputs=(artifact,),
        scope=CheckpointScope.SHARED,
    )

    assert stage.dependencies == ()
    assert stage.outputs == (artifact,)
    with pytest.raises(FrozenInstanceError):
        stage.key = "changed"  # type: ignore[misc]
