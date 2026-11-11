"""Measured central associations versus original, unmodified PREAN source.

No CA clustering or truth input. No oracle execution on undefined N3=0
BGO+barrel domains. Source REAL precision is retained; transcendental-derived
DEDX allows 3e-6 relative/absolute tolerance across libm implementations.
"""
from pathlib import Path
import math
import os
import random
import shutil
import struct
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[3]
G4 = ROOT / "03_mc_simulation/geant4"
ARCHIVE = ROOT / "docs/reference/fortran/prog/prean"


def run(command, **kwargs):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", MACOSX_DEPLOYMENT_TARGET="15.0")
    completed = subprocess.run([str(x) for x in command], text=True, capture_output=True,
                               timeout=120, env=env, **kwargs)
    assert completed.returncode == 0, f"{command}\n{completed.stdout}\n{completed.stderr}"
    return completed.stdout


@pytest.fixture(scope="module")
def binaries(tmp_path_factory):
    cpp = shutil.which("c++")
    fort = shutil.which(os.environ.get("GRAAL_FORTRAN_COMPILER", "gfortran"))
    if not cpp or not fort:
        pytest.skip("requires C++ and Fortran compilers")
    build = tmp_path_factory.mktemp("central-association-oracle")
    (build / "GRAAL_machine.h").write_text("/* Controlled original-source oracle. */\n")
    (build / "pilot.h").write_text("#define GRAAL_ASSOCIA_CYLBGO_BAR\n#define GRAAL_BGO_SP\n")
    source = build / "src"
    source.mkdir()
    sources = []
    for name in ("associa_2_new", "associa_3_new", "find_track_cbb", "delta_phi"):
        target = source / f"{name}.F"
        shutil.copyfile(ARCHIVE / "src" / target.name, target)
        sources.append(target)
    for name in ("angle", "pm_b_b", "parametres_cylindres", "traces_cylindres",
                 "ass_cbb", "coeff", "prean_const", "event"):
        shutil.copyfile(ARCHIVE / "include" / f"{name}.inc", build / f"{name}.inc")
    modern, original = build / "check", build / "oracle"
    run([cpp, "-std=c++17", "-O2", "-fno-fast-math", "-ffp-contract=off",
         "-Wall", "-Wextra", "-Werror", "-I", G4 / "src",
         G4 / "tests/check_central_association.cc", "-o", modern])
    run([fort, "-O0", "-std=legacy", "-fcheck=all", "-fno-fast-math", "-ffp-contract=off",
         "-ffixed-line-length-none", "-cpp", "-DGRAAL_ASSOCIA_CYLBGO_BAR", "-DGRAAL_BGO_SP",
         "-I", build, G4 / "tests/central_association_oracle.F", *sources, "-o", original])
    return modern, original


def bgo(theta=90, phi=0, raw_theta=None, raw_phi=None, energy=100):
    return [theta, phi, theta if raw_theta is None else raw_theta,
            phi if raw_phi is None else raw_phi, energy]


def encode(cases):
    lines = [str(len(cases))]
    def row(values):
        lines.append(" ".join(format(v, ".9g") for v in values))
    for case in cases:
        good, sp, bar, cyl = (case.get(k, []) for k in ("good", "sp", "bar", "cyl"))
        row([len(good), len(sp), len(bar), len(cyl), 1])
        angles = case.get("phi", [i*11.25 for i in range(32)])
        xba = case.get("xba", [.07]*32)
        for pair in zip(angles, xba):
            row(pair)
        for record in good+sp+bar+cyl:
            row(record)
    return "\n".join(lines)+"\n"


def decode(output, cases):
    tokens = iter(int(x) for x in output.split())
    discrete, real = [], []
    for _ in cases:
        status, n2, n3, links = [next(tokens) for _ in range(4)]
        discrete.extend([status, n2, n3, links])
        discrete.extend(next(tokens) for _ in range(2*n2))
        for _ in range(n3):
            discrete.extend(next(tokens) for _ in range(6))
            real.append(struct.unpack("f", struct.pack("i", next(tokens)))[0])
            # All measured/emitted fields and priorities are bit-exact;
            # only attenuation/path-corrected DEDX involves transcendental math.
            discrete.extend(next(tokens) for _ in range(9))
    assert next(tokens, None) is None
    return discrete, real


def compare(cases, binaries):
    payload = encode(cases)
    modern = decode(run([binaries[0]], input=payload), cases)
    original = decode(run([binaries[1]], input=payload), cases)
    assert modern[0] == original[0], "source indices/order/classification/observables differ"
    for actual, expected in zip(modern[1], original[1]):
        assert math.isclose(actual, expected, rel_tol=3e-6, abs_tol=3e-6), (actual, expected)
    return modern


def test_explicit_failures_and_hand_checked_observables(binaries):
    assert "fixtures passed" in run([binaries[0], "--selftest"])


def test_original_empty_pure_mixed_sp_and_priorities(binaries):
    cases = [{}, {"good": [bgo()]}, {"bar": [[1, 0, 3, 4]]}, {"cyl": [[90, 0]]},
             {"sp": [bgo(60, 45, 70, 47)]},
             {"good": [bgo(60, 45)], "cyl": [[61, 46]]},
             {"bar": [[1, 0, 2, 3]], "cyl": [[90, 0]]},
             {"good": [bgo(60, 45)], "bar": [[5, -1, 2, 3]], "cyl": [[61, 46]]},
             {"sp": [bgo(60, 45, 70, 47)], "bar": [[5, -5, 2, 3]], "cyl": [[60, 45]]},
             {"sp": [bgo(60, 45, 70, 47)], "bar": [[5, 0, 2, 3]], "cyl": [[180, 90]]}]
    for problem in (-6, -5, -1, 0):
        cases.append({"bar": [[2, problem, 2, 3]], "cyl": [[90, 11.25]]})
    compare(cases, binaries)


def test_original_wrap_boundaries_last_ties_and_unmatched_order(binaries):
    cases = []
    for theta in (0, 23.999, 24, 24.001, 90, 155.999, 156, 156.001, 180):
        cases.append({"good": [bgo(theta if 0<theta<180 else 90, 0)], "bar": [[1, 0, 2, 3]], "cyl": [[theta, 0]]})
    for delta in (11.499, 11.5, 11.501):
        cases.append({"good": [bgo(90, 0)], "cyl": [[90+delta, 0]]})
    for angle in (11.499, 11.5, 11.501, 348.5, 359, 360, -1):
        cases.append({"good": [bgo(90, 0)], "bar": [[1, 0, 2, 3]], "cyl": [[90, angle]]})
        cases.append({"good": [bgo(90, 45)], "bar": [[1, 0, 2, 3]], "cyl": [[90, angle]]})
    for n in (1, 2, 3, 5):
        cases.append({"good": [bgo()]*n, "bar": [[1, 0, 2, 3]]*n, "cyl": [[90, 0]]*n})
    cases.extend([
        {"good": [bgo(90, 180), bgo(90, 0)], "bar": [[1, 0, 2, 3], [2, -1, 4, 5]], "cyl": [[90, 90]]},
        {"good": [bgo(90, 0), bgo(90, 0)], "bar": [[1, 0, 2, 3]], "cyl": [[90, 0]]},
        {"good": [bgo(90, 0)], "bar": [[1, 0, 2, 3]], "cyl": [[90, 0], [90, 0]]},
    ])
    compare(cases, binaries)


def test_original_near90_path_and_source_capacities(binaries):
    cases = [{"bar": [[1, 0, 2, 3]], "cyl": [[theta, 0]]}
             for theta in (24.001, 60, 89.899, 89.9, 89.901, 90, 90.099, 90.1, 90.101, 120, 155.999)]
    cases.extend([
        {"good": [bgo(40+i, i*11) for i in range(30)],
         "sp": [bgo(50+i, i*12, 51+i, i*12+1) for i in range(30)],
         "bar": [[i+1, 0, 10, 20] for i in range(32)], "cyl": [[90, i*70] for i in range(5)]},
        {"good": [bgo(50, 100)]*30, "sp": [bgo(70, 200)]*30,
         "bar": [[i+1, 0, 10, 20] for i in range(32)], "cyl": [[1, 0]]*5, "phi": [0]*32},
    ])
    compare(cases, binaries)
    # All 60 BGO + 5 excluded cylinders + 32 barrels remain disjoint.
    output = run([binaries[0]], input=encode([cases[-1]]))
    assert [int(x) for x in output.split()[:4]] == [0, 65, 97, 97]


def test_original_random_measured_objects(binaries):
    rng = random.Random(261109)
    cases = []
    for _ in range(700):
        case = {"good": [bgo(rng.uniform(25, 155), rng.uniform(-360, 720)) for _ in range(rng.randrange(7))],
                "sp": [bgo(rng.uniform(25, 155), rng.uniform(0, 360), rng.uniform(25, 155), rng.uniform(0, 360)) for _ in range(rng.randrange(4))],
                "bar": [[rng.randint(1, 32), rng.choice([-6, -5, -1, 0]), rng.uniform(0, 50), rng.uniform(-1, 20)] for _ in range(rng.randrange(8))],
                "cyl": [[rng.uniform(0, 180), rng.uniform(-360, 720)] for _ in range(rng.randrange(1, 6))]}
        cases.append(case)
    compare(cases, binaries)
