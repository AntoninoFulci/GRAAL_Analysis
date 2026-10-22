"""Explicit polygons on raw M(eta), M(pi0), in GeV; no default physics contour."""

from dataclasses import dataclass
import json
from pathlib import Path

import numpy as np


def _cross(a, b, p):
    return (b[0] - a[0]) * (p[..., 1] - a[1]) - (b[1] - a[1]) * (p[..., 0] - a[0])


def _on_segment(a, b, p, tolerance):
    return ((np.abs(_cross(a, b, p)) <= tolerance * np.linalg.norm(b - a))
            & np.all(p >= np.minimum(a, b) - tolerance, axis=-1)
            & np.all(p <= np.maximum(a, b) + tolerance, axis=-1))


@dataclass(frozen=True)
class MassPolygon:
    """Simple (possibly concave) polygon with explicit boundary convention.

    Boundary roundoff tolerance is 32 machine eps times max(1, |vertices|)
    in GeV. Nonfinite masses fail selection. The polygon never reads fitted
    vectors, polarization, period, or an asymmetry result.
    """

    name: str
    defined_on: str
    boundary: str
    vertices: tuple[tuple[float, float], ...]

    def __post_init__(self):
        if not all(isinstance(s, str) and s.strip() for s in (self.name, self.defined_on)):
            raise ValueError("polygon name and independent definition sample are required")
        if self.boundary not in ("include", "exclude"):
            raise ValueError("polygon boundary must be include or exclude")
        v = np.asarray(self.vertices, dtype=float)
        if v.ndim != 2 or v.shape[1] != 2 or len(v) < 3 or not np.isfinite(v).all():
            raise ValueError("polygon requires at least three finite (eta, pi0) vertices")
        if np.array_equal(v[0], v[-1]):
            v = v[:-1]
        if len(v) < 3 or len(np.unique(v, axis=0)) != len(v):
            raise ValueError("polygon vertices must be distinct")
        tolerance = 32 * np.finfo(float).eps * max(1., float(np.abs(v).max()))
        shifted = v - v[0]
        area2 = np.sum(shifted[:, 0] * np.roll(shifted[:, 1], -1)
                       - shifted[:, 1] * np.roll(shifted[:, 0], -1))
        if abs(area2) <= tolerance * np.linalg.norm(np.ptp(v, axis=0)):
            raise ValueError("polygon has zero area")
        for i, a in enumerate(v):
            b = v[(i + 1) % len(v)]
            previous = v[(i - 1) % len(v)]
            if _on_segment(a, b, previous, tolerance) or _on_segment(previous, a, b, tolerance):
                raise ValueError("polygon has overlapping adjacent edges")
            for j in range(i + 1, len(v)):
                if j == i + 1 or (i == 0 and j == len(v) - 1):
                    continue
                c, d = v[j], v[(j + 1) % len(v)]
                crossing = ((_cross(a, b, c) * _cross(a, b, d) < 0)
                            and (_cross(c, d, a) * _cross(c, d, b) < 0))
                touching = any((_on_segment(a, b, c, tolerance), _on_segment(a, b, d, tolerance),
                                _on_segment(c, d, a, tolerance), _on_segment(c, d, b, tolerance)))
                if crossing or touching:
                    raise ValueError("polygon must not self-intersect or self-touch")
        object.__setattr__(self, "vertices", tuple(tuple(map(float, p)) for p in v))

    @classmethod
    def from_dict(cls, value):
        fields = {"schema", "name", "defined_on", "axes", "units", "boundary", "vertices"}
        if not isinstance(value, dict) or set(value) != fields:
            raise ValueError(f"polygon definition requires exactly {sorted(fields)}")
        if type(value["schema"]) is not int or value["schema"] != 1:
            raise ValueError("unsupported polygon schema")
        if value["axes"] != ["eta_mass", "pi0_mass"] or value["units"] != "GeV":
            raise ValueError("polygon axes must be raw eta_mass, pi0_mass in GeV")
        return cls(value["name"], value["defined_on"], value["boundary"], value["vertices"])

    @classmethod
    def read(cls, path):
        return cls.from_dict(json.loads(Path(path).read_text()))

    def to_dict(self):
        return dict(schema=1, name=self.name, defined_on=self.defined_on,
                    axes=["eta_mass", "pi0_mass"], units="GeV", boundary=self.boundary,
                    vertices=[list(p) for p in self.vertices])

    def mask(self, eta_mass, pi0_mass):
        eta, pi0 = np.asarray(eta_mass, dtype=float), np.asarray(pi0_mass, dtype=float)
        if eta.ndim != 1 or eta.shape != pi0.shape:
            raise ValueError("raw mass arrays must have the same one-dimensional shape")
        finite = np.isfinite(eta) & np.isfinite(pi0)
        points = np.column_stack((eta[finite], pi0[finite]))
        inside, boundary = np.zeros(len(points), dtype=bool), np.zeros(len(points), dtype=bool)
        v = np.asarray(self.vertices)
        tolerance = 32 * np.finfo(float).eps * max(1., float(np.abs(v).max()))
        for a, b in zip(v, np.roll(v, -1, axis=0)):
            boundary |= _on_segment(a, b, points, tolerance)
            if a[1] != b[1]:
                crosses = (a[1] > points[:, 1]) != (b[1] > points[:, 1])
                x = a[0] + (points[:, 1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
                inside ^= crosses & (points[:, 0] < x)
        result = np.zeros(eta.shape, dtype=bool)
        result[finite] = (inside | boundary) if self.boundary == "include" else (inside & ~boundary)
        return result
