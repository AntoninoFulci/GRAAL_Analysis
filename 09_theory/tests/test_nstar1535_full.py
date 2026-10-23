"""Composition checks for the reconstructed full N*(1535) strong amplitude."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from graal_theory.amplitudes.nstar1535_final_fit import load_final_fit_parameters
from graal_theory.amplitudes.nstar1535_full import (
    reconstructed_full_kernel,
    reconstructed_full_tmatrix,
)
from graal_theory.amplitudes.nstar1535_pipi_n import (
    pipi_n_kernel_correction,
    pipi_n_tmatrix,
)
from graal_theory.amplitudes.nstar1535_reduced import (
    load_reduced_parameters,
    loop_functions,
    reduced_tmatrix,
)
from graal_theory.amplitudes.nstar1535_vmd import (
    load_vector_masses, switching_energies, vmd_kernel,
)


REFERENCE_DIR = Path(__file__).resolve().parents[1] / "references"
SOURCES = REFERENCE_DIR / "sources.json"


@pytest.fixture
def final_parameters():
    base = load_reduced_parameters(
        REFERENCE_DIR / "nstar1535_reduced_parameters.json", SOURCES)
    return load_final_fit_parameters(
        base, REFERENCE_DIR / "nstar1535_final_subtractions.json", SOURCES)


@pytest.fixture
def vector_masses():
    return load_vector_masses(
        REFERENCE_DIR / "nstar1535_vmd_masses.json", SOURCES)


@pytest.mark.parametrize("w", [1.25, 1.55, 1.70])
def test_full_kernel_adds_pipi_n_once(w, final_parameters, vector_masses):
    p = final_parameters
    pion = p.meson_masses_gev[1]
    nucleon = (p.baryon_masses_gev[0] + p.baryon_masses_gev[1])/2
    expected = vmd_kernel(w, p, vector_masses)
    expected = expected + pipi_n_kernel_correction(w, pion, nucleon)
    actual = reconstructed_full_kernel(w, p, vector_masses)
    assert actual.shape == (6, 6)
    assert actual.dtype == np.complex128
    np.testing.assert_allclose(actual, expected, rtol=1e-13, atol=1e-13)


@pytest.mark.parametrize("at_threshold", [False, True])
def test_full_kernel_has_no_three_body_absorption_below_threshold(
    at_threshold, final_parameters, vector_masses,
):
    p = final_parameters
    pion = p.meson_masses_gev[1]
    nucleon = (p.baryon_masses_gev[0] + p.baryon_masses_gev[1])/2
    w = nucleon + 2*pion if at_threshold else 1.1
    kernel = reconstructed_full_kernel(w, p, vector_masses)
    np.testing.assert_array_equal(kernel.imag, 0)
    np.testing.assert_array_equal(kernel, vmd_kernel(w, p, vector_masses))


@pytest.mark.parametrize("w", [1.25, 1.55, 1.70])
def test_full_t_satisfies_matrix_equation(w, final_parameters, vector_masses):
    p = final_parameters
    v = reconstructed_full_kernel(w, p, vector_masses)
    g = loop_functions(w, p)
    t = reconstructed_full_tmatrix(w, p, vector_masses)
    assert t.shape == (6, 6)
    assert t.dtype == np.complex128
    assert np.all(np.isfinite(t))
    np.testing.assert_allclose(
        (np.eye(6) - v*g[None, :]) @ t, v, rtol=1e-10, atol=1e-10)
    np.testing.assert_allclose(t, t.T, rtol=1e-10, atol=1e-10)


def test_full_t_differs_from_reduced_and_pipi_n_variants(
    final_parameters, vector_masses,
):
    p = final_parameters
    t = reconstructed_full_tmatrix(1.55, p, vector_masses)
    assert np.max(abs(t - reduced_tmatrix(1.55, p))) > 1e-6
    assert np.max(abs(t - pipi_n_tmatrix(1.55, p))) > 1e-6


@pytest.mark.parametrize("w", [1.70, 1.75, 1.80])
def test_full_t_high_domain_solves_and_stops_at_source_ceiling(
    w, final_parameters, vector_masses,
):
    # Catches rejecting sourced high-W production or changing the matrix solve.
    v = reconstructed_full_kernel(w, final_parameters, vector_masses)
    g = loop_functions(w, final_parameters)
    t = reconstructed_full_tmatrix(w, final_parameters, vector_masses)
    assert np.isfinite(t).all()
    np.testing.assert_allclose(t, t.T, rtol=1e-10, atol=1e-10)
    residual = (np.eye(6) - v*g[None, :]) @ t - v
    assert np.max(np.abs(residual)) <= 1e-9*max(1., np.max(np.abs(v)))


def test_full_t_finite_on_each_source_landmark_side(final_parameters, vector_masses):
    # Catches extending the endpoint while leaving a threshold/switch hole.
    p = final_parameters
    lower = min(np.add(p.meson_masses_gev, p.baryon_masses_gev))
    landmarks = set(np.add(p.meson_masses_gev, p.baryon_masses_gev))
    switches = switching_energies(p, vector_masses)
    landmarks.update(switches[np.isfinite(switches)])
    landmarks.update((1.60, 1.70, 1.75, 1.80))
    for landmark in sorted(landmarks):
        for w in (np.nextafter(landmark, -np.inf), landmark,
                  np.nextafter(landmark, np.inf)):
            if lower <= w <= 1.80:
                t = reconstructed_full_tmatrix(float(w), p, vector_masses)
                assert np.isfinite(t).all(), (landmark, w)
                np.testing.assert_allclose(t, t.T, rtol=1e-10, atol=1e-10)


def test_full_t_rejects_one_step_past_source_ceiling(final_parameters, vector_masses):
    with pytest.raises(ValueError, match="W"):
        reconstructed_full_tmatrix(np.nextafter(1.80, np.inf),
                                   final_parameters, vector_masses)


@pytest.mark.parametrize("function", [
    reconstructed_full_kernel, reconstructed_full_tmatrix,
])
@pytest.mark.parametrize("w", [True, 1+0j, "1.55", float("nan"),
                              float("inf"), float("-inf"), 1.0,
                              np.nextafter(1.80, np.inf)])
def test_full_rejects_invalid_energy(function, w, final_parameters, vector_masses):
    with pytest.raises(ValueError, match="W"):
        function(w, final_parameters, vector_masses)


@pytest.mark.parametrize("condition", [1e13, float("inf"), float("nan")])
def test_full_t_preserves_condition_guard(
    monkeypatch, condition, final_parameters, vector_masses,
):
    monkeypatch.setattr(np.linalg, "cond", lambda system: condition)
    with pytest.raises(ValueError, match="ill-conditioned"):
        reconstructed_full_tmatrix(1.55, final_parameters, vector_masses)


def test_full_t_preserves_singular_guard(
    monkeypatch, final_parameters, vector_masses,
):
    def singular(system, kernel):
        raise np.linalg.LinAlgError("singular")

    monkeypatch.setattr(np.linalg, "solve", singular)
    with pytest.raises(ValueError, match="singular"):
        reconstructed_full_tmatrix(1.55, final_parameters, vector_masses)


def test_full_t_preserves_nonfinite_guard(
    monkeypatch, final_parameters, vector_masses,
):
    monkeypatch.setattr(np.linalg, "solve",
                        lambda system, kernel: np.full(kernel.shape, np.nan))
    with pytest.raises(ValueError, match="nonfinite"):
        reconstructed_full_tmatrix(1.55, final_parameters, vector_masses)
