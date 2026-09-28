from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
from typing import Any

from graal_common.io.filesystem import atomic_output_directory

from .model import (
    PipelinePlan,
    PlanAction,
    StageInvocation,
    ValidationResult,
)
from .registry import STAGES
from .state import (
    CheckpointStore,
    fingerprint_path,
    make_checkpoint,
    responsible_code_fingerprint,
)


@dataclass(frozen=True)
class StageRunResult:
    stage_key: str
    status: str
    exit_code: int
    log_path: Path | None
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class RunSummary:
    run_id: str
    results: tuple[StageRunResult, ...]
    exit_code: int


class RunLockedError(RuntimeError):
    def __init__(self, owner: Mapping[str, Any], *, stale: bool) -> None:
        self.owner = dict(owner)
        self.stale = stale
        state = "stale" if stale else "live or unverified"
        super().__init__(f"state directory lock is {state}: {self.owner}")


class RunLock:
    def __init__(self, state_directory: str | Path, *, run_id: str) -> None:
        self.path = Path(state_directory) / "run.lock"
        self.run_id = run_id
        self.host = socket.gethostname()
        self.acquired = False

    def _owner(self) -> dict[str, Any]:
        owner_path = self.path / "owner.json"
        if not owner_path.is_file():
            return {"pid": None, "run_id": "unknown", "host": "unknown"}
        try:
            value = json.loads(owner_path.read_text())
            return value if isinstance(value, dict) else {"raw": value}
        except (OSError, json.JSONDecodeError) as exc:
            return {"error": str(exc), "run_id": "unknown"}

    def _is_stale(self, owner: Mapping[str, Any]) -> bool:
        if owner.get("host") != self.host:
            return False
        pid = owner.get("pid")
        if not isinstance(pid, int) or pid <= 0:
            return True
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            return False
        return False

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.path.mkdir()
        except FileExistsError:
            owner = self._owner()
            raise RunLockedError(owner, stale=self._is_stale(owner)) from None
        owner = {
            "pid": os.getpid(),
            "run_id": self.run_id,
            "host": self.host,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            (self.path / "owner.json").write_text(
                json.dumps(owner, sort_keys=True, indent=2) + "\n"
            )
        except BaseException:
            shutil.rmtree(self.path, ignore_errors=True)
            raise
        self.acquired = True

    def release(self) -> None:
        if not self.acquired:
            return
        owner = self._owner()
        if owner.get("run_id") == self.run_id and owner.get("pid") == os.getpid():
            shutil.rmtree(self.path)
        self.acquired = False


Executor = Callable[[tuple[str, ...], Path, Path], int]
Validator = Callable[[str, StageInvocation], ValidationResult]
FailureHandler = Callable[[str, int, Path], str]


def _default_executor(command: tuple[str, ...], cwd: Path, log_path: Path) -> int:
    cwd.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as stream:
        stream.write("COMMAND: " + " ".join(command) + "\n")
        stream.flush()
        completed = subprocess.run(
            command,
            cwd=cwd,
            stdout=stream,
            stderr=subprocess.STDOUT,
            check=False,
        )
    return completed.returncode


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    CheckpointStore(path.parent).write(path, value)


def _plan_payload(plan: PipelinePlan) -> dict[str, Any]:
    return {
        "target": plan.target,
        "final_state": plan.final_state,
        "observable": plan.observable,
        "items": [
            {
                "stage": item.stage_key,
                "state": item.state.value,
                "action": item.action.value,
                "reasons": list(item.reasons),
                "estimated_seconds": item.estimated_seconds,
            }
            for item in plan.items
        ],
    }


def _stage_for_staging(
    invocation: StageInvocation,
) -> tuple[StageInvocation, Path]:
    canonical = invocation.output_argument
    canonical.parent.mkdir(parents=True, exist_ok=True)
    work_root = Path(
        tempfile.mkdtemp(
            prefix=f".{canonical.name}.pipeline-",
            dir=canonical.parent,
        )
    )
    staged_argument = (
        work_root / canonical.name
        if invocation.output_kind == "file"
        else work_root / "output"
    )
    if invocation.output_kind == "directory" and canonical.is_dir():
        shutil.copytree(canonical, staged_argument)

    def rewrite(value: str) -> str:
        return value.replace(str(canonical), str(staged_argument))

    staged_outputs: list[Path] = []
    for output in invocation.outputs:
        if output == canonical:
            staged_outputs.append(staged_argument)
        else:
            try:
                relative = output.relative_to(canonical)
            except ValueError:
                staged_outputs.append(output)
            else:
                staged_outputs.append(staged_argument / relative)
    staged = replace(
        invocation,
        commands=tuple(tuple(rewrite(argument) for argument in command) for command in invocation.commands),
        working_directory=(
            staged_argument
            if invocation.working_directory == canonical
            else invocation.working_directory
        ),
        outputs=tuple(staged_outputs),
        output_argument=staged_argument,
    )
    return staged, work_root


def _publish(staged: StageInvocation, canonical: StageInvocation) -> None:
    destination = canonical.output_argument
    source = staged.output_argument
    if canonical.output_kind == "file":
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, destination)
        return
    with atomic_output_directory(destination) as publication:
        if source.is_dir():
            shutil.copytree(source, publication, dirs_exist_ok=True)


def _checkpoint_stage(
    store: CheckpointStore,
    plan: PipelinePlan,
    invocation: StageInvocation,
    validation: ValidationResult,
    *,
    run_id: str,
    configuration: Mapping[str, Any],
    provenance: str = "produced",
    provenance_confident: bool = True,
) -> None:
    inputs = {str(path): fingerprint_path(path) for path in invocation.inputs}
    outputs = {str(path): fingerprint_path(path) for path in invocation.outputs}
    repository = Path.cwd()
    code = responsible_code_fingerprint(invocation.responsible_paths, repository)
    checkpoint = make_checkpoint(
        stage=invocation.stage_key,
        completed_at=datetime.now(timezone.utc),
        inputs=inputs,
        outputs=outputs,
        configuration=configuration,
        code=code,
        run_id=run_id,
        final_state=plan.final_state,
        observable=plan.observable,
        provenance=provenance,
        provenance_confident=provenance_confident,
        command=invocation.commands[-1],
        working_directory=str(invocation.working_directory),
        validator=validation.validator,
        verification=validation.level,
    )
    path = store.path_for(
        invocation.stage_key,
        invocation.scope,
        final_state=plan.final_state or "eta_pi0",
        observable=plan.observable or "beam_asymmetry",
    )
    store.write(path, checkpoint)


def run_plan(
    plan: PipelinePlan,
    invocations: Mapping[str, StageInvocation],
    *,
    state_directory: str | Path,
    executor: Executor = _default_executor,
    validator: Validator,
    on_failure: FailureHandler | None = None,
    max_retries: int = 0,
    keep_failed_work: bool = False,
    run_id: str | None = None,
    after_publish: Callable[[str, tuple[Path, ...]], None] | None = None,
    configuration: Mapping[str, Any] | None = None,
) -> RunSummary:
    selected_run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    state_root = Path(state_directory)
    run_root = state_root / "runs" / selected_run_id
    log_root = state_root / "logs" / selected_run_id
    run_root.mkdir(parents=True, exist_ok=True)
    log_root.mkdir(parents=True, exist_ok=True)
    _write_json(run_root / "plan.json", _plan_payload(plan))
    lock = RunLock(state_root, run_id=selected_run_id)
    lock.acquire()
    store = CheckpointStore(state_root)
    results: list[StageRunResult] = []
    by_stage: dict[str, StageRunResult] = {}
    aborted = False
    handler = on_failure or (lambda *_: "continue")
    effective_configuration = configuration or {}
    try:
        for item in plan.items:
            invocation = invocations[item.stage_key]
            log_path = log_root / f"{item.stage_key}.log"
            if aborted:
                result = StageRunResult(item.stage_key, "SKIPPED", 1, log_path, ("run aborted",))
            elif item.action is PlanAction.BLOCKED:
                result = StageRunResult(item.stage_key, "BLOCKED", 1, log_path, item.reasons)
            elif item.action is PlanAction.REUSE:
                result = StageRunResult(item.stage_key, "REUSED", 0, None, item.reasons)
            elif item.action is PlanAction.ADOPT:
                validation = validator(item.stage_key, invocation)
                if validation.valid:
                    _checkpoint_stage(
                        store,
                        plan,
                        invocation,
                        validation,
                        run_id=selected_run_id,
                        configuration=effective_configuration,
                        provenance="adopted_legacy_output",
                        provenance_confident=False,
                    )
                    result = StageRunResult(item.stage_key, "ADOPTED", 0, None, item.reasons)
                else:
                    result = StageRunResult(item.stage_key, "FAILED", 98, None, validation.reasons)
            else:
                dependencies = [
                    by_stage[key]
                    for key in STAGES[item.stage_key].dependencies
                    if key in by_stage
                ]
                failed_dependencies = [
                    dependency.stage_key
                    for dependency in dependencies
                    if dependency.status in {"FAILED", "BLOCKED", "SKIPPED"}
                ]
                if failed_dependencies:
                    result = StageRunResult(
                        item.stage_key,
                        "BLOCKED",
                        1,
                        log_path,
                        (f"blocked by dependencies: {', '.join(failed_dependencies)}",),
                    )
                else:
                    attempt = 0
                    result = StageRunResult(item.stage_key, "FAILED", 1, log_path)
                    while True:
                        staged, work_root = _stage_for_staging(invocation)
                        validation = ValidationResult(False, invocation.validator, ("not executed",))
                        try:
                            staged.working_directory.mkdir(parents=True, exist_ok=True)
                            exit_code = 0
                            for command in staged.commands:
                                exit_code = executor(command, staged.working_directory, log_path)
                                if exit_code != 0:
                                    break
                            if exit_code == 0:
                                validation = validator(item.stage_key, staged)
                                if not validation.valid:
                                    exit_code = 98
                            if exit_code == 0:
                                _publish(staged, invocation)
                                if after_publish is not None:
                                    after_publish(item.stage_key, invocation.outputs)
                                _checkpoint_stage(
                                    store,
                                    plan,
                                    invocation,
                                    validation,
                                    run_id=selected_run_id,
                                    configuration=effective_configuration,
                                )
                                result = StageRunResult(item.stage_key, "PASSED", 0, log_path)
                                break
                            reasons = validation.reasons if validation.reasons != ("not executed",) else (f"command exited {exit_code}",)
                            choice = handler(item.stage_key, exit_code, log_path)
                            if choice == "retry" and attempt < max_retries:
                                attempt += 1
                                continue
                            result = StageRunResult(item.stage_key, "FAILED", exit_code, log_path, reasons)
                            if choice == "abort":
                                aborted = True
                            break
                        finally:
                            if not keep_failed_work or result.status == "PASSED":
                                shutil.rmtree(work_root, ignore_errors=True)
            results.append(result)
            by_stage[item.stage_key] = result

        exit_code = int(any(result.status in {"FAILED", "BLOCKED", "SKIPPED"} for result in results))
        summary = RunSummary(selected_run_id, tuple(results), exit_code)
        payload = {
            "run_id": selected_run_id,
            "exit_code": exit_code,
            "results": [
                {
                    **asdict(result),
                    "log_path": str(result.log_path) if result.log_path else None,
                }
                for result in results
            ],
        }
        _write_json(run_root / "summary.json", payload)
        _write_json(state_root / "latest.json", payload)
        return summary
    finally:
        lock.release()
