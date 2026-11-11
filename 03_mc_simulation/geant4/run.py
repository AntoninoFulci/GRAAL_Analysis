#!/usr/bin/env python3
"""Build and run isolated Geant4 diagnostics on macOS, Linux and Windows."""
import argparse
from contextlib import contextmanager, nullcontext
import csv
from datetime import datetime
import hashlib
import json
import math
import os
import secrets
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

MODULE = Path(__file__).resolve().parent
ROOT = MODULE.parents[1]


def transport_seed(seed, *, excluded=()):
    """Draw OS entropy once per launch; retain explicit seeds for exact replay."""
    if seed is not None:
        if type(seed) is not int or not 1 <= seed <= 2**31-1:
            raise ValueError("seed must be in [1, 2147483647]")
        return seed, "explicit"
    while True:
        value = secrets.randbelow(2**31-1) + 1
        if value not in excluded:
            return value, "os_entropy"


def transport_threads(value, mode, truth):
    """None means historical serial; explicit integers select native MT even at 1."""
    supported = mode == "replay" and truth is not None and truth["schema_version"] == 2
    if value == "serial" or (value == "auto" and not supported):
        return None
    if value == "auto":
        count = getattr(os, "process_cpu_count", os.cpu_count)()
        if hasattr(os, "sched_getaffinity"):
            count = min(count or 1, len(os.sched_getaffinity(0)))
        return max(1, count or 1)
    if not value.isascii() or not value.isdecimal() or not 1 <= int(value) <= 2**31-1:
        raise ValueError("threads must be auto, serial, or an integer in [1, 2147483647]")
    if not supported:
        raise ValueError("Explicit threads require ROOT replay")
    return int(value)


@contextmanager
def single_transport(path):
    """OS lock: released on exit/crash; never unlink the shared lock inode."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as lock:
        if os.name == "nt":
            import msvcrt
            if path.stat().st_size == 0:
                lock.write(b"\0")
                lock.flush()
            lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as error:
                raise RuntimeError("A Geant4 transport job is already running") from error
        else:
            import fcntl
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise RuntimeError("A Geant4 transport job is already running") from error
        try:
            yield lock
        finally:
            if os.name == "nt":
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            # POSIX: close, never explicit LOCK_UN. The native child inherits this
            # open-file description and retains exclusion if its launcher dies.


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
    if (directory / "truth.root").exists():
        try:
            from .export_truth import validate_root_truth
        except ImportError:
            from export_truth import validate_root_truth
        return validate_root_truth(directory / "truth.root")
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


def validate_replay_completion(truth, input_path, summary):
    """Recheck transported inputs and source provenance before marking a run complete."""
    input_path = Path(input_path)
    root_replay = truth["schema_version"] == 2
    if summary["events"] != truth["events"]:
        raise ValueError("Transport count differs from truth manifest")
    if root_replay and (summary.get("source_mode") != "root_replay"
            or summary.get("input_source") != str(input_path)
            or summary.get("input_md5") != hashlib.md5(input_path.read_bytes()).hexdigest()):
        raise ValueError("Transport ROOT input identity differs from truth")
    if digest(input_path) != truth["truth_root_sha256" if root_replay else "primary_sha256"]:
        raise ValueError("Transported input differs from truth manifest")
    if root_replay and validate_truth(input_path.parent) != truth:
        raise ValueError("Truth provenance changed during build or transport")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("geometry", "smoke", "view", "replay"))
    parser.add_argument("--work-dir", type=Path, help="New diagnostic directory; existing paths are refused")
    parser.add_argument("--geant4-prefix", type=Path, help="Installed Geant4 prefix (Spack is optional)")
    parser.add_argument("--gdml", type=Path, help="Explicit existing geometry; default rebuilds the frozen snapshot")
    parser.add_argument("--macro", type=Path, help="Transport macro for smoke mode")
    parser.add_argument("--storage", choices=("compact", "full"), default="compact",
                        help="Transport output: compact response inputs (default), or full diagnostic steps")
    parser.add_argument("--threads", default="auto", metavar="auto|serial|N",
                        help="ROOT replay: all available CPUs by default; serial preserves historical RNG")
    parser.add_argument("--truth-dir", type=Path, help="Export directory from export_truth.py (replay only)")
    parser.add_argument("--period", help="Apply published target and observed XY conditions for this period")
    parser.add_argument("--conditions", type=Path, default=ROOT / "config/support/target_conditions_current",
                        help="Published target conditions directory")
    parser.add_argument("--seed", type=int, help="Reproducible seed with --period; default draws and records OS entropy")
    args = parser.parse_args()
    if args.macro and args.mode != "smoke":
        parser.error("--macro requires smoke mode")
    if (args.mode == "replay") != bool(args.truth_dir):
        parser.error("replay requires --truth-dir; other modes do not accept it")
    if args.period and (args.gdml or args.mode == "view"):
        parser.error("--period derives its own GDML and supports geometry, smoke or replay")
    if args.seed is not None and not args.period:
        parser.error("--seed requires --period")
    if args.seed is not None and not 0 < args.seed <= 2**31-1:
        parser.error("seed must be in [1, 2147483647]")
    work = (args.work_dir or ROOT / "results_test" /
            ("geant4-" + args.mode + "-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))).resolve()
    if work.exists():
        raise ValueError(f"Work directory exists; refusing overwrite: {work}")
    truth = validate_truth(args.truth_dir) if args.truth_dir else None
    threads = transport_threads(args.threads, args.mode, truth)
    if threads and os.environ.get("G4FORCENUMBEROFTHREADS") is not None:
        raise ValueError("Unset G4FORCENUMBEROFTHREADS; use --threads")
    if truth and truth["schema_version"] == 2 and not args.period:
        raise ValueError("ROOT truth replay requires --period")
    period = None
    if args.period:
        from period_conditions import load_period, validate_period_truth, write_inputs
        period = load_period(args.conditions, args.period)
        if truth:
            validate_period_truth(period, truth)
    config = find_geant4(args.geant4_prefix)
    geometry = args.gdml.resolve() if args.gdml else work / "geometry/geometry.gdml"
    macro = (args.macro or MODULE / "macros/smoke.mac").resolve()
    if args.gdml and not geometry.is_file():
        raise ValueError(f"GDML not found: {geometry}")
    if args.mode == "smoke" and not macro.is_file():
        raise ValueError(f"Macro not found: {macro}")
    guard = single_transport(ROOT / "results_test/geant4-runtime/transport.lock") if args.mode in ("smoke", "replay") else nullcontext()
    with guard as job_lock:
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
                               check=True, **({"pass_fds": (job_lock.fileno(),)}
                                              if job_lock and os.name != "nt" else {}))

        def binary(name):
            suffix = ".exe" if os.name == "nt" else ""
            candidates = (build / (name + suffix), build / "Release" / (name + suffix))
            return next((path for path in candidates if path.is_file()), candidates[0])

        record = {"status": "incomplete", "mode": args.mode, "geant4_dir": str(config), "commands": commands}
        if period:
            args.seed, record["seed_policy"] = transport_seed(
                args.seed, excluded={truth["seed"]} if truth else ())
            record["seed"] = args.seed
        if args.mode in ("smoke", "replay"):
            record["storage_mode"] = args.storage
            record["execution_mode"] = "multithreaded" if threads else "serial"
            record["threads"] = threads or 1
        # Persist entropy before invoking any producer, including failed/interrupted builds.
        (work / "run.json").write_text(json.dumps(record, indent=2) + "\n")
        try:
            condition_args = []
            snapshot = MODULE / "reference/geometry.g3"
            if period:
                inputs = work / "conditions"
                inputs.mkdir()
                record["period_conditions"] = write_inputs(period, inputs, snapshot, seed=args.seed)
                record["period_manifest_sha256"] = digest(inputs / "period.json")
                snapshot = inputs / "geometry.g3"
                condition_args = ["--conditions", inputs / "conditions.dat"]
            if truth:
                copied = work / "truth"
                copied.mkdir()
                artifacts = ("truth.root",) if truth["schema_version"] == 2 else ("manifest.json", "truth.csv", "primaries.dat")
                for name in artifacts:
                    shutil.copyfile(args.truth_dir / name, copied / name)
                copied_truth = validate_truth(copied)
                if copied_truth != truth:
                    raise ValueError("Truth changed while copying the replay input")
                truth = copied_truth
                record["truth"] = truth
                if truth["schema_version"] == 2:
                    record["truth_root_sha256"] = digest(copied / "truth.root")
                else:
                    record["truth_manifest_sha256"] = digest(copied / "manifest.json")
            execute(["cmake", "-S", MODULE, "-B", build, f"-DGeant4_DIR={config}",
                     "-DCMAKE_BUILD_TYPE=Release", "-DBUILD_TESTING=ON",
                     f"-DGRAAL_WITH_QT={'ON' if args.mode == 'view' else 'OFF'}"], "configure")
            execute(["cmake", "--build", build, "--config", "Release", "--parallel", "4"], "build")
            if not args.gdml:
                execute([binary("graal_geometry"), snapshot, work / "geometry"], "geometry")
                record["snapshot_sha256"] = digest(snapshot)
            record["gdml_sha256"] = digest(geometry)
            record["executable_sha256"] = digest(binary("graal_g4"))
            if args.mode == "smoke":
                record["macro_sha256"] = digest(macro)
                execute([binary("graal_g4"), geometry, macro, work / "events", *condition_args,
                         "--storage", args.storage], "transport")
            elif args.mode == "view":
                execute([binary("graal_g4"), geometry, "--vis", MODULE / "viewer/vis.mac"], "viewer")
            elif args.mode == "replay":
                root_replay = truth["schema_version"] == 2
                input_path = work / "truth" / ("truth.root" if root_replay else "primaries.dat")
                execute([binary("graal_g4"), geometry, "--root-events" if root_replay else "--hepevt",
                         input_path, work / "events", *condition_args,
                         *(["--threads", threads] if threads else []), "--storage", args.storage], "transport")
                from root_output import read_json
                summary = read_json(work / "events/transport.root")
                if threads and (summary.get("execution_mode") != "multithreaded" or summary.get("threads") != threads):
                    raise ValueError("Transport thread configuration differs from launcher")
                validate_replay_completion(truth, input_path, summary)
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
