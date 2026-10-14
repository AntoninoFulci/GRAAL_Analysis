"""Blocked, run-disjoint masking and nested model selection."""
from __future__ import annotations

from collections import defaultdict
import numpy as np
from graal_common.parallel import ordered_map, validate_workers
from flux_studies.metadata import GROUP_FIELDS, STATES, eligible, compatible, acquisition_midpoint, temporal_run_blocks
from flux_studies.methods import normalize_shape, project_shape, baseline_prediction, fit_ridge

METHODS = ('nearest', 'mean', 'median', 'linear', 'ridge')
ALPHAS = (0.1, 1., 10., 100.)


def blocked_folds(metadata, *, mode, n_splits):
    if mode not in ('offline', 'causal') or n_splits < 2:
        raise ValueError('invalid split mode or fold count')
    groups = defaultdict(dict)
    for (run, state), row in metadata.items():
        if not eligible(row):
            continue
        group = tuple(row[field] for field in GROUP_FIELDS)
        start, end = groups[group].get(run, (row['start'], row['end']))
        groups[group][run] = min(start, row['start']), max(end, row['end'])
    folds = []
    for group, intervals in sorted(groups.items()):
        members = {key: row for key, row in metadata.items()
                   if eligible(row) and tuple(row[f] for f in GROUP_FIELDS) == group}
        blocks = temporal_run_blocks(members, intervals)
        if len(blocks) < 2:
            continue
        partitions = [[run for i in chunk for run in blocks[int(i)]]
                      for chunk in np.array_split(np.arange(len(blocks)), min(n_splits, len(blocks)))]
        for index, test in enumerate(partitions):
            train = [run for j, part in enumerate(partitions) if j != index and (mode == 'offline' or j < index) for run in part]
            if train:
                folds.append(dict(fold_id=len(folds), group=group, train_runs=train, test_runs=test))
    return folds


def _features(audit, key, pattern, mode):
    metadata, histograms = audit['metadata'], audit['histograms']
    row = metadata[key]
    features = [acquisition_midpoint(row)]
    for state in STATES:
        if state in pattern:
            continue
        other = (key[0], state)
        context = metadata.get(other)
        known = (other in histograms and context is not None and eligible(context)
                 and all(context[field] == row[field] for field in GROUP_FIELDS)
                 and (mode == 'offline' or context['end'] <= row['start']))
        if known:
            values = histograms[other]
            features.extend([1., float(np.log1p(values.sum())), *normalize_shape(values)])
        else:
            features.extend([0.] * 130)
    return np.asarray(features)


def _exposure_compatible(a, b):
    return a is not None and b is not None and all(a.get(f) == b.get(f) for f in ('unit', 'definition'))


def _predict(audit, train_runs, key, pattern, mode, domain, method, alpha, multipliers=None):
    metadata, histograms = audit['metadata'], audit['histograms']
    query = metadata[key]
    donors = [(run, key[1]) for run in train_runs if (run, key[1]) in histograms
              and (run, key[1]) in metadata and eligible(metadata[(run, key[1])])
              and compatible(metadata[(run, key[1])], query)
              and (mode == 'offline' or metadata[(run, key[1])]['end'] < query['start'])]
    if method in ('linear', 'nearest'):
        donors = list(dict.fromkeys(donors))
    if domain == 'absolute':
        donors = [d for d in donors if _exposure_compatible(metadata[d].get('exposure'), query.get('exposure'))]
    result = dict(estimate=None, status='not_reconstructible', reason='no_donor', donor_keys=[], alpha=alpha)
    if not donors:
        return result
    scales = multipliers or {}
    def exposure(d):
        return metadata[d]['exposure']['value'] * scales.get(d, 1.)
    values = np.array([normalize_shape(histograms[d]) if domain == 'shape'
                       else histograms[d] / exposure(d) for d in donors])
    if method == 'ridge':
        if alpha is None or len(set(donors)) < 2:
            return {**result, 'reason': 'insufficient_nested_training'}
        model = fit_ridge(np.array([_features(audit, d, pattern, mode) for d in donors]), values, alpha=alpha)
        prediction = model.predict(_features(audit, key, pattern, mode)[None])[0]
        selected = donors
    else:
        baseline = baseline_prediction(method, np.array([acquisition_midpoint(metadata[d]) for d in donors]), values,
                                       acquisition_midpoint(query))
        if baseline['status'] != 'ok':
            return {**result, 'reason': baseline['reason']}
        prediction = baseline['values']
        selected = [donors[i] for i in baseline['donor_indices']]
    try:
        prediction = project_shape(prediction) if domain == 'shape' else np.maximum(prediction, 0)*exposure(key)
        if not np.all(np.isfinite(prediction)) or prediction.sum() <= 0:
            raise ValueError('invalid predicted integral')
    except ValueError:
        return {**result, 'reason': 'invalid_prediction'}
    return dict(estimate=prediction, status='ok', reason=None, donor_keys=selected, alpha=alpha)


def _subset_metadata(audit, runs, group):
    allowed = set(runs)
    return {k: row for k, row in audit['metadata'].items() if k[0] in allowed
            and eligible(row) and tuple(row[f] for f in GROUP_FIELDS) == tuple(group)}


def _eligible_target(audit, key, group):
    row = audit['metadata'].get(key)
    return (key in audit['histograms'] and row is not None and eligible(row)
            and tuple(row[f] for f in GROUP_FIELDS) == tuple(group))


def _choose_alpha(audit, runs, group, pattern, state, mode):
    folds = blocked_folds(_subset_metadata(audit, runs, group), mode=mode, n_splits=3)
    scores = {}
    for alpha in ALPHAS:
        errors = []
        for fold in folds:
            for run in fold['test_runs']:
                key = (run, state)
                if not _eligible_target(audit, key, fold['group']):
                    continue
                result = _predict(audit, fold['train_runs'], key, pattern, mode, 'shape', 'ridge', alpha)
                if result['status'] == 'ok':
                    errors.append(float(np.abs(result['estimate']-normalize_shape(audit['histograms'][key])).sum()))
        if errors:
            scores[alpha] = float(np.mean(errors))
    return min(scores, key=lambda a: (scores[a], -a)) if scores else None


def _training_residuals(audit, runs, group, pattern, state, mode, domain):
    residuals = defaultdict(list)
    folds = blocked_folds(_subset_metadata(audit, runs, group), mode=mode, n_splits=3)
    for fold in folds:
        # Tuning also excludes the calibration target; these are genuinely OOF residuals.
        alpha = _choose_alpha(audit, fold['train_runs'], group, pattern, state, mode)
        for run in fold['test_runs']:
            key = (run, state)
            if not _eligible_target(audit, key, fold['group']):
                continue
            for method in METHODS:
                p = _predict(audit, fold['train_runs'], key, pattern, mode, domain, method, alpha)
                if p['status'] != 'ok':
                    continue
                truth = audit['histograms'][key]
                truth = normalize_shape(truth) if domain == 'shape' else truth
                # Relative-to-predicted-integral residuals allow transfer across exposure sizes.
                residuals[method].append(dict(run_number=run, block=fold['fold_id'],
                                              values=(truth-p['estimate']) / (p['estimate'].sum() if domain == 'absolute' else 1.)))
    return dict(residuals)


def evaluate_holdouts(audit, *, mode, n_splits, mask_patterns, seed, calibrate_uncertainty=True,
                      workers=1):
    validate_workers(workers)
    folds = blocked_folds(audit['metadata'], mode=mode, n_splits=n_splits)

    def evaluate_group(task):
        fold, pattern, state = task
        predictions, contexts, excluded = [], {}, []
        alpha = _choose_alpha(audit, fold['train_runs'], fold['group'], pattern, state, mode)
        for domain in ('shape', 'absolute'):
            context_id = (fold['fold_id'], tuple(pattern), state, domain)
            residuals = (_training_residuals(audit, fold['train_runs'], fold['group'], pattern, state, mode, domain)
                         if calibrate_uncertainty else {})
            contexts[context_id] = dict(runs=fold['train_runs'], pattern=pattern,
                                       mode=mode, domain=domain, alpha=alpha, residuals=residuals)
            for run in fold['test_runs']:
                key = (run, state)
                row = audit['metadata'].get(key)
                if not _eligible_target(audit, key, fold['group']):
                    excluded.append(dict(run_number=run, state=state, reason='unusable_truth_or_metadata'))
                    continue
                if domain == 'absolute' and row.get('exposure') is None:
                    continue
                for method in METHODS:
                    p = _predict(audit, fold['train_runs'], key, pattern, mode, domain, method, alpha)
                    # Attach withheld truth after every predictor has returned.
                    truth = audit['histograms'][key]
                    truth = normalize_shape(truth) if domain == 'shape' else truth.copy()
                    single = len(set(p['donor_keys'])) == 1
                    times = [acquisition_midpoint(audit['metadata'][d]) for d in p['donor_keys']]
                    midpoint = acquisition_midpoint(row)
                    p.update(run_number=run, state=state, method=method, domain=domain, truth=truth,
                             fold_id=fold['fold_id'], mode=mode, mask=tuple(pattern),
                             target_key=(run, state, mode, fold['fold_id'], tuple(pattern), domain),
                             training_runs=fold['train_runs'], context_id=context_id,
                             stratum=('single_donor' if single else 'period_edge' if times and not min(times)<midpoint<max(times) else 'interior'),
                             multiple_missing=len(pattern)>1)
                    predictions.append(p)
        return predictions, contexts, excluded

    tasks = [(fold, pattern, state) for fold in folds for pattern in mask_patterns for state in pattern]
    predictions, contexts, excluded = [], {}, []
    for group_predictions, group_contexts, group_excluded in ordered_map(evaluate_group, tasks, workers=workers):
        predictions.extend(group_predictions)
        excluded.extend(group_excluded)
        # Replica generation keys shared exposure draws by audit identity. Never
        # retain the process-local copies returned by independent holdout jobs.
        for context in group_contexts.values():
            context['audit'] = audit
        contexts.update(group_contexts)
    return dict(predictions=predictions, folds=folds, excluded=excluded, contexts=contexts, seed=seed)
