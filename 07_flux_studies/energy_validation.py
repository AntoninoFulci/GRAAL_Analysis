"""Common-energy Extra Trees study, isolated from the historical native pilot.

All values are integrated bin fluxes. Callers supply manifest positions and
whole acquisition-block roles; no run-number distance or approved scientific
threshold is inferred here. Predictors never receive masked truth. Uncertainty
uses calibration-only *total* residuals split into log integral and normalized
shape. Block-bootstrap model/donor variation is retained as a separate diagnostic
and is not added to those total residuals (which would double count variance).
"""
from __future__ import annotations

from collections import Counter, defaultdict

import numpy as np

from flux_studies.flux_uncertainty import _clusters
from flux_studies.neighbor_models import GRIDS, fit_model, hybrid_prediction
from flux_studies.neighbor_validation import neighbor_example, score_prediction

ROLES = ('train', 'calibration', 'development', 'final')
METHODS = ('linear', 'extra_trees_hybrid')
META = ('run', 'period', 'state', 'group', 'position', 'count')


def validate_partitions(records, assignments):
    """Validate one role per whole run/block; return assignments keyed by run."""
    plan, blocks = {}, {}
    for item in assignments:
        run = item['run']
        if run in plan or item['role'] not in ROLES:
            raise ValueError('duplicate run or invalid statistical role')
        key = item['period'], item['block']
        if key in blocks and blocks[key] != item['role']:
            raise ValueError('acquisition block crosses statistical roles')
        blocks[key] = item['role']
        plan[run] = dict(item)
    seen, run_meta, positions = set(), {}, {}
    for row in records:
        run, key = row['run'], (row['run'], row['state'])
        if key in seen:
            raise ValueError('duplicate run/state record')
        seen.add(key)
        if run not in plan or plan[run]['period'] != row['period']:
            raise ValueError('record missing from matching period partition')
        metadata = row['period'], row['position']
        if run in run_meta and metadata != run_meta[run]:
            raise ValueError('states of one run have inconsistent manifest positions')
        if not np.isfinite(row['position']):
            raise ValueError('nonfinite manifest position')
        position_key = row['period'], row['position']
        if position_key in positions and positions[position_key] != run:
            raise ValueError('different runs share a manifest position')
        positions[position_key] = run
        run_meta[run] = metadata
        group = tuple(row['group'])
        if len(group) < 2 or group[0] != row['period'] or group[-1] != row['state']:
            raise ValueError('group must identify period and state')
    return plan


def _metadata(row):
    # Deliberate whitelist: no truth, independent axis, or observable enters X.
    return {**{k: row[k] for k in META}, 'group': tuple(row['group'])}


def _training_rows(records, plan, hidden_runs, n_bins=None):
    if n_bins is not None and (type(n_bins) is not int or n_bins < 1):
        raise ValueError('n_bins must be a positive declared integer')
    result, rejected, sizes = [], [], set()
    excluded_runs = {r['run'] for r in records if r.get('quality_excluded', False)}
    for row in records:
        if plan[row['run']]['role'] != 'train' or row['run'] in hidden_runs:
            continue
        reason = None
        values = np.asarray(row.get('values', []), dtype=float)
        if row['run'] in excluded_runs or row.get('eligible', True) is False:
            reason = 'ineligible_training_state'
        elif (values.ndim != 1 or not len(values) or not np.all(np.isfinite(values))
              or np.any(values < 0)):
            reason = 'invalid_training_spectrum'
        elif not np.isfinite(row['count']) or row['count'] <= 0:
            reason = 'invalid_inclusive_count'
        if reason:
            rejected.append(dict(run=row['run'], state=row['state'], reason=reason))
        else:
            result.append({**_metadata(row), 'values': values,
                           'measured_energy_support': row.get('measured_energy_support')})
            sizes.add(len(values))
    if len(sizes) > 1 or (sizes and n_bins is not None and sizes != {n_bins}):
        raise ValueError('training states require one declared common energy grid')
    if not sizes and n_bins is None:
        raise ValueError('no eligible training spectra; declare n_bins without reading hidden truth')
    return result, rejected, sizes.pop() if sizes else n_bins


def _example(row, donors, plan, *, hide_block=False):
    candidates = [d for d in donors if d['period'] == row['period']
                  and d['state'] == row['state'] and tuple(d['group']) == tuple(row['group'])
                  and (not hide_block or plan[d['run']]['block'] != plan[row['run']]['block'])]
    example = neighbor_example(_metadata(row), candidates)
    if example is not None:
        try:
            support = [np.asarray(d.get('measured_energy_support'), dtype=float)
                       for d in candidates if d['run'] in example['donors']]
        except (TypeError, ValueError):
            support = []
        valid = (len(support) == 2 and all(s.shape == (2,) and np.all(np.isfinite(s))
                 and s[1] > s[0] for s in support))
        interval = [max(s[0] for s in support), min(s[1] for s in support)] if valid else None
        example['energy_support'] = interval if interval is not None and interval[1] > interval[0] else None
    return example


def _training_examples(rows, plan):
    return [(r, e) for r in rows if (e := _example(r, rows, plan, hide_block=True)) is not None]


def _fit(examples, parameters, seed):
    if parameters is None or len(examples) < 2:
        return None
    return fit_model('extra_trees', np.array([e['features'] for _, e in examples]),
                     np.array([r['values'] / r['count'] for r, _ in examples]),
                     parameters, seed=seed)


def _tune(rows, plan, seed):
    """Bounded historical Extra Trees grid, evaluated only inside training."""
    blocks = sorted({plan[r['run']]['block'] for r in rows}, key=str)
    folds = []
    for index in range(3):
        held_blocks = set(blocks[index::3])
        fit = [r for r in rows if plan[r['run']]['block'] not in held_blocks]
        held = [r for r in rows if plan[r['run']]['block'] in held_blocks]
        examples = _training_examples(fit, plan)
        tests = [(r, _example(r, fit, plan)) for r in held]
        audit = dict(fold=index, fit_runs=sorted({r['run'] for r in fit}),
                     held_runs=sorted({r['run'] for r in held}),
                     training_examples=[dict(run=r['run'], donors=e['donors']) for r, e in examples],
                     held_examples=[dict(run=r['run'], donors=[] if e is None else e['donors'],
                                         status='no_training_bracket' if e is None else 'available')
                                    for r, e in tests])
        folds.append((examples, tests, audit))
    candidates = []
    for parameters in GRIDS['extra_trees']:
        losses, expected, failures, bracketed = [], 0, [], 0
        for examples, tests, audit in folds:
            model = _fit(examples, parameters, seed)
            for row, example in tests:
                expected += 1
                prediction = None
                if example is not None:
                    bracketed += 1
                    if model is not None:
                        prediction = hybrid_prediction(model.predict(example['features'][None])[0],
                                                       example['linear'].sum())
                if prediction is None or row['values'].sum() <= 0:
                    failures.append(dict(run=row['run'], fold=audit['fold'],
                        reason='no_training_bracket' if example is None else 'unavailable_model_or_truth'))
                else:
                    losses.append(score_prediction(row['values'], prediction)['relative_l1'])
        candidates.append(dict(parameters=parameters.copy(), expected=expected, bracketed=bracketed,
                               evaluated=len(losses), failed=expected-len(losses), failures=failures,
                               relative_l1=float(np.mean(losses)) if losses else None))
    # Geometry failures stay in the denominator. They are parameter independent;
    # candidates are ordered first by failure count, then predictive loss.
    available = [c for c in candidates if c['evaluated'] > 0]
    best = min(available, key=lambda c: (c['failed'], c['relative_l1'])) if available else None
    return dict(selected=None if best is None else best['parameters'], candidates=candidates,
                folds=[f[2] for f in folds], objective='fewest_failures_then_mean_relative_l1',
                fixed_parameters=dict(n_estimators=64, n_jobs=1, random_state=seed))


def _predict(rows, targets, plan, parameters, seed, *, multiplicity=None):
    by_group = defaultdict(list)
    for row in rows:
        by_group[tuple(row['group'])].append(row)
    models = {}
    for group, local in by_group.items():
        examples = _training_examples(local, plan)
        if multiplicity is not None:
            examples = [(r, e) for r, e in examples for _ in range(multiplicity[plan[r['run']]['block']])]
        models[group] = _fit(examples, parameters.get(group), seed)
    predictions = []
    for target in targets:
        row = _metadata(target)
        example, error = None, None
        if target.get('quality_excluded', False) or target.get('eligible', True) is False:
            error = 'ineligible_target'
        elif not np.isfinite(row['count']) or row['count'] <= 0:
            error = 'invalid_inclusive_count'
        else:
            example = _example(row, rows, plan)
            if example is None:
                error = 'no_training_bracket'
        for method in METHODS:
            prediction, status = None, error
            if example is not None:
                if method == 'linear':
                    prediction = example['linear']
                elif models.get(row['group']) is not None:
                    shape = models[row['group']].predict(example['features'][None])[0]
                    prediction = hybrid_prediction(shape, example['linear'].sum())
                    if prediction is None:
                        status = 'invalid_predicted_shape'
                else:
                    status = 'unavailable_model'
                if prediction is not None and (not np.all(np.isfinite(prediction)) or prediction.sum() <= 0):
                    prediction, status = None, 'invalid_prediction'
            predictions.append(dict(**row, role=plan[row['run']]['role'], block=plan[row['run']]['block'],
                method=method, estimate=prediction, status=status or 'available',
                donors=[] if example is None else example['donors'],
                gap=None if example is None else example['gap'],
                energy_support=None if example is None else example['energy_support']))
    return predictions


def _result(predictions, assignments, fits, rejected, k, seed):
    return dict(predictions=predictions, assignments=[dict(a) for a in assignments], fits=fits,
                training_exclusions=rejected, n_bins=k, feature_count=3*k+3, seed=seed,
                methods=list(METHODS), representation='common_energy_integrated_bin_flux',
                summary=dict(expected=len(predictions),
                             available=sum(p['status'] == 'available' for p in predictions),
                             failed=sum(p['status'] != 'available' for p in predictions)))


def predict_energy(records, targets, *, assignments, seed, parameters, n_bins=None):
    """Predict explicit missing targets from frozen per-group Extra Trees params.

    ``parameters`` maps the full record ``group`` tuple to the selected dict.
    Targets need only META fields; their values are never accessed. All states
    of each target run are withheld, including targets assigned to training.
    """
    if seed < 0 or parameters is None:
        raise ValueError('nonnegative seed and frozen parameters required')
    plan = validate_partitions(records, assignments)
    validate_partitions(targets, assignments)
    existing = {(r['run'], r['state']): r for r in records}
    for target in targets:
        original = existing.get((target['run'], target['state']))
        if original is not None and _metadata(original) != _metadata(target):
            raise ValueError('target metadata differs from its acquisition record')
    excluded = {r['run'] for r in records if r.get('quality_excluded', False)}
    targets = [{**t, 'quality_excluded': t.get('quality_excluded', False) or t['run'] in excluded}
               for t in targets]
    train, rejected, k = _training_rows(records, plan, {t['run'] for t in targets}, n_bins)
    parameters = {tuple(g): p for g, p in parameters.items()}
    predictions = _predict(train, targets, plan, parameters, seed)
    fits = [dict(group=list(g), parameters=p, tuning=None) for g, p in parameters.items()]
    return _result(predictions, assignments, fits, rejected, k, seed)


def evaluate_energy(records, *, assignments, masks, seed, parameters=None, n_bins=None):
    """Fit in train and evaluate explicit masked keys; final requires freeze.

    Truth is attached after every estimate and donor decision has been made.
    Calibration/development/final are never fit data or donor candidates.
    """
    if seed < 0:
        raise ValueError('seed must be nonnegative')
    plan = validate_partitions(records, assignments)
    masks = [tuple(m) for m in masks]
    if len(masks) != len(set(masks)):
        raise ValueError('duplicate masked target')
    lookup = {(r['run'], r['state']): r for r in records}
    if any(key not in lookup for key in masks):
        raise ValueError('masked truth record missing')
    excluded = {r['run'] for r in records if r.get('quality_excluded', False)}
    targets = [{**lookup[key], 'quality_excluded': key[0] in excluded} for key in masks]
    if any(plan[t['run']]['role'] == 'train' for t in targets):
        raise ValueError('evaluation masks require non-training roles')
    if parameters is None and any(plan[t['run']]['role'] == 'final' for t in targets):
        raise ValueError('final evaluation requires frozen parameters')
    train, rejected, k = _training_rows(records, plan, {t['run'] for t in targets}, n_bins)
    fits, selected = [], {}
    for group in sorted({r['group'] for r in train}):
        local = [r for r in train if r['group'] == group]
        tuning = _tune(local, plan, seed) if parameters is None else None
        selected[group] = tuning['selected'] if tuning else parameters.get(group)
        fits.append(dict(group=list(group), parameters=selected[group], tuning=tuning))
    predictions = _predict(train, targets, plan, selected, seed)
    for prediction in predictions:
        truth = np.asarray(lookup[prediction['run'], prediction['state']]['values'], dtype=float)
        if truth.shape != (k,) or np.any(truth < 0) or not np.all(np.isfinite(truth)):
            raise ValueError('masked truth is not a valid common-grid spectrum')
        prediction['truth'] = truth.copy()
        prediction['metrics'] = (score_prediction(truth, prediction['estimate'])
                                 if prediction['estimate'] is not None else None)
    result = _result(predictions, assignments, fits, rejected, k, seed)
    result['masks'] = [list(m) for m in masks]
    return result


def calibrate_energy_uncertainty(study, *, min_groups):
    """Calibrate integral and shape separately using calibration role only.

    Connected calibration runs sharing a block or donor are a dependency group.
    Required support is supplied by the scientific protocol, never defaulted.
    """
    if min_groups < 1:
        raise ValueError('min_groups must be positive')
    residuals, support = [], []
    for period in sorted({a['period'] for a in study['assignments']}):
        predictions = [p for p in study['predictions'] if p['period'] == period and p['role'] == 'calibration']
        blocks = {a['run']: a['block'] for a in study['assignments'] if a['period'] == period}
        valid = [p for p in predictions if p['status'] == 'available'
                 and p.get('truth') is not None and np.sum(p['truth']) > 0]
        clusters = _clusters(valid, blocks)
        for p in valid:
            truth, estimate = np.asarray(p['truth'], dtype=float), np.asarray(p['estimate'], dtype=float)
            residuals.append(dict(period=period, run=p['run'], state=p['state'], method=p['method'],
                group=list(p['group']), dependency_group=clusters[p['run']],
                log_integral=float(np.log(truth.sum()) - np.log(estimate.sum())),
                shape=truth / truth.sum() - estimate / estimate.sum()))
        groups = sorted(set(clusters.values()))
        support.append(dict(period=period, expected=len(predictions), evaluated=len(valid),
                            failed=len(predictions)-len(valid), groups=groups, n_groups=len(groups),
                            status='available' if len(groups) >= min_groups else 'insufficient_groups'))
    return dict(residuals=residuals, support=support, min_groups=min_groups,
                role='calibration', components=['log_integral', 'normalized_shape'],
                interpretation='total_predictive_residual; marginal not simultaneous')


def energy_replicas(records, study, calibration, *, roles, n_replicas, seed, min_groups):
    """Aligned group draws; model/donor bootstrap retained but not added twice.

    A shared calibration run supplies the paired state/method integral and shape
    residuals to targets connected by actual bootstrap donors or masking block.
    Unsupported or failed replicas remain NaN at their original aligned index.
    """
    if (n_replicas < 2 or seed < 0 or min_groups < 1 or not set(roles) <= set(ROLES)
            or ('train' in roles and 'masks' in study)):
        raise ValueError('invalid replicas, roles or externally supplied support')
    predictions = [{**p, 'estimate': None if p['estimate'] is None else np.asarray(p['estimate'], dtype=float)}
                   for p in study['predictions'] if p['role'] in roles]
    keys = [{k: p[k] for k in ('period', 'run', 'state', 'method')} for p in predictions]
    shape = (n_replicas, len(predictions), study['n_bins'])
    draws, model_draws = np.full(shape, np.nan), np.full(shape, np.nan)
    integral_draws = np.full(shape[:2], np.nan)
    shape_draws = np.full(shape, np.nan)
    plan = validate_partitions(records, study['assignments'])
    train, _, _ = _training_rows(records, plan, {p['run'] for p in predictions}, study['n_bins'])
    parameters = {tuple(f['group']): f['parameters'] for f in study['fits']}
    rng, audit, support, joint_support = np.random.default_rng(seed), [], [], []
    sampled_by_period = {}
    for period in sorted({p['period'] for p in predictions}):
        blocks = sorted({plan[r['run']]['block'] for r in train if r['period'] == period}, key=str)
        sampled_by_period[period] = [rng.choice(blocks, len(blocks), replace=True).tolist()
                                     if blocks else [] for _ in range(n_replicas)]
    for domain in sorted({tuple(p['group'][:-1]) for p in predictions}):
        period = domain[0]
        indices = [i for i, p in enumerate(predictions) if tuple(p['group'][:-1]) == domain]
        local = [r for r in train if tuple(r['group'][:-1]) == domain]
        blocks = {a['run']: a['block'] for a in study['assignments'] if a['period'] == period}
        targets = list({(predictions[i]['run'], predictions[i]['state']):
                        _metadata(predictions[i]) for i in indices}.values())
        residuals, residual_groups = defaultdict(dict), {}
        states = sorted({predictions[i]['state'] for i in indices})
        required = {state: {(state, predictions[i]['method']) for i in indices
                            if predictions[i]['state'] == state and predictions[i]['estimate'] is not None}
                    for state in states}
        for r in calibration['residuals']:
            if tuple(r['group'][:-1]) == domain:
                residuals[r['run']][r['state'], r['method']] = r
                residual_groups[r['run']] = r['dependency_group']
        minimum = max(min_groups, calibration['min_groups'])
        pools, group_pools = {}, {}
        for state in states:
            pools[state] = [r for r in sorted(residuals)
                            if required[state] and required[state] <= residuals[r].keys()]
            group_pools[state] = sorted({residual_groups[r] for r in pools[state]})
            support.append(dict(period=period, domain=list(domain), state=state,
                paired_runs=pools[state], n_groups=len(group_pools[state]),
                status='available' if len(group_pools[state]) >= minimum else 'insufficient_groups'))
        pol_states = [state for state in states if state in ('POL1', 'POL2')]
        joint_pool, joint_groups = [], []
        if len(pol_states) == 2:
            joint_pool = sorted(set(pools['POL1']) & set(pools['POL2']))
            joint_groups = sorted({residual_groups[r] for r in joint_pool})
            joint_support.append(dict(period=period, domain=list(domain), states=pol_states,
                paired_runs=joint_pool, n_groups=len(joint_groups),
                status='available' if len(joint_groups) >= minimum else 'insufficient_groups'))
        for replica in range(n_replicas):
            sampled = sampled_by_period[period][replica]
            multiplicity = Counter(sampled)
            donors = [r for r in local if multiplicity[blocks[r['run']]]]
            boot = _predict(donors, targets, plan, parameters, seed+replica, multiplicity=multiplicity)
            boot_map = {(p['run'], p['state'], p['method']): p for p in boot}
            actual = [boot_map[predictions[i]['run'], predictions[i]['state'], predictions[i]['method']]
                      for i in indices]
            # Include all nominally available targets: even a failed bracket must
            # not erase the shared block relation from the audit.
            clusters = _clusters(actual, blocks)
            innovations = {}
            # BREM is an independent control. Missing support for any state
            # cannot erase another state's diagnostic uncertainty. Joint POL
            # adoption requires the separately reported paired-state support.
            batches = ([pol_states] if len(joint_groups) >= minimum
                       else [[state] for state in pol_states])
            if 'BREM' in states:
                batches.append(['BREM'])
            for batch in batches:
                pool = joint_pool if len(batch) == 2 else pools[batch[0]]
                groups = joint_groups if len(batch) == 2 else group_pools[batch[0]]
                if len(groups) >= minimum:
                    for cluster in sorted(set(clusters.values())):
                        group = rng.choice(groups)
                        source = int(rng.choice([r for r in pool if residual_groups[r] == group]))
                        for state in batch:
                            innovations[state, cluster] = source
            target_audit = []
            for i, boot_prediction in zip(indices, actual, strict=True):
                p = predictions[i]
                source = innovations.get((p['state'], clusters[p['run']]))
                status = boot_prediction['status']
                if boot_prediction['estimate'] is not None:
                    model_draws[replica, i] = boot_prediction['estimate']
                if source is None:
                    status = 'insufficient_residual_support'
                elif p['estimate'] is not None and boot_prediction['estimate'] is not None:
                    residual = residuals[source][p['state'], p['method']]
                    total = float(p['estimate'].sum() * np.exp(residual['log_integral']))
                    new_shape = np.maximum(p['estimate'] / p['estimate'].sum() + residual['shape'], 0.)
                    if np.isfinite(total) and total > 0 and new_shape.sum() > 0:
                        new_shape /= new_shape.sum()
                        draws[replica, i] = total * new_shape
                        integral_draws[replica, i], shape_draws[replica, i] = total, new_shape
                        status = 'available'
                    else:
                        status = 'invalid_residual_draw'
                elif p['estimate'] is None:
                    status = p['status']
                target_audit.append(dict(prediction_index=i, run=p['run'], state=p['state'], method=p['method'],
                    donors=boot_prediction['donors'], cluster=clusters[p['run']], residual_run=source, status=status))
            audit.append(dict(period=period, domain=list(domain), replica=replica, sampled_blocks=sampled,
                              sampled_runs=sorted({r['run'] for r in donors}), targets=target_audit))
    summary = []
    for i, key in enumerate(keys):
        valid = np.isfinite(draws[:, i]).all(axis=1)
        totals = draws[valid, i].sum(axis=1)
        nominal = predictions[i]['estimate']
        relative = (float(np.std(totals, ddof=1) / nominal.sum())
                    if len(totals) >= 2 and nominal is not None and nominal.sum() > 0 else None)
        summary.append(dict(**key, requested_replicas=n_replicas, valid_replicas=int(valid.sum()),
                            relative_integral_uncertainty=relative))
    return dict(keys=keys, draws=draws, model_draws=model_draws, integral_draws=integral_draws,
                shape_draws=shape_draws, bootstrap_audit=audit, residual_support=support,
                joint_state_support=joint_support,
                target_summary=summary, requested_replicas=n_replicas, seed=seed,
                combination='calibrated_total_residual_only',
                caveats=['model/donor bootstrap is a separate diagnostic, not an additive component',
                         'shared donor/block residual dependence is an assumption requiring qualification',
                         'reference measured-flux uncertainties are not supplied by this model'])


def grouped_energy_coverage(study, replicas, *, min_groups, n_resamples, seed):
    """Marginal bin, integral and shape coverage with dependency-group intervals.

    Failures remain in expected_targets and each level's unavailable denominator;
    coverage is descriptive on evaluable targets and never an acceptance pass.
    """
    if min_groups < 1 or n_resamples < 2 or seed < 0:
        raise ValueError('invalid grouped coverage controls')
    lookup = {(p['period'], p['run'], p['state'], p['method']): p for p in study['predictions']}
    predictions = [lookup[k['period'], k['run'], k['state'], k['method']] for k in replicas['keys']]
    # Union nominal and replica donor identities, preserving all dependencies.
    expanded = [dict(p) for p in predictions]
    for audit in replicas['bootstrap_audit']:
        for target in audit['targets']:
            i = target['prediction_index']
            expanded[i] = {**expanded[i], 'donors': sorted(set(expanded[i]['donors']) | set(target['donors']))}
    groups = {}
    for period in sorted({p['period'] for p in predictions}):
        blocks = {a['run']: a['block'] for a in study['assignments'] if a['period'] == period}
        groups.update({(period, run): (period, cluster) for run, cluster in
                       _clusters([p for p in expanded if p['period'] == period], blocks).items()})
    result = _coverage_summary(predictions, replicas['draws'], groups, study['n_bins'],
                               min_groups=min_groups, n_resamples=n_resamples, seed=seed)
    result['domains'] = []
    for group, method in sorted({(tuple(p['group']), p['method']) for p in predictions}):
        indices = [i for i, p in enumerate(predictions) if tuple(p['group']) == group and p['method'] == method]
        report = _coverage_summary([predictions[i] for i in indices], replicas['draws'][:, indices],
                                   groups, study['n_bins'], min_groups=min_groups,
                                   n_resamples=n_resamples, seed=seed)
        result['domains'].append(dict(group=list(group), method=method, **report))
    return result


def _coverage_summary(predictions, draws, groups, k, *, min_groups, n_resamples, seed):
    rng, reports = np.random.default_rng(seed), {}
    evaluated_groups = set()
    for level, quantiles in ((68, (.16, .84)), (95, (.025, .975))):
        hits = defaultdict(list)
        for i, p in enumerate(predictions):
            values = draws[:, i]
            values = values[np.isfinite(values).all(axis=1)]
            truth = None if p.get('truth') is None else np.asarray(p['truth'], dtype=float)
            if len(values) < 2 or truth is None or truth.sum() <= 0:
                continue
            low, high = np.quantile(values, quantiles, axis=0)
            ilo, ihi = np.quantile(values.sum(axis=1), quantiles)
            slo, shi = np.quantile(values / values.sum(axis=1)[:, None], quantiles, axis=0)
            group = groups[p['period'], p['run']]
            hits[group].append(np.r_[(truth >= low) & (truth <= high),
                                    ilo <= truth.sum() <= ihi,
                                    (truth / truth.sum() >= slo) & (truth / truth.sum() <= shi)])
        evaluated_groups.update(hits)
        evaluated = sum(len(v) for v in hits.values())
        estimate = np.mean(np.concatenate(list(hits.values())), axis=0) if hits else None
        interval = None
        if len(hits) >= min_groups:
            pools = list(hits.values())
            sampled = [np.mean(np.concatenate([pools[j] for j in rng.integers(0, len(pools), len(pools))]), axis=0)
                       for _ in range(n_resamples)]
            interval = np.quantile(sampled, [.025, .975], axis=0).tolist()
        reports[str(level)] = dict(evaluated=evaluated, unavailable=len(predictions)-evaluated,
            bin_coverage=None if estimate is None else estimate[:k].tolist(),
            integral_coverage=None if estimate is None else float(estimate[k]),
            shape_coverage=None if estimate is None else estimate[k+1:].tolist(),
            grouped_diagnostic_interval95=interval)
    return dict(status='descriptive_only' if len(evaluated_groups) >= min_groups else 'insufficient_groups',
                expected_targets=len(predictions), n_groups=len(evaluated_groups), levels=reports,
                interpretation='marginal coverage; no simultaneous-band or qualification claim')
