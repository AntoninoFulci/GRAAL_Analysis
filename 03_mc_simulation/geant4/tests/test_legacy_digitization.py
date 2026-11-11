"""Pure period09 arithmetic against original Fortran, never archived binaries.

The oracle compiles unmodified archived sources and original COMMON includes in
pytest's disposable campaign directory. Its replacement pilot selects 09 and
its injected EXT_GAUS gives deterministic draw-count/order comparisons. This is
an arithmetic test, not GEANT3/GEANT4 transport or HBOOK serialization parity.
"""
from copy import deepcopy
from pathlib import Path
import os
import random
import shutil
import struct
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[3]
G4 = ROOT / "03_mc_simulation/geant4"
ARCHIVE = ROOT / "docs/reference/fortran/prog/lagdig"


def real(value):
    return struct.unpack("f", struct.pack("f", value))[0]


def neighbor(value, delta):
    """Adjacent positive binary32 values, rather than binary64 nextafter."""
    bits = struct.unpack("I", struct.pack("f", value))[0]
    return struct.unpack("f", struct.pack("I", bits + delta))[0]


@pytest.fixture(scope="module")
def config():
    lines = (ROOT / "docs/reference/fortran/prog/data/base/data09.base").read_text().splitlines()
    scalar = lambda line: real(float(lines[line - 1][:15]))
    # Preserve CONSTAN's REAL division, including historical CLIGHT=3.e10.
    light = real(real(3.e10) / scalar(155))
    return {
        "scalars": [scalar(n) for n in (2, 3, 4, 40, 41, 42, 43, 83, 152, 153, 154)] + [light],
        "enabled": 1,
        "attenuation": [[real(float(v)) for v in line.split()[:4]] for line in lines[45:77]],
    }


def run(command, **kwargs):
    result = subprocess.run([str(part) for part in command], text=True, capture_output=True,
                            timeout=120, **kwargs)
    assert result.returncode == 0, f"{command}\n{result.stdout}\n{result.stderr}"
    return result.stdout


@pytest.fixture(scope="module")
def binaries(tmp_path_factory):
    compiler = shutil.which("c++")
    fortran = shutil.which(os.environ.get("GRAAL_FORTRAN_COMPILER", "gfortran"))
    if not compiler or not fortran:
        pytest.skip("pure legacy oracle requires c++ and gfortran (or GRAAL_FORTRAN_COMPILER)")
    build = tmp_path_factory.mktemp("legacy09-oracle")
    source = build / "src"
    source.mkdir()
    # Exact source copies preserve the original relative ../pilot.h include.
    for name in ("bgod.F", "dedx.F", "atdedx.F"):
        shutil.copyfile(ARCHIVE / "src" / name, source / name)
    for name in ("nthit", "bgo", "datbgo", "itrig", "barrel", "datdex", "datvert", "nthead"):
        shutil.copyfile(ARCHIVE / "include" / f"{name}.inc", build / f"{name}.inc")
    (build / "GRAAL_machine.h").write_text("/* Controlled oracle: no machine-specific macros. */\n")
    (build / "pilot.h").write_text("#define GRAAL_09\n#define GRAAL_OLD_CYL\n")
    cpp, oracle = build / "kernel-check", build / "fortran-oracle"
    run([compiler, "-std=c++17", "-O2", "-fno-fast-math", "-ffp-contract=off",
         "-Wall", "-Wextra", "-Werror", "-I", G4 / "src",
         G4 / "tests/check_legacy_digitization.cc", "-o", cpp])
    run([fortran, "-O0", "-std=legacy", "-fcheck=all", "-fno-fast-math", "-ffp-contract=off",
         "-ffixed-line-length-none", "-cpp", "-DGRAAL_OLD_CYL", "-I", build,
         G4 / "tests/legacy_digitization_oracle.F",
         *[source / name for name in ("bgod.F", "dedx.F", "atdedx.F")], "-o", oracle])
    return cpp, oracle


def encode(cases, default_config):
    def numbers(values):
        return " ".join(format(v, ".9g") for v in values)
    lines = [str(len(cases))]
    for case in cases:
        c = case.get("config", default_config)
        lines.append(numbers([*c["scalars"], c["enabled"]]))
        lines.extend(numbers(row) for row in c["attenuation"])
        lines.append(str(case["mode"]))
        if case["mode"] in (1, 2):
            lines.append(str(len(case["hits"])))
            lines.extend(numbers(hit) for hit in case["hits"])
        if case["mode"] == 2:
            draws = case.get("draws", [0] * 132)
            lines.append(str(len(draws)))
            if draws:
                lines.append(numbers(draws))
        if case["mode"] == 3:
            lines.append(numbers(case["position"]))
    return "\n".join(lines) + "\n"


def compare(cases, config, binaries):
    payload = encode(cases, config)
    modern = run([binaries[0]], input=payload).split()
    historical = run([binaries[1]], input=payload).split()
    assert modern == historical, "C++ output/draw count/raw-REAL bits differ from original Fortran"


def test_independently_expected_fixtures_and_invalid_boundaries(binaries):
    assert "fixtures passed" in run([binaries[0], "--selftest"])


def test_original_bgod_threshold_rounding_neighbors_and_saturation(config, binaries):
    cases = [{"mode": 1, "hits": hits} for hits in (
        [], [(1, .01)], [(1, .09)], [(1, 1), (480, 1)], [(1, 1.2901)],
        [(i, .0019) for i in range(1, 51)], [(i, .002) for i in range(1, 481)])]
    scale, full = config["scalars"][:2]
    for count in (0, 1, 2, 3, 4, 15, 16, 100, 2047, 2048, 2049):
        edge = real((count + .5) * full / scale)
        for delta in (-2, -1, 0, 1, 2):
            cases.append({"mode": 1, "hits": [(1, neighbor(edge, delta))]})
    rng = random.Random(9026)
    for _ in range(40):
        channels = sorted(rng.sample(range(1, 481), rng.randint(0, 100)))
        cases.append({"mode": 1, "hits": [(ch, rng.uniform(0, .02)) for ch in channels]})
    compare(cases, config, binaries)


def test_original_dedx_thresholds_draw_order_negative_contributions_and_times(config, binaries):
    threshold, zc3 = config["scalars"][6:8]
    cases = [{"mode": 2, "hits": hits} for hits in (
        [], [(1, .001, -zc3, 10.e-9)], [(1, .001, zc3, 0)],
        [(1, .001, -zc3, -10.e-9)], [(1, 1, 0, 0)],
        [(i % 32 + 1, .001, 0, 0) for i in range(100)])]
    for delta in (-1, 0, 1):
        cases.append({"mode": 2, "hits": [(1, neighbor(threshold, delta), 0, 0)]})
        cases.append({"mode": 2, "hits": [(1, .001, 0, neighbor(real(100.e-9), delta))]})
    # Accepted suppressed records consume energy draws; rejected late records
    # consume none; surviving time draws follow first-seen unique-bar order.
    cases.extend([
        {"mode": 2, "hits": [(3, .001, -zc3, 0), (1, .001, 0, 0),
                              (3, .002, -zc3, 20.e-9)], "draws": [-10, 0, 0, 0, 1000]},
        {"mode": 2, "hits": [(2, .001, 0, neighbor(real(100.e-9), 1)),
                              (3, 1.e-7, 0, 0), (1, .001, 0, 0)], "draws": [1, 2, -100]},
        {"mode": 2, "hits": [(1, .001, 0, 0)], "draws": [-100]},
        {"mode": 2, "hits": [(1, .001, -zc3, 0)], "draws": [0, -100]},
        {"mode": 2, "hits": [(1, .001, 0, 0)], "draws": [0, 1000]},
    ])
    scale, full = config["scalars"][3:5]
    for count in (3, 4, 10, 89, 2047, 2048):
        edge = real((count + .5) * full / scale)
        for delta in (-1, 0, 1):
            cases.append({"mode": 2, "hits": [(1, neighbor(edge, delta), 0, 0)]})
    # TDC half-channel neighbors use z=-ZC3 so there is no propagation term.
    tdc_scale, tdc_full = config["scalars"][8:10]
    for count in (0, 1, 10, 175, 176, 1000, 1760):
        edge = real((count + .5) * tdc_full / tdc_scale)
        for delta in (-1, 0, 1):
            cases.append({"mode": 2, "hits": [(1, .001, -zc3, neighbor(edge, delta))]})
    rng = random.Random(909)
    for _ in range(40):
        hits = [(rng.randint(1, 32), rng.uniform(0, .003), rng.uniform(-zc3, zc3),
                 rng.uniform(-1.e-9, 101.e-9)) for _ in range(rng.randint(0, 100))]
        cases.append({"mode": 2, "hits": hits, "draws": [rng.gauss(0, 1) for _ in range(132)]})
    compare(cases, config, binaries)


def test_original_atdedx_all_database_rows_and_generic_old_ratio(config, binaries):
    zc3 = config["scalars"][7]
    cases = [{"mode": 3, "position": (ch, z)}
             for ch in range(1, 33) for z in (-zc3, 0, zc3)]
    generic = deepcopy(config)
    generic["attenuation"] = [[.2 + ch / 100, .01, .1, .02] for ch in range(32)]
    cases.extend({"mode": 3, "position": (ch, z), "config": generic}
                 for ch in range(1, 33) for z in (-zc3, 0, zc3))
    disabled = deepcopy(generic)
    disabled["enabled"] = 0
    cases.extend({"mode": 3, "position": (ch, zc3), "config": disabled} for ch in range(1, 33))
    # Also exercise attenuation inside DEDX and its draw/rounding path.
    cases.append({"mode": 2, "hits": [(ch, .001, (-1) ** ch * zc3, 0) for ch in range(1, 33)],
                  "config": generic})
    compare(cases, config, binaries)
