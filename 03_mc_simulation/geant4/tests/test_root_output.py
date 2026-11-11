"""ROOT is the transport data contract; no parallel text data dump."""
import os
from pathlib import Path
import subprocess
import sys

import pytest
import uproot
import numpy as np


def test_transport_writes_compressed_typed_root_only(tmp_path):
    binary, geometry = os.environ.get("GRAAL_G4_EXE"), os.environ.get("GRAAL_GDML")
    if not binary or not geometry:
        pytest.skip("Set native Geant4 binaries and geometry")
    macro = tmp_path / "input.mac"
    macro.write_text("/run/initialize\n/gps/particle proton\n/gps/energy 200 MeV\n"
                     "/gps/direction 1 0 0\n/run/beamOn 2\n")
    output = tmp_path / "output"
    result = subprocess.run([binary, geometry, str(macro), str(output)],
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr[-4000:]
    assert {p.name for p in output.iterdir()} == {"transport.root"}
    with uproot.open(output / "transport.root") as root:
        assert {"events", "detector_steps", "primaries", "channels", "bgo_hits",
                "vertices", "summary", "materials", "input_macro", "random_state_run_0"} <= set(root.keys(cycle=False))
        assert root["events"].num_entries == root["primaries"].num_entries == 2
        assert root["channels"].num_entries == 592
        assert root["detector_steps"].num_entries > 0
        assert root["detector_steps"]["edep_MeV"].typename == "double"
        assert root["events"]["steps"].typename == "uint64_t"
        assert root["detector_steps"]["track"].typename == "int32_t"
        assert root["detector_steps"].compressed_bytes < root["detector_steps"].uncompressed_bytes
        assert str(root["input_macro"]) == macro.read_text()


def root_writer():
    binary = os.environ.get("GRAAL_G4_EXE")
    if not binary:
        pytest.skip("Set native Geant4 binaries")
    writer = Path(binary).with_name("graal_root_check")
    assert writer.is_file(), "Build the ROOT writer test harness"
    return writer


def test_root_writer_preserves_uint64_across_basket_flushes(tmp_path):
    result = subprocess.run([str(root_writer()), str(tmp_path)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    with uproot.open(tmp_path / "transport.root") as root:
        rows = root["rows"].arrays(library="np")
        assert np.array_equal(rows["id"], np.arange(20000, dtype=np.uint64) + np.uint64(2**53))
        assert np.all(np.isfinite(rows["energy"]))
        assert np.all(rows["name"] == "channel")


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file-size limit fault injection")
def test_storage_write_failure_never_promotes_partial_root(tmp_path):
    import resource
    import signal

    def limit_file():
        signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
        resource.setrlimit(resource.RLIMIT_FSIZE, (16384, 16384))

    result = subprocess.run([str(root_writer()), str(tmp_path)], capture_output=True,
                            text=True, timeout=30, preexec_fn=limit_file)
    assert result.returncode == 1, result.stderr
    assert "ERROR:" in result.stderr
    assert not (tmp_path / "transport.root").exists()
    assert (tmp_path / "transport.partial.root").exists()
