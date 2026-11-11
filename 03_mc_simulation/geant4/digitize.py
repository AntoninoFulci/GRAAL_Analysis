#!/usr/bin/env python3
"""Offline, uncalibrated period09 BGO/barrel diagnostic; never an efficiency chain."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import uproot

from mc_simulation.geant4.legacy_response import write_response_config

MODULE = Path(__file__).resolve().parent
DEFAULT_DATA = MODULE.parents[1] / "docs/reference/fortran/prog/data"


def sha256(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def _write_provenance(path, provenance):
    with uproot.create(path, compression=uproot.ZSTD(5)) as root:
        root["metadata"] = json.dumps(provenance, sort_keys=True)


def digitize(input_root, historical_run, legacy_data, output, executable, seed):
    """No rebuild or input mutation. Publish digits only after SHA256 rechecks."""
    input_root, executable = Path(input_root).resolve(strict=True), Path(executable).resolve(strict=True)
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**64:
        raise ValueError("seed must be an integer in [0,2**64)")
    output = Path(output).resolve()
    # Atomic directory creation provides the launcher-wide no-overwrite boundary.
    output.mkdir(parents=False, exist_ok=False)
    config = output / "response_config.root"
    sources = [MODULE / "digitize.py", MODULE / "legacy_response.py", MODULE / "src/digitize.cc",
               MODULE / "src/LegacyDigitization.hh", MODULE / "src/RootOutput.hh", MODULE / "src/RootInput.hh", MODULE / "src/TransportStorage.hh"]
    provenance = {
        "input_path": str(input_root), "input_sha256": sha256(input_root),
        "executable_path": str(executable), "executable_sha256": sha256(executable),
        "code_sha256": {str(path): sha256(path) for path in sources},
        "seed": seed, "mode": "legacy09_diagnostic", "physics_validation": False,
        "hash_policy": "actual files; source hashes identify present sources, binary hash identifies executed build",
    }
    write_response_config(legacy_data, historical_run, config)
    with uproot.update(config) as root:
        root["launcher_provenance"] = json.dumps(provenance, sort_keys=True)
    config_digest = sha256(config)
    staging = output / "digits.pending"
    result = subprocess.run([str(executable), str(input_root), str(config), str(staging), str(seed)],
                            capture_output=True, text=True, check=False)
    # Retain stdout/stderr as diagnostic evidence, never a substitute success file.
    (output / "native.log").write_text(result.stdout + result.stderr)
    response = staging / "response.root"
    try:
        if result.returncode:
            raise RuntimeError(f"Native diagnostic failed ({result.returncode}): {result.stderr[-4000:]}")
        if sha256(input_root) != provenance["input_sha256"] or sha256(config) != config_digest:
            raise RuntimeError("Input/config changed during digitization; response invalidated")
        if sha256(executable) != provenance["executable_sha256"] or any(
                sha256(path) != digest for path, digest in provenance["code_sha256"].items()):
            raise RuntimeError("Executable/source changed during digitization; response invalidated")
        with uproot.open(response) as root:
            summary = json.loads(str(root["summary"]))
            if summary.get("status") != "legacy09_diagnostic_complete" or summary.get("physics_validation") is not False:
                raise RuntimeError("Missing diagnostic completion summary")
        provenance["config_sha256"] = config_digest
        provenance["response_sha256"] = sha256(response)
        provenance["historical_run"] = historical_run
        provenance["summary"] = summary
        # The manifest is ROOT launcher success evidence. Publish the directory
        # only after every checked write and recheck, so failures stay pending.
        _write_provenance(staging / "provenance.root", provenance)
        if sha256(input_root) != provenance["input_sha256"] or sha256(config) != config_digest:
            raise RuntimeError("Input/config changed before publication; response invalidated")
        staging.rename(output / "digits")
    except BaseException:
        if response.exists():
            response.rename(staging / "response.invalid.root")
        raise
    return output / "digits/response.root"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["legacy09_diagnostic"], required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--historical-run", type=int, choices=[1321, 1324], required=True)
    parser.add_argument("--legacy-data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output", type=Path, required=True, help="new directory; response is digits/response.root")
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    args = parser.parse_args(argv)
    try:
        path = digitize(args.input, args.historical_run, args.legacy_data, args.output, args.executable, args.seed)
    except (OSError, ValueError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"DIAGNOSTIC ONLY: unqualified 1998 geometry, uncalibrated response: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
