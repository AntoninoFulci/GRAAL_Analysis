import numpy as np
import pytest
from observable_extraction.core.signal_yields import (
    MassModel,
    fit_mass_model,
    signal_weights,
    yield_influence,
)


def test_templates_respect_cut_and_linear_signal_closure():
    model = MassModel(bins=16, extended=True)
    theta = model.initial.copy()
    templates, fractions = model.components(theta)
    np.testing.assert_allclose(templates.sum(axis=0), 1)
    assert np.all(templates[~model.active] == 0)
    weights = signal_weights(templates, templates @ fractions)
    np.testing.assert_allclose(weights @ templates, [1, 0, 0, 0], atol=1e-10)
    counts = templates @ np.array([7000, 1200, 900, 500])
    assert counts @ weights == pytest.approx(7000)


def test_asimov_fit_and_influence_includes_shape_count_covariance():
    model = MassModel(bins=16, extended=True)
    templates, fractions = model.components(model.initial)
    counts = 30000 * (templates @ fractions)
    fit = fit_mass_model(model, counts)
    assert fit["converged"]
    assert fit["signal_yield"] == pytest.approx(30000 * fractions[0], rel=0.003)
    # Splitting a sample must preserve yield and uncertainty when recombined.
    split = np.stack([0.3 * counts, 0.7 * counts])
    yields, covariance, _ = yield_influence(model, fit, split)
    y1, c1, _ = yield_influence(model, fit, counts[None, :])
    assert yields.sum() == pytest.approx(y1[0])
    assert covariance.sum() == pytest.approx(c1[0, 0], rel=1e-6)
    assert abs(covariance[0, 1]) > 1
    assert np.linalg.eigvalsh(covariance).min() > 0


def test_invalid_mass_counts_rejected():
    model = MassModel(bins=16, extended=True)
    with pytest.raises(ValueError):
        fit_mass_model(model, np.full(model.bins**2, -1))


def test_nominal_two_component_asimov_closure_and_empty_cells():
    model = MassModel(bins=16)
    templates, fractions = model.components(model.initial)
    counts = 12000 * (templates @ fractions)
    fit = fit_mass_model(model, counts)
    y, covariance, _ = yield_influence(
        model, fit, np.stack([counts, np.zeros_like(counts)])
    )
    assert y[0] == pytest.approx(12000 * fractions[0], rel=0.003)
    assert y[1] == 0
    assert covariance[1, 1] == 0
    with pytest.raises(ValueError, match="disjoint"):
        yield_influence(model, fit, np.stack([counts, counts]))
