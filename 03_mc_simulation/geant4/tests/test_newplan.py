"""Exact binary32 NEW_PLAN comparison against unmodified archived Fortran.

Only the test driver injects COMMON inputs, HRNDM draws and output formatting.
SORTZV is CERNLIB generic reference, not an asserted historical binary identity:
https://github.com/apc-llc/cernlib/blob/ef83476ab09eed4972aff95685fcb27c24e6a18c/2006/src/packlib/kernlib/kerngen/tcgen/sortzv.F
SHA256 384ef84ca682f103d14b5aa67c6538d73d73091f2cba491fa234e506ec26f263.
The GPL oracle fixture/license in reference/cernlib is never linked production.
"""
from pathlib import Path
import os
import random
import shutil
import struct
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[3]
G4 = ROOT / "03_mc_simulation/geant4"
ARCHIVE = ROOT / "docs/reference/fortran/prog"
GEOMETRY = [48, 57.6, 94.4, 134.4, 320, 384, -45]


def run(command, **kwargs):
    env = dict(os.environ, MACOSX_DEPLOYMENT_TARGET="15.0", PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run([str(p) for p in command], text=True, capture_output=True,
                            timeout=120, env=env, **kwargs)
    assert result.returncode == 0, f"{command}\n{result.stdout}\n{result.stderr}"
    return result.stdout


@pytest.fixture(scope="module")
def binaries(tmp_path_factory):
    cpp = shutil.which("c++")
    fort = shutil.which(os.environ.get("GRAAL_FORTRAN_COMPILER", "gfortran"))
    if not cpp or not fort:
        pytest.skip("requires c++ and gfortran (or GRAAL_FORTRAN_COMPILER)")
    build = tmp_path_factory.mktemp("newplan-oracle")
    (build / "GRAAL_machine.h").write_text("/* Controlled oracle machine. */\n")
    (build / "pilot.h").write_text("#define GRAAL_26\n#define GRAAL_NEW_PLAN\n#define GRAAL_OLD_CYL\n")
    (build / "kerngen").mkdir()
    shutil.copyfile(G4 / "tests/reference/cernlib/gconsp.inc", build / "gconsp.inc")
    (build / "kerngen/pilot.h").write_text("/* Generic CERNLIB implementation. */\n")
    sources = []
    for namespace, component, kernels, includes in (
        ("digit", "lagdig", ("plch", "lagrota", "laglwh"),
         ("nthit", "chamber_inter", "lagvert", "datvert", "datpla")),
        ("track", "prean", ("anapln4", "anapln_clusters", "transfo"),
         ("chamber", "dime", "cham_geom", "event", "lflag", "servizio", "prean_const")),
    ):
        directory = build / namespace
        directory.mkdir()
        for name in kernels:
            path = directory / f"{name}.F"
            shutil.copyfile(ARCHIVE / component / "src" / f"{name}.F", path)
            sources.append(path)
        for name in includes:
            shutil.copyfile(ARCHIVE / component / "include" / f"{name}.inc",
                            directory / f"{name}.inc")
    modern, original = build / "check", build / "oracle"
    run([cpp, "-std=c++17", "-O2", "-fno-fast-math", "-ffp-contract=off",
         "-Wall", "-Wextra", "-Werror", "-I", G4 / "src",
         G4 / "tests/check_newplan.cc", "-o", modern])
    run([fort, "-O0", "-std=legacy", "-fcheck=all", "-fno-fast-math", "-ffp-contract=off",
         "-ffixed-line-length-none", "-cpp", "-DGRAAL_NEW_PLAN", "-DGRAAL_OLD_CYL",
         "-I", build, "-I", build / "digit", "-I", build / "track",
         G4 / "tests/newplan_oracle.F", *sources,
         G4 / "tests/reference/cernlib/sortzv.F", "-o", original])
    return modern, original


def encode(cases):
    lines = [str(len(cases))]
    numbers = lambda values: " ".join(format(v, ".9g") for v in values)
    for case in cases:
        mode = case["mode"]
        lines.append(str(mode))
        if mode == 3:
            lines.extend([str(len(case["values"])), numbers(case["values"])])
            continue
        lines.append(numbers(case.get("geometry", GEOMETRY)))
        if mode == 1:
            hits = case["hits"]
            lines.append(str(len(hits)))
            lines.extend(numbers(hit) for hit in hits)
            draws = case.get("draws", [1] * len(hits))
            lines.append(str(len(draws)))
            if draws:
                lines.append(numbers(draws))
        else:
            lines.append(numbers([len(w) for w in case["wires"]]))
            lines.extend(numbers(w) for w in case["wires"] if w)
    return "\n".join(lines) + "\n"


def compare(cases, binaries):
    payload = encode(cases)
    modern = run([binaries[0]], input=payload).split()
    # ANAPLN_CLUSTERS intentionally emits its original duplicate warnings.
    original = run([binaries[1]], input=payload)
    original = "\n".join(line for line in original.splitlines() if "DOUBLE HIT" not in line).split()
    assert modern == original, "C++ values/order/REAL bits differ from unmodified Fortran"


def real(value):
    return struct.unpack("f", struct.pack("f", value))[0]


def neighbor(value, delta):
    bits = struct.unpack("I", struct.pack("f", value))[0]
    return struct.unpack("f", struct.pack("I", bits + delta))[0]


def test_independent_expected_and_unsupported_cases(binaries):
    assert "fixtures passed" in run([binaries[0], "--selftest"])


def test_cern_sortzv_ties_and_non_tied_order(binaries):
    cases = [{"mode": 3, "values": values} for values in
             ([], [1], [1, 1], [1] * 256, [2, 1, 2, 1, 3, 3, 0], list(range(256)), list(range(255, -1, -1)))]
    rng = random.Random(26)
    cases += [{"mode": 3, "values": [rng.randrange(10) for _ in range(n)]} for n in range(2, 257)]
    compare(cases, binaries)


def test_original_plch_order_duplicates_efficiency_and_negative_integer_neighbors(binaries):
    cases = [{"mode": 1, "hits": hits} for hits in
             ([], [(0, 0, 0)], [(p, 0, 0) for p in range(4)],
              [(2, .9, 0), (2, -.3, 0), (2, .9, 0)],
              [(3, 0, 4), (1, 3, 1), (2, -3, 0), (0, 2, -1)])]
    for angle in (-45, 45, 0, 17.3, -71.7):
        geom = GEOMETRY[:-1] + [angle]
        cases.append({"mode": 1, "geometry": geom, "hits": [(p, 3, 4) for p in range(4)]})
    for count in range(-190, 191):
        edge = real(real(count) * real(.3))
        for delta in (-1, 0, 1):
            value = neighbor(edge, delta) if edge else 0
            cases.append({"mode": 1, "hits": [(2, value, 0), (3, 0, value)]})
    # Each wire, including channels 1/N; exact negative integer quirk and
    # address0->1 are tested separately from safe wire-bin interiors.
    for p in range(4):
        n = 320 if p < 2 else 384
        half = 48 if p < 2 else 57.6
        for wire in range(1, n + 1):
            coordinate = real((wire - .5) * .3 - half)
            cases.append({"mode": 1, "geometry": GEOMETRY[:-1] + [0],
                          "hits": [(p, coordinate if p % 2 == 0 else 0,
                                     coordinate if p % 2 else 0)]})
    hits = [(3, 1, 1), (0, 2, 2), (2, 3, 3), (0, 2, 2), (1, 4, 4)]
    cases += [{"mode": 1, "hits": hits, "draws": draws} for draws in ([0] * 5, [1] * 5, [0, 1, 0, 1, 1])]
    cases.append({"mode": 1, "hits": [(0, 49, 0), (0, 50, 0)], "geometry": GEOMETRY[:-1] + [0]})
    rng = random.Random(2601)
    for _ in range(100):
        hits = [(p, rng.uniform(-20, 20), rng.uniform(-20, 20)) for p in range(4) for _ in range(rng.randrange(21))]
        rng.shuffle(hits)
        cases.append({"mode": 1, "hits": hits, "draws": [rng.randrange(2) for _ in hits]})
    compare(cases, binaries)


def test_original_anapln4_missing_views_limits_clusters_and_tracks(binaries):
    cases = [{"mode": 2, "wires": wires} for wires in
             ([[], [], [], []], [[160], [161], [192], [193]],
              [[140, 180], [150, 190], [170, 210], [160, 220]],
              [[160, 161, 162], [160, 161], [190], [200]],
              [[162, 161, 160], [161, 160], [190], [200]],
              [[1], [320], [1], [384]], [[1], [], [], []],
              [[1, 10], [], [1], [1]], [[1] * 21, [1], [1], [1]],
              [[1, 10, 20, 30, 40]] * 4,
              [[140, 150, 160], [160], [190], [200]],
              [[160, 160], [161], [190], [200]])]
    for p in range(4):
        wires = [[160], [161], [192], [193]]
        wires[p] = []
        cases.append({"mode": 2, "wires": wires})
    for angle in (-45, 45, 0, 17.3, -71.7):
        for wire in range(1, 321):
            cases.append({"mode": 2, "geometry": GEOMETRY[:-1] + [angle],
                          "wires": [[wire], [321 - wire], [wire], [385 - wire]]})
    rng = random.Random(2602)
    for _ in range(400):
        # One track, plus extra unrelated-plane candidates exercises sorted
        # greedy selection and every confidence class without undefined output.
        counts = [1] + [rng.randrange(1, 5) for _ in range(3)]
        rng.shuffle(counts)
        wires = [rng.sample(range(1, 321 if p < 2 else 385), n) for p, n in enumerate(counts)]
        cases.append({"mode": 2, "wires": wires})
    compare(cases, binaries)


def inspect_tracking(cases, binaries):
    """Inspect explicit modern status without reading undefined legacy outputs."""
    tokens = iter(run([binaries[0]], input=encode([{**case, "mode": 4} for case in cases])).split())
    records = []
    for _ in cases:
        status, candidates, count, confidence = [int(next(tokens)) for _ in range(4)]
        reduced = [int(next(tokens)) for _ in range(4)]
        tracks = [[int(next(tokens)) for _ in range(5)] for _ in range(count)]
        records.append((status, candidates, count, confidence, reduced, tracks))
    assert next(tokens, None) is None
    return records


def test_original_multitrack_defined_domain_and_collision_boundary(binaries):
    rng = random.Random(2603)
    cases = []
    for n in (2, 3, 4):
        for _ in range(150):
            cases.append({"mode": 2, "wires": [rng.sample(range(1, 321 if p < 2 else 385), n)
                                                  for p in range(4)]})
    # Exact rotational symmetries produce tied scores and transformed-coordinate
    # reuse; preserve CERN ordering and reject only the undefined count cases.
    for angle in (-45, 45, 0):
        for first in (1, 50, 150, 160):
            cases.append({"mode": 2, "geometry": GEOMETRY[:-1] + [angle],
                          "wires": [[first, 321-first], [first, 321-first],
                                    [first, 385-first], [first, 385-first]]})
    statuses = inspect_tracking(cases, binaries)
    defined = [case for case, result in zip(cases, statuses) if result[0] == 0]
    assert len(defined) >= 400
    assert all(result[0] in (0, 128) for result in statuses)
    assert any(result[2] >= 2 for result in statuses)
    compare(defined, binaries)

    duplicate = {"mode": 2, "wires": [[10, 10], [20, 20], [30, 30], [40, 40]]}
    result = inspect_tracking([duplicate], binaries)[0]
    assert result[:3] == (128, 16, 0)  # CoordinateCollision; zero valid tracks.
    legacy = run([binaries[1]], input=encode([duplicate]))
    tokens = "\n".join(line for line in legacy.splitlines() if "DOUBLE HIT" not in line).split()
    assert int(tokens[0]) == 2
    # Original says two tracks but only initializes the first. The sentinel
    # CL proves the mismatch; never make goldens from its endpoint storage.
    assert int(tokens[11]) == -999
