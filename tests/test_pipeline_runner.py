from __future__ import annotations

import io
import json
import os
import sys
import threading
from pathlib import Path

import pytest


def test_default_executor_tees_stdout_and_stderr_to_console_and_log(
    tmp_path, capsys
):
    from graal_pipeline.runner import _default_executor

    log_path = tmp_path / "stage.log"
    command = (
        sys.executable,
        "-c",
        (
            "import sys; "
            "print('child stdout', flush=True); "
            "print('child stderr', file=sys.stderr, flush=True); "
            "raise SystemExit(7)"
        ),
    )

    exit_code = _default_executor(command, tmp_path, log_path)

    console = capsys.readouterr().out
    persisted = log_path.read_text(encoding="utf-8")
    assert console == persisted
    assert console.endswith("child stdout\nchild stderr\n")
    assert exit_code == 7


def test_default_executor_streams_output_before_child_exits(tmp_path, monkeypatch):
    from graal_pipeline.runner import _default_executor

    output_seen = threading.Event()

    class ConsoleProbe(io.StringIO):
        def write(self, value):
            written = super().write(value)
            if "streamed before exit\n" in self.getvalue():
                output_seen.set()
            return written

    console = ConsoleProbe()
    monkeypatch.setattr(sys, "stdout", console)
    continue_marker = tmp_path / "continue"
    log_path = tmp_path / "stage.log"
    command = (
        sys.executable,
        "-c",
        (
            "from pathlib import Path; import sys, time; "
            "print('streamed before exit', flush=True); "
            "marker = Path(sys.argv[1]); "
            "exec(\"while not marker.exists():\\n time.sleep(0.01)\"); "
            "print('finished', flush=True)"
        ),
        str(continue_marker),
    )
    result = {}
    worker = threading.Thread(
        target=lambda: result.setdefault(
            "exit_code", _default_executor(command, tmp_path, log_path)
        )
    )

    worker.start()
    try:
        assert output_seen.wait(timeout=2)
        assert worker.is_alive()
    finally:
        continue_marker.touch()
        worker.join(timeout=2)

    assert not worker.is_alive()
    assert result["exit_code"] == 0
    assert "streamed before exit\nfinished\n" in log_path.read_text(
        encoding="utf-8"
    )


def _item(stage_key, action):
    from graal_pipeline.model import ArtifactState, PlanItem

    return PlanItem(stage_key, ArtifactState.MISSING, action)


def _plan(*items):
    from graal_pipeline.model import PipelinePlan

    return PipelinePlan("test-target", tuple(items), final_state="eta_pi0")


def _invocation(
    stage_key: str,
    output: Path,
    *,
    kind: str = "file",
    responsible_paths: tuple[str, ...] = (),
):
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
        responsible_paths=responsible_paths,
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
        repository_root=tmp_path,
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
        repository_root=tmp_path,
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
        repository_root=tmp_path,
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
        repository_root=tmp_path,
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
        repository_root=tmp_path,
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
            repository_root=tmp_path,
            run_id="crash-run",
            executor=FakeExecutor(),
            validator=_validator,
            after_publish=crash_after_publish,
        )

    assert (output / "product.txt").read_text() == f"new {stage}\n"
    assert list((state / "checkpoints").rglob("*.json")) == []
    assert json.loads((state / "latest.json").read_text())["run_id"] == "crash-run"
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
        repository_root=tmp_path,
        run_id="successful-run",
        executor=FakeExecutor(),
        validator=_validator,
    )

    assert summary.results[0].status == "PASSED"
    assert output.read_text() == "new signal_mc_generation\n"
    assert list((state / "checkpoints").rglob("signal_mc_generation.json"))
    assert not (state / "run.lock").exists()


def test_checkpoint_code_fingerprint_uses_repository_root_not_caller_cwd(
    tmp_path, monkeypatch
):
    from graal_pipeline.model import PlanAction
    from graal_pipeline.runner import run_plan

    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "responsible.py").write_text("VERSION = 1\n")
    caller = tmp_path / "caller"
    caller.mkdir()
    monkeypatch.chdir(caller)

    state = tmp_path / "state"
    stage = "signal_mc_generation"
    run_plan(
        _plan(_item(stage, PlanAction.RUN)),
        {
            stage: _invocation(
                stage,
                tmp_path / "mc.root",
                responsible_paths=("responsible.py",),
            )
        },
        state_directory=state,
        repository_root=repository,
        run_id="outside-cwd",
        executor=FakeExecutor(),
        validator=_validator,
    )

    checkpoint_path = state / "checkpoints/eta_pi0/signal_mc_generation.json"
    checkpoint = json.loads(checkpoint_path.read_text())
    assert checkpoint["code"]["files"] == {
        "responsible.py": "e0cb9debdb563025b7c11817ec16198da076090d46dbee8ccc4c3d58a3734ab9"
    }


def test_existing_lock_prevents_all_run_state_mutation(tmp_path):
    from graal_pipeline.model import PlanAction
    from graal_pipeline.runner import RunLock, RunLockedError, run_plan

    state = tmp_path / "state"
    lock = RunLock(state, run_id="existing")
    lock.path.mkdir(parents=True)
    (lock.path / "owner.json").write_text(
        json.dumps({"pid": os.getpid(), "run_id": "existing", "host": lock.host})
    )

    with pytest.raises(RunLockedError):
        run_plan(
            _plan(_item("signal_mc_generation", PlanAction.RUN)),
            {
                "signal_mc_generation": _invocation(
                    "signal_mc_generation", tmp_path / "mc.root"
                )
            },
            state_directory=state,
            repository_root=tmp_path,
            run_id="refused",
            executor=FakeExecutor(),
            validator=_validator,
        )

    assert not (state / "runs").exists()
    assert not (state / "logs").exists()


def test_failed_enabled_optional_dependency_blocks_consumer(tmp_path):
    from graal_pipeline.model import PlanAction
    from graal_pipeline.runner import run_plan

    executor = FakeExecutor(failures=("grid_search",))
    summary = run_plan(
        _plan(
            _item("grid_search", PlanAction.RUN),
            _item("bdt_training", PlanAction.RUN),
        ),
        {
            "grid_search": _invocation("grid_search", tmp_path / "grid.json"),
            "bdt_training": _invocation("bdt_training", tmp_path / "model.json"),
        },
        state_directory=tmp_path / "state",
        repository_root=tmp_path,
        executor=executor,
        validator=_validator,
    )

    assert [result.status for result in summary.results] == ["FAILED", "BLOCKED"]
    assert executor.calls == ["grid_search"]


def test_full_verification_checkpoint_is_immediately_fresh_and_records_profile(
    tmp_path,
):
    from graal_pipeline.model import ArtifactState, PlanAction
    from graal_pipeline.runner import run_plan
    from graal_pipeline.state import CheckpointStore, inspect_invocation_status

    output = tmp_path / "large.root"
    invocation = _invocation("signal_mc_generation", output)

    def large_executor(command, _cwd, _log_path):
        Path(command[2]).write_bytes(b"x" * (1024 * 1024 + 1))
        return 0

    state = tmp_path / "state"
    configuration = {"profile": "farm"}
    run_plan(
        _plan(_item("signal_mc_generation", PlanAction.RUN)),
        {"signal_mc_generation": invocation},
        state_directory=state,
        repository_root=tmp_path,
        verification="full",
        configuration=configuration,
        executor=large_executor,
        validator=_validator,
    )

    checkpoint_path = state / "checkpoints/eta_pi0/signal_mc_generation.json"
    checkpoint = json.loads(checkpoint_path.read_text())
    status = inspect_invocation_status(
        invocation,
        checkpoint_store=CheckpointStore(state),
        configuration=configuration,
        repository_root=tmp_path,
        final_state="eta_pi0",
        observable=None,
        max_age_days=30,
        verification="full",
        validator=_validator,
    )

    assert checkpoint["verification"] == "full"
    assert checkpoint["profile"] == "farm"
    assert "sha256" in next(iter(checkpoint["outputs"].values()))
    assert status.state is ArtifactState.FRESH


def test_automatic_run_ids_do_not_collide_within_one_second(tmp_path):
    from graal_pipeline.model import PlanAction
    from graal_pipeline.runner import run_plan

    stage = "signal_mc_generation"
    invocation = _invocation(stage, tmp_path / "mc.root")
    kwargs = {
        "state_directory": tmp_path / "state",
        "repository_root": tmp_path,
        "executor": FakeExecutor(),
        "validator": _validator,
    }
    first = run_plan(_plan(_item(stage, PlanAction.RUN)), {stage: invocation}, **kwargs)
    second = run_plan(_plan(_item(stage, PlanAction.RUN)), {stage: invocation}, **kwargs)

    assert first.run_id != second.run_id


def test_unrelated_configuration_change_does_not_stale_stage_checkpoint(tmp_path):
    from graal_pipeline.model import ArtifactState, PlanAction
    from graal_pipeline.runner import run_plan
    from graal_pipeline.state import CheckpointStore, inspect_invocation_status

    stage = "signal_mc_generation"
    invocation = _invocation(stage, tmp_path / "mc.root")
    state = tmp_path / "state"
    run_plan(
        _plan(_item(stage, PlanAction.RUN)),
        {stage: invocation},
        state_directory=state,
        repository_root=tmp_path,
        configuration={"profile": "production", "bootstrap_replicas": 10},
        executor=FakeExecutor(),
        validator=_validator,
    )

    status = inspect_invocation_status(
        invocation,
        checkpoint_store=CheckpointStore(state),
        configuration={"profile": "production", "bootstrap_replicas": 999},
        repository_root=tmp_path,
        final_state="eta_pi0",
        observable=None,
        max_age_days=30,
        validator=_validator,
    )

    assert status.state is ArtifactState.FRESH
