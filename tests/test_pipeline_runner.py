from __future__ import annotations

from pathlib import Path
import json
import os

import pytest


def _item(stage_key, action):
    from graal_pipeline.model import ArtifactState, PlanItem

    return PlanItem(stage_key, ArtifactState.MISSING, action)


def _plan(*items):
    from graal_pipeline.model import PipelinePlan

    return PipelinePlan("test-target", tuple(items), final_state="eta_pi0")


def _invocation(stage_key: str, output: Path, *, kind: str = "file"):
    from graal_pipeline.model import CheckpointScope, StageInvocation

    return StageInvocation(
        stage_key=stage_key,
        commands=(("fake", stage_key, str(output)),),
        working_directory=output.parent,
        inputs=(),
        outputs=(output,),
        output_argument=output,
        output_kind=kind,
        scope=CheckpointScope.FINAL_STATE,
        validator="test",
        responsible_paths=(),
    )


def _validator(_stage_key, invocation):
    from graal_pipeline.model import ValidationResult

    missing = [str(path) for path in invocation.outputs if not path.exists()]
    return ValidationResult(not missing, "test", tuple(f"missing {path}" for path in missing))


class FakeExecutor:
    def __init__(self, failures=()):
        self.failures = list(failures)
        self.calls: list[str] = []

    def __call__(self, command, cwd, log_path):
        stage = command[1]
        self.calls.append(stage)
        with Path(log_path).open("a") as stream:
            stream.write(f"executed {stage}\n")
        if self.failures and self.failures[0] == stage:
            self.failures.pop(0)
            return 42
        output = Path(command[2])
        if output.suffix:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(f"new {stage}\n")
        else:
            output.mkdir(parents=True, exist_ok=True)
            (output / "product.txt").write_text(f"new {stage}\n")
        return 0


def test_failed_stage_blocks_dependents_but_independent_branch_continues(tmp_path):
    from graal_pipeline.model import PlanAction
    from graal_pipeline.runner import run_plan

    invocations = {
        "preanalysis": _invocation("preanalysis", tmp_path / "pre.root"),
        "event_selection": _invocation("event_selection", tmp_path / "selected.root"),
        "signal_mc_generation": _invocation("signal_mc_generation", tmp_path / "mc.root"),
    }
    plan = _plan(
        _item("preanalysis", PlanAction.RUN),
        _item("event_selection", PlanAction.RUN),
        _item("signal_mc_generation", PlanAction.RUN),
    )
    executor = FakeExecutor(failures=("preanalysis",))

    summary = run_plan(
        plan,
        invocations,
        state_directory=tmp_path / "state",
        executor=executor,
        validator=_validator,
        on_failure=lambda *_: "continue",
    )

    statuses = {result.stage_key: result.status for result in summary.results}
    assert statuses == {
        "preanalysis": "FAILED",
        "event_selection": "BLOCKED",
        "signal_mc_generation": "PASSED",
    }
    assert executor.calls == ["preanalysis", "signal_mc_generation"]
    assert summary.exit_code == 1


def test_retry_and_abort_choices_are_honored(tmp_path):
    from graal_pipeline.model import PlanAction
    from graal_pipeline.runner import run_plan

    output = tmp_path / "product.root"
    plan = _plan(_item("signal_mc_generation", PlanAction.RUN))
    invocation = _invocation("signal_mc_generation", output)
    executor = FakeExecutor(failures=("signal_mc_generation",))

    retried = run_plan(
        plan,
        {"signal_mc_generation": invocation},
        state_directory=tmp_path / "retry-state",
        executor=executor,
        validator=_validator,
        on_failure=lambda *_: "retry",
        max_retries=1,
    )

    assert retried.results[0].status == "PASSED"
    assert executor.calls == ["signal_mc_generation", "signal_mc_generation"]

    abort_plan = _plan(
        _item("preanalysis", PlanAction.RUN),
        _item("signal_mc_generation", PlanAction.RUN),
    )
    aborted = run_plan(
        abort_plan,
        {
            "preanalysis": _invocation("preanalysis", tmp_path / "abort-pre.root"),
            "signal_mc_generation": _invocation("signal_mc_generation", tmp_path / "abort-mc.root"),
        },
        state_directory=tmp_path / "abort-state",
        executor=FakeExecutor(failures=("preanalysis",)),
        validator=_validator,
        on_failure=lambda *_: "abort",
    )
    assert [result.status for result in aborted.results] == ["FAILED", "SKIPPED"]


@pytest.mark.parametrize(("pid", "stale"), [(os.getpid(), False), (99999999, True)])
def test_live_and_stale_locks_refuse_mutation_without_deletion(tmp_path, pid, stale):
    from graal_pipeline.runner import RunLock, RunLockedError

    lock = RunLock(tmp_path, run_id="new-run")
    lock.path.mkdir(parents=True)
    owner = {"pid": pid, "run_id": "existing-run", "host": lock.host}
    (lock.path / "owner.json").write_text(json.dumps(owner))

    with pytest.raises(RunLockedError) as error:
        lock.acquire()

    assert error.value.stale is stale
    assert error.value.owner["run_id"] == "existing-run"
    assert lock.path.is_dir()
    assert json.loads((lock.path / "owner.json").read_text()) == owner


def test_run_persists_plan_logs_summary_and_latest(tmp_path):
    from graal_pipeline.model import PlanAction
    from graal_pipeline.runner import run_plan

    state = tmp_path / "state"
    stage = "signal_mc_generation"
    summary = run_plan(
        _plan(_item(stage, PlanAction.RUN)),
        {stage: _invocation(stage, tmp_path / "mc.root")},
        state_directory=state,
        run_id="recorded-run",
        executor=FakeExecutor(),
        validator=_validator,
    )

    assert summary.exit_code == 0
    assert (state / "runs/recorded-run/plan.json").is_file()
    assert (state / "runs/recorded-run/summary.json").is_file()
    assert (state / "logs/recorded-run/signal_mc_generation.log").is_file()
    assert json.loads((state / "latest.json").read_text())["run_id"] == "recorded-run"


def test_failed_validation_preserves_old_file_and_cleans_staging(tmp_path):
    from graal_pipeline.model import PlanAction, ValidationResult
    from graal_pipeline.runner import run_plan

    output = tmp_path / "product.root"
    output.write_text("known good\n")
    state = tmp_path / "state"

    summary = run_plan(
        _plan(_item("signal_mc_generation", PlanAction.REBUILD)),
        {"signal_mc_generation": _invocation("signal_mc_generation", output)},
        state_directory=state,
        executor=FakeExecutor(),
        validator=lambda *_: ValidationResult(False, "test", ("bad staged output",)),
    )

    assert summary.results[0].status == "FAILED"
    assert output.read_text() == "known good\n"
    assert list(tmp_path.glob(".product.root.pipeline-*")) == []


def test_directory_publication_is_atomic_and_checkpoint_is_written_last(tmp_path):
    from graal_pipeline.model import ArtifactState, PlanAction
    from graal_pipeline.runner import run_plan
    from graal_pipeline.state import classify_artifact

    output = tmp_path / "published"
    output.mkdir()
    (output / "product.txt").write_text("known good\n")
    state = tmp_path / "state"
    stage = "signal_mc_generation"

    def crash_after_publish(*_):
        raise RuntimeError("simulated crash")

    with pytest.raises(RuntimeError, match="simulated crash"):
        run_plan(
            _plan(_item(stage, PlanAction.REBUILD)),
            {stage: _invocation(stage, output, kind="directory")},
            state_directory=state,
            run_id="crash-run",
            executor=FakeExecutor(),
            validator=_validator,
            after_publish=crash_after_publish,
        )

    assert (output / "product.txt").read_text() == f"new {stage}\n"
    assert list((state / "checkpoints").rglob("*.json")) == []
    status = classify_artifact(
        exists=True,
        validation=_validator(stage, _invocation(stage, output, kind="directory")),
        checkpoint=None,
        current_inputs={},
        current_outputs={},
        current_configuration={},
        current_code={},
        max_age_days=30,
    )
    assert status.state is ArtifactState.UNTRACKED


def test_successful_publication_writes_checkpoint_and_releases_lock(tmp_path):
    from graal_pipeline.model import PlanAction
    from graal_pipeline.runner import run_plan

    state = tmp_path / "state"
    output = tmp_path / "product.root"
    summary = run_plan(
        _plan(_item("signal_mc_generation", PlanAction.RUN)),
        {"signal_mc_generation": _invocation("signal_mc_generation", output)},
        state_directory=state,
        run_id="successful-run",
        executor=FakeExecutor(),
        validator=_validator,
    )

    assert summary.results[0].status == "PASSED"
    assert output.read_text() == "new signal_mc_generation\n"
    assert list((state / "checkpoints").rglob("signal_mc_generation.json"))
    assert not (state / "run.lock").exists()
