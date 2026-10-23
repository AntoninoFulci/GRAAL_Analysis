#!/usr/bin/env python3
"""Prepare a fresh geometry-only build inside the pinned legacy image.

Run from Python 3 on the host, then compile generated sources with image g77.
Only explicit CALL sites are instrumented; GEANT3 library remains unchanged.
"""

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

ROUTINES = [
    "ugeom",
    "lagmat",
    "lagtmp",
    "lagcri",
    "lagtrp",
    "lagcxyz",
    "lagcang",
    "lagecvr",
    "lagbers",
    "lagvrtx",
    "lagplch",
    "lagwall",
    "lagcalo",
    "lagctdisk",
]
CALLS = dict(
    zip(
        ("GSVOLU", "GSPOS", "GSPOSP", "GSROTM", "GSMATE", "GSMIXT", "GSTMED"),
        ("AUDVOL", "AUDPOS", "AUDPOP", "AUDROT", "AUDMAT", "AUDMIX", "AUDMED"),
    )
)


def prepare(source: Path, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=False)
    program = source / "software/prog/laggen"
    shutil.copytree(program / "include", output / "include")
    shutil.copy(program / "pilot.h", output / "pilot.h")
    shutil.copy(program / "check_pilot.h", output / "check_pilot.h")
    for name in ("GRAAL_period.h", "GRAAL_machine.h"):
        shutil.copy(source / "software/prog/include" / name, output / "include" / name)
    src = output / "src"
    src.mkdir()
    hashes = {}
    for name in ROUTINES:
        original = program / "src" / (name + ".F")
        hashes[str(original.relative_to(source))] = hashlib.sha256(
            original.read_bytes()
        ).hexdigest()
        text = original.read_text()
        if name == "ugeom":
            # Remove only file/graphics output after geometry closure.
            before, marker, _ = text.partition("      CALL GGCLOS")
            if not marker:
                raise ValueError("UGEOM closure marker not found")
            text = before + marker + "\n      RETURN\n      END\n"
        for old, new in CALLS.items():
            text = re.sub(r"(?im)^(\s+CALL\s+)" + old + r"\b", r"\g<1>" + new, text)
        (src / original.name).write_text(text)
    for name in ("geometry_driver.F", "record_geometry.F"):
        shutil.copy(Path(__file__).with_name(name), src / name)
        hashes["extractor/" + name] = hashlib.sha256(
            Path(__file__).with_name(name).read_bytes()
        ).hexdigest()
    shutil.copy(Path(__file__).with_name("run_in_image.sh"), output / "run_in_image.sh")
    controls = [
        program / "pilot.h",
        program / "check_pilot.h",
        source / "software/prog/include/GRAAL_period.h",
        source / "software/prog/include/GRAAL_machine.h",
        source / "data/inp_laggen/laggen.dat",
        *(program / "include").glob("*.inc"),
    ]
    for path in controls:
        hashes[str(path.relative_to(source))] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
    (output / "source-hashes.json").write_text(json.dumps(hashes, indent=2) + "\n")


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--source", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    prepare(args.source, args.output)
