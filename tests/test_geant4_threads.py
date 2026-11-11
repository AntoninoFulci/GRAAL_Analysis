"""Thread policy and exclusive launcher admission, without scientific transport."""
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "03_mc_simulation/geant4/run.py"


def launcher():
    spec = importlib.util.spec_from_file_location("g4_threads", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_auto_uses_available_cpus_and_keeps_legacy_serial(monkeypatch):
    api = launcher()
    monkeypatch.setattr(api.os, "process_cpu_count", lambda: 8, raising=False)
    monkeypatch.setattr(api.os, "sched_getaffinity", lambda _: set(range(8)), raising=False)
    assert api.transport_threads("auto", "replay", {"schema_version": 2}) == 8
    assert api.transport_threads("auto", "replay", {"schema_version": 1}) is None
    assert api.transport_threads("auto", "smoke", None) is None
    assert api.transport_threads("serial", "replay", {"schema_version": 2}) is None
    assert api.transport_threads("1", "replay", {"schema_version": 2}) == 1
    monkeypatch.setattr(api.os, "sched_getaffinity", lambda _: {0,1})
    assert api.transport_threads("auto", "replay", {"schema_version": 2}) == 2


@pytest.mark.parametrize("value", ["0", "-1", "1.5", "foo", "2147483648"])
def test_bad_thread_request_rejected(value):
    with pytest.raises(ValueError, match="threads"):
        launcher().transport_threads(value, "replay", {"schema_version": 2})


@pytest.mark.parametrize("mode,truth", [("smoke", None), ("view", None),
                                       ("replay", {"schema_version": 1})])
def test_explicit_mt_requires_root_replay(mode, truth):
    with pytest.raises(ValueError, match="ROOT replay"):
        launcher().transport_threads("2", mode, truth)


def test_second_job_refused_and_lock_released_after_exception(tmp_path):
    api = launcher()
    path = tmp_path / "job.lock"
    with pytest.raises(RuntimeError, match="injected"):
        with api.single_transport(path):
            with pytest.raises(RuntimeError, match="already running"):
                with api.single_transport(path):
                    pytest.fail("Concurrent job admitted")
            raise RuntimeError("injected")
    with api.single_transport(path):
        pass


def test_posix_child_retains_lock_after_launcher_death(tmp_path):
    import os
    import signal
    import subprocess
    import sys
    if os.name == "nt":
        pytest.skip("POSIX inherited open-file-description lock")
    path = tmp_path / "job.lock"
    code = f'''
import importlib.util, os, subprocess, sys
spec=importlib.util.spec_from_file_location("g4", {str(SCRIPT)!r})
api=importlib.util.module_from_spec(spec); spec.loader.exec_module(api)
with api.single_transport(api.Path({str(path)!r})) as lock:
    child=subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"],
        pass_fds=(lock.fileno(),),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    print(child.pid,flush=True)
    os._exit(0)
'''
    parent = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, text=True, timeout=10)
    assert parent.returncode == 0, parent.stderr
    pid = int(parent.stdout.strip())
    try:
        with pytest.raises(RuntimeError, match="already running"):
            with launcher().single_transport(path):
                pytest.fail("Admitted another job while transport still owns lock")
    finally:
        os.kill(pid, signal.SIGTERM)
