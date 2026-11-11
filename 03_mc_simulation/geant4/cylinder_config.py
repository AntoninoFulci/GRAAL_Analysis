"""Strict selected26 OLD_CYL configuration, independent of legacy09 response.

Original CONSTAN record formats and REAL conversion apply. The ROOT product
contains source configuration, LAGFILL-derived constants and provenance only.
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
RECORDS = {
    "rc1_cm": (79, "RC1"), "rc2_cm": (80, "RC2"),
    "zc1_cm": (81, "ZC1"), "zc2_cm": (82, "ZC2"),
    "pc1_cm": (90, "PC1"), "pc2_cm": (91, "PC2"),
    "nf1": (92, "NF1"), "nf2": (93, "NF2"),
    "nfc1": (94, "NFC1"), "nfc2": (95, "NFC2"),
    **{f"nb{i}": (95+i, f"NB{i}") for i in range(1, 5)},
    "bl_cm": (100, "BL"), "dfca_cm": (101, "DFCA"),
    "sccat": (103, "SCCAT"), "vsccat": (104, "VSCCAT"),
    "conv": (105, "CONV"), "cythre": (106, "CYTHRE"),
    "sigce1": (107, "SIGCE(1)"), "sigct": (108, "SIGCT"),
    **{f"angle{i}_deg": (109+i, f"ANG({i})") for i in range(1, 6)},
    "effcyc1": (116, "EFFCYC(1)"), "effcyc2": (117, "EFFCYC(2)"),
    "nbord": (162, "NBORD"),
    **{f"sigce{i}": (164+i, f"SIGCE({i})") for i in range(2, 5)},
}
INTEGER_KEYS = {"nf1", "nf2", "nfc1", "nfc2", "nb1", "nb2", "nb3", "nb4", "nbord"}


def _real(value):
    try:
        result = struct.unpack("f", struct.pack("f", value))[0]
    except (OverflowError, struct.error) as error:
        raise ValueError("Outside source REAL domain") from error
    if not math.isfinite(result):
        raise ValueError("Nonfinite source REAL")
    return result


def _f15_3(line):
    if len(line) < 15:
        raise ValueError("Truncated F15.3 field")
    token = line[:15].strip()
    if not _REAL.fullmatch(token):
        raise ValueError("Malformed F15.3 field")
    value = float(token.replace("D", "E").replace("d", "e"))
    if "." not in token:
        value /= 1000
    return _real(value)


def _i5(line):
    if len(line) < 5 or not re.fullmatch(r"[+-]?\d+", line[:5].strip()):
        raise ValueError("Malformed I5 field")
    return int(line[:5])


def _list_real(line):
    token = line.split("!", 1)[0].strip()
    if not _REAL.fullmatch(token):
        raise ValueError("Malformed list-directed REAL")
    return _real(float(token.replace("D", "E").replace("d", "e")))


def _validate(c):
    expected = dict(nf1=320, nf2=384, nfc1=128, nfc2=192, nb1=60, nb2=64, nb3=96, nb4=96)
    if any(c[key] != value for key, value in expected.items()) or c["angle5_deg"] != -45:
        raise ValueError("Requires selected26 NEW_PLAN + OLD_CYL channel layout")
    for key in ("rc1_cm", "rc2_cm", "zc1_cm", "zc2_cm", "bl_cm", "dfca_cm", "sccat", "vsccat", "conv"):
        if c[key] <= 0:
            raise ValueError(f"Nonpositive cylinder scale: {key}")
    if c["dfca_cm"] >= min(c["rc1_cm"], c["rc2_cm"]):
        raise ValueError("Cathode radius is nonpositive")
    if c["sccat"] != int(c["sccat"]) or c["sccat"] > 1e6:
        raise ValueError("ADC scale must be a bounded integer")
    if not 0 <= c["nbord"] <= 60:
        raise ValueError("Neighbor range outside source single-wrap domain")
    for key in ("cythre", "sigct", "sigce1", "sigce2", "sigce3", "sigce4"):
        if c[key] < 0:
            raise ValueError(f"Negative response parameter: {key}")
    for key in ("effcyc1", "effcyc2"):
        if not 0 <= c[key] <= 1:
            raise ValueError(f"Invalid efficiency: {key}")
    for i in range(1, 5):
        if not 0 < abs(c[f"angle{i}_deg"]) < 90:
            raise ValueError("Unsupported stereo angle")


def _derived(c):
    """LAGFILL REAL assignments, with non-CERNLIB_SINGLE gconsp constants."""
    r = {}
    for ch in (1, 2):
        r[f"ri{ch}_cm"] = _real(c[f"rc{ch}_cm"] - c["dfca_cm"])
        r[f"re{ch}_cm"] = _real(c[f"rc{ch}_cm"] + c["dfca_cm"])
        r[f"ucf{ch}_cm"] = _real(6.28318530717958648 * c[f"rc{ch}_cm"])
    for i in range(1, 5):
        angle = _real(c[f"angle{i}_deg"] * 0.0174532925199432958)
        s, co = _real(math.sin(angle)), _real(math.cos(angle))
        radius = r[f"r{'i' if i % 2 else 'e'}{(i+1)//2}_cm"]
        uc = _real(6.28318530717958648 * radius)
        xbl = _real(uc * co)
        be = _real(_real(xbl / c[f"nb{i}"]) - c["bl_cm"])
        if xbl <= 0 or be < 0:
            raise ValueError("Source strip pitch cannot contain the strip width")
        r.update({f"sang{i}": s, f"cang{i}": co, f"xbl{i}_cm": xbl, f"be{i}_cm": be})
    return r


def read_selected26_cylinder(data_directory):
    payload = (Path(data_directory) / "base/data26.base").read_bytes()
    lines = payload.decode("ascii").splitlines()
    c = {}
    for key, (record, label) in RECORDS.items():
        if len(lines) < record or not re.match(r"\s*"+re.escape(label)+r"(?:\s|=|$)", lines[record-1].split("!", 1)[-1]):
            raise ValueError(f"Missing selected26 field label {label} at record {record}")
        reader = _i5 if key in INTEGER_KEYS else (_list_real if key in ("sigce2", "sigce3", "sigce4") else _f15_3)
        c[key] = reader(lines[record-1])
    _validate(c)
    c.update(_derived(c))
    sources = [dict(path="base/data26.base", sha256=hashlib.sha256(payload).hexdigest())]
    for path in ("lagdig/src/constan.F", "lagdig/src/cych_old.F", "lagdig/src/lagstrip_old.F",
                 "lagdig/src/lagfill.F", "lagdig/src/lagangle.F", "lagdig/src/laglwh.F",
                 "lagdig/src/lagmod.F", "lagdig/src/lagrota.F", "prean/src/initialisation_cylindres.F",
                 "laggen/src/gustep.F", "laggen/src/lagwrev.F", "lagdig/src/histo.F"):
        sources.append(dict(path=path, sha256=hashlib.sha256((_FORTRAN/path).read_bytes()).hexdigest()))
    tracker = (_FORTRAN / "prean/src/initialisation_cylindres.F").read_text()
    half_lengths = []
    for name in ("ZC1", "ZC2"):
        match = re.search(r"^\s*"+name+r"\s*=\s*(\d+(?:\.\d*)?)\s*$", tracker, re.M)
        if not match:
            raise ValueError(f"Cannot extract source tracking half length {name}")
        half_lengths.append(_real(float(match.group(1))))
    return dict(schema=1, mode="selected26_old_cyl_diagnostic", **c,
                baseline=["GRAAL_26", "GRAAL_NEW_PLAN", "GRAAL_OLD_CYL"],
                physical_validation=False, physics_validation=False,
                units=dict(length="cm", energy="GeV", charge="electrons", angle="degree"),
                sources=sources, records={key: record for key, (record, _) in RECORDS.items()},
                precision="CONSTAN F15.3/I5/list-directed fields rounded to REAL binary32; gconsp DOUBLE constants",
                tracking_profile=dict(mode="INITIALISATION_CYLINDRES_OLD_CYL_LSIMUL",
                                      half_lengths_cm=half_lengths, source=sources[9]),
                gas_floor_GeV=_real(1e-7), gas_mapping="GUSTEP shared SAVE, all-callback passive epochs",
                outer_rotation_center="PC1, as CYCH_OLD source",
                rng_policy="injected NORRAN/HRNDM; independent diagnostic stream; no historical stream claim",
                initialization="safe zero extension; strict source state unknown until first passive epoch")


def write_cylinder_config(data_directory, output_root):
    """Publish new ROOT scalars + JSON TObjString metadata; refuse replacement."""
    import numpy as np
    import uproot
    output = Path(output_root)
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Refusing to overwrite cylinder configuration: {output}")
    config = read_selected26_cylinder(data_directory)
    scalars = {key: value for key, value in config.items() if type(value) in (int, float)}
    # schema/physical flags belong in metadata, not detector constants.
    scalars.pop("schema")
    descriptor, temporary = tempfile.mkstemp(prefix=f".{output.name}.", suffix=".partial", dir=output.parent)
    os.close(descriptor)
    partial = Path(temporary)
    try:
        with uproot.recreate(partial, compression=uproot.ZSTD(5)) as root:
            types = {key: "int32" if key in INTEGER_KEYS else "float64" for key in scalars}
            tree = root.mktree("scalars", types)
            tree.extend({key: np.asarray([value], dtype=types[key]) for key, value in scalars.items()})
            root["metadata"] = json.dumps(config, sort_keys=True, allow_nan=False)
        with partial.open("rb") as stream:
            os.fsync(stream.fileno())
        os.link(partial, output)
    finally:
        partial.unlink(missing_ok=True)
    return config
