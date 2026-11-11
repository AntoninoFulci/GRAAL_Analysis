"""GUSTEP exact branch specification replay, explicitly not full-routine parity."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[3]
G4 = ROOT / "03_mc_simulation/geant4"
ARCHIVE = ROOT / "docs/reference/fortran/prog"


def run(command, **kwargs):
    result = subprocess.run([str(x) for x in command], capture_output=True, text=True, timeout=60,
                            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", MACOSX_DEPLOYMENT_TARGET="15.0"), **kwargs)
    assert result.returncode == 0, f"{command}\n{result.stdout}\n{result.stderr}"
    return result.stdout


@pytest.fixture(scope="module")
def binaries(tmp_path_factory):
    cpp, fort = shutil.which("c++"), shutil.which("gfortran")
    if not cpp or not fort: pytest.skip("requires c++ and gfortran")
    build = tmp_path_factory.mktemp("central-response-input-source")
    original_source = ARCHIVE / "laggen/src/gustep.F"
    payload = original_source.read_bytes()
    lines = payload.decode("ascii").splitlines(keepends=True)
    # Exact byte-identical source lines with preserved source labels and code.
    ranges = [(155, 159), (320, 329), (337, 346), (404, 412), (434, 442)]
    branches = ["".join(lines[first-1:last]) for first, last in ranges]
    assert "GO TO (1,2,3,4,5,6,7,8,9,10,11,12,13,14) ISVOL" in branches[0]
    assert "DECI(MULT1) = DECI(MULT1) + DEGAS + DESTEP" in branches[3]
    assert "DECE(MULT2) = DECE(MULT2) + DEGAS + DESTEP" in branches[4]
    header = '''      SUBROUTINE GUSTEP_CENTRAL_EXTRACT(ISVOL,CHARGE,INWVOL,
     & VECT,DESTEP)
      INTEGER ISVOL,INWVOL,ITOUCH
      REAL CHARGE,VECT(3),DESTEP,DEGAS
      SAVE ITOUCH,DEGAS
#include "nthit.inc"
'''
    # Noncentral source branches do not modify these SAVE variables. Their
    # detector-specific actions are outside this extracted specification.
    returns = "".join(f"{label:5d} RETURN\n" for label in (1, 2, 3, 4, 5, 8, 9, 12, 13, 14))
    extracted = build / "gustep_central_extract.F"
    extracted.write_text(header + "".join(branches) + returns + "      END\n")
    shutil.copyfile(ARCHIVE / "lagdig/include/nthit.inc", build / "nthit.inc")
    modern, original = build / "modern", build / "specification"
    run([cpp, "-std=c++17", "-O2", "-fno-fast-math", "-ffp-contract=off", "-Wall", "-Wextra", "-Werror",
         "-I", G4 / "src", G4 / "tests/check_cylinder_input.cc", "-o", modern])
    run([fort, "-O0", "-std=legacy", "-fcheck=all", "-fno-fast-math", "-ffp-contract=off",
         "-ffixed-line-length-none", "-cpp", "-DGRAAL_OLD_CYL", "-I", build,
         G4 / "tests/cylinder_input_oracle.F", extracted, "-o", original])
    manifest = dict(kind="exact_source_branch_specification_replay_not_full_GUSTEP", source=str(original_source.relative_to(ROOT)),
                    source_sha256=hashlib.sha256(payload).hexdigest(),
                    branches=[dict(first=first, last=last, sha256=hashlib.sha256(branch.encode("ascii")).hexdigest())
                              for (first, last), branch in zip(ranges, branches)],
                    initialization="all oracle streams establish SAVE through a real passive callback before gas use",
                    extracted_fixture_sha256=hashlib.sha256(extracted.read_bytes()).hexdigest())
    (build / "central-response-input-source-manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
    return modern, original


def s(role, e=0, charged=0, entrance=0, xyz=(1, 2, 3)):
    return [role, charged, entrance, *xyz, e]


def compare(events, binaries):
    lines = [str(len(events))]
    for event in events:
        lines += [str(len(event)), *(" ".join(format(v, ".9g") for v in row) for row in event)]
    payload = "\n".join(lines)+"\n"
    assert run([binaries[0], "--source"], input=payload).split() == run([binaries[1]], input=payload).split()


def test_expected_status_accounting_and_final_passive_epoch(binaries):
    assert "input fixtures passed" in run([binaries[0]])


def test_source_branch_gas_before_entry_neutral_noncentral_zero_and_reentry(binaries):
    compare([[s(0), s(10, 1e-6), s(8), s(10, 2e-6), s(6, charged=1, entrance=1),
              s(10), s(10, 3e-6), s(6, charged=0, entrance=1), s(10, 4e-6),
              s(6, charged=1, entrance=1, xyz=(3, 4, 5)), s(10, 5e-6)]], binaries)


def test_source_branch_cross_chamber_shared_pending_and_passive_zero_reset(binaries):
    compare([[s(0), s(10, 1e-6), s(11, 2e-6), s(7, charged=1, entrance=1), s(11, 3e-6),
              s(0), s(11, 4e-6), s(0), s(6, charged=1, entrance=1), s(10, 5e-6)]], binaries)


def test_source_branch_cross_event_pending_and_saved_touch(binaries):
    compare([[s(0), s(10, 1e-6)], [],
             [s(7, charged=1, entrance=1), s(11, 2e-6)],
             [s(7, charged=1, entrance=1), s(11, 3e-6)]], binaries)


def test_source_branch_binary32_rounding_floor_and_twenty_crossings(binaries):
    compare([[s(0), s(6, charged=1, entrance=1), s(10, 1), s(10, 2**-24), s(10, 2**-24),
              s(0), s(10, 2**-24), s(10, 2**-24), s(6, charged=1, entrance=1), s(10, 1),
              *(s(6, charged=1, entrance=1) for _ in range(18))]], binaries)
