#!/usr/bin/env python3
"""Offline selected26 NEW_PLAN wire digitization and chamber-only tracking diagnostic."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

import uproot

from mc_simulation.geant4.legacy_response import write_newplan_config
from mc_simulation.geant4.digitize import sha256, _write_provenance

MODULE = Path(__file__).resolve().parent
DEFAULT_DATA = MODULE.parents[1] / "docs/reference/fortran/prog/data"


def reconstruct(input_root, legacy_data, output, executable):
    """No rebuild or input mutation. Publish chamber diagnostics only after SHA256 rechecks."""
    input_root, executable = Path(input_root).resolve(strict=True), Path(executable).resolve(strict=True)
    output = Path(output).resolve()
    # Atomic directory creation provides the launcher-wide no-overwrite boundary.
    output.mkdir(parents=False, exist_ok=False)
    config = output / "newplan_config.root"
    sources = [MODULE / "newplan.py", MODULE / "legacy_response.py", MODULE / "src/newplan.cc",
               MODULE / "src/NewPlan.hh", MODULE / "src/RootOutput.hh", MODULE / "src/RootInput.hh", MODULE / "src/TransportStorage.hh", MODULE / "digitize.py"]
    provenance = {
        "input_path": str(input_root), "input_sha256": sha256(input_root),
        "executable_path": str(executable), "executable_sha256": sha256(executable),
        "code_sha256": {str(path): sha256(path) for path in sources},
        "mode": "selected26_newplan_diagnostic", "physics_validation": False, "physical_validation": False,
        "hash_policy": "actual files; source hashes identify present sources, binary hash identifies executed build",
    }
    write_newplan_config(legacy_data, config)
    with uproot.update(config) as root:
        root["launcher_provenance"] = json.dumps(provenance, sort_keys=True)
    config_digest = sha256(config)
    staging = output / "tracking.pending"
    result = subprocess.run([str(executable), str(input_root), str(config), str(staging)],
                            capture_output=True, text=True, check=False)
    # Retain stdout/stderr as diagnostic evidence, never a substitute success file.
    response = staging / "tracking.root"
    try:
        (output / "native.log").write_text(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(f"Native diagnostic failed ({result.returncode}): {result.stderr[-4000:]}")
        if sha256(input_root) != provenance["input_sha256"] or sha256(config) != config_digest:
            raise RuntimeError("Input/config changed during digitization; response invalidated")
        if sha256(executable) != provenance["executable_sha256"] or any(
                sha256(path) != digest for path, digest in provenance["code_sha256"].items()):
            raise RuntimeError("Executable/source changed during digitization; response invalidated")
        with uproot.open(response) as root:
            summary = json.loads(str(root["summary"]))
            if summary.get("status") != "selected26_newplan_diagnostic_complete" or summary.get("physics_validation") is not False:
                raise RuntimeError("Missing diagnostic completion summary")
        provenance["config_sha256"] = config_digest
        provenance["response_sha256"] = sha256(response)
        provenance["summary"] = summary
        # The manifest is ROOT launcher success evidence. Publish the directory
        # only after every checked write and recheck, so failures stay pending.
        _write_provenance(staging / "provenance.root", provenance)
        if sha256(input_root) != provenance["input_sha256"] or sha256(config) != config_digest:
            raise RuntimeError("Input/config changed before publication; response invalidated")
        if sha256(executable) != provenance["executable_sha256"] or any(
                sha256(path) != digest for path, digest in provenance["code_sha256"].items()):
            raise RuntimeError("Executable/source changed before publication; tracking invalidated")
        staging.rename(output / "tracking")
    except BaseException:
        if response.exists():
            response.rename(staging / "tracking.invalid.root")
        raise
    return output / "tracking/tracking.root"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["selected26_newplan_diagnostic"], required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--legacy-data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output", type=Path, required=True, help="new directory; response is tracking/tracking.root")
    parser.add_argument("--executable", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        path = reconstruct(args.input, args.legacy_data, args.output, args.executable)
    except (OSError, ValueError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"DIAGNOSTIC ONLY: unit-efficiency wires and chamber tracks; no physical validation: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
