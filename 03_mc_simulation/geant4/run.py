#!/usr/bin/env python3
"""Build and run isolated Geant4 diagnostics on macOS, Linux and Windows."""
import argparse
import csv
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

MODULE = Path(__file__).resolve().parent
ROOT = MODULE.parents[1]


def find_geant4(prefix):
    """Prefer explicit configuration; otherwise use an installed tool or external Spack."""
    prefix = prefix or os.environ.get("GEANT4_PREFIX")
    if not prefix and os.environ.get("Geant4_DIR"):
        config = Path(os.environ["Geant4_DIR"]).expanduser().resolve()
        if not config.is_dir():
            raise ValueError(f"Geant4_DIR does not exist: {config}")
        return config
    if not prefix:
        # Explicit Spack settings select the requested installation over PATH.
        config_tool = shutil.which("geant4-config")
        if config_tool and not (os.environ.get("SPACK_BIN") or os.environ.get("SPACK_ENV")):
            prefix = subprocess.check_output([config_tool, "--prefix"], text=True).strip()
        else:
            spack = os.environ.get("SPACK_BIN") or shutil.which("spack")
            if not spack:
                raise ValueError("Set GEANT4_PREFIX or Geant4_DIR, load geant4-config on PATH, "
                                 "or set SPACK_BIN and optional external SPACK_ENV/SPACK_SPEC")
            command = [spack]
            if os.environ.get("SPACK_ENV"):
                command += ["-e", os.environ["SPACK_ENV"]]
            command += ["location", "-i", os.environ.get("SPACK_SPEC", "geant4")]
            prefix = subprocess.check_output(command, text=True).strip()
    prefix = Path(prefix).expanduser().resolve()
    for lib in ("lib", "lib64"):
        config = prefix / lib / "cmake/Geant4"
        if config.is_dir():
            return config
    raise ValueError(f"Geant4 CMake package not found below {prefix}; set Geant4_DIR explicitly")


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def validate_truth(directory):
    """Require a complete, unchanged export before building or transporting."""
    directory = Path(directory)
    report = json.loads((directory / "manifest.json").read_text())
    required = {"schema_version": 1, "status": "diagnostic_truth_export", "units": "GeV",
                "vertex_mm": [0, 0, 0], "time_ns": 0, "generation_target": "free_proton",
                "geometry_target": "deuterium_diagnostic_only", "polarization": "not_modeled",
                "weight_policy": "unit_unweighted_no_flux_or_cross_section_normalization"}
    if any(report.get(key) != value for key, value in required.items()):
        raise ValueError("Unsupported truth manifest; use export_truth.py")
    count, total = report.get("events"), report.get("source_events")
    if type(count) is not int or type(total) is not int or not 0 < count <= total:
        raise ValueError("Invalid truth event counts")
    channel = report.get("channel")
    seed, window = report.get("seed"), report.get("beam_window_GeV")
    if (not isinstance(channel, str) or not channel or not channel.replace("_", "").isalnum()
            or report.get("generator") != f"generate_{channel}_dataset"
            or report.get("generator_schema_version") != 1
            or report.get("sampling") != "accept-reject-unweighted; TRandom3 shared with TGenPhaseSpace"
            or not all(isinstance(report.get(key), str) and report[key]
                       for key in ("source", "source_uuid", "source_sha256", "generator_root_version"))
            or type(seed) is not int or not 0 < seed <= 2**32 - 1
            or not isinstance(window, list) or len(window) != 2
            or not all(type(v) in (int, float) and math.isfinite(v) for v in window)
            or not 0 < window[0] < window[1]):
        raise ValueError("Incomplete or invalid truth provenance")
    try:
        uuid.UUID(report["source_uuid"])
        source_hash = report["source_sha256"]
        if len(source_hash) != 64 or any(c not in "0123456789abcdef" for c in source_hash):
            raise ValueError("Invalid SHA-256")
    except ValueError as error:
        raise ValueError("Invalid truth source identity") from error
    for name, field in (("primaries.dat", "primary_sha256"), ("truth.csv", "mapping_sha256")):
        if digest(directory / name) != report.get(field):
            raise ValueError(f"Truth artifact hash mismatch: {name}")
    with (directory / "truth.csv").open(newline="") as stream:
        mapping = csv.DictReader(stream)
        if mapping.fieldnames != ["event", "source_entry", "beam_energy_GeV", "generation_weight"]:
            raise ValueError("Invalid truth mapping columns")
        rows = 0
        for entry, row in enumerate(mapping):
            try:
                energy = float(row["beam_energy_GeV"])
                valid = (int(row["event"]) == entry and int(row["source_entry"]) == entry
                         and float(row["generation_weight"]) == 1 and window[0] <= energy <= window[1])
            except (TypeError, ValueError) as error:
                raise ValueError("Invalid truth mapping row") from error
            if not valid:
                raise ValueError("Invalid truth entry, energy or weight mapping")
            rows += 1
        if rows != count:
            raise ValueError("Truth mapping count mismatch")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("geometry", "smoke", "view", "replay"))
    parser.add_argument("--work-dir", type=Path, help="New diagnostic directory; existing paths are refused")
    parser.add_argument("--geant4-prefix", type=Path, help="Installed Geant4 prefix (Spack is optional)")
    parser.add_argument("--gdml", type=Path, help="Explicit existing geometry; default rebuilds the frozen snapshot")
    parser.add_argument("--macro", type=Path, help="Transport macro for smoke mode")
    parser.add_argument("--truth-dir", type=Path, help="Export directory from export_truth.py (replay only)")
    args = parser.parse_args()
    if args.macro and args.mode != "smoke":
        parser.error("--macro requires smoke mode")
    if (args.mode == "replay") != bool(args.truth_dir):
        parser.error("replay requires --truth-dir; other modes do not accept it")
    work = (args.work_dir or ROOT / "results_test" /
            ("geant4-" + args.mode + "-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))).resolve()
    if work.exists():
        raise ValueError(f"Work directory exists; refusing overwrite: {work}")
    truth = validate_truth(args.truth_dir) if args.truth_dir else None
    config = find_geant4(args.geant4_prefix)
    geometry = args.gdml.resolve() if args.gdml else work / "geometry/geometry.gdml"
    macro = (args.macro or MODULE / "macros/smoke.mac").resolve()
    if args.gdml and not geometry.is_file():
        raise ValueError(f"GDML not found: {geometry}")
    if args.mode == "smoke" and not macro.is_file():
        raise ValueError(f"Macro not found: {macro}")
    work.mkdir(parents=True)
    environment = os.environ.copy()
    for name, child in (("TMPDIR", "tmp"), ("MPLCONFIGDIR", "mpl")):
        (work / child).mkdir()
        environment[name] = str(work / child)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    # Windows needs the Geant4 DLL directory; Unix installations use rpaths.
    environment["PATH"] = str(config.parents[2] / "bin") + os.pathsep + environment.get("PATH", "")
    build = work / "build"
    commands = []

    def execute(command, label):
        command = list(map(str, command))
        commands.append(command)
        log = work / (label + ".log")
        print(f"{label}: {log}", flush=True)
        with log.open("w") as stream:
            subprocess.run(command, env=environment, stdout=stream, stderr=subprocess.STDOUT,
                           check=True)

    def binary(name):
        suffix = ".exe" if os.name == "nt" else ""
        candidates = (build / (name + suffix), build / "Release" / (name + suffix))
        return next((path for path in candidates if path.is_file()), candidates[0])

    record = {"status": "incomplete", "mode": args.mode, "geant4_dir": str(config), "commands": commands}
    try:
        if truth:
            copied = work / "truth"
            copied.mkdir()
            for name in ("manifest.json", "truth.csv", "primaries.dat"):
                shutil.copyfile(args.truth_dir / name, copied / name)
            truth = validate_truth(copied)
            record["truth"] = truth
            record["truth_manifest_sha256"] = digest(copied / "manifest.json")
        execute(["cmake", "-S", MODULE, "-B", build, f"-DGeant4_DIR={config}",
                 "-DCMAKE_BUILD_TYPE=Release", "-DBUILD_TESTING=ON",
                 f"-DGRAAL_WITH_QT={'ON' if args.mode == 'view' else 'OFF'}"], "configure")
        execute(["cmake", "--build", build, "--config", "Release", "--parallel", "4"], "build")
        if not args.gdml:
            execute([binary("graal_geometry"), MODULE / "reference/geometry.g3", work / "geometry"], "geometry")
            record["snapshot_sha256"] = digest(MODULE / "reference/geometry.g3")
        record["gdml_sha256"] = digest(geometry)
        record["executable_sha256"] = digest(binary("graal_g4"))
        if args.mode == "smoke":
            record["macro_sha256"] = digest(macro)
            execute([binary("graal_g4"), geometry, macro, work / "events"], "transport")
        elif args.mode == "view":
            execute([binary("graal_g4"), geometry, "--vis", MODULE / "viewer/vis.mac"], "viewer")
        elif args.mode == "replay":
            execute([binary("graal_g4"), geometry, "--hepevt", work / "truth/primaries.dat",
                     work / "events"], "transport")
            summary = json.loads((work / "events/summary.json").read_text())
            if summary["events"] != truth["events"]:
                raise ValueError("Transport count differs from truth manifest")
            if digest(work / "events/primaries.dat") != truth["primary_sha256"]:
                raise ValueError("Transported input differs from truth manifest")
        record["status"] = "diagnostic_complete"
        print(f"Completed {args.mode}: {work}\nDiagnostic only; not production acceptance.")
    finally:
        (work / "run.json").write_text(json.dumps(record, indent=2) + "\n")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
