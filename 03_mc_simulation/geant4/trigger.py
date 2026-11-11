#!/usr/bin/env python3
"""Source-backed LAGDIG TRIG diagnostic. No hardware or efficiency claim.

The pure kernel accepts measured post-threshold wall/barrel multiplicities.
An optional independently provenanced forward response supplies measured wall
counts. Unknown decisions are encoded as -1, never rejection.
"""
import argparse
from dataclasses import dataclass
import json
import math
from numbers import Integral, Real
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

import numpy as np
import uproot

from mc_simulation.geant4.digitize import sha256, _write_provenance
from mc_simulation.geant4.legacy_response import _f15_3

MODULE = Path(__file__).resolve().parent
ARCHIVE = MODULE.parents[1] / "docs/reference/fortran/prog"
MODES = ("none", "bgo", "three_particle", "either")


@dataclass(frozen=True)
class TriggerDecision:
    accepted: bool | None
    bgo: bool | None
    three_particle: bool | None
    bit_values: int
    known_bits: int
    itrig: int | None


def _real32(value):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        return None
    if value < 0 or value > float(np.finfo(np.float32).max) or not math.isfinite(value):
        return None
    return float(np.float32(value))


def _count(value, maximum):
    return (int(value) if isinstance(value, Integral) and not isinstance(value, (bool, np.bool_))
            and 0 <= value <= maximum else None)


def evaluate_trigger(mode, bgo_raw_total_GeV, threshold_GeV, *,
                     wall_horizontal=None, wall_vertical=None, barrel=None,
                     response_available=True):
    """Evaluate archived TRIG with binary32 REAL and explicit availability.

    known_bits identifies available components (BGO=1, 3PC=8), including known
    false components. bit_values contains only known true bits; itrig is absent
    until both components are available. None mode always accepts. Either mode
    can accept on one known true component while the full mask stays incomplete.
    Capacities are the archived TOFWALL/BARREL arrays (26/26/32).
    """
    if mode not in MODES:
        raise ValueError(f"Unknown trigger mode: {mode}")
    threshold = _real32(threshold_GeV)
    if threshold is None:
        raise ValueError("Trigger threshold must be a finite nonnegative binary32 value")
    if type(response_available) is not bool:
        raise ValueError("response_available must be bool")
    energy = _real32(bgo_raw_total_GeV) if response_available else None
    counts = [_count(value, maximum) for value, maximum in
              ((wall_horizontal, 26), (wall_vertical, 26), (barrel, 32))]
    bgo = None if energy is None else energy >= threshold
    three = None
    if response_available and all(value is not None for value in counts):
        three = max(counts[:2]) >= 2 and counts[2] >= 1
    known = (1 if bgo is not None else 0) | (8 if three is not None else 0)
    bits = (1 if bgo else 0) | (8 if three else 0)
    enabled = {"none": [], "bgo": [bgo], "three_particle": [three], "either": [bgo, three]}[mode]
    accepted = True if not enabled or any(value is True for value in enabled) else (
        None if any(value is None for value in enabled) else False)
    return TriggerDecision(accepted, bgo, three, bits, known, bits if known == 9 else None)


def read_trigger_config(data_directory, period, historical_run):
    """Only selected data09/data26 record 161, FORMAT(F15.3) -> REAL."""
    if period not in ("09", "26"):
        raise ValueError("Explicit legacy period must be 09 or 26")
    if type(historical_run) is not int or historical_run <= 0 or historical_run > 2**31-1:
        raise ValueError("Explicit positive historical_run required, distinct from transport run")
    path = (Path(data_directory) / f"base/data{period}.base").resolve(strict=True)
    digest = sha256(path)
    lines = path.read_text(encoding="ascii").splitlines()
    if len(lines) < 161 or not re.search(r"!\s*ETOTTHRES(?:\s|$)", lines[160]):
        raise ValueError("Missing source ETOTTHRES record 161")
    threshold = _real32(_f15_3(lines[160]))
    if threshold is None:
        raise ValueError("Invalid source trigger threshold")
    if sha256(path) != digest:
        raise RuntimeError("Trigger database changed while reading")
    return dict(schema=1, legacy_period=period, historical_run=historical_run,
                threshold_GeV=threshold, record=161, precision="F15.3 -> IEEE binary32",
                source_path=str(path), source_sha256=digest, physics_validation=False)


def _json(root, name):
    try:
        value = json.loads(str(root[name]))
        if not isinstance(value, dict):
            raise ValueError("not an object")
        return value
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"Missing/invalid ROOT {name}") from error


def _hash_record(path, digest, label):
    if not isinstance(path, str) or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError(f"Missing immutable {label} SHA256 identity")
    source = Path(path).resolve(strict=True)
    if sha256(source) != digest:
        raise ValueError(f"Immutable {label} SHA256 mismatch")
    return source


def _read_response(path, config):
    """Strict all-event ledger; no auxiliary count is promoted to wall data."""
    with uproot.open(path) as root:
        metadata = _json(root, "metadata")
        selected = _json(root, "config_metadata")
        launcher = _json(root, "launcher_provenance")
        summary = _json(root, "summary")
        transport = _hash_record(launcher.get("input_path"), launcher.get("input_sha256"), "transport")
        if metadata.get("input_path") != launcher["input_path"]:
            raise ValueError("Response/launcher transport identity mismatch")
        if (metadata.get("mode") != "legacy09_diagnostic" or
                selected.get("legacy_period") != "09" or config["legacy_period"] != "09"):
            raise ValueError("Selected trigger period does not match supported legacy09 response")
        if any(type(row.get("historical_run")) is not int or row["historical_run"] != config["historical_run"]
               for row in (metadata, selected)):
            raise ValueError("Selected historical_run does not match response")
        applied = selected.get("applied_sources")
        if not isinstance(applied, list) or not any(
                isinstance(row, dict) and row.get("path") == "base/data09.base"
                and row.get("sha256") == config["source_sha256"] for row in applied):
            raise ValueError("Selected trigger database SHA256 does not match applied response config")
        if (summary.get("status") != "legacy09_diagnostic_complete" or
                summary.get("physics_validation") is not False or type(summary.get("events")) is not int):
            raise ValueError("Response has no valid diagnostic completion summary")
        tree = root["response_events"]
        required = dict(run="int32", event="int32", historical_run="int32", aborted="int32",
                        bgo_raw_total_GeV="float64", barrel_digits="int32", barrel_records="uint64")
        arrays = {}
        for name, dtype in required.items():
            try:
                value = tree[name].array(library="np")
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError(f"Missing/invalid response branch {name}") from error
            if value.ndim != 1 or value.dtype != np.dtype(dtype):
                raise ValueError(f"Wrong response scalar type for {name}: expected {dtype}")
            arrays[name] = value
        try:
            status = tree["status"].array(library="np")
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("Missing response status") from error
        if status.ndim != 1 or any(not isinstance(value, str) for value in status):
            raise ValueError("Wrong response status string type")
        arrays["response_status"] = status
        size = len(status)
        if summary["events"] != size or any(len(value) != size for value in arrays.values()):
            raise ValueError("Response event conservation mismatch")
        keys = list(zip(arrays["run"].tolist(), arrays["event"].tolist()))
        if keys != sorted(set(keys)) or any(run < 0 or event < 0 for run, event in keys):
            raise ValueError("Response event keys must be unique, nonnegative and ordered")
        if np.any(arrays["historical_run"] != config["historical_run"]):
            raise ValueError("Response ledger historical_run mismatch")
        if np.any(~np.isin(arrays["aborted"], [0, 1])) or np.any(arrays["barrel_digits"] < 0) or np.any(arrays["barrel_digits"] > 32):
            raise ValueError("Invalid response count/aborted field")
        energy = arrays["bgo_raw_total_GeV"]
        if np.any(~np.isfinite(energy)) or np.any(energy < 0) or np.any(energy > np.finfo(np.float32).max):
            raise ValueError("Invalid finite nonnegative response BGO energy")
        for index, value in enumerate(status):
            if value not in ("diagnostic_only", "unsupported_barrel_record_overflow"):
                raise ValueError("Unknown response event status")
            overflow = arrays["barrel_records"][index] > 100
            if overflow != (value == "unsupported_barrel_record_overflow"):
                raise ValueError("Response overflow status/count mismatch")
            if overflow and arrays["barrel_digits"][index] != 0:
                raise ValueError("Overflow event contains barrel digits")
    return arrays, dict(transport_path=str(transport), transport_sha256=launcher["input_sha256"],
                        response_metadata=metadata, response_config=selected)


def _uint(metadata, name, maximum=2**64-1):
    value = metadata.get(name)
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError(f"Forward metadata {name} must be an integer in 0..{maximum}")
    return value


def _strict_json(root, name):
    names = [key.rsplit(";", 1)[0] for key in root.keys(cycle=True)]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate forward ROOT key/cycle")

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate forward JSON key")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError(f"Nonfinite forward JSON constant: {value}")

    try:
        obj = root[name]
        text = str(obj)
        if obj.classname != "TObjString" or "\x00" in text:
            raise ValueError("Malformed forward metadata string")
        value = json.loads(text, object_pairs_hook=pairs, parse_constant=invalid_constant)
        if not isinstance(value, dict) or "\\u0000" in text.lower():
            raise ValueError("Malformed forward JSON object")
        return value
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"Missing/invalid forward ROOT {name}: {error}") from error


def _read_forward(path, response, response_lineage):
    """Join complete measured wall counts, independently of reconstruction."""
    path = Path(path).resolve(strict=True)
    provenance_path = path.with_name("provenance.root").resolve(strict=True)
    watched = {path: sha256(path), provenance_path: sha256(provenance_path)}
    with uproot.open(provenance_path) as root:
        provenance = _strict_json(root, "metadata")
    if provenance.get("response_sha256") != watched[path]:
        raise ValueError("Forward output/provenance SHA256 mismatch")
    transport = _hash_record(provenance.get("input_path"), provenance.get("input_sha256"), "forward transport")
    if (str(transport) != response_lineage["transport_path"] or
            provenance["input_sha256"] != response_lineage["transport_sha256"]):
        raise ValueError("Forward and BGO/barrel response use different immutable transports")
    with uproot.open(path) as root:
        metadata = _strict_json(root, "metadata")
        selected = _strict_json(root, "config_metadata")
        summary = _strict_json(root, "summary")
        launcher = _strict_json(root, "launcher_provenance")
        mode = "selected26_forward_reconstruction_diagnostic"
        for item in (metadata, selected, provenance, launcher):
            if (item.get("mode") != mode or item.get("physics_validation") is not False or
                    item.get("physical_validation") is not False):
                raise ValueError("Incomplete/non-diagnostic forward configuration or provenance")
        for item in (metadata, provenance, launcher):
            if item.get("input_path") != str(transport):
                raise ValueError("Forward transport path identity mismatch")
        if launcher.get("input_sha256") != provenance["input_sha256"]:
            raise ValueError("Forward launcher transport SHA256 mismatch")
        if _uint(metadata, "schema_version", 100) != 1 or _uint(selected, "schema", 100) != 1:
            raise ValueError("Unsupported forward metadata schema")
        source_run = _uint(metadata, "source_run", 65535)
        if not isinstance(selected.get("reconstruction"), dict) or _uint(selected["reconstruction"], "source_run", 65535) != source_run:
            raise ValueError("Forward source_run configuration mismatch")
        if not isinstance(selected.get("baseline"), list) or "GRAAL_26" not in selected["baseline"]:
            raise ValueError("Forward selected26 identity missing")
        if _uint(metadata, "seed") != _uint(provenance, "seed") or metadata["seed"] != _uint(launcher, "seed"):
            raise ValueError("Forward seed/provenance mismatch")
        if (summary.get("status") != "selected26_forward_diagnostic_complete" or
                summary.get("physical_validation") is not False or summary.get("physics_validation") is not False or
                _uint(summary, "schema_version", 100) != 1):
            raise ValueError("Incomplete forward diagnostic summary")
        size = _uint(summary, "events")
        unsupported = _uint(summary, "unsupported_events", size)
        particles = _uint(summary, "particles")
        _uint(summary, "normal_draws")
        if provenance.get("summary") != summary:
            raise ValueError("Forward completion summary/provenance mismatch")
        # Validate counter types in both copies: JSON 3 == 3.0 otherwise compares
        # equal and must never bless fractional/bool completion metadata.
        if not isinstance(provenance.get("summary"), dict):
            raise ValueError("Missing forward provenance summary")
        if any(provenance["summary"].get(flag) is not False for flag in ("physical_validation", "physics_validation")):
            raise ValueError("Invalid forward provenance summary validation flags")
        for key in ("schema_version", "events", "unsupported_events", "particles", "normal_draws"):
            _uint(provenance["summary"], key)
        for key in ("tracking_sha256", "config_sha256", "executable_sha256"):
            if not isinstance(provenance.get(key), str) or not re.fullmatch(r"[0-9a-f]{64}", provenance[key]):
                raise ValueError(f"Missing forward provenance {key}")
        for key in ("code_sha256", "legacy_source_sha256"):
            hashes = provenance.get(key)
            if not isinstance(hashes, dict) or not hashes or any(
                    not isinstance(name, str) or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
                    for name, digest in hashes.items()):
                raise ValueError(f"Missing forward source provenance {key}")
        for key in ("tracking_sha256", "executable_sha256", "code_sha256", "legacy_source_sha256"):
            if provenance[key] != launcher.get(key):
                raise ValueError(f"Forward launcher/final provenance mismatch: {key}")
        for name in ("config", "tracking"):
            actual = _hash_record(provenance.get(f"{name}_path"), provenance.get(f"{name}_sha256"), f"forward {name}")
            if metadata.get(f"{name}_path") != str(actual):
                raise ValueError(f"Forward {name} path identity mismatch")
            watched[actual] = provenance[f"{name}_sha256"]
            if name == "config":
                with uproot.open(actual) as config_root:
                    if _strict_json(config_root, "metadata") != selected:
                        raise ValueError("Forward applied configuration metadata mismatch")
        if _uint(selected["reconstruction"], "rf_bunch", 0) != 0 or selected["reconstruction"].get("simulation") is not True:
            raise ValueError("Forward trigger requires declared simulation RF0 profile")
        required = dict(run="int32", event="int32", source_entry="uint64", wall_response_status="int32",
                        wall_response_available="int32", wall_h_accepted="uint64", wall_v_accepted="uint64",
                        association_status="int32", wall_reconstruction_status="int32", particles="uint64")
        arrays = {}
        tree = root["forward_events"]
        if tree.classname != "TTree":
            raise ValueError("Forward event ledger must be a TTree")
        for name, dtype in required.items():
            value = tree[name].array(library="np")
            if value.ndim != 1 or value.dtype != np.dtype(dtype) or len(value) != size:
                raise ValueError(f"Wrong forward scalar type/cardinality: {name}")
            arrays[name] = value
        if (size != len(response["run"]) or not np.array_equal(arrays["run"], response["run"]) or
                not np.array_equal(arrays["event"], response["event"]) or
                not np.array_equal(arrays["source_entry"], np.arange(size, dtype="uint64"))):
            raise ValueError("Forward/BGO event ledgers are not identical and ordered")
        status = arrays["wall_response_status"]
        available = arrays["wall_response_available"]
        if (np.any(status < 0) or np.any(status > 7) or np.any(~np.isin(available, [0, 1])) or
                np.any(available != (status == 0))):
            raise ValueError("Incoherent forward wall response status/availability")
        for name in ("wall_h_accepted", "wall_v_accepted"):
            if np.any(arrays[name] > 26) or np.any(arrays[name][available == 0] != 0):
                raise ValueError("Invalid forward accepted count/unsupported placeholder")
        for name in ("association_status", "wall_reconstruction_status"):
            if np.any(arrays[name] < 0) or np.any(arrays[name] > 3):
                raise ValueError("Invalid forward reconstruction status")
        if unsupported != np.count_nonzero(arrays["association_status"]) or particles != sum(map(int, arrays["particles"])):
            raise ValueError("Forward summary/ledger mismatch")
    return arrays, dict(forward_path=str(path), forward_sha256=watched[path],
                        forward_provenance_path=str(provenance_path), forward_provenance_sha256=watched[provenance_path],
                        forward_metadata=metadata, forward_config=selected, forward_provenance=provenance,
                        configuration_status="mixed_legacy09_BGO_barrel_selected26_forward_diagnostic"), watched


def diagnose_trigger(input_root, mode, period, historical_run, legacy_data, output, *, forward_root=None):
    """Publish config.root, trigger.root and provenance.root as one new directory.

    Every input response row survives in source order. Failed publication removes
    staged ROOT files. An existing destination (including a symlink) is refused.
    """
    if mode not in MODES:
        raise ValueError("Explicit supported trigger mode required")
    source = Path(input_root).resolve(strict=True)
    destination = Path(output).absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Refusing to overwrite trigger diagnostic: {destination}")
    input_digest = sha256(source)
    config = read_trigger_config(legacy_data, period, historical_run)
    watched = {source: input_digest, Path(config["source_path"]): config["source_sha256"]}
    code = [MODULE / "trigger.py", MODULE / "digitize.py", MODULE / "legacy_response.py",
            ARCHIVE / "lagdig/src/trig.F", ARCHIVE / "lagdig/src/bgod.F",
            ARCHIVE / "lagdig/src/dedx.F", ARCHIVE / "lagdig/src/wall.F",
            ARCHIVE / "lagdig/src/constan.F", ARCHIVE / "lagdig/pilot.h"]
    code_hashes = {str(path): sha256(path) for path in code}
    watched.update({Path(path): digest for path, digest in code_hashes.items()})
    arrays, lineage = _read_response(source, config)
    watched[Path(lineage["transport_path"])] = lineage["transport_sha256"]
    forward = None
    if forward_root is not None:
        forward, forward_lineage, forward_watched = _read_forward(forward_root, arrays, lineage)
        lineage.update(forward_lineage)
        watched.update(forward_watched)
    size = len(arrays["run"])
    decisions = [evaluate_trigger(mode, float(arrays["bgo_raw_total_GeV"][i]), config["threshold_GeV"],
                                 wall_horizontal=(int(forward["wall_h_accepted"][i]) if forward is not None
                                                  and forward["wall_response_available"][i] else None),
                                 wall_vertical=(int(forward["wall_v_accepted"][i]) if forward is not None
                                                and forward["wall_response_available"][i] else None),
                                 barrel=int(arrays["barrel_digits"][i]),
                                 response_available=bool(arrays["response_status"][i] == "diagnostic_only"
                                                         and arrays["aborted"][i] == 0)) for i in range(size)]
    summary = dict(status="trigger_diagnostic_complete", events=size,
                   accepted=sum(row.accepted is True for row in decisions),
                   rejected=sum(row.accepted is False for row in decisions),
                   unavailable=sum(row.accepted is None for row in decisions),
                   full_itrig_available=sum(row.itrig is not None for row in decisions), physics_validation=False)
    provenance = dict(schema=1, diagnostic="LAGDIG_TRIG", mode=mode,
                      input_path=str(source), input_sha256=input_digest, **lineage,
                      historical_run=historical_run, legacy_period=period, code_sha256=code_hashes,
                      summary=summary, physics_validation=False, hardware_trigger_validation=False,
                      efficiency_validation=False, wall_response_input_available=forward is not None,
                      wall_response_available=bool(forward is not None and np.all(forward["wall_response_available"])),
                      limitations=[("No measured wall response: 3PC and full ITRIG unavailable" if forward is None else
                                    "Mixed legacy09 BGO/barrel and selected26 forward diagnostic; not homogeneous acquisition"),
                                   "Existing BGO response adaptation is diagnostic; no hardware or efficiency claim",
                                   "Overflow/aborted events unavailable; all response events retained"])
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.", suffix=".pending", dir=destination.parent))
    reserved = False
    try:
        with uproot.create(staging / "config.root", compression=uproot.ZSTD(5)) as root:
            tree = root.mktree("trigger_config", dict(threshold_GeV="float32", historical_run="int32"))
            tree.extend(dict(threshold_GeV=np.asarray([config["threshold_GeV"]], dtype="float32"),
                             historical_run=np.asarray([historical_run], dtype="int32")))
            root["metadata"] = json.dumps(dict(config, mode=mode), sort_keys=True, allow_nan=False)
        values = dict(arrays, source_entry=np.arange(size, dtype="int64"))
        if forward is not None:
            values.update({name: forward[name] for name in ("wall_response_status", "wall_response_available",
                                                          "wall_h_accepted", "wall_v_accepted",
                                                          "wall_reconstruction_status", "association_status")})
        types = {name: ("string" if name == "response_status" else str(value.dtype)) for name, value in values.items()}
        for name in ("accepted", "bgo", "three_particle", "itrig", "known_bits", "bit_values"):
            values[name] = np.asarray([-1 if getattr(row, name) is None else int(getattr(row, name))
                                       for row in decisions], dtype="int32")
            types[name] = "int32"
        with uproot.create(staging / "trigger.root", compression=uproot.ZSTD(5)) as root:
            tree = root.mktree("trigger_events", types)
            if size:
                tree.extend(values)
            root["metadata"] = json.dumps(provenance, sort_keys=True, allow_nan=False)
            root["summary"] = json.dumps(summary, sort_keys=True)
        provenance["config_sha256"] = sha256(staging / "config.root")
        provenance["result_sha256"] = sha256(staging / "trigger.root")
        _write_provenance(staging / "provenance.root", provenance)
        for path, digest in watched.items():
            if sha256(path) != digest:
                raise RuntimeError(f"Input/config/source changed before trigger publication: {path}")
        # Reserve the exact name without replacement, then move the complete
        # bundle under it. The only consumable layout is output/diagnostic/.
        destination.mkdir()
        reserved = True
        staging.rename(destination / "diagnostic")
    except BaseException:
        if reserved:
            destination.rmdir()
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return destination / "diagnostic/trigger.root"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--forward", type=Path, help="optional complete forward.root with sibling provenance.root")
    parser.add_argument("--mode", required=True, choices=MODES)
    parser.add_argument("--period", required=True, choices=("09", "26"))
    parser.add_argument("--historical-run", required=True, type=int)
    parser.add_argument("--legacy-data", type=Path, default=ARCHIVE / "data")
    parser.add_argument("--output", required=True, type=Path, help="new directory; result at diagnostic/trigger.root")
    args = parser.parse_args(argv)
    try:
        result = diagnose_trigger(args.input, args.mode, args.period, args.historical_run, args.legacy_data, args.output,
                                  forward_root=args.forward)
    except (OSError, ValueError, RuntimeError, KeyError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"TRIGGER DIAGNOSTIC ONLY: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
