"""Digit-only OLD_CYL reconstruction versus ORIGINAL archived PREAN routines.

The original source is copied unmodified into an isolated test build. CERNLIB
SORTZV fixture/license is test-only; this is generic CERNLIB source parity,
not proof of the historical h70 executable/configuration lineage.
"""
from pathlib import Path
import os
import math
import random
import shutil
import struct
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[3]
G4 = ROOT / "03_mc_simulation/geant4"
ARCHIVE = ROOT / "docs/reference/fortran/prog/prean"


def run(command, **kwargs):
    env = dict(os.environ, MACOSX_DEPLOYMENT_TARGET="15.0", PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run([str(x) for x in command], text=True, capture_output=True,
                            timeout=120, env=env, **kwargs)
    assert result.returncode == 0, f"{command}\n{result.stdout}\n{result.stderr}"
    return result.stdout


@pytest.fixture(scope="module")
def binaries(tmp_path_factory):
    cpp = shutil.which("c++")
    fort = shutil.which(os.environ.get("GRAAL_FORTRAN_COMPILER", "gfortran"))
    if not cpp or not fort:
        pytest.skip("requires c++ and gfortran (or GRAAL_FORTRAN_COMPILER)")
    build = tmp_path_factory.mktemp("central-tracking-oracle")
    (build / "GRAAL_machine.h").write_text("/* Controlled oracle machine. */\n")
    (build / "pilot.h").write_text("#define GRAAL_26\n#define GRAAL_NEW_PLAN\n#define GRAAL_OLD_CYL\n")
    (build / "kerngen").mkdir()
    (build / "kerngen/pilot.h").write_text("/* Generic CERNLIB implementation. */\n")
    source_dir = build / "track"
    source_dir.mkdir()
    sources = []
    for name in ("initialisation_cylindres", "analyse_cylindre_cathode_2",
                 "recherche_clusters", "analyse_cylindre_fils_1", "association_cylindres",
                 "association_chambres", "teta_phi_trace_calcul"):
        target = source_dir / f"{name}.F"
        shutil.copyfile(ARCHIVE / "src" / target.name, target)
        sources.append(target)
    for name in ("parametres_cylindres", "geometrie_cylindres", "piedestaux_cylindres",
                 "clusters_cylindres", "chamber", "groupes_cylindres", "event",
                 "associations_cylindres", "traces_cylindres", "lflag", "prean_const"):
        shutil.copyfile(ARCHIVE / "include" / f"{name}.inc", build / f"{name}.inc")
    modern, original = build / "check", build / "oracle"
    run([cpp, "-std=c++17", "-O2", "-fno-fast-math", "-ffp-contract=off",
         "-Wall", "-Wextra", "-Werror", "-I", G4 / "src",
         G4 / "tests/check_cylinder_tracking.cc", "-o", modern])
    run([fort, "-O0", "-std=legacy", "-fcheck=all", "-fno-fast-math", "-ffp-contract=off",
         "-ffixed-line-length-none", "-cpp", "-DGRAAL_NEW_PLAN", "-DGRAAL_OLD_CYL",
         "-I", build, G4 / "tests/cylinder_tracking_oracle.F", *sources,
         G4 / "tests/reference/cernlib/sortzv.F", "-o", original])
    return modern, original


def encode(cases):
    lines = [str(len(cases))]
    numbers = lambda values: " ".join(format(v, ".9g") for v in values)
    for case in cases:
        mode = 2 if "angle" in case else int("config" in case)
        lines.append(str(mode))
        if mode == 2:
            lines.append(numbers(case["angle"]))
            continue
        if mode == 1:
            c = case["config"]
            lines.extend(numbers(row) for row in c["cathodes"])
            lines.extend(numbers(row) for row in c["chambers"])
            lines.append(numbers([c["dphi"]]))
        for wires in case.get("wires", [[], []]):
            lines.append(str(len(wires)))
            if wires:
                lines.append(numbers(wires))
        for strips in case.get("strips", [[], [], [], []]):
            lines.append(str(len(strips)))
            lines.extend(numbers(s) for s in strips)
    return "\n".join(lines) + "\n"


def decode(output, cases):
    tokens = iter(int(x) for x in output.split())
    discrete, real_values = [], []

    def exact(n):
        discrete.extend(next(tokens) for _ in range(n))

    def real_values_at(n, tolerance):
        for _ in range(n):
            bits = next(tokens)
            real_values.append((struct.unpack("f", struct.pack("i", bits))[0], tolerance))

    for case in cases:
        if "angle" in case:
            exact(1)
            real_values_at(2, 0.0002)
            continue
        exact(2)  # unsupported + original composed status
        exact(16)  # source default/config REAL coefficient bits are exact
        for _ in range(4):
            n = next(tokens)
            discrete.append(n)
            exact(1)
            exact(3*n)  # cluster multiplicity/center/charge bits exact
        for _ in range(2):
            n = next(tokens)
            discrete.append(n)
            exact(1)
            exact(2*n)  # group multiplicity/phi bits exact
        for _ in range(2):
            n = next(tokens)
            discrete.append(n)
            exact(1)
            exact(10*n)  # all association fields/REAL bits/links exact
        n = next(tokens)
        discrete.append(n)
        for _ in range(n):
            exact(4)  # association links and DZ bits exact
            real_values_at(6, 0.00002)  # xyz cm
            exact(1)  # DPHI bits exact
            real_values_at(2, 0.0002)  # theta/phi degrees
            real_values_at(1, 0.00002)  # vertex z cm
    assert next(tokens, None) is None
    return discrete, real_values


def compare(cases, binaries):
    payload = encode(cases)
    modern = decode(run([binaries[0]], input=payload), cases)
    original = decode(run([binaries[1]], input=payload), cases)
    assert modern[0] == original[0], "Defined discrete fields/order/links or pre-track REAL bits differ"
    assert len(modern[1]) == len(original[1])
    # clang/libSystem may fuse sin/cos into __sincosf_stret while gfortran uses
    # separate libm entries. Keep strict binary32, allow the measured small
    # transcendental-library differences only in endpoints/derived angles.
    for (actual, tolerance), (expected, _) in zip(modern[1], original[1]):
        assert abs(actual-expected) <= tolerance, (actual, expected, tolerance)
    return modern


def controlled(dz=.35, dphi=8, min_multi=2):
    # Explicit test geometry maps cluster centers to z. No production override.
    return {"cathodes": [[0, -1, 0, 40, .2, 0, 2, min_multi, 0] for _ in range(4)],
            "chambers": [[0, 0, 100, dz], [0, 0, 100, dz]], "dphi": dphi}


def f32(value):
    return struct.unpack("f", struct.pack("f", value))[0]


def neighbor(value, offset):
    bits = struct.unpack("I", struct.pack("f", value))[0]
    return struct.unpack("f", struct.pack("I", bits + offset))[0]


def test_explicit_unsupported_and_independent_expected_cases(binaries):
    assert "fixtures passed" in run([binaries[0], "--selftest"])


def test_original_empty_noise_threshold_periodic_and_overlap(binaries):
    patterns = [[], [(1, 0), (2, -1)], [(1, 10)], [(1, 10), (2, 20)],
                [(59, 10), (60, 20), (1, 30), (2, 10)],
                [(1, 10), (2, 30), (3, 5), (4, 4), (5, 40), (6, 10)],
                [(1, 10), (2, 30), (3, 4), (4, 40), (5, 10)],
                [(1, 10), (2, 30), (3, 30), (4, 30), (5, 10)],
                [(2, 10), (2, 20), (3, 30)],
                [(i, 10) for i in range(1, 61)]]
    cases = [{"strips": [pattern, [], [], []]} for pattern in patterns]
    for p, n in enumerate((60, 64, 96, 96)):
        for pattern in ([(n-1, 10), (n, 20), (1, 30), (2, 10)],
                        [(i, 10) for i in range(1, n+1)],
                        [(i, 10) for i in range(1, n+1, 2)]):
            strips = [[], [], [], []]
            strips[p] = pattern
            cases.append({"strips": strips})
    config = controlled()
    config["cathodes"][0][5] = 10  # charge==threshold is excluded.
    cases.append({"config": config, "strips": [[(1, 10), (2, 11)], [], [], []]})
    rng = random.Random(260901)
    for _ in range(350):
        strips = [[(k, rng.randint(-10, 20000)) for k in rng.sample(range(1, n+1), rng.randrange(n+1))]
                  for n in (60, 64, 96, 96)]
        cases.append({"strips": strips})
    compare(cases, binaries)


def test_original_associations_sharing_ties_cuts_and_overflows(binaries):
    pair = [(10, 10), (11, 10)]
    strips = [pair] * 4
    cases = [{"config": controlled(), "wires": wires, "strips": strips}
             for wires in ([[1], [1]], [[128], [192]], [[1, 2], [1, 2]],
                           [[1, 1], [1, 1]], [[1, 2, 3, 4, 5], [1, 2, 3, 4, 5]],
                           [[1, 2, 3, 4, 5, 6], [1]], [[1] * 21, [1]],
                           [[1], [1] * 21])]
    # DPHI equality is accepted, DZ equality rejected (binary32 neighbors).
    for dphi in [neighbor(.46875, -1), .46875, neighbor(.46875, 1)]:
        cases.append({"config": controlled(dphi=dphi), "wires": [[1], [1]], "strips": strips})
    for cut in [neighbor(.25, -1), .25, neighbor(.25, 1)]:
        config = controlled(dz=cut)
        for p in (1, 3):
            config["cathodes"][p][4] = .45
        cases.append({"config": config, "wires": [[1], [1]], "strips": strips})
    # Inclusive active-z endpoint; strict total charge cut; negative/positive wrap.
    for value in [neighbor(4., -1), 4., neighbor(4., 1)]:
        config = controlled()
        config["chambers"][0][2] = value
        cases.append({"config": config, "wires": [[1], [1]], "strips": strips})
    for charge in (19, 20, 21):
        config = controlled()
        config["cathodes"][0][8] = charge
        cases.append({"config": config, "wires": [[1], [1]], "strips": strips})
    for offsets in ((-2, 0), (360, 360), (0, -360)):
        config = controlled(dphi=360)
        for ch in range(2):
            config["chambers"][ch][0] = offsets[ch]
        cases.append({"config": config, "wires": [[1, 128], [1, 192]], "strips": strips})
    # Two independent cathode candidates, sharing remains permitted per wire.
    candidates = pair + [(30, 10), (31, 20)]
    cases.append({"config": controlled(), "wires": [[1, 2, 3], [1, 2]], "strips": [candidates] * 4})
    rng = random.Random(260902)
    for _ in range(500):
        wires = [[rng.randint(1, n) for _ in range(rng.randrange(1, 6))] for n in (128, 192)]
        cases.append({"config": controlled(dphi=360), "wires": wires, "strips": [candidates] * 4})
    # Actual source profile, every wire and cathode response in plausible digits.
    for wire in range(1, 129):
        cases.append({"wires": [[wire], [1 + (wire-1)*192//128]],
                      "strips": [[(k, 10), (k+1, 20)] for k in (10, 20, 30, 40)]})
    compare(cases, binaries)


def test_original_degenerate_x_and_angle_quadrants(binaries):
    cases = [{"angle": [0, 0, 0, *delta]} for delta in
             ([0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1],
              [1, 1, 1], [-1, 1, 1], [-1, -1, 1], [1, -1, 1])]
    compare(cases, binaries)


def test_original_default_simulation_profile_complete_tracks_every_azimuth(binaries):
    # Generate measured two-strip ADC fixtures by searching channel combinations
    # with the documented geometry. These are inputs, never expected outputs.
    angles = [33.86, -41.01, 41.01, -46.63]
    radii = [4.6, 5.4, 8.1, 8.9]
    counts = [60, 64, 96, 96]
    coefficients = [(-r/math.tan(math.radians(a))*math.pi/180,
                     -1/math.sin(math.radians(a))) for r, a in zip(radii, angles)]
    cases = []
    for inner_wire in range(1, 129):
        outer_wire = 1 + (inner_wire-1)*192//128
        strips = []
        for chamber, (wire, nf) in enumerate(((inner_wire, 128), (outer_wire, 192))):
            phi = (wire-.5)*360/nf
            candidates = []
            for p in (2*chamber, 2*chamber+1):
                a, b = coefficients[p]
                options = []
                for k in range(1, counts[p]):
                    z = a*phi-b*(.4*k)
                    if z < 0:
                        z += 360*abs(a)
                    if 0 <= z <= (39 if chamber == 0 else 49.5):
                        options.append((k, z))
                candidates.append(options)
            k1, k2 = min(((x, y) for x in candidates[0] for y in candidates[1]),
                         key=lambda pair: abs(pair[0][1]-pair[1][1]))
            strips.extend([[(k, 10), (k+1, 10)] for k in (k1[0], k2[0])])
        cases.append({"wires": [[inner_wire], [outer_wire]], "strips": strips})
    result = compare(cases, binaries)
    assert len(result[1]) == 128*9  # Every azimuth yields a complete track.
