"""Small numerical methods; selection and masking belong to validation."""
from __future__ import annotations
import numpy as np


def normalize_shape(values):
    values = np.asarray(values, dtype=float)
    if values.shape[-1:] != (128,) or not np.all(np.isfinite(values)) or np.any(values < 0):
        raise ValueError('shape requires 128 finite nonnegative bins')
    sums = values.sum(axis=-1, keepdims=True)
    if np.any(sums <= 0):
        raise ValueError('zero integral has no normalized shape')
    return values / sums


def project_shape(values):
    values = np.asarray(values, dtype=float)
    if not np.all(np.isfinite(values)):
        raise ValueError('nonfinite prediction')
    return normalize_shape(np.maximum(values, 0))


def baseline_prediction(method, times, values, query_time):
    times, values = np.asarray(times, dtype=float), np.asarray(values, dtype=float)
    unavailable = dict(values=None, donor_indices=[], status='not_reconstructible', reason='no_donor')
    if len(times) == 0:
        return unavailable
    if values.shape != (len(times), 128) or not np.all(np.isfinite(values)) or not np.all(np.isfinite(times)) or not np.isfinite(query_time):
        raise ValueError('invalid baseline input')
    order = np.argsort(times, kind='stable')
    if method == 'nearest':
        index = min(order, key=lambda i: (abs(times[i]-query_time), times[i]))
        indices, prediction = [int(index)], values[index].copy()
    elif method in ('mean', 'median'):
        indices = list(range(len(times)))
        prediction = (np.mean if method == 'mean' else np.median)(values, axis=0)
    elif method == 'linear':
        before, after = order[times[order] < query_time], order[times[order] > query_time]
        if not len(before) or not len(after) or len(np.unique(times)) != len(times):
            return {**unavailable, 'reason': 'no_unique_bracket'}
        left, right = int(before[-1]), int(after[0])
        weight = (query_time-times[left])/(times[right]-times[left])
        indices, prediction = [left, right], (1-weight)*values[left]+weight*values[right]
    else:
        raise ValueError(f'unknown baseline: {method}')
    return dict(values=prediction, donor_indices=indices, status='ok', reason=None)


def fit_ridge(features, targets, *, alpha):
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    features, targets = np.asarray(features, dtype=float), np.asarray(targets, dtype=float)
    if (features.ndim != 2 or targets.shape != (len(features), 128) or len(features) < 2
            or not np.all(np.isfinite(features)) or not np.all(np.isfinite(targets))
            or not np.isfinite(alpha) or alpha <= 0):
        raise ValueError('invalid Ridge training data')
    return make_pipeline(StandardScaler(), Ridge(alpha=alpha)).fit(features, targets)
