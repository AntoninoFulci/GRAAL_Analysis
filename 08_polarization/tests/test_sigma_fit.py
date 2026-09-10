from __future__ import annotations

import numpy as np
import pytest

from contracts import PolarizationContractError
from sigma_fit import fit_sigma_binned


def asimov_sample(sigma: float = 0.35) -> dict[str, np.ndarray]:
    phi_one_state = (np.arange(16, dtype=float) + 0.5) * np.pi / 16.0
    phi = np.concatenate([phi_one_state, phi_one_state])
    orientation_sign = np.concatenate([-np.ones(16), np.ones(16)])
    polarization = np.concatenate([np.full(16, 0.72), np.full(16, 0.64)])
    # Different phi response in each state catches dropping acceptance from model.
    acceptance = np.concatenate(
        [
            0.25 + 0.65 * np.sin(phi_one_state) ** 2,
            0.30 + 0.55 * np.cos(phi_one_state - 0.2) ** 2,
        ]
    )
    exposure = np.concatenate([np.full(16, 1.3), np.full(16, 0.8)])
    state_scale = np.where(orientation_sign < 0, 1100.0, 850.0)
    observed = (
        exposure
        * acceptance
        * state_scale
        * (1.0 + orientation_sign * polarization * sigma * np.cos(2.0 * phi))
    )
    return {
        "phi": phi,
        "orientation_sign": orientation_sign,
        "polarization": polarization,
        "acceptance": acceptance,
        "exposure": exposure,
        "observed": observed,
    }


def test_acceptance_aware_fit_recovers_exact_asimov_sigma():
    result = fit_sigma_binned(**asimov_sample(0.35))
    assert result.converged
    assert result.sigma == pytest.approx(0.35, abs=2e-6)
    assert result.stat_uncertainty > 0.0
    assert result.covariance.shape == (3, 3)
    assert result.ndof == 29
    assert result.pearson_chi2 == pytest.approx(0.0, abs=1e-8)
    assert np.max(np.abs(result.residuals)) < 1e-4


def test_orientation_sign_swap_inverts_fitted_sigma():
    sample = asimov_sample(-0.42)
    nominal = fit_sigma_binned(**sample)
    sample["orientation_sign"] = -sample["orientation_sign"]
    swapped = fit_sigma_binned(**sample)
    assert nominal.sigma == pytest.approx(-0.42, abs=2e-6)
    assert swapped.sigma == pytest.approx(0.42, abs=2e-6)


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("acceptance", 0.0, "acceptance"),
        ("polarization", 1.1, "polarization"),
        ("exposure", 0.0, "exposure"),
        ("observed", -1.0, "observed"),
        ("orientation_sign", 0.0, "orientation_sign"),
    ],
)
def test_fit_rejects_nonphysical_inputs(field, value, match):
    sample = asimov_sample()
    sample[field] = sample[field].copy()
    sample[field][0] = value
    with pytest.raises(PolarizationContractError, match=match):
        fit_sigma_binned(**sample)


def test_fit_rejects_incomplete_angular_coverage():
    sample = asimov_sample()
    sample["phi"] = np.full_like(sample["phi"], 0.1)
    with pytest.raises(PolarizationContractError, match="angular coverage"):
        fit_sigma_binned(**sample)


def test_fit_rejects_shape_mismatch_and_nonfinite_values():
    sample = asimov_sample()
    sample["observed"] = sample["observed"][:-1]
    with pytest.raises(PolarizationContractError, match="same shape"):
        fit_sigma_binned(**sample)

    sample = asimov_sample()
    sample["phi"][0] = np.nan
    with pytest.raises(PolarizationContractError, match="finite"):
        fit_sigma_binned(**sample)
