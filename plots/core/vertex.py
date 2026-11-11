"""Central-central closest approach from Giuseppe's vertex2.F (IWHERE=1).

Coordinates retain the h70 centimetre convention. Lines are extrapolated,
not clamped to the measured chamber segments. No target-position prior.
"""
from dataclasses import dataclass
from itertools import combinations

import numpy as np


STATUS = {"ok": 0, "nonfinite": 1, "sentinel": 2, "zero_length": 3, "parallel": 4}
MIN_SIN2 = 1e-10  # numerical guard, not a detector-resolution cut


@dataclass(frozen=True)
class Vertex:
    xyz: np.ndarray
    dca: float
    sin2: float
    status: str


def closest_vertex(inner1, outer1, inner2, outer2):
    """Midpoint of closest points on two infinite lines; undefined => NaNs."""
    points = np.asarray([inner1, outer1, inner2, outer2], dtype=float)
    if points.shape != (4, 3):
        raise ValueError("expected four 3D chamber points")

    def invalid(status, sin2=np.nan):
        return Vertex(np.full(3, np.nan), np.nan, float(sin2), status)

    if not np.isfinite(points).all():
        return invalid("nonfinite")
    if np.any(points == -1000):
        return invalid("sentinel")
    p, p2, q, q2 = points
    u, v, w = p2 - p, q2 - q, p - q
    chi, psi, omega = u @ u, v @ v, u @ v
    if chi == 0 or psi == 0:
        return invalid("zero_length")
    # |u x v|^2 equals CHI*PSI-OMEGA^2, with less cancellation.
    cross = np.cross(u, v)
    delta = cross @ cross
    sin2 = delta / (chi * psi)
    if sin2 <= MIN_SIN2:
        return invalid("parallel", sin2)
    csi, ro = u @ w, v @ w
    h = (omega * ro - psi * csi) / delta
    t = (chi * ro - omega * csi) / delta
    first, second = p + h * u, q + t * v
    xyz = (first + second) / 2
    dca = np.linalg.norm(first - second)
    if not np.isfinite([*xyz, dca, sin2]).all():
        return invalid("nonfinite")
    return Vertex(xyz, float(dca), float(sin2), "ok")


def central_pairs(associations, n_cylinders):
    """Return association-row pairs with distinct cylinder and barrel hits.

    h70 Iass_3 rows: [BGO, barrel, cylinder], using Fortran 1-based indices;
    zero means absent. Repeated cylinder associations count as one track,
    retaining the first eligible row. No PID, BGO-energy or vertex cut.
    """
    if not 0 <= n_cylinders <= 5:
        raise ValueError("invalid cylinder count")
    rows = np.asarray(associations)
    if rows.size == 0:
        return [], 0
    if rows.ndim != 2 or rows.shape[1] != 3 or rows.dtype.kind not in "iu":
        raise ValueError("Iass_3 must have integer rows [BGO, barrel, cylinder]")
    if np.any(rows < 0) or np.any(rows[:, 2] > n_cylinders):
        raise ValueError("invalid cylinder/association index")
    unique = {}
    for row, (_, barrel, cylinder) in enumerate(rows):
        if barrel > 0 and cylinder > 0:
            unique.setdefault(int(cylinder), row)
    tracks = list(unique.values())
    pairs = [(i, j) for i, j in combinations(tracks, 2) if rows[i, 1] != rows[j, 1]]
    return pairs, len(tracks)
