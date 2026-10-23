"""Color terminal output without changing stage messages or persisted logs."""

from __future__ import annotations

import codecs
from contextlib import contextmanager
import os
import re
import selectors
import subprocess
import sys
import threading


_MODE = "auto"
_OUTPUT_LOCK = threading.RLock()
_ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_COLORS = {
    "info": "\x1b[1;36m",
    "success": "\x1b[32m",
    "warning": "\x1b[33m",
    "error": "\x1b[1;31m",
    "detail": "\x1b[2m",
}
_LEVELS = (
    ("error", re.compile(
        r"^\s*(?:\[(?:ERROR|FATAL|CRITICAL)\]|"
        r"(?:ERROR|FATAL|CRITICAL)(?:\s+in\s+<[^>]*>)?\s*:|"
        r"Traceback \(most recent call last\):|\w*(?:Error|Exception):)", re.I)),
    ("warning", re.compile(
        r"^\s*(?:\[WARN(?:ING)?\]|WARN(?:ING)?(?:\s+in\s+<[^>]*>)?\s*:)|"
        r":\d+(?::\d+)?:\s*\w*Warning:", re.I)),
    ("info", re.compile(r"^\s*(?:\[INFO\]|INFO(?:\s+in\s+<[^>]*>)?\s*:)", re.I)),
    ("success", re.compile(
        r"^\s*(?:Saved|Wrote|Generated|Created file|Selection complete|Pipeline complete)\b", re.I)),
)


@contextmanager
def color_mode(mode: str):
    """Apply one policy to the entire launch, including its worker threads."""
    global _MODE
    previous = _MODE
    _MODE = mode
    try:
        yield
    finally:
        _MODE = previous


def use_color(stream=None) -> bool:
    stream = sys.stdout if stream is None else stream
    if _MODE == "never" or "NO_COLOR" in os.environ:
        return False
    return _MODE == "always" or (
        stream.isatty() and os.environ.get("TERM") != "dumb"
    )


def format_message(message: str, role: str | None = None, *, stream=None) -> str:
    """Recognize explicit levels, not words inside ordinary metrics or paths."""
    message = _ANSI.sub("", message)
    if not use_color(stream):
        return message
    if role is None:
        role = next((name for name, pattern in _LEVELS if pattern.search(message)), None)
    if role is None:
        return message
    body = message.rstrip("\r\n")
    return f"{_COLORS[role]}{body}\x1b[0m{message[len(body):]}"


def emit(message: str, role: str | None = None, *, stream=None) -> None:
    stream = sys.stdout if stream is None else stream
    with _OUTPUT_LOCK:
        print(format_message(message, role, stream=stream), file=stream, flush=True)


def run_streamed(argv, *, env=None, check=False, **kwargs):
    """Drain both child streams concurrently; serialize complete terminal lines.

    Keep stdout and stderr separate. Python children flush immediately even
    though their output is piped. Native stages retain their own flush policy.
    """
    child_env = dict(os.environ if env is None else env)
    child_env["PYTHONUNBUFFERED"] = "1"
    # The relay owns presentation; avoid competing child color policies.
    child_env["NO_COLOR"] = "1"
    with subprocess.Popen(
        argv, env=child_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs
    ) as process:
        try:
            with selectors.DefaultSelector() as selector:
                pending = {}
                decoders = {}
                for pipe, target in ((process.stdout, sys.stdout), (process.stderr, sys.stderr)):
                    selector.register(pipe, selectors.EVENT_READ, target)
                    pending[pipe] = ""
                    decoders[pipe] = codecs.getincrementaldecoder(target.encoding or "utf-8")("replace")
                while selector.get_map():
                    for key, _ in selector.select():
                        pipe, target = key.fileobj, key.data
                        chunk = os.read(pipe.fileno(), 8192)
                        pending[pipe] += decoders[pipe].decode(chunk, final=not chunk)
                        # Include CR progress updates and an unterminated final line.
                        parts = re.split(r"(?<=[\r\n])", pending[pipe])
                        pending[pipe] = parts.pop()
                        if not chunk:
                            parts.append(pending[pipe])
                            pending[pipe] = ""
                            selector.unregister(pipe)
                        for line in parts:
                            if line:
                                with _OUTPUT_LOCK:
                                    target.write(format_message(line, stream=target))
                                    target.flush()
            returncode = process.wait()
        except BaseException:
            # Match subprocess.run cleanup, including Ctrl-C and broken pipes.
            process.kill()
            process.wait()
            raise
    if check and returncode:
        raise subprocess.CalledProcessError(returncode, argv)
    return subprocess.CompletedProcess(argv, returncode)
