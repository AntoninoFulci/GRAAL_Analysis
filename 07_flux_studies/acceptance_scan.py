"""Inference-only cuts for a fixed, nested whole-run acceptance scan.

Thresholds are frozen analyst choices, not physical constants. Only training
donor spectra, target metadata, estimates and validation-calibrated replicas
enter decisions. Test truth, error metrics and empirical coverage never enter.
"""
from collections import defaultdict
from numbers import Integral

import numpy as np


POLICIES = tuple(
    dict(name=name, max_donor_distance_minutes=distance, count_trim_quantile=trim,
         max_donor_normalization_difference=normalization,
         max_model_shape_l1=shape, max_predicted_l1_uncertainty95=uncertainty)
    for name, distance, trim, normalization, shape, uncertainty in zip(
        ('strict_1', 'strict_2', 'moderate_3', 'loose_4', 'loose_5'),
        (15., 30., 45., 75., 150.), (.10, .05, .025, 0., 0.),
        (.10, .20, .35, .50, 1.), (.03, .05, .08, .12, .20),
        (.05, .10, .20, .35, .50), strict=True))

_PRIMARY = 'extra_trees_hybrid'
_COMPARISON = 'kernel_ridge_hybrid'


def _run(value):
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ValueError('run IDs must be integers')
    return int(value)


def _key(row, *, method=False):
    try:
        result = (row['period'], _run(row['run']), row['state'])
        if not isinstance(result[0], str) or not isinstance(result[2], str):
            raise ValueError('period and state IDs must be strings')
        return result + (row['method'],) if method else result
    except KeyError as exc:
        raise ValueError('missing identity field') from exc


def _index(rows, *, method=False):
    result = {}
    for row in rows:
        key = _key(row, method=method)
        if key in result:
            raise ValueError(f'duplicate identity: {key}')
        result[key] = row
    return result


def _spectrum(value):
    try:
        array = np.asarray(value, dtype=float)
    except (ValueError, TypeError):
        return None
    if (array.shape != (128,) or not np.isfinite(array).all()
            or np.any(array < 0) or not np.isfinite(array.sum()) or array.sum() <= 0):
        return None
    return array


def _positive(value):
    try:
        value = float(value)
        return value if np.isfinite(value) and value > 0 else None
    except (TypeError, ValueError):
        return None


def _replicas(uncertainty):
    if uncertainty is None:
        return {}, None, 0, {}
    keys = uncertainty.get('keys', [])
    _index(keys, method=True)
    requested = uncertainty.get('requested_replicas', 0)
    if isinstance(requested, bool) or not isinstance(requested, Integral) or requested < 0:
        raise ValueError('requested_replicas must be a nonnegative integer')
    draws = np.asarray(uncertainty.get('draws', np.empty((requested, 0, 128))), dtype=float)
    if draws.shape != (requested, len(keys), 128):
        raise ValueError('malformed aligned replica draw shape')
    support = {}
    for row in uncertainty.get('residual_support', []):
        if row['period'] in support:
            raise ValueError('duplicate residual support period')
        support[row['period']] = row
    return {_key(row, method=True): i for i, row in enumerate(keys)}, draws, int(requested), support


def state_diagnostics(records, study, uncertainty, *, excluded_runs=()):
    """Return every target represented by any test prediction, even without ET.

    The caller must verify coverage against its actual mask when all methods
    are missing for a target. ``excluded_runs`` must be the frozen quality
    exclusion set; it is not inferred from model-fit exclusion messages.
    """
    rows = _index(records)
    predictions = _index(study['predictions'], method=True)
    excluded = {_run(run) for run in excluded_runs}
    splits = {}
    for period, assignments in study['splits'].items():
        for assignment in assignments:
            key = (period, _run(assignment['run']))
            if key in splits:
                raise ValueError('duplicate split run')
            if assignment['role'] not in ('train', 'validation', 'test'):
                raise ValueError('invalid split role')
            splits[key] = assignment
    replica_keys, draws, requested, support = _replicas(uncertainty)
    targets = defaultdict(dict)
    for key, prediction in predictions.items():
        if prediction['role'] == 'test':
            targets[key[:3]][key[3]] = prediction
    output = []
    for key, methods in sorted(targets.items()):
        period, run, state = key
        blockers = []
        metrics = dict(count=None, count_bounds={}, max_donor_distance_minutes=None,
                       donor_normalization_difference=None, model_shape_l1=None,
                       predicted_l1_uncertainty95=None, requested_replicas=requested,
                       valid_replicas=0, available_replica_fraction=None,
                       paired_validation_runs=0, validation_blocks=0)
        target = rows.get(key)
        if target is None:
            blockers.append('missing_target_metadata')
        if run in excluded:
            blockers.append('excluded_target')
        if splits.get((period, run), {}).get('role') != 'test':
            blockers.append('target_not_in_test_split')
        spectra = {}
        for method in (_PRIMARY, _COMPARISON):
            prediction = methods.get(method)
            spectra[method] = _spectrum(prediction.get('estimate')) if prediction else None
            if spectra[method] is None:
                blockers.append('missing_' + method if prediction is None else 'invalid_' + method)
        if all(spectra[method] is not None for method in spectra):
            et, krr = spectra[_PRIMARY], spectra[_COMPARISON]
            metrics['model_shape_l1'] = float(np.abs(et / et.sum() - krr / krr.sum()).sum())

        reference = methods.get(_PRIMARY, next(iter(methods.values())))
        donors = [_run(d) for d in reference.get('donors', [])]
        if any(d in excluded for d in donors):
            blockers.append('excluded_donor')
        if any(method in methods and methods[method].get('donors') != donors
               for method in (_PRIMARY, _COMPARISON)):
            blockers.append('inconsistent_method_donors')
        donor_rows = [rows.get((period, d, state)) for d in donors]
        bracket_valid = (target is not None and len(set(donors)) == len(donors) == 2
                         and all(d != run and splits.get((period, d), {}).get('role') == 'train'
                                 for d in donors)
                         and all(d is not None and d['group'] == target['group'] for d in donor_rows))
        if bracket_valid:
            try:
                positions = [float(d['position']) for d in donor_rows]
                position = float(target['position'])
                bracket_valid = (np.isfinite([*positions, position]).all()
                                 and positions[0] < position < positions[1])
            except (KeyError, TypeError, ValueError):
                bracket_valid = False
        if not bracket_valid:
            blockers.append('invalid_training_bracket')
        else:
            metrics['max_donor_distance_minutes'] = float(max(position - positions[0], positions[1] - position))
            rates = []
            for donor in donor_rows:
                values, count = _spectrum(donor.get('values')), _positive(donor.get('count'))
                if values is not None and count is not None:
                    rates.append(float(values.sum() / count))
            if len(rates) == 2:
                metrics['donor_normalization_difference'] = float(abs(rates[0] - rates[1]) / np.mean(rates))
            else:
                blockers.append('invalid_donor_normalization')
        if target is not None:
            count = metrics['count'] = _positive(target.get('count'))
            counts = [_positive(row.get('count')) for row in records
                      if row['group'] == target['group'] and row['run'] not in excluded
                      and splits.get((row['period'], row['run']), {}).get('role') == 'train']
            if count is None or not counts or any(value is None for value in counts):
                blockers.append('invalid_training_count_support')
            else:
                for policy in POLICIES:
                    q = policy['count_trim_quantile']
                    metrics['count_bounds'][policy['name']] = np.quantile(counts, [q, 1 - q]).tolist()
                if not min(counts) <= count <= max(counts):
                    blockers.append('count_outside_training_range')

        calibration = support.get(period, {})
        paired = calibration.get('paired_validation_runs', [])
        paired_ids = {_run(r) for r in paired}
        if len(paired_ids) != len(paired):
            raise ValueError('duplicate paired validation run')
        valid_pairs = {r for r in paired_ids if r not in excluded
                       and splits.get((period, r), {}).get('role') == 'validation'}
        blocks = {splits[period, r]['block'] for r in valid_pairs}
        metrics['paired_validation_runs'], metrics['validation_blocks'] = len(valid_pairs), len(blocks)
        if (len(valid_pairs) < 8 or len(blocks) < 4 or valid_pairs != paired_ids
                or state not in calibration.get('states', [])):
            blockers.append('insufficient_paired_validation_support')
        index = replica_keys.get((*key, _PRIMARY))
        if index is None or draws is None or requested == 0:
            blockers.append('missing_uncertainty')
        else:
            values = draws[:, index]
            valid = (np.isfinite(values).all(axis=1) & (values >= 0).all(axis=1)
                     & np.isfinite(values.sum(axis=1)) & (values.sum(axis=1) > 0))
            number = metrics['valid_replicas'] = int(valid.sum())
            metrics['available_replica_fraction'] = number / requested
            if number < 32:
                blockers.append('insufficient_valid_replicas')
            if number / requested < .9:
                blockers.append('insufficient_replica_availability')
            central = spectra[_PRIMARY]
            if number and central is not None:
                metrics['predicted_l1_uncertainty95'] = float(np.quantile(
                    np.abs(values[valid] - central).sum(axis=1) / central.sum(), .95))
        output.append(dict(period=period, run=run, state=state, donors=donors,
                           metrics=metrics, blockers=blockers))
    return output


def decide_runs(diagnostics, policy, *, excluded_runs=()):
    """Accept a run only when every represented masked state passes."""
    _index(diagnostics)
    if policy not in POLICIES:
        raise ValueError('policy must be one of the frozen ladder policies')
    excluded = {_run(run) for run in excluded_runs}
    state_decisions = []
    passed = defaultdict(list)
    limits = ('donor_normalization_difference', 'model_shape_l1', 'predicted_l1_uncertainty95')
    for diagnostic in diagnostics:
        reasons = list(diagnostic['blockers'])
        run, metrics = diagnostic['run'], diagnostic['metrics']
        if run in excluded:
            reasons.append('excluded_target')
        if any(d in excluded for d in diagnostic['donors']):
            reasons.append('excluded_donor')
        for metric in ('donor_distance_minutes', *limits):
            metric_key = 'max_donor_distance_minutes' if metric == 'donor_distance_minutes' else metric
            value = metrics.get(metric_key)
            if value is None or not np.isfinite(value) or value > policy['max_' + metric]:
                reasons.append(metric + '_cut')
        bounds = metrics.get('count_bounds', {}).get(policy['name'])
        count = metrics.get('count')
        if bounds is None or count is None or not bounds[0] <= count <= bounds[1]:
            reasons.append('training_count_quantile_cut')
        reasons = list(dict.fromkeys(reasons))
        accepted = not reasons
        passed[run].append(accepted)
        state_decisions.append(dict(period=diagnostic['period'], run=run, state=diagnostic['state'],
                                    accepted=accepted, blockers=reasons))
    accepted = sorted(run for run, states in passed.items() if all(states))
    return dict(policy=policy['name'], accepted_runs=accepted,
                rejected_runs=sorted(set(passed) - set(accepted)), state_decisions=state_decisions)
