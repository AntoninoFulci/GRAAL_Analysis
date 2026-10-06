"""Strong-grid accuracy against the sourced direct matrix, including cusps."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from graal_theory.amplitudes.nstar1535_full import reconstructed_full_tmatrix
from graal_theory.amplitudes import nstar1535_grid
from graal_theory.amplitudes.nstar1535_grid import build_strong_t_grid
from graal_theory.amplitudes.nstar1535_vmd import switching_energies
from graal_theory.models.eta_pi0_p_full import EtaPi0PFullModel


REFERENCE_DIR = Path(__file__).resolve().parents[1] / "references"


@pytest.fixture(scope="module")
def sourced():
    return EtaPi0PFullModel.from_files(REFERENCE_DIR).parameters


@pytest.fixture(scope="module")
def grid(sourced):
    return build_strong_t_grid(sourced.strong, sourced.vector_masses)


def _assert_direct_bound(grid, sourced, w):
    direct = reconstructed_full_tmatrix(float(w), sourced.strong, sourced.vector_masses)
    error = np.abs(grid.evaluate(float(w)) - direct)
    assert np.all(error <= np.maximum(1e-8, 1e-4 * np.abs(direct))), w


def test_grid_off_node_respects_direct_matrix_bound(grid, sourced):
    # Catches inaccurate linear interpolation in smooth high-W intervals.
    for w in (1.612345, 1.735678, 1.799123):
        _assert_direct_bound(grid, sourced, w)
    for w in np.linspace(grid.lower_gev + 0.00041, 1.79941, 33):
        _assert_direct_bound(grid, sourced, w)


def test_grid_splits_every_threshold_and_vmd_switch(grid, sourced):
    # Catches interpolation through a nonanalytic branch/switch.
    p = sourced.strong
    expected = set(np.add(p.meson_masses_gev, p.baryon_masses_gev))
    switches = switching_energies(p, sourced.vector_masses)
    expected.update(switches[np.isfinite(switches)])
    for w in expected:
        assert w in grid.landmarks_gev
        for probe in (np.nextafter(w, -np.inf), w, np.nextafter(w, np.inf)):
            if grid.lower_gev <= probe <= grid.upper_gev:
                _assert_direct_bound(grid, sourced, probe)


def test_grid_returns_independent_matrices_and_rejects_unsupported_w(grid, sourced):
    before = grid.evaluate(1.75)
    original = before.copy()
    assert before.shape == (6, 6) and before.dtype == np.complex128
    if before.flags.writeable:
        before[0, 0] = 1e10
    else:
        with pytest.raises(ValueError):
            before[0, 0] = 1e10
    np.testing.assert_array_equal(grid.evaluate(1.75), original)
    with pytest.raises(ValueError, match="W"):
        grid.evaluate(np.nextafter(1.80, np.inf))


def test_grid_fingerprint_covers_strong_and_vector_parameters(grid, sourced):
    strong = sourced.strong
    vectors = sourced.vector_masses
    assert grid.matches(strong, vectors)
    changed_subtractions = list(strong.subtraction_constants)
    changed_subtractions[0] += 0.01
    assert not grid.matches(replace(strong, subtraction_constants=tuple(changed_subtractions)), vectors)
    assert not grid.matches(strong, replace(vectors, rho_gev=vectors.rho_gev + 0.01))
    assert build_strong_t_grid(strong, vectors) is grid
    assert build_strong_t_grid(strong, vectors, rtol=5e-5) is not grid


def test_implementation_version_is_part_of_grid_cache_key(monkeypatch, grid, sourced):
    monkeypatch.setattr(nstar1535_grid, "_VERSION", "strong-t-grid-test-version")
    other = build_strong_t_grid(sourced.strong, sourced.vector_masses)
    assert other is not grid
    assert other.fingerprint != grid.fingerprint


def test_unresolved_sharp_interval_falls_back_to_direct(monkeypatch, sourced):
    # Catches returning an inaccurate interpolant after refinement budget ends.
    def sharp(w, parameters, masses):
        return np.eye(6, dtype=np.complex128) * np.sin(1000*w)

    monkeypatch.setattr(nstar1535_grid, "reconstructed_full_tmatrix", sharp)
    monkeypatch.setattr(nstar1535_grid, "_MAX_DEPTH", 0)
    monkeypatch.setattr(nstar1535_grid, "_VERSION", "sharp-test-v1")
    grid = build_strong_t_grid(sourced.strong, sourced.vector_masses)
    direct_parts = [part for part in grid.segments if part.direct_only]
    assert direct_parts
    part = direct_parts[0]
    w = (part.lower + part.upper)/2
    np.testing.assert_array_equal(grid.evaluate(w), sharp(w, sourced.strong,
                                                            sourced.vector_masses))
