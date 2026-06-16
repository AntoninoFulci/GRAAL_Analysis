"""Vectorised 4-vector math for the photon-pairing study.

A 4-vector is a numpy array whose last axis is [E, px, py, pz].
All functions broadcast over leading axes.
"""
import numpy as np

MPI0 = 0.134977
META = 0.547862
CHI2_RES = 0.08  # fractional mass resolution used by the baseline chi2


def _p3(v):
    return v[..., 1:4]


def invariant_mass(a, b):
    s = a + b
    e = s[..., 0]
    p2 = np.sum(s[..., 1:4] ** 2, axis=-1)
    m2 = e * e - p2
    return np.sqrt(np.clip(m2, 0.0, None))


def energy_asymmetry(a, b):
    ea, eb = a[..., 0], b[..., 0]
    return np.abs(ea - eb) / (ea + eb)


def cos_angle(a, b):
    pa, pb = _p3(a), _p3(b)
    na = np.linalg.norm(pa, axis=-1)
    nb = np.linalg.norm(pb, axis=-1)
    denom = np.where((na * nb) == 0.0, 1.0, na * nb)
    c = np.sum(pa * pb, axis=-1) / denom
    return np.clip(c, -1.0, 1.0)


def opening_angle(a, b):
    return np.arccos(cos_angle(a, b))


def pt(v):
    return np.sqrt(v[..., 1] ** 2 + v[..., 2] ** 2)


def beta(v):
    p = np.linalg.norm(_p3(v), axis=-1)
    e = v[..., 0]
    return p / e


def chi2_pairing(m_low, m_high):
    return (
        ((m_low - MPI0) / (CHI2_RES * MPI0)) ** 2
        + ((m_high - META) / (CHI2_RES * META)) ** 2
    )
