from __future__ import annotations

import numpy as np
import pytest

from contracts import PolarizationContractError
from flux_ratio import fit_flux_ratio, flux_normalized_ratio


def asimov_counts(sigma: float):
    phi = (np.arange(12, dtype=float) + 0.5) * np.pi / 12.0
    cosine = np.cos(2.0 * phi)
    acceptance = 0.15 + 0.75 * np.sin(phi + 0.17) ** 2
    flux_vertical = np.full(12, 1.2e6)
    flux_horizontal = np.full(12, 0.9e6)
    p_vertical = np.full(12, 0.83)
    p_horizontal = np.full(12, 0.71)
    rate = 0.004 * acceptance
    vertical = rate * flux_vertical * (1.0 + p_vertical * sigma * cosine)
    horizontal = rate * flux_horizontal * (1.0 - p_horizontal * sigma * cosine)
    return {
        "phi": phi,
        "vertical": vertical,
        "horizontal": horizontal,
        "flux_vertical": flux_vertical,
        "flux_horizontal": flux_horizontal,
        "polarization_vertical": p_vertical,
        "polarization_horizontal": p_horizontal,
    }


@pytest.mark.parametrize("injected", [-0.7, -0.25, 0.0, 0.38, 0.75])
def test_profiled_flux_ratio_fit_recovers_asimov_sigma_with_nonuniform_acceptance(injected):
    result = fit_flux_ratio(**asimov_counts(injected))
    assert result.converged
    assert result.sigma == pytest.approx(injected, abs=2e-6)
    assert result.stat_uncertainty > 0.0
    assert result.binomial_deviance == pytest.approx(0.0, abs=1e-8)
    assert result.ndof == 11


def test_equal_polarization_reduces_to_normalized_ratio_identity():
    sample = asimov_counts(0.4)
    sample["polarization_vertical"][:] = 0.8
    sample["polarization_horizontal"][:] = 0.8
    phi = sample["phi"]
    acceptance = 0.15 + 0.75 * np.sin(phi + 0.17) ** 2
    rate = 0.004 * acceptance
    cosine = np.cos(2.0 * phi)
    sample["vertical"] = (
        rate * sample["flux_vertical"] * (1.0 + 0.8 * 0.4 * cosine)
    )
    sample["horizontal"] = (
        rate * sample["flux_horizontal"] * (1.0 - 0.8 * 0.4 * cosine)
    )
    ratio, uncertainty = flux_normalized_ratio(
        sample["vertical"],
        sample["horizontal"],
        sample["flux_vertical"],
        sample["flux_horizontal"],
    )
    assert ratio == pytest.approx(0.5 * (1.0 + 0.8 * 0.4 * cosine))
    assert np.all(uncertainty > 0.0)


def test_flux_ratio_supports_exact_uniform_phi_bin_average():
    sample = asimov_counts(0.52)
    width = np.pi / 12.0
    scale = np.sin(width) / width
    center_cosine = np.cos(2.0 * sample["phi"])
    rate = 0.004 * (0.15 + 0.75 * np.sin(sample["phi"] + 0.17) ** 2)
    sample["vertical"] = rate * sample["flux_vertical"] * (
        1.0 + sample["polarization_vertical"] * 0.52 * scale * center_cosine
    )
    sample["horizontal"] = rate * sample["flux_horizontal"] * (
        1.0 - sample["polarization_horizontal"] * 0.52 * scale * center_cosine
    )
    result = fit_flux_ratio(**sample, modulation_scale=scale)
    assert result.sigma == pytest.approx(0.52, abs=2e-6)


def test_state_label_swap_inverts_sigma():
    sample = asimov_counts(-0.45)
    nominal = fit_flux_ratio(**sample)
    swapped = fit_flux_ratio(
        phi=sample["phi"],
        vertical=sample["horizontal"],
        horizontal=sample["vertical"],
        flux_vertical=sample["flux_horizontal"],
        flux_horizontal=sample["flux_vertical"],
        polarization_vertical=sample["polarization_horizontal"],
        polarization_horizontal=sample["polarization_vertical"],
    )
    assert nominal.sigma == pytest.approx(-0.45, abs=2e-6)
    assert swapped.sigma == pytest.approx(0.45, abs=2e-6)


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("vertical", -1.0, "counts"),
        ("horizontal", -1.0, "counts"),
        ("flux_vertical", 0.0, "flux"),
        ("flux_horizontal", 0.0, "flux"),
        ("polarization_vertical", 0.0, "polarization"),
        ("polarization_horizontal", 1.1, "polarization"),
    ],
)
def test_flux_ratio_rejects_nonphysical_inputs(field, value, match):
    sample = asimov_counts(0.2)
    sample[field] = sample[field].copy()
    sample[field][0] = value
    with pytest.raises(PolarizationContractError, match=match):
        fit_flux_ratio(**sample)


def test_flux_ratio_rejects_shape_mismatch_and_insufficient_phi_coverage():
    sample = asimov_counts(0.2)
    sample["vertical"] = sample["vertical"][:-1]
    with pytest.raises(PolarizationContractError, match="same shape"):
        fit_flux_ratio(**sample)

    sample = asimov_counts(0.2)
    sample["phi"][:] = 0.2
    with pytest.raises(PolarizationContractError, match="angular coverage"):
        fit_flux_ratio(**sample)


def test_flux_ratio_rejects_boundary_pegged_solution():
    sample = asimov_counts(0.999999)
    with pytest.raises(PolarizationContractError, match="boundary"):
        fit_flux_ratio(**sample)
