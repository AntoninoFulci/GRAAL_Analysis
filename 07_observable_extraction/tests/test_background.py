import numpy as np
import pytest

from graal_common.physics.channels import ETA_PI0_HYP, M_ETA, M_PI0, M_PROTON
from observable_extraction.core.background import (
    Region,
    SidebandWindows,
    classify_region,
    correct_sigma,
    correct_sigma_with_uncertainty,
    factorized_sideband_template,
    fit_background_fraction,
    fraction_in_mask,
    signal_leakage_fraction,
    validate_signal_leakage,
)


WINDOWS = SidebandWindows(
    eta_center=M_ETA,
    eta_half_width=ETA_PI0_HYP.heavy_window,
    pi0_center=M_PI0,
    pi0_half_width=ETA_PI0_HYP.light_window,
    missing_center=M_PROTON,
    missing_half_width=0.06,
)


@pytest.mark.parametrize(
    ("eta_pull", "pi0_pull", "missing_pull", "expected"),
    [
        (0.2, -0.3, 0.5, Region.SIGNAL),
        (2.5, -2.2, 0.2, Region.HARD_SIDEBAND),
        (1.4, 0.2, 0.3, Region.TRANSITION),
        (4.2, 2.5, 0.1, Region.OUTSIDE),
    ],
)
def test_multidimensional_region_classification(
    eta_pull, pi0_pull, missing_pull, expected
):
    region = classify_region(
        eta_mass=M_ETA + eta_pull * WINDOWS.eta_half_width,
        pi0_mass=M_PI0 + pi0_pull * WINDOWS.pi0_half_width,
        missing_mass=M_PROTON + missing_pull * WINDOWS.missing_half_width,
        windows=WINDOWS,
    )

    assert region is expected


def test_template_fraction_fit_recovers_known_mixture():
    signal = np.array([0.60, 0.30, 0.10])
    background = np.array([0.10, 0.30, 0.60])
    data = 100_000 * (0.7 * signal + 0.3 * background)

    estimate = fit_background_fraction(data, signal, background)

    assert estimate.fraction == pytest.approx(0.30, abs=1e-5)
    assert estimate.error > 0.0
    assert estimate.converged is True


def test_background_correction_inverts_mixture():
    observed = 0.7 * 0.40 + 0.3 * (-0.10)

    corrected = correct_sigma(
        observed, background_fraction=0.3, sigma_background=-0.10
    )

    assert corrected == pytest.approx(0.40)


def test_background_correction_propagates_independent_uncertainties():
    corrected, error = correct_sigma_with_uncertainty(
        sigma_observed=0.25,
        observed_error=0.04,
        background_fraction=0.2,
        fraction_error=0.03,
        sigma_background=-0.1,
        background_error=0.05,
    )

    assert corrected == pytest.approx(0.3375)
    expected_variance = (
        (0.04 / 0.8) ** 2
        + (0.2 * 0.05 / 0.8) ** 2
        + ((0.25 - (-0.1)) * 0.03 / 0.8**2) ** 2
    )
    assert error == pytest.approx(np.sqrt(expected_variance))


def test_signal_leakage_gate_rejects_impure_hard_sideband():
    regions = np.array(
        [Region.SIGNAL] * 90 + [Region.HARD_SIDEBAND] * 10,
        dtype=object,
    )

    assert signal_leakage_fraction(regions) == pytest.approx(0.10)
    with pytest.raises(ValueError, match="signal leakage"):
        validate_signal_leakage(regions, maximum=0.05)


def test_factorized_sideband_template_extrapolates_into_signal_region():
    histogram = np.zeros((3, 3, 3))
    histogram[0, 0, 1] = 10
    histogram[0, 1, 2] = 20
    histogram[1, 2, 0] = 30

    template = factorized_sideband_template(histogram)

    assert template.shape == histogram.shape
    assert template.sum() == pytest.approx(1.0)
    assert template[1, 1, 1] > 0.0


def test_fraction_in_mask_converts_broad_fit_to_signal_region_fraction():
    signal = np.array([0.8, 0.2])
    background = np.array([0.25, 0.75])

    fraction = fraction_in_mask(0.3, signal, background, np.array([True, False]))

    expected = 0.3 * 0.25 / (0.7 * 0.8 + 0.3 * 0.25)
    assert fraction == pytest.approx(expected)
