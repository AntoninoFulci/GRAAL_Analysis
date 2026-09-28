from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .model import (
    ArtifactState,
    ArtifactStatus,
    PipelinePlan,
    PlanAction,
    PlanItem,
)
from .registry import STAGES, require_capability, target_closure


class PlanningError(ValueError):
    """Raised when available state cannot produce a complete plan."""


class PolicyDecisionRequired(PlanningError):
    exit_code = 2

    def __init__(self, stage_key: str, state: ArtifactState) -> None:
        self.stage_key = stage_key
        self.state = state
        super().__init__(
            f"stage {stage_key} is {state.value}; choose an explicit non-interactive policy"
        )


@dataclass(frozen=True)
class PlanningPolicies:
    old: str = "ask"
    stale: str = "ask"
    untracked: str = "ask"

    def __post_init__(self) -> None:
        allowed = {
            "old": {"ask", "rebuild", "reuse", "fail"},
            "stale": {"ask", "rebuild", "reuse", "fail"},
            "untracked": {"ask", "adopt", "rebuild", "fail"},
        }
        for field, choices in allowed.items():
            value = getattr(self, field)
            if value not in choices:
                raise ValueError(f"invalid {field} policy: {value}")


def _policy_action(
    stage_key: str,
    status: ArtifactStatus,
    policies: PlanningPolicies,
    *,
    non_interactive: bool,
) -> tuple[PlanAction, tuple[str, ...]]:
    state = status.state
    reasons = status.reasons
    if state is ArtifactState.FRESH:
        return PlanAction.REUSE, reasons
    if state is ArtifactState.MISSING:
        return PlanAction.RUN, reasons or ("required output is missing",)
    if state is ArtifactState.INVALID:
        return PlanAction.REBUILD, reasons or ("artifact validation failed",)

    if state is ArtifactState.OLD:
        policy = policies.old
    elif state is ArtifactState.STALE:
        policy = policies.stale
    elif state is ArtifactState.UNTRACKED:
        policy = policies.untracked
    else:  # pragma: no cover - enum exhaustiveness guard
        raise PlanningError(f"unsupported state for {stage_key}: {state}")

    if policy == "ask":
        if non_interactive:
            raise PolicyDecisionRequired(stage_key, state)
        return PlanAction.BLOCKED, reasons + (f"decision required for {state.value}",)
    if policy == "fail":
        return PlanAction.BLOCKED, reasons + (f"policy refuses {state.value}",)
    if policy == "rebuild":
        return PlanAction.REBUILD, reasons
    if policy == "reuse":
        return PlanAction.REUSE, reasons + (f"reused by {state.value} policy",)
    if policy == "adopt":
        return PlanAction.ADOPT, reasons
    raise PlanningError(f"unsupported policy {policy} for {stage_key}")


def plan_target(
    target: str,
    statuses: Mapping[str, ArtifactStatus],
    *,
    policies: PlanningPolicies | None = None,
    forced: set[str] | frozenset[str] = frozenset(),
    non_interactive: bool = False,
    yes: bool = False,
    enabled_optional_dependencies: frozenset[str] = frozenset(),
    historical_durations: Mapping[str, float] | None = None,
    final_state: str | None = None,
    observable: str | None = None,
) -> PipelinePlan:
    del yes  # confirmation never chooses semantic reuse/rebuild policy
    selected_policies = policies or PlanningPolicies()
    ordered = target_closure(
        target,
        enabled_optional_dependencies=enabled_optional_dependencies,
    )
    unknown_forced = set(forced) - set(ordered)
    if unknown_forced:
        raise PlanningError(
            f"forced stages are outside target closure: {', '.join(sorted(unknown_forced))}"
        )
    missing_statuses = [stage for stage in ordered if stage not in statuses]
    if missing_statuses:
        raise PlanningError(
            f"missing artifact status for: {', '.join(missing_statuses)}"
        )

    items: list[PlanItem] = []
    by_stage: dict[str, PlanItem] = {}
    durations = historical_durations or {}
    for stage_key in ordered:
        status = statuses[stage_key]
        action, reasons = _policy_action(
            stage_key,
            status,
            selected_policies,
            non_interactive=non_interactive,
        )
        if stage_key in forced and action is not PlanAction.RUN:
            action = PlanAction.REBUILD
            reasons = reasons + ("forced by user",)

        stage = STAGES[stage_key]
        dependency_keys = list(stage.dependencies)
        dependency_keys.extend(
            dependency
            for dependency in stage.optional_dependencies
            if dependency in enabled_optional_dependencies
        )
        dependencies = [by_stage[key] for key in dependency_keys]
        blocked = [item.stage_key for item in dependencies if item.action is PlanAction.BLOCKED]
        if blocked:
            action = PlanAction.BLOCKED
            reasons = reasons + (
                f"blocked by dependencies: {', '.join(blocked)}",
            )
        elif any(
            item.action in {PlanAction.RUN, PlanAction.REBUILD}
            for item in dependencies
        ):
            if action in {PlanAction.REUSE, PlanAction.ADOPT}:
                action = PlanAction.REBUILD
                changed = [
                    item.stage_key
                    for item in dependencies
                    if item.action in {PlanAction.RUN, PlanAction.REBUILD}
                ]
                reasons = reasons + (
                    f"dependency will change: {', '.join(changed)}",
                )

        item = PlanItem(
            stage_key=stage_key,
            state=status.state,
            action=action,
            reasons=reasons,
            estimated_seconds=durations.get(stage_key),
        )
        items.append(item)
        by_stage[stage_key] = item

    return PipelinePlan(
        target=target,
        items=tuple(items),
        final_state=final_state,
        observable=observable,
    )


def plan_extraction(
    final_state: str,
    observable: str,
    statuses: Mapping[str, ArtifactStatus],
    **kwargs,
) -> PipelinePlan:
    capability = require_capability(final_state, observable)
    assert capability.production_target is not None
    return plan_target(
        capability.production_target,
        statuses,
        final_state=final_state,
        observable=observable,
        **kwargs,
    )
