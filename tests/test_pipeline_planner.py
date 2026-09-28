from __future__ import annotations

import pytest


def _status(state, *reasons):
    from graal_pipeline.model import ArtifactStatus

    return ArtifactStatus(state, tuple(reasons))


def _fresh_statuses(target: str):
    from graal_pipeline.model import ArtifactState
    from graal_pipeline.registry import target_closure

    return {stage: _status(ArtifactState.FRESH) for stage in target_closure(target)}


def test_fresh_prerequisites_are_reused_and_only_missing_target_runs():
    from graal_pipeline.model import ArtifactState, PlanAction
    from graal_pipeline.planner import plan_target

    statuses = _fresh_statuses("beam_asymmetry_full")
    statuses["beam_asymmetry_full"] = _status(ArtifactState.MISSING)

    plan = plan_target("beam_asymmetry_full", statuses)

    assert plan.items[-1].action is PlanAction.RUN
    assert all(item.action is PlanAction.REUSE for item in plan.items[:-1])
    assert plan.items[-1].reasons == ("required output is missing",)


def test_earliest_missing_stage_rebuilds_fresh_downstream_only():
    from graal_pipeline.model import ArtifactState, PlanAction
    from graal_pipeline.planner import plan_target

    statuses = _fresh_statuses("beam_asymmetry_first_pass")
    statuses["preanalysis"] = _status(ArtifactState.MISSING)

    plan = plan_target("beam_asymmetry_first_pass", statuses)
    actions = {item.stage_key: item.action for item in plan.items}

    assert actions["preanalysis"] is PlanAction.RUN
    assert actions["event_selection"] is PlanAction.REBUILD
    assert actions["flux_calibration"] is PlanAction.REBUILD
    assert actions["mc_generation"] is PlanAction.REUSE
    assert actions["beam_asymmetry_first_pass"] is PlanAction.REBUILD


def test_forced_stage_rebuilds_it_and_its_dependents():
    from graal_pipeline.model import PlanAction
    from graal_pipeline.planner import plan_target

    statuses = _fresh_statuses("beam_asymmetry_first_pass")
    plan = plan_target("beam_asymmetry_first_pass", statuses, forced={"reco_bdt_raw"})
    actions = {item.stage_key: item.action for item in plan.items}

    assert actions["reco_bdt_raw"] is PlanAction.REBUILD
    assert actions["beam_asymmetry_first_pass"] is PlanAction.REBUILD
    assert actions["flux_calibration"] is PlanAction.REUSE


def test_state_policies_emit_all_plan_actions():
    from graal_pipeline.model import ArtifactState, PlanAction
    from graal_pipeline.planner import PlanningPolicies, plan_target

    statuses = _fresh_statuses("beam_asymmetry_full")
    statuses["preanalysis"] = _status(ArtifactState.OLD, "too old")
    statuses["mc_generation"] = _status(ArtifactState.UNTRACKED, "no checkpoint")
    statuses["signal_mc_generation"] = _status(ArtifactState.STALE, "code changed")
    statuses["reco_chi2_raw"] = _status(ArtifactState.INVALID, "bad tree")
    statuses["beam_asymmetry_full"] = _status(ArtifactState.MISSING)
    policies = PlanningPolicies(old="reuse", stale="fail", untracked="adopt")

    plan = plan_target("beam_asymmetry_full", statuses, policies=policies)
    actions = {item.stage_key: item.action for item in plan.items}

    assert actions["preanalysis"] is PlanAction.REUSE
    assert actions["mc_generation"] is PlanAction.ADOPT
    assert actions["signal_mc_generation"] is PlanAction.BLOCKED
    assert actions["reco_chi2_raw"] is PlanAction.REBUILD
    assert actions["beam_asymmetry_full"] is PlanAction.BLOCKED


def test_noninteractive_ask_fails_before_execution_even_with_yes():
    from graal_pipeline.model import ArtifactState
    from graal_pipeline.planner import PolicyDecisionRequired, plan_target

    statuses = _fresh_statuses("beam_asymmetry_first_pass")
    statuses["flux_calibration"] = _status(ArtifactState.OLD, "too old")

    with pytest.raises(PolicyDecisionRequired) as error:
        plan_target(
            "beam_asymmetry_first_pass",
            statuses,
            non_interactive=True,
            yes=True,
        )

    assert error.value.exit_code == 2
    assert error.value.stage_key == "flux_calibration"


def test_invalid_artifact_cannot_be_reused_by_policy():
    from graal_pipeline.model import ArtifactState, PlanAction
    from graal_pipeline.planner import PlanningPolicies, plan_target

    statuses = _fresh_statuses("beam_asymmetry_first_pass")
    statuses["reco_bdt_raw"] = _status(ArtifactState.INVALID, "missing branch")

    plan = plan_target(
        "beam_asymmetry_first_pass",
        statuses,
        policies=PlanningPolicies(old="reuse", stale="reuse", untracked="adopt"),
    )

    item = next(item for item in plan.items if item.stage_key == "reco_bdt_raw")
    assert item.action is PlanAction.REBUILD


def test_disabled_observable_is_rejected_during_planning():
    from graal_pipeline.registry import CapabilityError
    from graal_pipeline.planner import plan_extraction

    with pytest.raises(CapabilityError, match="2pi0.*beam_asymmetry"):
        plan_extraction("2pi0", "beam_asymmetry", {})


def test_optional_grid_search_and_duration_estimates_are_preserved():
    from graal_pipeline.model import ArtifactState
    from graal_pipeline.planner import plan_target
    from graal_pipeline.registry import target_closure

    closure = target_closure(
        "bdt_training", enabled_optional_dependencies=frozenset({"grid_search"})
    )
    statuses = {stage: _status(ArtifactState.FRESH) for stage in closure}

    plan = plan_target(
        "bdt_training",
        statuses,
        enabled_optional_dependencies=frozenset({"grid_search"}),
        historical_durations={"grid_search": 123.5},
    )

    grid = next(item for item in plan.items if item.stage_key == "grid_search")
    assert grid.estimated_seconds == 123.5
