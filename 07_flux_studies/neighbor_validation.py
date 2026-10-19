"""Run-block isolated benchmark with training-only multi-output model search."""
from __future__ import annotations

from collections import defaultdict
import numpy as np

from flux_studies.neighbor_models import DEFAULTS, FAMILIES, GRIDS, fit_model, hybrid_prediction

BASELINES = ('nearest', 'linear_unscaled', 'linear')
METHODS = BASELINES + tuple(f'{family}{suffix}' for family in FAMILIES
                            for suffix in ('', '_hybrid', '_default', '_default_hybrid'))
ALPHAS = tuple(p['alpha'] for p in GRIDS['ridge'])


def split_runs(runs, *, block_size, seed):
    if block_size < 1 or seed < 0:
        raise ValueError('invalid block size or seed')
    runs = sorted(set(runs))
    chunks = [runs[i:i + block_size] for i in range(0, len(runs), block_size)]
    if len(chunks) < 5:
        return {}, {}
    order = np.random.default_rng(seed).permutation(len(chunks))
    size = max(1, len(chunks) // 5)
    validation, test = set(order[:size]), set(order[size:2 * size])
    roles, blocks = {}, {}
    for index, chunk in enumerate(chunks):
        for run in chunk:
            roles[run] = 'validation' if index in validation else 'test' if index in test else 'train'
            blocks[run] = index
    return roles, blocks


def neighbor_example(target, donors):
    """Only count/position/group of target are read: no target truth or axis."""
    donors = [d for d in donors if d['run'] != target['run'] and d['group'] == target['group']]
    left = [d for d in donors if d['position'] < target['position']]
    right = [d for d in donors if d['position'] > target['position']]
    if not left or not right:
        return None
    left, right = max(left, key=lambda d: d['position']), min(right, key=lambda d: d['position'])
    dl, dr = target['position'] - left['position'], right['position'] - target['position']
    weight = dl / (dl + dr)
    ql, qr = left['values'] / left['count'], right['values'] / right['count']
    rate = (1 - weight) * ql + weight * qr
    nearest = ql if dl <= dr else qr
    return dict(features=np.r_[ql, qr, rate, dl, dr, weight],
                linear=rate * target['count'], nearest=nearest * target['count'],
                linear_unscaled=(1 - weight) * left['values'] + weight * right['values'],
                donors=[left['run'], right['run']], gap=dl + dr)


def _examples(targets, donors, blocks, *, hide_block=False):
    result = []
    for row in targets:
        available = [d for d in donors if not hide_block or blocks[d['run']] != blocks[row['run']]]
        example = neighbor_example(row, available)
        if example is not None:
            result.append((row, example))
    return result


def _example_audit(examples, blocks):
    return [dict(run=r['run'], block=blocks[r['run']], donors=e['donors'],
                 donor_blocks=[blocks[d] for d in e['donors']]) for r, e in examples]


def _inner_folds(train, blocks):
    unique_blocks = sorted({blocks[r['run']] for r in train})
    folds = []
    for fold in range(3):
        held_blocks = set(unique_blocks[fold::3])
        fit_rows = [r for r in train if blocks[r['run']] not in held_blocks]
        held_rows = [r for r in train if blocks[r['run']] in held_blocks]
        examples = _examples(fit_rows, fit_rows, blocks, hide_block=True)
        held = _examples(held_rows, fit_rows, blocks)
        audit = dict(fold=fold, fit_runs=[r['run'] for r in fit_rows],
                     held_runs=[r['run'] for r in held_rows],
                     training_examples=_example_audit(examples, blocks),
                     held_examples=_example_audit(held, blocks))
        folds.append((examples, held, audit))
    return folds


def _metric_summary(scores, expected):
    keys = ('relative_l1', 'shape_l1', 'absolute_relative_integral_error')
    result = dict(n=len(scores), expected=expected, unavailable=expected - len(scores))
    for key in keys:
        values = [s[key] for s in scores if s[key] is not None]
        result[key] = float(np.mean(values)) if values else None
        result[f'{key}_n'] = len(values)
    return result


def _candidate_score(truth, prediction):
    score = score_prediction(truth, prediction)
    score['absolute_relative_integral_error'] = (abs(score['relative_integral_error'])
                                               if score['relative_integral_error'] is not None else None)
    return score


def _tune_family(family, folds, *, seed):
    candidates = []
    for parameters in GRIDS[family]:
        all_scores = dict(direct=[], hybrid=[])
        expected = 0
        fold_scores = []
        for examples, held, audit in folds:
            count = sum(bool(r['values'].sum() > 0) for r, _ in held)
            expected += count
            scores = dict(direct=[], hybrid=[])
            diagnostics = None
            if len(examples) >= 2 and held:
                model = fit_model(family, np.array([e['features'] for _, e in examples]),
                                  np.array([r['values'] / r['count'] for r, _ in examples]),
                                  parameters, seed=seed)
                diagnostics = getattr(model, 'diagnostics_', None)
                predicted = model.predict(np.array([e['features'] for _, e in held]))
                for (row, example), rate in zip(held, predicted, strict=True):
                    if row['values'].sum() <= 0:
                        continue
                    direct = np.maximum(rate * row['count'], 0.)
                    scores['direct'].append(_candidate_score(row['values'], direct))
                    hybrid = hybrid_prediction(direct, example['linear'].sum())
                    if hybrid is not None:
                        scores['hybrid'].append(_candidate_score(row['values'], hybrid))
            fold_scores.append(dict(fold=audit['fold'], n_training=len(examples),
                                    n_held=len(held), fit_diagnostics=diagnostics, **{kind: _metric_summary(scores[kind], count)
                                                        for kind in scores}))
            for kind in scores:
                all_scores[kind].extend(scores[kind])
        candidates.append(dict(parameters=parameters.copy(), folds=fold_scores,
                               **{kind: _metric_summary(all_scores[kind], expected)
                                  for kind in all_scores}))
    selected = {}
    for kind in ('direct', 'hybrid'):
        # A candidate cannot benefit from dropping unreconstructible targets.
        eligible = [c for c in candidates if c[kind]['n'] > 0 and
                    c[kind]['n'] == c[kind]['expected']]
        best = min(eligible, key=lambda c: (c[kind]['relative_l1'],
                   -c['parameters'].get('alpha', 0))) if eligible else None
        selected[kind] = best['parameters'].copy() if best else None
    from flux_studies.neural_models import FIXED_PARAMETERS
    return dict(candidates=candidates, selected=selected, default=DEFAULTS[family].copy(),
                folds=[audit for _, _, audit in folds],
                fixed_parameters=(FIXED_PARAMETERS.copy() if family in ('mlp', 'cnn1d') else
                                  {'n_estimators': 64, 'n_jobs': 1, 'random_state': seed}
                                  if family == 'extra_trees' else
                                  {'kernel': 'rbf', 'standardized': True} if family == 'kernel_ridge'
                                  else {'standardized': True}))


def _alpha_curve(metadata):
    return [dict(alpha=c['parameters']['alpha'], error=c['direct']['relative_l1'],
                 n=c['direct']['n'], fold_counts={f['fold']: f['direct']['n'] for f in c['folds']})
            for c in metadata['candidates'] if c['direct']['n']]


def _choose_alpha(train, blocks):
    metadata = _tune_family('ridge', _inner_folds(train, blocks), seed=0)
    parameters = metadata['selected']['direct']
    return (parameters['alpha'] if parameters else None), _alpha_curve(metadata)


def score_prediction(truth, prediction):
    ti, pi = float(np.sum(truth)), float(np.sum(prediction))
    return dict(true_integral=ti, predicted_integral=pi,
                relative_integral_error=pi / ti - 1 if ti > 0 else None,
                relative_l1=float(np.abs(prediction - truth).sum() / ti) if ti > 0 else None,
                shape_l1=float(np.abs(prediction / pi - truth / ti).sum()) if ti > 0 and pi > 0 else None)


def _intervals(validation):
    residuals = np.array([(p['truth'] - p['estimate']) / p['estimate'].sum()
                          for p in validation if p['estimate'].sum() > 0])
    if len(residuals) < 5:
        return None
    return dict(n=len(residuals), residuals=residuals,
                bin68=np.quantile(np.abs(residuals), .68, axis=0),
                bin95=np.quantile(np.abs(residuals), .95, axis=0),
                integral68=float(np.quantile(np.abs(residuals.sum(axis=1)), .68)),
                integral95=float(np.quantile(np.abs(residuals.sum(axis=1)), .95)))


def _validate_models(models):
    models = tuple(models)
    if len(set(models)) != len(models) or any(m not in FAMILIES for m in models):
        raise ValueError('unknown or repeated model family')
    return models


def _explicit_splits(plan, universe):
    """Validate complete, unambiguous period/run and whole-block assignments."""
    if set(plan) != set(universe):
        raise ValueError('split plan periods must exactly cover the split universe')
    result = {}
    for period, assignments in plan.items():
        roles, blocks, block_roles = {}, {}, {}
        for assignment in assignments:
            try:
                run, role, block = (assignment[k] for k in ('run', 'role', 'block'))
                if run in roles:
                    raise ValueError('duplicate run in split plan')
                if role not in ('train', 'validation', 'test'):
                    raise ValueError('invalid role in split plan')
                if block in block_roles and block_roles[block] != role:
                    raise ValueError('split plan assigns different roles within a block')
                roles[run], blocks[run], block_roles[block] = role, block, role
            except (KeyError, TypeError) as exc:
                raise ValueError('split assignments require run, role and hashable block') from exc
        if set(roles) != set(universe[period]):
            raise ValueError('split plan must exactly cover the split universe')
        result[period] = roles, blocks
    return result


def _fit_configurations(examples, model_metadata, *, seed, include_defaults=True):
    """Fit each selected configuration once, shared by direct/hybrid methods."""
    fitted, method_models = {}, {}
    for family, metadata in model_metadata.items():
        configurations = {family: metadata['selected']['direct'],
                          f'{family}_hybrid': metadata['selected']['hybrid']}
        if include_defaults:
            configurations.update({f'{family}_default': metadata['default'],
                                   f'{family}_default_hybrid': metadata['default']})
        for method, parameters in configurations.items():
            if parameters is None or len(examples) < 2:
                method_models[method] = None
                continue
            key = (family, tuple(sorted(parameters.items())))
            if key not in fitted:
                fitted[key] = fit_model(family, np.array([e['features'] for _, e in examples]),
                                        np.array([r['values'] / r['count'] for r, _ in examples]),
                                        parameters, seed=seed)
            if hasattr(fitted[key], 'diagnostics_'):
                metadata.setdefault('fit_diagnostics', {})[method] = fitted[key].diagnostics_
            method_models[method] = key
    return fitted, method_models


def _method_prediction(method, row, example, index, predictions, method_models):
    if method in BASELINES:
        return example[method], 0, None
    if method_models[method] is None:
        return None, 0, 'insufficient_inner_training'
    raw = predictions[method_models[method]][index] * row['count']
    clipped = int(np.count_nonzero(raw < 0))
    prediction = np.maximum(raw, 0.)
    if method.endswith('_hybrid'):
        prediction = hybrid_prediction(prediction, example['linear'].sum())
        if prediction is None:
            return None, clipped, 'zero_predicted_shape'
    return prediction, clipped, None


def predict_missing_neighbors(records, targets, *, models=('extra_trees', 'kernel_ridge'), seed=0):
    """Predict absent spectra from compatible good donors, without target truth/axis.

    All supplied records are training data. Selection uses the same three-fold,
    donor-isolated grid as the evaluator, with one run per block. Target metadata
    needs only run/state/period/group/position/count. Returned spectra live on the
    donor common grid; this API does not establish a target native strip axis.
    Intervals remain unavailable because no independently calibrated residual
    sample is supplied (the selection folds are not independent calibration).
    """
    models = _validate_models(models)
    if seed < 0:
        raise ValueError('invalid seed')
    methods = ('linear',) + tuple(f'{family}{suffix}' for family in models for suffix in ('', '_hybrid'))
    groups, requested = defaultdict(list), defaultdict(list)
    for row in records:
        groups[row['group']].append(row)
    for target in targets:
        requested[target['group']].append(target)
    output = dict(predictions=[], fits=[], exclusions=[], methods=list(methods),
                  model_families=list(models), seed=seed,
                  uncertainty_status='unavailable_no_independent_calibration',
                  grid_status='donor_common_grid_only')
    for group, group_targets in sorted(requested.items()):
        train = groups[group]
        blocks = {run: i for i, run in enumerate(sorted({r['run'] for r in train}))}
        examples = _examples(train, train, blocks, hide_block=True)
        folds = _inner_folds(train, blocks)
        metadata = {family: _tune_family(family, folds, seed=seed) for family in models}
        fitted, method_models = _fit_configurations(examples, metadata, seed=seed, include_defaults=False)
        fit = dict(group=group, n_training=len(examples), models=metadata,
                   training_examples=_example_audit(examples, blocks),
                   intervals={method: None for method in methods},
                   uncertainty_status=output['uncertainty_status'])
        usable = []
        for target in group_targets:
            if not np.isfinite(target['count']) or target['count'] <= 0:
                reason = 'invalid_target_count'
                example = None
            else:
                example = neighbor_example(target, train)
                reason = 'no_training_bracket'
            if example is None:
                output['exclusions'].append(dict(run=target['run'], state=target['state'],
                                                 group=group, role='missing', reason=reason))
            else:
                usable.append((target, example))
        predicted = {key: model.predict(np.array([e['features'] for _, e in usable]))
                     for key, model in fitted.items()} if usable else {}
        for index, (row, example) in enumerate(usable):
            for method in methods:
                prediction, clipped, reason = _method_prediction(
                    method, row, example, index, predicted, method_models)
                if reason:
                    output['exclusions'].append(dict(run=row['run'], state=row['state'], group=group,
                                                     role='missing', method=method, reason=reason))
                    continue
                output['predictions'].append(dict(
                    run=row['run'], state=row['state'], period=row['period'], group=group,
                    role='missing', method=method, donors=example['donors'], gap=example['gap'],
                    count=row['count'], estimate=prediction, predicted_integral=float(prediction.sum()),
                    negative_bins_projected=clipped, lower68=None, upper68=None, lower95=None, upper95=None,
                    uncertainty_status=output['uncertainty_status']))
        output['fits'].append(fit)
    output['status'] = 'experimental_candidates' if output['predictions'] else 'insufficient_data'
    return output


def evaluate_neighbors(records, *, block_size, seed, split_runs_by_period=None,
                       models=('ridge',), split_plan=None):
    """Evaluate using original eligible runs for splits, retained records for fits.

    ``split_runs_by_period`` must describe eligibility before quality exclusion.
    An omitted mapping retains legacy behavior for callers without exclusions.
    An explicit ``split_plan`` maps periods to run/role/block assignments and
    must exactly cover that universe (or all retained runs when omitted).
    """
    models = _validate_models(models)
    methods = BASELINES + tuple(f'{family}{suffix}' for family in models
                               for suffix in ('', '_hybrid', '_default', '_default_hybrid'))
    groups, periods = defaultdict(list), defaultdict(set)
    for row in records:
        groups[row['group']].append(row)
        periods[row['period']].add(row['run'])
    if split_runs_by_period is not None:
        universe = {p: set(runs) for p, runs in split_runs_by_period.items()}
        if any(not runs <= universe.get(p, set()) for p, runs in periods.items()):
            raise ValueError('split universe does not contain every retained run')
        periods = universe
    splits = (_explicit_splits(split_plan, periods) if split_plan is not None else
              {p: split_runs(runs, block_size=block_size, seed=seed) for p, runs in periods.items()})
    output = dict(predictions=[], fits=[], exclusions=[], splits={
        p: [dict(run=r, role=roles[r], block=blocks[r]) for r in sorted(roles)]
        for p, (roles, blocks) in splits.items()}, block_size=block_size, seed=seed,
        methods=list(methods), model_families=list(models))
    for group, rows in sorted(groups.items()):
        roles, blocks = splits[group[0]]
        if not roles:
            output['exclusions'].append(dict(group=group, reason='fewer_than_five_blocks'))
            continue
        train = [r for r in rows if roles[r['run']] == 'train']
        examples = _examples(train, train, blocks, hide_block=True)
        folds = _inner_folds(train, blocks)
        model_metadata = {family: _tune_family(family, folds, seed=seed) for family in models}
        ridge = model_metadata.get('ridge')
        alpha = ridge['selected']['direct']['alpha'] if ridge and ridge['selected']['direct'] else None
        fit = dict(group=group, alpha=alpha, tuning=_alpha_curve(ridge) if ridge else [],
                   n_training=len(examples), models=model_metadata,
                   training_examples=_example_audit(examples, blocks), intervals={},
                   model_status='ok' if any(m['selected']['direct'] for m in model_metadata.values())
                   else 'insufficient_inner_training')
        fitted, method_models = _fit_configurations(examples, model_metadata, seed=seed)
        group_predictions = []
        for role in ('train', 'validation', 'test'):
            targets = [r for r in rows if roles[r['run']] == role]
            usable = examples if role == 'train' else _examples(targets, train, blocks)
            present = {r['run'] for r, e in usable}
            for row in targets:
                if row['run'] not in present:
                    output['exclusions'].append(dict(run=row['run'], group=group, role=role, reason='no_training_bracket'))
            # Shared configurations are fit once, then predict each role in one batch.
            predictions = {key: model.predict(np.array([e['features'] for _, e in usable]))
                           for key, model in fitted.items()} if usable else {}
            for index, (row, example) in enumerate(usable):
                for method in methods:
                    prediction, clipped, reason = _method_prediction(
                        method, row, example, index, predictions, method_models)
                    if reason is not None:
                        output['exclusions'].append(dict(run=row['run'], group=group, role=role,
                                                         method=method, reason=reason))
                        continue
                    group_predictions.append(dict(run=row['run'], state=row['state'], period=row['period'],
                                                  role=role, method=method, donors=example['donors'],
                                                  gap=example['gap'], count=row['count'],
                                                  truth=row['values'].copy(), estimate=prediction,
                                                  negative_bins_projected=clipped,
                                                  lower68=None, upper68=None, lower95=None, upper95=None,
                                                  **score_prediction(row['values'], prediction)))
        for method in methods:
            intervals = _intervals([p for p in group_predictions if p['role'] == 'validation' and p['method'] == method])
            fit['intervals'][method] = intervals
            if intervals is None:
                continue
            for prediction in group_predictions:
                if prediction['method'] != method:
                    continue
                integral = prediction['predicted_integral']
                active = prediction['truth'] + prediction['estimate'] > 0
                for level in (68, 95):
                    error = intervals[f'bin{level}'] * integral
                    lower, upper = np.maximum(prediction['estimate'] - error, 0), prediction['estimate'] + error
                    prediction[f'lower{level}'], prediction[f'upper{level}'] = lower, upper
                    inside = (prediction['truth'] >= lower) & (prediction['truth'] <= upper)
                    prediction[f'coverage{level}'] = float(inside[active].mean()) if active.any() else None
                    prediction[f'integral_covered{level}'] = bool(abs(prediction['true_integral'] - integral)
                                                                <= intervals[f'integral{level}'] * integral)
        output['fits'].append(fit)
        output['predictions'].extend(group_predictions)
    output['status'] = 'exploratory' if any(p['role'] == 'test' for p in output['predictions']) else 'insufficient_data'
    return output
