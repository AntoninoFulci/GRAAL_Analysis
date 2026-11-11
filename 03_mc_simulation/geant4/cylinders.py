#!/usr/bin/env python3
"""Selected26 OLD_CYL diagnostic response and digit-only central reconstruction."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import uproot

from mc_simulation.geant4.cylinder_config import read_selected26_cylinder, write_cylinder_config

MODULE = Path(__file__).resolve().parent
REPO = MODULE.parents[1]
DEFAULT_DATA = REPO / "docs/reference/fortran/prog/data"


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _exclusive_text(path, text):
    # Refuse pre-existing files/symlinks; stdout is evidence even on native failure.
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
    """Hash all repository-local quoted includes, including tracker dependencies."""
    pending = [MODULE / "src/cylinders.cc"]
    sources = {MODULE / "cylinders.py", MODULE / "cylinder_config.py", MODULE / "CMakeLists.txt"}
    while pending:
        path = pending.pop().resolve(strict=True)
        if path in sources:
            continue
        sources.add(path)
        for name in re.findall(r'^\s*#\s*include\s*"([^"]+)"', path.read_text(), re.M):
            include = path.parent / name
            if include.is_file():
                pending.append(include)
            elif name.endswith(".hh"):
                raise FileNotFoundError(f"Missing current-source include: {include}")
    return sorted(sources)


def _unchanged(provenance, input_root, config, config_digest, executable):
    if sha256(input_root) != provenance["input_sha256"] or sha256(config) != config_digest:
        raise RuntimeError("Input/config changed during cylinder reconstruction")
    if sha256(executable) != provenance["executable_sha256"] or any(
            sha256(path) != digest for path, digest in provenance["code_sha256"].items()):
        raise RuntimeError("Executable/source changed during cylinder reconstruction")
    if any(sha256(path) != digest for path, digest in provenance["legacy_source_sha256"].items()):
        raise RuntimeError("Legacy configuration/source changed during cylinder reconstruction")


def reconstruct(input_root, legacy_data, output, executable, seed):
    """Publish only a SHA256-verified complete ROOT diagnostic; never overwrite."""
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**64:
        raise ValueError("seed must be an integer in [0,2**64)")
    input_root = Path(input_root).resolve(strict=True)
    executable = Path(executable).resolve(strict=True)
    legacy_data = Path(legacy_data).resolve(strict=True)
    # resolve() must not hide a destination symlink.
    output = Path(os.path.abspath(output))
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Refusing to overwrite cylinder output: {output}")
    source_config = read_selected26_cylinder(legacy_data)
    legacy_sources = {}
    for source in source_config["sources"]:
        path = (legacy_data if source["path"].startswith("base/") else DEFAULT_DATA.parent) / source["path"]
        if sha256(path) != source["sha256"]:
            raise RuntimeError(f"Legacy source changed while reading: {path}")
        legacy_sources[str(path.resolve())] = source["sha256"]
    provenance = dict(input_path=str(input_root), input_sha256=sha256(input_root),
                      executable_path=str(executable), executable_sha256=sha256(executable),
                      code_sha256={str(path): sha256(path) for path in _source_files()},
                      legacy_source_sha256=legacy_sources, seed=seed,
                      mode="selected26_old_cyl_diagnostic", physics_validation=False,
                      hash_policy="actual current transitive repository sources; executable identifies executed build; no binary/source build equivalence assertion")
    output.mkdir(parents=False, exist_ok=False)
    config = output / "cylinder_config.root"
    applied_config = write_cylinder_config(legacy_data, config)
    if applied_config != source_config:
        raise RuntimeError("Cylinder source configuration changed during preparation")
    with uproot.update(config) as root:
        root["launcher_provenance"] = json.dumps(provenance, sort_keys=True, allow_nan=False)
    config_digest = sha256(config)
    staging = output / "cylinders.pending"
    response = staging / "cylinders.root"
    try:
        _unchanged(provenance, input_root, config, config_digest, executable)
        result = subprocess.run([str(executable), str(input_root), str(config), str(staging), str(seed)],
                                capture_output=True, text=True, check=False)
        _exclusive_text(output / "native.log", result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(f"Native cylinders failed ({result.returncode}): {result.stderr[-4000:]}")
        _unchanged(provenance, input_root, config, config_digest, executable)
        with uproot.open(response) as root:
            summary = json.loads(str(root["summary"]))
            if (summary.get("status") != "selected26_old_cyl_diagnostic_complete"
                    or summary.get("physics_validation") is not False
                    or summary.get("physical_validation") is not False):
                raise RuntimeError("Missing cylinder diagnostic completion summary")
        provenance.update(config_sha256=config_digest, response_sha256=sha256(response), summary=summary)
        _write_provenance(staging / "provenance.root", provenance)
        _unchanged(provenance, input_root, config, config_digest, executable)
        if sha256(response) != provenance["response_sha256"]:
            raise RuntimeError("Cylinder output changed before publication")
        destination = output / "cylinders"
        if destination.exists() or destination.is_symlink():
            raise FileExistsError(f"Refusing to overwrite cylinder publication: {destination}")
        staging.rename(destination)
    except BaseException:
        if response.exists():
            # Hard-link invalidation is exclusive even if an unexpected file appears.
            invalid = staging / "cylinders.invalid.root"
            try:
                os.link(response, invalid)
            finally:
                response.unlink()
        raise
    return output / "cylinders/cylinders.root"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["selected26_old_cyl_diagnostic"], required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--legacy-data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    args = parser.parse_args(argv)
    try:
        path = reconstruct(args.input, args.legacy_data, args.output, args.executable, args.seed)
    except (OSError, ValueError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"DIAGNOSTIC ONLY: selected26 OLD_CYL response/tracking, physical validation=false: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
