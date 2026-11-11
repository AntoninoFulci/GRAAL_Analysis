"""Original selected26 CYCH_OLD routines versus pure C++ binary32 port."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import random
import shutil
import struct
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[3]
G4 = ROOT / "03_mc_simulation/geant4"
ARCHIVE = ROOT / "docs/reference/fortran/prog"


def run(command, **kwargs):
    env = dict(os.environ, MACOSX_DEPLOYMENT_TARGET="15.0", PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run([str(x) for x in command], capture_output=True, text=True,
                            timeout=120, env=env, **kwargs)
    assert result.returncode == 0, f"{command}\n{result.stdout}\n{result.stderr}"
    return result.stdout


@pytest.fixture(scope="module")
def binaries(tmp_path_factory):
    cpp, fort = shutil.which("c++"), shutil.which("gfortran")
    if not cpp or not fort:
        pytest.skip("requires c++ and gfortran")
    build = tmp_path_factory.mktemp("central-response-oracle")
    (build / "GRAAL_machine.h").write_text("/* Controlled oracle machine. */\n")
    (build / "pilot.h").write_text("#define GRAAL_26\n#define GRAAL_NEW_PLAN\n#define GRAAL_OLD_CYL\n")
    digit = build / "digit"
    digit.mkdir()
    (build / "geant321").mkdir()
    shutil.copyfile(G4 / "tests/reference/cernlib/gconsp.inc", build / "geant321/gconsp.inc")
    sources = []
    manifest = []
    for name in ("cych_old", "lagstrip_old", "lagfill", "lagangle", "laglwh", "lagmod", "lagrota"):
        source = ARCHIVE / "lagdig/src" / f"{name}.F"
        dest = digit / source.name
        shutil.copyfile(source, dest)
        sources.append(dest)
        manifest.append(dict(path=str(source.relative_to(ROOT)), sha256=hashlib.sha256(source.read_bytes()).hexdigest()))
    for name in ("nthit", "chamber_inter", "lagvert", "datvert", "datcyc", "c_strip"):
        shutil.copyfile(ARCHIVE / "lagdig/include" / f"{name}.inc", digit / f"{name}.inc")
    modern, original, accumulator = build / "modern", build / "original", build / "accumulator"
    flags = ["-std=c++17", "-O2", "-fno-fast-math", "-ffp-contract=off", "-Wall", "-Wextra", "-Werror", "-I", G4 / "src"]
    run([cpp, *flags, G4 / "tests/check_cylinder_response.cc", "-o", modern])
    run([cpp, *flags, G4 / "tests/check_cylinder_input.cc", "-o", accumulator])
    run([fort, "-O0", "-std=legacy", "-fcheck=all", "-fno-fast-math", "-ffp-contract=off",
         "-ffixed-line-length-none", "-cpp", "-DGRAAL_26", "-DGRAAL_NEW_PLAN", "-DGRAAL_OLD_CYL",
         "-I", build, "-I", digit, G4 / "tests/cylinder_response_oracle.F", *sources, "-o", original])
    (build / "central-response-oracle-sources.json").write_text(json.dumps(manifest, indent=2)+"\n")
    return modern, original, accumulator


def config():
    spec = importlib.util.spec_from_file_location("cylinder_config", G4 / "cylinder_config.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    c = module.read_selected26_cylinder(ARCHIVE / "data")
    keys = ["rc1_cm", "rc2_cm", "zc1_cm", "zc2_cm", "pc1_cm", "pc2_cm", "nfc1", "nfc2",
            "nb1", "nb2", "nb3", "nb4", "bl_cm", "dfca_cm", "sccat", "vsccat", "conv", "cythre",
            "sigce1", "sigce2", "sigce3", "sigce4", "sigct", "angle1_deg", "angle2_deg", "angle3_deg", "angle4_deg",
            "effcyc1", "effcyc2", "nbord"]
    return [c[k] for k in keys]


def encode(cases):
    lines = [str(len(cases))]
    fmt = lambda xs: " ".join(format(v, ".9g") for v in xs)
    for case in cases:
        hits = case.get("hits", [])
        lines += [fmt(case.get("config", config())), str(len(hits))]
        lines += [fmt(hit) for hit in hits]
        draws = case.get("normal", [0] * (316+len(hits)))
        eff = case.get("efficiency", [1] * len(hits))
        lines += [str(len(draws)), fmt(draws), str(len(eff)), fmt(eff)]
    return "\n".join(lines)+"\n"


def compare(cases, binaries):
    payload = encode(cases)
    modern = run([binaries[0]], input=payload).split()
    original = run([binaries[1]], input=payload).split()
    assert modern == original, next(((i, a, b) for i, (a, b) in enumerate(zip(modern, original)) if a != b), "different token counts")


def test_expected_status_links_noise_and_accumulator(binaries):
    assert "response fixtures passed" in run([binaries[0], "--selftest"])
    assert "input fixtures passed" in run([binaries[2]])


def test_original_empty_noise_only_saturation_and_cyclic_neighbors(binaries):
    cases = [{}, {"normal": [4]*316}, {"normal": [1000]*316}]
    for strip in (0, 59, 60, 123, 124, 219, 220, 315):
        normal = [.2] * 316
        normal[strip] = 3
        cases.append(dict(normal=normal))
    compare(cases, binaries)


def test_original_threshold_adc_boundaries_and_negative_total_charge(binaries):
    c = config()
    c[18:22] = [1]*4  # SIGCE; inject exact source-REAL charges directly.
    cases = []
    def neighbor(value, offset):
        bits = struct.unpack("I", struct.pack("f", value))[0]
        return struct.unpack("f", struct.pack("I", bits+offset))[0]
    for value in (6000., 400000., 400000./1024*.5, 400000./1024*1.5):
        for delta in (-1, 0, 1):
            normal = [0.]*316
            normal[0] = 6001.
            normal[1] = neighbor(value, delta)
            cases.append(dict(config=c, normal=normal))
    cases.append(dict(hits=[(0, 3, 4, 0, 1e-5), (1, -3, 4, 0, 1e-5)],
                      normal=[-10, -10]+[0]*316))
    compare(cases, binaries)


def test_original_realistic_repeated_crossings_efficiencies_axes_and_pc1(binaries):
    hits = [(0, 3, 4, 0, 1e-6), (1, 3, 4, 2, 1e-6),
            (0, 3, 4, 0, 1e-6), (1, 3, 4, 2, 1e-6)]
    cases = [dict(hits=hits), dict(hits=list(reversed(hits)))]
    for eff in ([0]*4, [1]*4, [0, 1, 0, 1], [1, 0, 1, 0],
                [-.499, .499, .5, 1.499], [.5, .499, -.1, 1.1]):
        cases.append(dict(hits=hits, efficiency=eff))
    for ch in (0, 1):
        for x, y in ((0, 1), (1, 0), (-1, 0), (0, -1), (1e-7, -1), (-1, 1e-7), (3, -4), (-3, -4)):
            for z in (-19, 0, 19):
                cases.append(dict(hits=[(ch, x, y, z, 1e-7)]))
    c = config()
    c[5] = 17.5  # Outer PC2 ignored by source rotation; PC1 retained.
    cases.append(dict(config=c, hits=hits))
    compare(cases, binaries)


def test_original_random_twenty_per_chamber_and_source_draw_order(binaries):
    rng = random.Random(260901)
    cases = []
    for _ in range(150):
        hits = [(ch, rng.uniform(-8, 8), rng.uniform(-8, 8), rng.uniform(-24, 24),
                 10**rng.uniform(-7, -4)) for ch in (0, 1) for _ in range(rng.randrange(21))]
        rng.shuffle(hits)
        cases.append(dict(hits=hits, normal=[rng.gauss(0, 1) for _ in range(316+len(hits))],
                          efficiency=[rng.randrange(2) for _ in hits]))
    compare(cases, binaries)
