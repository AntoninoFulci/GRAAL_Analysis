#!/usr/bin/env python3
"""Run the real GEANT4 conversion and compare independent GEANT3 probes.

Exit nonzero if geometry cannot be certified. Conversion artifacts are kept
even on failure so differences can be reviewed without rerunning GEANT3.
"""

import argparse
import json
import subprocess
from collections import defaultdict
from pathlib import Path


def reference_contract(reference):
    children = defaultdict(list)
    volumes = {}
    media = {}
    materials = {}
    for line in reference.read_text().splitlines():
        r = line.split()
        if r[0] == "P":
            children[r[3]].append((r[1], r[2]))
        elif r[0] == "V":
            volumes[r[1]] = int(r[3])
        elif r[0] == "T":
            media[int(r[1])] = int(r[2])
        elif r[0] == "M":
            materials[int(r[1])] = (float(r[5]), [[float(r[3]), float(r[4]), 1.0]])
        elif r[0] == "X":
            components = [list(map(float, r[i : i + 3])) for i in range(5, len(r), 3)]
            total = sum(c[2] for c in components)
            materials[int(r[1])] = (
                float(r[3]),
                [[a, z, w / total] for a, z, w in components],
            )
    identities = {}

    def visit(name, copy, path):
        assert len(path) < 30, "Geometry hierarchy exceeds GEANT3 depth"
        path = path + (name, copy)
        identities[path] = (volumes[name], media[volumes[name]])
        for child, number in children[name]:
            # Confirmed hidden-volume policy; original declarations retained.
            if child != "TROU":
                visit(child, number, path)

    visit("LAGR", "1", ())
    return identities, materials


def verify(executable: Path, reference: Path, navigation: Path, output: Path):
    assert executable.is_file(), "GEANT4 converter has not been built"
    assert navigation.read_text().strip(), (
        "Empty navigation reference cannot certify geometry"
    )
    result = subprocess.run(
        [str(executable), str(reference), str(output), str(navigation)], check=False
    )
    assert result.returncode in (0, 2), f"Conversion failed: exit {result.returncode}"
    summary = json.loads((output / "summary.json").read_text())
    assert summary["bgo_copies"] == 480, summary
    assert (output / "geometry.gdml").is_file(), "Reopenable GEANT4 geometry missing"
    scene = json.loads((output / "scene.json").read_text())
    assert sum(item["name"] == "BGO" for item in scene) == 480
    identities, materials = reference_contract(reference)
    scene_ids = {}
    for item in scene:
        path = tuple(
            part
            for node in item["path"].strip("/").split("/")
            for part in node.split(":")
        )
        scene_ids[path] = (item["medium"], item["material"])
    assert scene_ids == identities, (
        "Converted placement inventory/IDs differ from source"
    )
    expected = [line.split() for line in navigation.read_text().splitlines()]
    observed = [
        line.split() for line in (output / "navigation.g4").read_text().splitlines()
    ]
    assert len(expected) == len(observed), "Point queries dropped"
    covered = {tuple(row[5:]) for row in expected if int(row[3]) > 0}
    assert covered == set(identities), (
        f"Reference lacks full occupied-volume coverage: {set(identities) - covered}"
    )
    differences = []
    for index, (old, new) in enumerate(zip(expected, observed)):
        assert all(abs(float(a) - float(b)) < 1.0e-8 for a, b in zip(old[:3], new[:3]))
        # GMEDIA returns medium 0 outside the world, but leaves GCVOLU's
        # previous world hint in place. That path is not a located volume.
        if old[3] == new[3] == "0":
            continue
        if old[3:] != new[3:]:
            differences.append(
                {
                    "index": index,
                    "point_cm": list(map(float, old[:3])),
                    "geant3": old[3:],
                    "geant4": new[3:],
                }
            )
    report = {
        "queries": len(expected),
        "outside_world_queries": sum(row[3] == "0" for row in expected),
        "covered_physical_identities": len(covered),
        "path_mismatches": len(differences),
        "medium_mismatches": sum(d["geant3"][0] != d["geant4"][0] for d in differences),
        "overlap_volumes": summary["overlap_volumes"],
        "differences": differences,
    }
    (output / "comparison.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "differences"}, indent=2))
    assert not differences, "GEANT3/GEANT4 navigation differs; inspect comparison.json"
    assert not summary["overlap_volumes"], "Unresolved overlaps; inspect conversion log"
    checker = executable.with_name("graal_gdml_check" + executable.suffix)
    assert checker.is_file(), (
        "Build with BUILD_TESTING=ON for GDML round-trip verification"
    )
    subprocess.run(
        [
            str(checker),
            str(output / "geometry.gdml"),
            str(navigation),
            str(output / "roundtrip"),
        ],
        check=True,
    )
    props = json.loads((output / "roundtrip/materials.json").read_text())
    assert props["instances"] == len(identities) and props["bgo_copies"] == 480
    used = {material for _, material in identities.values()}
    assert {m["id"] for m in props["materials"]} == used
    for actual in props["materials"]:
        density, elements = materials[actual["id"]]
        assert abs(actual["density"] - density) < 1.0e-10 * max(1.0, density), (
            f"GDML changed density of material {actual['id']}"
        )
        assert len(actual["elements"]) == len(elements)
        for got, want in zip(sorted(actual["elements"]), sorted(elements)):
            assert all(
                abs(a - b) < 1.0e-10 * max(1.0, abs(b)) for a, b in zip(got, want)
            ), f"GDML changed A/Z/fraction of material {actual['id']}: {got} vs {want}"
    reopened = [
        line.split()
        for line in (output / "roundtrip/navigation.g4").read_text().splitlines()
    ]
    assert reopened == observed, (
        "GDML round trip changed point coordinates, paths or media"
    )
    report["gdml_roundtrip"] = "passed"
    report["materials_checked"] = len(used)
    report["status"] = "geometry_checks_passed"
    (output / "comparison.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--executable", type=Path, required=True)
    cli.add_argument("--reference", type=Path, required=True)
    cli.add_argument("--navigation", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    verify(args.executable, args.reference, args.navigation, args.output)
