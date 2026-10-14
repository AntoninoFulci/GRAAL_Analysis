"""Terminal presentation must preserve stage output and execution contracts."""

import io
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

from scripts import run_pipeline as pipeline
from scripts.parallel_pipeline import bounded_runner


ANSI = re.compile(r"\x1b\[[0-9;]*m")


def test_cli_forces_color_for_errors_on_redirected_stderr(monkeypatch, capsys):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr(
        pipeline, "run",
        lambda args: (_ for _ in ()).throw(pipeline.PipelineError("broken")),
    )
    assert pipeline.main(["--mode", "test_data", "--color", "always"]) == 1
    error = capsys.readouterr().err
    assert "\x1b[" in error
    assert ANSI.sub("", error) == "ERROR: broken\n"


@pytest.mark.parametrize("mode", ["auto", "never"])
def test_cli_keeps_redirected_errors_plain(monkeypatch, capsys, mode):
    monkeypatch.setattr(
        pipeline, "run",
        lambda args: (_ for _ in ()).throw(pipeline.PipelineError("broken")),
    )
    assert pipeline.main(["--mode", "test_data", "--color", mode]) == 1
    assert capsys.readouterr().err == "ERROR: broken\n"


@pytest.mark.parametrize(
    "mode,tty,term,no_color,want",
    [
        ("auto", True, "xterm", False, True),
        ("auto", False, "xterm", False, False),
        ("auto", True, "dumb", False, False),
        ("always", False, "dumb", False, True),
        ("never", True, "xterm", False, False),
        ("always", True, "xterm", True, False),
    ],
)
def test_color_policy_respects_stream_and_environment(
    monkeypatch, mode, tty, term, no_color, want
):
    monkeypatch.setenv("TERM", term)
    monkeypatch.delenv("NO_COLOR", raising=False)
    if no_color:
        monkeypatch.setenv("NO_COLOR", "")
    stream = io.StringIO()
    monkeypatch.setattr(stream, "isatty", lambda: tty)
    with pipeline.console.color_mode(mode):
        assert pipeline.console.use_color(stream) is want


def test_message_roles_keep_content_and_differentiate_severity(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    messages = (
        "[INFO] reading input\n", "Warning in <ROOT>: missing histogram\n",
        "ValueError: invalid input\n", "Saved model to artifacts\n",
        "warning counts: 0; error estimate: 0.02\n",
    )
    with pipeline.console.color_mode("always"):
        rendered = [pipeline.console.format_message(line) for line in messages]
    assert [ANSI.sub("", line) for line in rendered] == list(messages)
    assert len({ANSI.match(line).group() for line in rendered[:4]}) == 4
    assert not ANSI.match(rendered[-1])  # Ordinary metrics are not errors.


@pytest.mark.parametrize("mode", ["always", "never"])
def test_stage_colors_never_enter_command_log(tmp_path, monkeypatch, capsys, mode):
    monkeypatch.delenv("NO_COLOR", raising=False)
    paths = pipeline.build_paths(pipeline.mode_config("test_data", tmp_path))
    pipeline.prepare_output_dirs(paths)
    with pipeline.console.color_mode(mode):
        pipeline._log_decision(paths.command_log, "selection", "RUN", "fresh input")
        pipeline.execute_plan(
            (pipeline.Stage("example", ("tool",)),), paths,
            runner=lambda argv, **kwargs: subprocess.CompletedProcess(argv, 0),
        )
    output = capsys.readouterr().out
    assert ("\x1b[" in output) is (mode == "always")
    assert "example" in ANSI.sub("", output)
    assert "\x1b" not in paths.command_log.read_text()


@pytest.mark.parametrize("mode", ["always", "never"])
def test_streamed_child_preserves_both_streams_exit_and_environment(monkeypatch, capsys, mode):
    monkeypatch.delenv("NO_COLOR", raising=False)
    script = (
        "import os, sys; "
        "print('[INFO] threads=' + os.environ['OMP_NUM_THREADS']); "
        "sys.stdout.write('café\\rprogress\\nlast fragment'); "
        "sys.stderr.write('Warning in <ROOT>: check input\\n'); "
        "sys.stderr.write('ERROR: failed\\n'); sys.exit(7)"
    )
    with pipeline.console.color_mode(mode):
        result = bounded_runner((sys.executable, "-c", script), check=False, shell=False)
    captured = capsys.readouterr()
    assert result.returncode == 7
    assert ANSI.sub("", captured.out) == "[INFO] threads=1\ncafé\rprogress\nlast fragment"
    assert ANSI.sub("", captured.err) == "Warning in <ROOT>: check input\nERROR: failed\n"
    assert ("\x1b[" in captured.out) is (mode == "always")
    assert ("\x1b[" in captured.err) is (mode == "always")


def test_streaming_delivers_output_before_child_exits(tmp_path, monkeypatch):
    acknowledgement = tmp_path / "seen"

    class AcknowledgingStream(io.StringIO):
        def write(self, value):
            if "ready" in value:
                acknowledgement.touch()
            return super().write(value)

    output = AcknowledgingStream()
    monkeypatch.setattr(sys, "stdout", output)
    script = """
import pathlib, sys, time
print('ready')
ack = pathlib.Path(sys.argv[1])
deadline = time.monotonic() + 5
while not ack.exists() and time.monotonic() < deadline:
    time.sleep(0.01)
sys.exit(0 if ack.exists() else 9)
"""
    with pipeline.console.color_mode("always"):
        result = bounded_runner((sys.executable, "-c", script, str(acknowledgement)))
    assert result.returncode == 0
    assert output.getvalue() == "ready\n"


def test_large_parallel_output_does_not_deadlock_or_mix_color_sequences(monkeypatch, capsys):
    monkeypatch.delenv("NO_COLOR", raising=False)
    script = (
        "import sys; "
        "[(print('[INFO] ' + sys.argv[1] + ' ' + str(i)), "
        "print('WARNING: ' + sys.argv[1] + ' ' + str(i), file=sys.stderr)) "
        "for i in range(2000)]"
    )
    with pipeline.console.color_mode("always"):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(
                lambda name: bounded_runner((sys.executable, "-c", script, name)),
                ("one", "two"),
            ))
    assert all(result.returncode == 0 for result in results)
    captured = capsys.readouterr()
    for output, prefix in ((captured.out, "[INFO]"), (captured.err, "WARNING:")):
        lines = ANSI.sub("", output).splitlines()
        assert len(lines) == 4000
        assert set(lines) == {f"{prefix} {name} {i}" for name in ("one", "two") for i in range(2000)}


def test_plain_streaming_removes_child_ansi(monkeypatch, capsys):
    with pipeline.console.color_mode("never"):
        bounded_runner((sys.executable, "-c", "print('\\x1b[31mERROR: child\\x1b[0m')"))
    assert capsys.readouterr().out == "ERROR: child\n"


def test_streamed_runner_propagates_check_failure(capsys):
    with pipeline.console.color_mode("never"):
        with pytest.raises(subprocess.CalledProcessError) as error:
            bounded_runner((sys.executable, "-c", "print('last output'); exit(3)"), check=True)
    assert error.value.returncode == 3
    assert capsys.readouterr().out == "last output\n"
