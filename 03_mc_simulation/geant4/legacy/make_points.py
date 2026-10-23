#!/usr/bin/env python3
"""Deterministic global, per-copy, thin-layer and boundary probes.

Coordinates come from declared GEANT3 primitives. Expected identities and
materials must be obtained independently by running the GEANT3 navigator.
"""

import argparse
import math
import random
from collections import defaultdict
from pathlib import Path


def matvec(matrix, vector):
    return tuple(sum(a * b for a, b in zip(row, vector)) for row in matrix)


def matmul(a, b):
    return tuple(
        tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3))
        for i in range(3)
    )


def primitive(shape, p):
    inset = 0.0002  # 2 micrometres; larger than the REAL*4 contacts.
    if shape == "BOX":
        yield from (
            (x * p[0], y * p[1], z * p[2])
            for x in (-0.8, 0, 0.8)
            for y in (-0.8, 0, 0.8)
            for z in (-0.8, 0, 0.8)
        )
        for axis in range(3):
            for sign in (-1, 1):
                for offset in (-inset, inset):
                    q = [0.0, 0.0, 0.0]
                    q[axis] = sign * (p[axis] + offset)
                    yield tuple(q)
    elif shape in {"TUBE", "TUBS", "CONS"}:
        half = p[2] if shape != "CONS" else p[0]
        lo, span = (
            (p[3], p[4] - p[3])
            if shape == "TUBS"
            else ((p[5], p[6] - p[5]) if shape == "CONS" else (0.0, 360.0))
        )
        for fz in (-0.8, 0.0, 0.8):
            low, high = (
                (p[0], p[1])
                if shape != "CONS"
                else (
                    (1 - fz) / 2 * p[1] + (1 + fz) / 2 * p[3],
                    (1 - fz) / 2 * p[2] + (1 + fz) / 2 * p[4],
                )
            )
            for fr in (0.02, 0.5, 0.98):
                radius = low + fr * (high - low)
                for fphi in (0.125, 0.375, 0.625, 0.875):
                    phi = math.radians(lo + span * fphi)
                    yield radius * math.cos(phi), radius * math.sin(phi), fz * half
            phi = math.radians(lo + span * 0.375)
            for boundary in (low, high):
                if boundary == 0:
                    continue
                for offset in (-inset, inset):
                    radius = boundary + offset
                    yield radius * math.cos(phi), radius * math.sin(phi), fz * half
        radius = (p[0] + p[1]) / 2 if shape != "CONS" else sum(p[1:5]) / 4
        phi = math.radians(lo + span * 0.375)
        for sign in (-1, 1):
            for offset in (-inset, inset):
                yield (
                    radius * math.cos(phi),
                    radius * math.sin(phi),
                    sign * (half + offset),
                )
    elif shape == "TRAP":
        for fz in (-0.8, 0.0, 0.8):
            f = (fz + 1) / 2
            dy = (1 - f) * p[3] + f * p[7]
            dx1 = (1 - f) * p[4] + f * p[8]
            dx2 = (1 - f) * p[5] + f * p[9]
            alpha = (1 - f) * math.tan(math.radians(p[6])) + f * math.tan(
                math.radians(p[10])
            )
            z = fz * p[0]
            cx = z * math.tan(math.radians(p[1])) * math.cos(math.radians(p[2]))
            cy = z * math.tan(math.radians(p[1])) * math.sin(math.radians(p[2]))
            for fy in (-0.8, 0.0, 0.8):
                y = fy * dy
                dx = (1 - fy) / 2 * dx1 + (1 + fy) / 2 * dx2
                for fx in (-0.8, 0.0, 0.8):
                    yield cx + y * alpha + fx * dx, cy + y, z
            for sign in (-1, 1):
                for offset in (-inset, inset):
                    yield cx + sign * ((dx1 + dx2) / 2 + offset), cy, z
                    yield cx + sign * dy * alpha, cy + sign * (dy + offset), z
    elif shape == "PGON":
        for z in (p[4] * 0.8, p[7] * 0.8):
            for phi in (p[0] + i * 90 + 45 for i in range(4)):
                radius = (p[5] + p[6]) / 2
                yield (
                    radius * math.cos(math.radians(phi)),
                    radius * math.sin(math.radians(phi)),
                    z,
                )
    else:
        raise ValueError("Unsupported primitive: " + shape)


def make_points(reference: Path, output: Path):
    if output.exists():
        raise FileExistsError(output)
    volumes = {}
    children = defaultdict(list)
    rotations = {0: ((1, 0, 0), (0, 1, 0), (0, 0, 1))}
    for line in reference.read_text().splitlines():
        r = line.split()
        if r[0] == "V":
            volumes[r[1]] = (r[2], list(map(float, r[5:])))
        elif r[0] == "P":
            children[r[3]].append(
                (r[1], tuple(map(float, r[4:7])), int(r[7]), list(map(float, r[10:])))
            )
        elif r[0] == "R":
            a = list(map(math.radians, map(float, r[2:])))
            columns = [
                (
                    math.sin(a[i]) * math.cos(a[i + 1]),
                    math.sin(a[i]) * math.sin(a[i + 1]),
                    math.cos(a[i]),
                )
                for i in (0, 2, 4)
            ]
            rotations[int(r[1])] = tuple(zip(*columns))
    rng = random.Random(231026)
    points = [
        (0, 0, 0),
        (0, 0, 3.059),
        (0, 0, 3.061),
        (0, 0, 10),
        (0, 0, 94.4),
        (0, 0, 134.4),
        (0, 0, 301.53),
        (0, 0, 305.594),
        (0, 0, 336.375),
    ]
    points += [
        (rng.uniform(-199, 199), rng.uniform(-199, 199), rng.uniform(-369, 369))
        for _ in range(15000)
    ]
    points += [
        (rng.uniform(-40, 40), rng.uniform(-40, 40), rng.uniform(-100, 100))
        for _ in range(20000)
    ]
    points += [
        (rng.uniform(-160, 160), rng.uniform(-160, 160), rng.uniform(85, 355))
        for _ in range(20000)
    ]
    points += [
        (x, y, z)
        for x in (0.1, 1.9, 2.1, 2.9, 3.1, 4.9, 5.1, 9.5, 20.0, 40.0, 60.0)
        for y in (0.13, 2.0, 6.0, 12.0)
        for z in (
            93.391,
            93.9,
            94.4,
            94.9,
            95.409,
            133.391,
            133.9,
            134.4,
            134.9,
            135.409,
            300.5,
            301.53,
            303.6,
            305.594,
            330.0,
            336.375,
        )
    ]
    for radius in (2.139, 2.141, 2.19, 2.201, 2.499, 2.501, 2.525, 2.549, 2.551):
        for z in (-3.073, -3.071, -3.067, -3.061, -3.059, -3.05):
            for phi in (0.13, 0.97, 1.97, 3.18):
                points.append((radius * math.cos(phi), radius * math.sin(phi), z))
    for x in (
        -4.9,
        -3.1,
        -2.9,
        -2.1,
        -1.9,
        -0.12,
        -0.1,
        0.0,
        0.1,
        0.12,
        1.9,
        2.1,
        2.9,
        3.1,
        4.9,
    ):
        for y in (-4.9, -2.1, -0.6, 0.13, 0.6, 2.1, 4.9):
            for z in (
                93.9,
                94.4,
                94.9,
                133.9,
                134.4,
                134.9,
                300.01,
                301.53,
                303.3,
                305.594,
                306.9,
                326.0,
                329.0,
                331.875,
                336.375,
                340.875,
                345.3,
            ):
                points.append((x, y, z))

    def visit(name, rotation, position, override=None):
        shape, original = volumes[name]
        params = override or original
        for local in primitive(shape, params):
            vector = matvec(rotation, local)
            points.append(tuple(a + b for a, b in zip(vector, position)))
        for child, translation, ir, child_parameters in children[name]:
            delta = matvec(rotation, translation)
            visit(
                child,
                matmul(rotation, rotations[ir]),
                tuple(a + b for a, b in zip(position, delta)),
                child_parameters,
            )

    visit("LAGR", rotations[0], (0, 0, 0))
    output.write_text(
        "".join(" ".join(format(v, ".12g") for v in p) + "\n" for p in points)
    )
    print(f"{output}: {len(points)} independent GEANT3 queries required")


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("reference", type=Path)
    cli.add_argument("output", type=Path)
    args = cli.parse_args()
    make_points(args.reference, args.output)
