"""Strict source configuration for selected26 WALL_DEV + run340 SHOW_DEV.

WALL uses calib_4300. Simulation shower reconstruction uses run340 from the
144..391 RW file; SHOW_DEV's separate literal electronics are retained too.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import tempfile

_REPO = Path(__file__).resolve().parents[2]
_FORTRAN = _REPO / "docs/reference/fortran/prog"
_REAL = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][+-]?\d+)?")
WALL_FIELDS = ("pedestals", "tdccal", "gaincards", "timewalk", "tdcoffset", "gainpms")


def _real(token):
    if not _REAL.fullmatch(token):
        raise ValueError(f"Malformed source REAL: {token!r}")
    try:
        value = struct.unpack("f", struct.pack("f", float(token.replace("D", "E").replace("d", "e"))))[0]
    except (OverflowError, struct.error) as exc:
        raise ValueError("Outside source REAL domain") from exc
    if not math.isfinite(value):
        raise ValueError("Nonfinite source REAL")
    return value


def _values(text, count):
    tokens = text.replace(",", " ").split()
    if len(tokens) != count:
        raise ValueError(f"Expected {count} source values, found {len(tokens)}")
    return [_real(token) for token in tokens]


def _table(source, name, count):
    # Fixed form: only code columns, excluding comments; continuation column
    # must never become part of a numeric literal.
    code = "\n".join(line[6:] for line in source.splitlines()
                     if line and line[0] not in "Cc*!#" and len(line) >= 6)
    matches = re.findall(r"\bDATA\s+"+name+r"\s*/([^/]+)/", code, re.I)
    if len(matches) != 1:
        raise ValueError(f"Expected unique source DATA {name}")
    return _values(matches[0], count)


def _rw_run340(text):
    lines = text.splitlines()
    # RW_READ reads a run label then exactly 81 values: RT/RB/AY/BY/BT/AE.
    # Annotated labels are comments after the first integer, as source READ(*,*).
    labels = [i for i, line in enumerate(lines[1:], 1)
              if re.match(r"^\s*340(?:\s|$)", line)]
    if len(labels) != 1:
        raise ValueError("Missing/duplicate simulation RW run340")
    start = labels[0]+1
    values = []
    end = start
    while len(values) < 81 and end < len(lines):
        values.extend(_values(lines[end], len(lines[end].split())))
        end += 1
    if len(values) != 81:
        raise ValueError("Malformed RW run340 value count")
    if end >= len(lines) or not re.match(r"^\s*\d+(?:\s|$)", lines[end]):
        raise ValueError("Missing RW next-run boundary")
    result = dict(rt=values[:16], rb=values[16:32], ay=values[32],
                  by=values[33:49], bt=values[49:65], ae=values[65:81])
    if result["ay"] <= 0 or any(v <= 0 for key in ("rt", "rb", "ae") for v in result[key]):
        raise ValueError("Nonpositive RW run340 divisor")
    return result


def read_selected26_forward(data_directory, *, source_directory=None):
    data = Path(data_directory)
    source = Path(source_directory) if source_directory is not None else _FORTRAN
    wall_path = data / "calib_wall/calib_4300.cal"
    rw_path = data / "calib_rw/rw_calibr_144_391.dat"
    wall_bytes, rw_bytes = wall_path.read_bytes(), rw_path.read_bytes()
    values = _values(wall_bytes.decode("ascii"), 660)
    wall = {key: values[i*110:(i+1)*110] for i, key in enumerate(WALL_FIELDS)}
    for key in ("tdccal", "gaincards", "gainpms"):
        if any(value <= 0 for value in wall[key][:104]):
            raise ValueError(f"Nonpositive used WALL {key} channel1..104")
    show = (source / "lagdig/src/show.F").read_text(encoding="ascii")
    active = show.split("#if defined(GRAAL_SHOW_DEV)")
    if len(active) != 2:
        raise ValueError("Missing/ambiguous active SHOW_DEV branch")
    shower = {name.lower(): _table(active[1], name, 16) for name in ("RT", "RB", "AE", "BU", "BD")}
    ay = re.findall(r"^\s*AY\s*=\s*(\S+)\s*$", active[1], re.M)
    if len(ay) != 1:
        raise ValueError("Missing/ambiguous SHOW_DEV AY")
    shower["ay"] = _real(ay[0])
    if shower["ay"] <= 0 or any(v <= 0 for key in ("rt", "rb", "ae") for v in shower[key]):
        raise ValueError("Nonpositive SHOW_DEV divisor")
    block = (source / "lagdig/src/blockdata.F").read_text(encoding="ascii")
    attenuation = {name.lower(): _table(block, name, count) for name, count in (("ATTN", 6), ("ATTS", 6), ("ATTH", 18))}
    files = [("data/calib_wall/calib_4300.cal", wall_bytes),
             ("data/calib_rw/rw_calibr_144_391.dat", rw_bytes)]
    for name in ("lagdig/src/wall.F", "lagdig/src/show.F", "lagdig/src/wall_att.F",
                 "lagdig/src/blockdata.F", "lagdig/src/wall_read.F", "lagdig/src/wall_choose_file.F",
                 "lagdig/pilot.h", "laggen/src/gustep.F", "laggen/src/lagwrev.F", "prean/src/rw_calibr.F"):
        files.append((name, (source/name).read_bytes()))
    return dict(schema=1, mode="selected26_forward_dev_diagnostic", wall=wall, shower=shower,
                attenuation=attenuation, simulation_rw=_rw_run340(rw_bytes.decode("ascii")),
                sources=[dict(path=name, sha256=hashlib.sha256(payload).hexdigest()) for name, payload in files],
                baseline=["GRAAL_26", "GRAAL_WALL_DEV", "GRAAL_SHOW_DEV", "RW_SIMULATION_RUN340"],
                units=dict(energy="GeV", length="cm", time="s", digits="ADC/TDC integer channels"),
                physics_validation=False, physical_validation=False,
                rng_policy="injected standard normals; independent diagnostic stream; source order",
                compaction_policy="post-step global x(H),y(V/SHOW),time; G4 all-process diagnostic; G3 mechanism22 mapping unknown",
                wall_domain="require initialized horizontal counterpart for each vertical compact record; negative timing partial writes invalid",
                precision="Fortran REAL binary32, integer truncation before pedestal; no fast-math")


def write_forward_config(data_directory, output_root):
    """Atomically publish source tables and JSON metadata in a new ROOT file."""
    import numpy as np
    import uproot
    output = Path(output_root)
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Refusing to overwrite forward configuration: {output}")
    config = read_selected26_forward(data_directory)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{output.name}.", suffix=".partial", dir=output.parent)
    os.close(descriptor)
    partial = Path(temporary)
    try:
        with uproot.recreate(partial, compression=uproot.ZSTD(5)) as root:
            def table(name, values):
                tree = root.mktree(name, {key: "float32" for key in values})
                tree.extend({key: np.asarray(value, dtype="float32") for key, value in values.items()})
            table("wall", config["wall"])
            table("shower", {key: value for key, value in config["shower"].items() if key != "ay"})
            table("scalars", {"shower_ay": [config["shower"]["ay"]], "simulation_rw_ay": [config["simulation_rw"]["ay"]]})
            table("simulation_rw", {key: value for key, value in config["simulation_rw"].items() if key != "ay"})
            for key, values in config["attenuation"].items():
                table(key, {"coefficient": values})
            root["metadata"] = json.dumps(config, sort_keys=True, allow_nan=False)
        with partial.open("rb") as stream:
            os.fsync(stream.fileno())
        os.link(partial, output)
    finally:
        partial.unlink(missing_ok=True)
    return config
