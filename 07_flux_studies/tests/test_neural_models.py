"""Native-strip neural shape contracts; no target integral enters prediction."""
import json

import numpy as np
import pytest

pytest.importorskip('torch', reason='optional neural benchmark dependency; use .venv-flux')

from flux_studies.neighbor_models import fit_model, hybrid_prediction


def examples(n=12):
    rng = np.random.default_rng(84)
    left, right = rng.uniform(.1, 2., (2, n, 128))
    weight = np.linspace(.1, .9, n)
    linear = left * (1 - weight[:, None]) + right * weight[:, None]
    features = np.c_[left, right, linear, weight * 4, (1 - weight) * 4, weight]
    shape = linear * np.linspace(.7, 1.4, 128)
    return features, shape / shape.sum(axis=1, keepdims=True) * 100


@pytest.mark.parametrize('family', ['mlp', 'cnn1d'])
def test_neural_predicts_positive_shapes_and_input_integral_reproducibly(family):
    x, y = examples()
    parameters = dict(width=8, weight_decay=.001, epochs=12)
    first = fit_model(family, x, y, parameters, seed=7)
    second = fit_model(family, x, y, parameters, seed=7)
    prediction = first.predict(x[:3])
    assert prediction.shape == (3, 128)
    assert np.all(np.isfinite(prediction)) and np.all(prediction > 0)
    np.testing.assert_array_equal(prediction, second.predict(x[:3]))
    np.testing.assert_allclose(prediction.sum(axis=1), x[:3, 256:384].sum(axis=1), rtol=1e-14)
    np.testing.assert_allclose(hybrid_prediction(prediction[0], 1234.).sum(), 1234., rtol=1e-14)
    assert len(first.diagnostics_['initializations']) >= 3
    assert all(np.isfinite(d['final_loss']) for d in first.diagnostics_['initializations'])
    json.dumps(first.diagnostics_, allow_nan=False)


@pytest.mark.parametrize('family', ['mlp', 'cnn1d'])
def test_neural_target_amplitude_and_prediction_batch_cannot_change_shape(family):
    x, y = examples()
    parameters = dict(width=8, weight_decay=0., epochs=8)
    model = fit_model(family, x, y, parameters, seed=4)
    rescaled = fit_model(family, x, y * np.arange(1, len(y) + 1)[:, None], parameters, seed=4)
    np.testing.assert_allclose(model.predict(x[:1]), rescaled.predict(x[:1]), rtol=1e-7)
    # An extreme new query cannot refit the training preprocessor.
    query = x[-1:].copy()
    query[:, :384] *= 1e7
    np.testing.assert_allclose(model.predict(np.r_[x[:1], query])[:1], model.predict(x[:1]), rtol=1e-6)
    np.testing.assert_array_equal(model.predict(np.empty((0, 387))), np.empty((0, 128)))


@pytest.mark.parametrize('family', ['mlp', 'cnn1d'])
def test_neural_rejects_invalid_training_or_prediction_input(family):
    x, y = examples()
    params = dict(width=8, weight_decay=0., epochs=2)
    for bad_x, bad_y in [(x[:, :-1], y), (x, y[:, :-1]), (x, -y), (x * np.nan, y), (x[:0], y[:0])]:
        with pytest.raises(ValueError):
            fit_model(family, bad_x, bad_y, params, seed=1)
    model = fit_model(family, x, y, params, seed=1)
    with pytest.raises(ValueError):
        model.predict(np.ones((2, 386)))
    with pytest.raises(ValueError):
        model.predict(x * np.nan)
    zero = x[:1].copy()
    zero[:, :384] = 0
    np.testing.assert_array_equal(model.predict(zero), np.zeros((1, 128)))


def test_neural_hidden_test_truth_cannot_change_features_predictions_or_selection(monkeypatch):
    from flux_studies import neighbor_models
    from flux_studies.neighbor_validation import evaluate_neighbors, split_runs
    from flux_studies.tests.test_calibrated_neighbors import records
    monkeypatch.setitem(neighbor_models.GRIDS, 'mlp', [dict(width=8, weight_decay=.001, epochs=2)])
    monkeypatch.setitem(neighbor_models.DEFAULTS, 'mlp', dict(width=8, weight_decay=.001, epochs=2))
    rows = records(30)[::3]
    roles, _ = split_runs(range(1, 31), block_size=1, seed=42)
    changed = [{**r, 'values': r['values'] * (20 if roles[r['run']] == 'test' else 1)} for r in rows]
    a = evaluate_neighbors(rows, block_size=1, seed=42, models=('mlp',))
    b = evaluate_neighbors(changed, block_size=1, seed=42, models=('mlp',))
    assert a['fits'][0]['models'] == b['fits'][0]['models']
    assert a['fits'][0]['models']['mlp']['candidates'][0]['folds'][0]['fit_diagnostics']['device'] == 'cpu'
    for first, second in zip(a['predictions'], b['predictions'], strict=True):
        np.testing.assert_array_equal(first['estimate'], second['estimate'])
