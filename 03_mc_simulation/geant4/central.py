#!/usr/bin/env python3
"""Measured BGO/barrel/cylinder reconstruction; explicit PREAN configuration required."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import uproot

MODULE = Path(__file__).resolve().parent
MODE = "selected26_central_reconstruction_diagnostic"


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _json(value):
    return json.loads(str(value), object_pairs_hook=_pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))


def _exclusive_text(path, text):
    with Path(path).open("x") as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())


def _write_provenance(path, provenance):
    with uproot.create(path, compression=uproot.ZSTD(5)) as root:
        root["metadata"] = json.dumps(provenance, sort_keys=True, allow_nan=False)
    with Path(path).open("rb") as stream:
        os.fsync(stream.fileno())


def _source_files():
    sources = {MODULE / name for name in ("central.py", "bgo_config.py", "CMakeLists.txt")}
    pending = [MODULE / "src/central.cc"]
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
                raise FileNotFoundError(include)
    return sorted(sources)


def _upstream(path, input_root, input_digest):
    """Bind historical producer evidence without comparing it to today's sources."""
    manifest = path.parent / "provenance.root"
    with uproot.open(path) as root, uproot.open(manifest) as evidence:
        metadata = _json(root["metadata"])
        provenance = _json(evidence["metadata"])
        if (provenance.get("response_sha256") != sha256(path)
                or provenance.get("input_sha256") != input_digest
                or provenance.get("summary") != _json(root["summary"])):
            raise ValueError("Measured input provenance does not match immutable transport/result")
        if Path(provenance["input_path"]).resolve(strict=True) != input_root:
            raise ValueError("Measured input transport path mismatch")
        producer_config = Path(metadata["config_path"]).resolve(strict=True)
        if sha256(producer_config) != provenance.get("config_sha256"):
            raise ValueError("Measured input producer configuration changed")
        with uproot.open(producer_config) as config:
            if _json(config["metadata"]) != _json(root["config_metadata"]):
                raise ValueError("Measured producer configuration metadata mismatch")
        launched = _json(root["launcher_provenance"])
        for key in ("input_path", "input_sha256", "executable_sha256", "code_sha256", "mode"):
            if launched.get(key) != provenance.get(key):
                raise ValueError("Measured input launcher/final provenance mismatch")
        return provenance, {str(manifest.resolve()): sha256(manifest),
                            str(producer_config): sha256(producer_config)}


def _unchanged(provenance):
    for group in ("input_sha256", "code_sha256", "configuration_source_sha256"):
        for path, digest in provenance[group].items():
            if sha256(path) != digest:
                raise RuntimeError("Central input/configuration/executable/source changed")


def reconstruct(input_root, response_root, cylinders_root, config_root, output, executable, seed):
    """Publish a complete ROOT diagnostic only after all immutable inputs recheck."""
    if type(seed) is not int or not 0 <= seed < 2**64:
        raise ValueError("seed must be uint64")
    input_root, response_root, cylinders_root, config_root, executable = (
        Path(path).resolve(strict=True) for path in
        (input_root, response_root, cylinders_root, config_root, executable))
    output = Path(os.path.abspath(output))
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Refusing to overwrite central output: {output}")
    inputs = {str(path): sha256(path) for path in
              (input_root, response_root, cylinders_root, config_root, executable)}
    upstream = {}
    for name, path in (("response", response_root), ("cylinders", cylinders_root)):
        upstream[name], dependencies = _upstream(path, input_root, inputs[str(input_root)])
        inputs.update(dependencies)
    with uproot.open(config_root) as root:
        configuration = _json(root["metadata"])
    configuration_sources = {}
    for entry in configuration["sources"]:
        path = Path(entry["path"]).resolve(strict=True)
        digest = sha256(path)
        if digest != entry["sha256"]:
            raise ValueError("Central original source changed while preparing configuration")
        configuration_sources[str(path)] = digest
    provenance = dict(mode=MODE, physical_validation=False, physics_validation=False, seed=seed,
                      transport_path=str(input_root), transport_sha256=inputs[str(input_root)],
                      response_path=str(response_root), cylinders_path=str(cylinders_root),
                      configuration_path=str(config_root), executable_path=str(executable),
                      input_sha256=inputs, code_sha256={str(p): sha256(p) for p in _source_files()},
                      configuration_source_sha256=configuration_sources, upstream=upstream,
                      configuration=configuration,
                      hash_policy="current production source closure and executed binary separately; upstream source hashes historical; no build equivalence assertion")
    output.mkdir(parents=False, exist_ok=False)
    staging = output / "central.pending"
    result_path = staging / "central.root"
    try:
        _unchanged(provenance)
        result = subprocess.run([str(executable), str(input_root), str(response_root), str(cylinders_root),
                                 str(config_root), str(staging), str(seed)],
                                capture_output=True, text=True, check=False)
        _exclusive_text(output / "native.log", result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(f"Native central failed ({result.returncode}): {result.stderr[-4000:]}")
        _unchanged(provenance)
        with uproot.open(result_path) as root:
            summary = _json(root["summary"])
            if (summary.get("status") != "selected26_central_diagnostic_complete"
                    or summary.get("physical_validation") is not False
                    or summary.get("physics_validation") is not False
                    or type(summary.get("events")) is not int
                    or summary["events"] != root["central_events"].num_entries):
                raise RuntimeError("Missing complete central ROOT result")
        provenance.update(summary=summary, result_sha256=sha256(result_path))
        _write_provenance(staging / "provenance.root", provenance)
        _unchanged(provenance)
        if sha256(result_path) != provenance["result_sha256"]:
            raise RuntimeError("Central result changed before publication")
        destination = output / "central"
        if destination.exists() or destination.is_symlink():
            raise FileExistsError(destination)
        staging.rename(destination)
    except BaseException:
        if result_path.exists():
            try:
                os.link(result_path, staging / "central.invalid.root")
            finally:
                result_path.unlink()
        raise
    return output / "central/central.root"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=[MODE])
    for name in ("input", "response", "cylinders", "config", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--executable", type=Path, default=os.environ.get("GRAAL_CENTRAL_EXE"))
    parser.add_argument("--seed", required=True, type=int)
    args = parser.parse_args(argv)
    if args.executable is None:
        parser.error("--executable or GRAAL_CENTRAL_EXE is required")
    try:
        path = reconstruct(args.input, args.response, args.cylinders, args.config,
                           args.output, args.executable, args.seed)
    except (OSError, ValueError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"DIAGNOSTIC ONLY: explicit PREAN initialization, physical_validation=false: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
