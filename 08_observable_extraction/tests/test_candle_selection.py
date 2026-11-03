import numpy as np
import pytest

from graal_common.physics.channels import M_ETA, M_PI0
from observable_extraction.core.candle import (
    MassResolutionFit,
    fit_mass_resolution,
    split_by_fitted_ellipse,
    split_candle_core_tails,
)
from observable_extraction.io.reconstructed_events import EventArrays


def _events(eta_mass, pi0_mass):
    eta_mass = np.asarray(eta_mass, dtype=np.float64)
    pi0_mass = np.asarray(pi0_mass, dtype=np.float64)
    count = len(eta_mass)
    vectors = np.zeros((count, 4), dtype=np.float64)
    return EventArrays(
        run_number=np.arange(count, dtype=np.int64),
        xstrip=np.zeros(count, dtype=np.int64),
        polarization=np.ones(count, dtype=np.int64),
        beam_energy_gev=np.full(count, 1.2),
        eta=vectors,
        pi0=vectors,
        proton=vectors,
        missing_mass_gev=np.full(count, 0.938),
        eta_mass_gev=eta_mass,
        pi0_mass_gev=pi0_mass,
        bdt_score=np.ones(count),
        n_photons_input=np.full(count, 4, dtype=np.int64),
    )


@pytest.mark.parametrize(
    ("center", "half_range", "injected_sigma"),
    [(M_ETA, 0.080, 0.012), (M_PI0, 0.040, 0.006)],
)
def test_mass_resolution_fit_recovers_gaussian_peak_over_flat_background(
    center, half_range, injected_sigma
):
    rng = np.random.default_rng(20261103)
    signal = rng.normal(center + 0.001, injected_sigma, 12_000)
    background = rng.uniform(center - half_range, center + half_range, 3_000)
    masses = np.concatenate((signal, background, [np.nan, np.inf]))

    result = fit_mass_resolution(
        masses,
        center_gev=center,
        half_range_gev=half_range,
    )

    assert result.center_gev == center
    assert result.fit_half_range_gev == half_range
    assert result.fitted_mean_gev == pytest.approx(center + 0.001, abs=0.001)
    assert result.sigma_gev == pytest.approx(injected_sigma, rel=0.10)
    assert result.model == "gaussian_plus_linear_background"


def test_mass_resolution_fit_rejects_insufficient_entries():
    with pytest.raises(ValueError, match="insufficient"):
        fit_mass_resolution(
            np.linspace(M_ETA - 0.01, M_ETA + 0.01, 39),
            center_gev=M_ETA,
            half_range_gev=0.080,
        )


def test_mass_resolution_fit_rejects_flat_spectrum_without_peak():
    edges = np.linspace(M_ETA - 0.080, M_ETA + 0.080, 81)
    centers = 0.5 * (edges[:-1] + edges[1:])
    masses = np.repeat(centers, 100)

    with pytest.raises(ValueError, match="peak|fit"):
        fit_mass_resolution(
            masses,
            center_gev=M_ETA,
            half_range_gev=0.080,
        )


def test_mass_resolution_fit_initializes_peak_inside_bounds_with_sloped_background():
    edges = np.linspace(M_ETA - 0.080, M_ETA + 0.080, 81)
    centers = 0.5 * (edges[:-1] + edges[1:])
    counts = np.rint(
        300.0 * np.exp(-0.5 * np.square((centers - M_ETA) / 0.012))
        + 1_000.0
        + 10_000.0 * (centers - M_ETA)
    ).astype(np.int64)
    masses = np.repeat(centers, counts)

    result = fit_mass_resolution(
        masses,
        center_gev=M_ETA,
        half_range_gev=0.080,
    )

    assert result.fitted_mean_gev == pytest.approx(M_ETA, abs=0.001)
    assert result.sigma_gev == pytest.approx(0.012, rel=0.05)


def _fixed_fits():
    return (
        MassResolutionFit(M_ETA, M_ETA, 0.010, 0.080),
        MassResolutionFit(M_PI0, M_PI0, 0.005, 0.040),
    )


@pytest.mark.parametrize(
    ("distances", "expected_threshold", "scale_relation"),
    [
        ([0.04, 0.16, 0.36, 0.64], 0.26, "below"),
        ([0.25, 0.75, 1.25, 1.75], 1.00, "equal"),
        ([1.0, 2.0, 3.0, 4.0], 2.50, "above"),
    ],
)
def test_fitted_ellipse_solves_common_scale_for_exact_even_split(
    distances, expected_threshold, scale_relation
):
    eta_fit, pi0_fit = _fixed_fits()
    eta_mass = M_ETA + eta_fit.sigma_gev * np.sqrt(distances)
    events = _events(eta_mass, np.full(len(distances), M_PI0))

    result = split_by_fitted_ellipse(
        events,
        eta_fit=eta_fit,
        pi0_fit=pi0_fit,
        core_fraction=0.5,
    )

    assert result.distance_threshold == pytest.approx(expected_threshold)
    assert result.scale_factor == pytest.approx(np.sqrt(expected_threshold))
    assert [len(result.core), len(result.tails)] == [2, 2]
    assert result.core.run_number.tolist() == [0, 1]
    assert result.tails.run_number.tolist() == [2, 3]
    if scale_relation == "below":
        assert result.scale_factor < 1.0
    elif scale_relation == "equal":
        assert result.scale_factor == pytest.approx(1.0)
    else:
        assert result.scale_factor > 1.0


def test_fitted_ellipse_odd_and_nonfinite_counts_are_deterministic():
    eta_fit, pi0_fit = _fixed_fits()
    distances = np.array([0.04, 0.16, 0.36, 0.64, 1.0])
    eta_mass = np.concatenate(
        (M_ETA + eta_fit.sigma_gev * np.sqrt(distances), [np.nan, M_ETA])
    )
    pi0_mass = np.concatenate(
        (np.full(len(distances), M_PI0), [M_PI0, np.inf])
    )

    result = split_by_fitted_ellipse(
        _events(eta_mass, pi0_mass),
        eta_fit=eta_fit,
        pi0_fit=pi0_fit,
        core_fraction=0.5,
    )

    assert [len(result.core), len(result.tails)] == [2, 3]
    assert result.finite_event_count == 5
    assert result.excluded_nonfinite_count == 2
    assert result.core.run_number.tolist() == [0, 1]
    assert result.tails.run_number.tolist() == [2, 3, 4]
    assert result.requested_core_fraction == 0.5


def test_fitted_ellipse_rejects_tie_across_quantile_boundary():
    eta_fit, pi0_fit = _fixed_fits()
    distances = np.array([0.25, 1.0, 1.0, 2.25])
    events = _events(
        M_ETA + eta_fit.sigma_gev * np.sqrt(distances),
        np.full(len(distances), M_PI0),
    )

    with pytest.raises(ValueError, match="tie"):
        split_by_fitted_ellipse(
            events,
            eta_fit=eta_fit,
            pi0_fit=pi0_fit,
            core_fraction=0.5,
        )


@pytest.mark.parametrize("fraction", [0.0, 1.0, -0.1, 1.1, np.nan])
def test_fitted_ellipse_rejects_invalid_core_fraction(fraction):
    eta_fit, pi0_fit = _fixed_fits()
    events = _events([M_ETA, M_ETA + 0.01], [M_PI0, M_PI0])

    with pytest.raises(ValueError, match="core_fraction"):
        split_by_fitted_ellipse(
            events,
            eta_fit=eta_fit,
            pi0_fit=pi0_fit,
            core_fraction=fraction,
        )


def test_candle_selector_fits_both_margins_and_uses_every_finite_event_once():
    rng = np.random.default_rng(103)
    count = 4_000
    events = _events(
        rng.normal(M_ETA + 0.001, 0.012, count),
        rng.normal(M_PI0 - 0.0005, 0.006, count),
    )

    result = split_candle_core_tails(events, core_fraction=0.5)

    assert [len(result.core), len(result.tails)] == [2_000, 2_000]
    assert result.eta_fit.sigma_gev == pytest.approx(0.012, rel=0.15)
    assert result.pi0_fit.sigma_gev == pytest.approx(0.006, rel=0.15)
    assert np.intersect1d(
        result.core.run_number, result.tails.run_number
    ).size == 0
    assert np.sort(np.concatenate(
        (result.core.run_number, result.tails.run_number)
    )).tolist() == list(range(count))
