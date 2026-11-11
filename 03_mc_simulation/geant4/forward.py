#!/usr/bin/env python3
"""Measured selected26 WALL/SHOW plus NEW_PLAN forward diagnostic launcher."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import uproot

from mc_simulation.geant4.forward_reconstruction_config import (
    read_selected26_forward_reconstruction, write_forward_reconstruction_config,
)

MODULE = Path(__file__).resolve().parent
REPO = MODULE.parents[1]
DEFAULT_DATA = REPO / "docs/reference/fortran/prog/data"


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _exclusive_text(path, value):
    with Path(path).open("x") as stream:
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())


def _write_provenance(path, value):
    with uproot.create(path, compression=uproot.ZSTD(5)) as root:
        root["metadata"] = json.dumps(value, sort_keys=True, allow_nan=False)
    with Path(path).open("rb") as stream:
        os.fsync(stream.fileno())


def _source_files():
    pending = [MODULE / "src/forward.cc"]
    sources = {MODULE / name for name in ("forward.py", "forward_config.py", "forward_reconstruction_config.py", "CMakeLists.txt")}
    while pending:
        path = pending.pop().resolve(strict=True)
        if path in sources:
            continue
        sources.add(path)
        for name in re.findall(r'^\s*#\s*include\s*"([^\"]+)"', path.read_text(), re.M):
            include = path.parent / name
            if include.is_file():
                pending.append(include)
            elif name.endswith((".hh", ".inc")):
                raise FileNotFoundError(f"Missing production include: {include}")
    return sorted(sources)


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate JSON key")
        value[key] = item
    return value


def _json(value):
    return json.loads(str(value), object_pairs_hook=_pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))


def _unchanged(provenance, config, config_digest):
    for key in ("input", "tracking", "executable"):
        if sha256(provenance[key + "_path"]) != provenance[key + "_sha256"]:
            raise RuntimeError(f"{key} changed during forward reconstruction")
    if sha256(config) != config_digest:
        raise RuntimeError("configuration changed during forward reconstruction")
    for group in ("code_sha256", "legacy_source_sha256"):
        if any(sha256(path) != digest for path, digest in provenance[group].items()):
            raise RuntimeError("source changed during forward reconstruction")


def reconstruct(input_root, tracking_root, legacy_data, output, executable, seed, *, source_run):
    if type(seed) is not int or not 0 <= seed < 2**64:
        raise ValueError("seed must be uint64")
    if type(source_run) is not int or not 0 <= source_run <= 65535:
        raise ValueError("source_run must be explicit uint16")
    input_root, tracking_root = Path(input_root).resolve(strict=True), Path(tracking_root).resolve(strict=True)
    legacy_data, executable = Path(legacy_data).resolve(strict=True), Path(executable).resolve(strict=True)
    output = Path(os.path.abspath(output))
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Refusing to overwrite forward output: {output}")
    source_config = read_selected26_forward_reconstruction(legacy_data, source_run=source_run)
    legacy_sources = {}
    for entry in source_config["sources"]:
        path = (legacy_data / entry["path"][5:] if entry["path"].startswith("data/")
                else DEFAULT_DATA.parent / entry["path"])
        if sha256(path) != entry["sha256"]:
            raise RuntimeError(f"Legacy source changed while reading: {path}")
        legacy_sources[str(path.resolve())] = entry["sha256"]
    provenance = dict(input_path=str(input_root), input_sha256=sha256(input_root),
                      tracking_path=str(tracking_root), tracking_sha256=sha256(tracking_root),
                      executable_path=str(executable), executable_sha256=sha256(executable),
                      code_sha256={str(path): sha256(path) for path in _source_files()},
                      legacy_source_sha256=legacy_sources, seed=seed, source_run=source_run,
                      mode="selected26_forward_reconstruction_diagnostic", physics_validation=False,
                      physical_validation=False,
                      hash_policy="current transitive sources and executed binary separately; no binary/source build equivalence assertion")
    # Native MD5 is independently checked too. SHA256 binds the matched tracking
    # launcher's immutable transport identity before native code consumes it.
    with uproot.open(tracking_root) as root:
        tm = _json(root["metadata"])
        if "launcher_provenance" in root:
            tp = _json(root["launcher_provenance"])
            if tp.get("input_sha256") != provenance["input_sha256"]:
                raise ValueError("Tracking references a different transport SHA256")
        if tm.get("input_md5") != hashlib.md5(input_root.read_bytes()).hexdigest():
            raise ValueError("Tracking references a different immutable transport")
    output.mkdir(parents=False, exist_ok=False)
    config = output / "forward_config.root"
    staging = output / "forward.pending"
    response = staging / "forward.root"
    try:
        if write_forward_reconstruction_config(legacy_data, config, source_run=source_run) != source_config:
            raise RuntimeError("Forward source configuration changed during preparation")
        with uproot.update(config) as root:
            root["launcher_provenance"] = json.dumps(provenance, sort_keys=True, allow_nan=False)
        config_digest = sha256(config)
        _unchanged(provenance, config, config_digest)
        result = subprocess.run([str(executable), str(input_root), str(tracking_root), str(config), str(staging), str(seed)],
                                capture_output=True, text=True, check=False)
        _exclusive_text(output / "native.log", result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(f"Native forward failed ({result.returncode}): {result.stderr[-4000:]}")
        _unchanged(provenance, config, config_digest)
        with uproot.open(response) as root:
            summary = _json(root["summary"])
            if (summary.get("status") != "selected26_forward_diagnostic_complete"
                    or summary.get("physical_validation") is not False
                    or summary.get("physics_validation") is not False
                    or type(summary.get("events")) is not int
                    or summary["events"] != root["forward_events"].num_entries):
                raise RuntimeError("Missing forward diagnostic completion summary")
        provenance.update(config_path=str(config), config_sha256=config_digest, response_sha256=sha256(response), summary=summary)
        _write_provenance(staging / "provenance.root", provenance)
        _unchanged(provenance, config, config_digest)
        if sha256(response) != provenance["response_sha256"]:
            raise RuntimeError("Forward output changed before publication")
        destination = output / "forward"
        if destination.exists() or destination.is_symlink():
            raise FileExistsError(destination)
        staging.rename(destination)
    except BaseException:
        if response.exists():
            try:
                os.link(response, staging / "forward.invalid.root")
            finally:
                response.unlink()
        raise
    return output / "forward/forward.root"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["selected26_forward_reconstruction_diagnostic"], required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--tracking", type=Path, required=True)
    parser.add_argument("--legacy-data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--executable", type=Path, default=os.environ.get("GRAAL_FORWARD_EXE"))
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--source-run", type=int, required=True)
    args = parser.parse_args(argv)
    if args.executable is None:
        parser.error("--executable or GRAAL_FORWARD_EXE is required")
    try:
        path = reconstruct(args.input, args.tracking, args.legacy_data, args.output,
                           args.executable, args.seed, source_run=args.source_run)
    except (OSError, ValueError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"DIAGNOSTIC ONLY: measured WALL/SHOW/NEW_PLAN; physical_validation=false: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
