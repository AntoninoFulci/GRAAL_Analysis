"""Bounded, deterministic multi-output estimators and flux-shape composition."""
from itertools import product

import numpy as np

FAMILIES = ('ridge', 'kernel_ridge', 'extra_trees', 'mlp', 'cnn1d')
GRIDS = {
    'mlp': [dict(width=w, weight_decay=d) for w, d in product((32, 64), (0., .001))],
    'cnn1d': [dict(width=w, weight_decay=d) for w, d in product((8, 16), (0., .001))],
    'ridge': [dict(alpha=a) for a in (.001, .01, .1, 1., 10., 100., 1000.)],
    'kernel_ridge': [dict(alpha=a, gamma=g) for a, g in
                     product((.01, 1., 100.), (.0003, .003, .03))],
    'extra_trees': [dict(min_samples_leaf=leaf, max_features=features)
                    for leaf, features in product((1, 3, 8), (.5, 1.))],
}
# Fixed reference configurations, chosen before looking at any holdout.
# KRR uses the middle grid gamma; "default" denotes this study's control.
DEFAULTS = {'mlp': dict(width=32, weight_decay=.001),
            'cnn1d': dict(width=8, weight_decay=.001), 'ridge': dict(alpha=1.), 'kernel_ridge': dict(alpha=1., gamma=.003),
            'extra_trees': dict(min_samples_leaf=1, max_features=1.)}


def fit_model(family, features, targets, parameters, *, seed):
    if family in ('mlp', 'cnn1d'):
        from flux_studies.neural_models import TorchShapeEnsemble
        return TorchShapeEnsemble(family, seed=seed, **parameters).fit(features, targets)

    from sklearn.ensemble import ExtraTreesRegressor
    from sklearn.kernel_ridge import KernelRidge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from flux_studies.methods import fit_ridge

    if family == 'ridge':
        return fit_ridge(features, targets, alpha=parameters['alpha'])
    if family == 'kernel_ridge':
        model = make_pipeline(StandardScaler(), KernelRidge(kernel='rbf', **parameters))
    elif family == 'extra_trees':
        model = ExtraTreesRegressor(n_estimators=64, n_jobs=1, random_state=seed, **parameters)
    else:
        raise ValueError(f'unknown model family: {family}')
    return model.fit(features, targets)


def hybrid_prediction(prediction, linear_integral):
    """Return a nonnegative ML shape at the baseline integral, or unavailable."""
    positive = np.maximum(np.asarray(prediction, dtype=float), 0.)
    integral = float(positive.sum())
    if not np.isfinite(integral) or integral <= 0:
        return None
    return positive / integral * linear_integral
