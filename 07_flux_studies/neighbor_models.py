"""Bounded, deterministic multi-output estimators and flux-shape composition."""
from itertools import product

import numpy as np

FAMILIES = ('extra_trees', 'kernel_ridge')
GRIDS = {
    'kernel_ridge': [dict(alpha=a, gamma=g) for a, g in
                     product((.01, 1., 100.), (.0003, .003, .03))],
    'extra_trees': [dict(min_samples_leaf=leaf, max_features=features)
                    for leaf, features in product((1, 3, 8), (.5, 1.))],
}
# Fixed reference configurations, chosen before looking at any holdout.
# KRR uses the middle grid gamma; "default" denotes this study's control.
DEFAULTS = {'kernel_ridge': dict(alpha=1., gamma=.003),
            'extra_trees': dict(min_samples_leaf=1, max_features=1.)}


def fit_model(family, features, targets, parameters, *, seed):
    from sklearn.ensemble import ExtraTreesRegressor
    from sklearn.kernel_ridge import KernelRidge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
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
