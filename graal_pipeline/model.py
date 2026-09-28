from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CheckpointScope(str, Enum):
    SHARED = "shared"
    FINAL_STATE = "final_state"
    OBSERVABLE = "observable"


class ArtifactState(str, Enum):
    FRESH = "FRESH"
    OLD = "OLD"
    UNTRACKED = "UNTRACKED"
    STALE = "STALE"
    MISSING = "MISSING"
    INVALID = "INVALID"


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    validator: str
    reasons: tuple[str, ...] = ()
    level: str = "fast"


@dataclass(frozen=True)
class ArtifactStatus:
    state: ArtifactState
    reasons: tuple[str, ...] = ()
    age_days: float | None = None


@dataclass(frozen=True)
class ArtifactSpec:
    key: str
    description: str
    path_key: str
    kind: str = "file"
    required: bool = True


@dataclass(frozen=True)
class StageSpec:
    key: str
    description: str
    dependencies: tuple[str, ...] = ()
    optional_dependencies: tuple[str, ...] = ()
    inputs: tuple[ArtifactSpec, ...] = ()
    outputs: tuple[ArtifactSpec, ...] = ()
    command_builder: Callable[[Any], tuple[str, ...]] | None = field(
        default=None, compare=False, repr=False
    )
    validator: str | None = None
    responsible_paths: tuple[str, ...] = ()
    max_age_days: int | None = 30
    scope: CheckpointScope = CheckpointScope.SHARED
    final_states: frozenset[str] = frozenset()
    observables: frozenset[str] = frozenset()


@dataclass(frozen=True)
class FinalStateSpec:
    key: str
    label: str
    description: str
    hypothesis: str
    model_dir: str | None
    reconstruction_target: str
    enabled: bool = True
    disabled_reason: str | None = None


@dataclass(frozen=True)
class ObservableSpec:
    key: str
    label: str
    description: str
    enabled: bool
    disabled_reason: str | None = None


@dataclass(frozen=True)
class ObservableCapability:
    final_state: str
    observable: str
    enabled: bool
    disabled_reason: str | None
    production_target: str | None = None
    first_pass_target: str | None = None
    validation_target: str | None = None
