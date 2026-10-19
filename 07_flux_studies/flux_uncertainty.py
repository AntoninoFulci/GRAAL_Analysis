"""Aligned native-strip replicas; deliberately exploratory, never an adoption gate.

Whole training blocks are sampled together across states and methods. Features
and nearest available donors are rebuilt in each draw. Validation residuals are
sampled as complete spectra, paired across states/methods and shared by target
clusters that overlap a donor or masking block. This is an assumed dependence
model, not a measured cross-run covariance. Adding full prediction residuals to
bootstrap variation can double count fitting variance; coverage must be checked.
"""
from collections import Counter, defaultdict
import numpy as np

from flux_studies.neighbor_models import fit_model, hybrid_prediction
from flux_studies.neighbor_validation import _examples, neighbor_example


def _clusters(predictions, blocks):
    """Connected targets share an innovation if they share donors or a block."""
    runs = sorted({p['run'] for p in predictions})
    parent = {r: r for r in runs}
    def root(r):
        while parent[r] != r:
            r = parent[r]
        return r
    identities = {}
    for p in predictions:
        r = p['run']
        for identity in [('block', blocks[r]), *[('donor', d) for d in p['donors']]]:
            if identity in identities:
                parent[root(r)] = root(identities[identity])
            identities[identity] = r
    return {r: root(r) for r in runs}


def neighbor_replicas(records, study, *, methods, n_replicas, seed):
    """Generate test-target draws without ever reading test flux values.

    Selected hyperparameters are frozen from inner training folds. Invalid donor
    brackets and absent paired validation support remain NaN with full requested
    replica denominators. No replacement with a zero error is allowed.
    """
    if n_replicas < 2 or seed < 0 or not methods or len(set(methods)) != len(methods):
        raise ValueError('need distinct methods, nonnegative seed and >=2 replicas')
    methods = tuple(methods)
    if any(m != 'linear' and not m.endswith('_hybrid') for m in methods):
        raise ValueError('replicas support linear and hybrid methods')
    predictions = [p for p in study['predictions'] if p['role'] == 'test' and p['method'] in methods]
    keys = [{k: p[k] for k in ('period', 'run', 'state', 'method')} for p in predictions]
    if len({tuple(k.values()) for k in keys}) != len(keys):
        raise ValueError('duplicate prediction keys')
    draws = np.full((n_replicas, len(keys), 128), np.nan)
    means = np.full_like(draws, np.nan)
    fits = {tuple(f['group']): f for f in study['fits']}
    rng = np.random.default_rng(seed)
    audit, support = [], []
    for period, assignments in sorted(study['splits'].items()):
        roles = {a['run']: a['role'] for a in assignments}
        blocks = {a['run']: a['block'] for a in assignments}
        indices = [i for i, p in enumerate(predictions) if p['period'] == period]
        if not indices:
            continue
        target_rows = {(r['run'], r['state']): r for r in records if r['period'] == period}
        train = [r for r in records if r['period'] == period and roles[r['run']] == 'train']
        train_blocks = sorted({blocks[r['run']] for r in train})
        groups = sorted({r['group'] for r in train})
        states = sorted({predictions[i]['state'] for i in indices})
        required = {(s, m) for s in states for m in methods}
        residuals = defaultdict(dict)
        for p in study['predictions']:
            if p['period'] != period or p['role'] != 'validation' or (p['state'], p['method']) not in required:
                continue
            total = float(np.sum(p['estimate']))
            if total > 0:
                residuals[p['run']][(p['state'], p['method'])] = (p['truth'] - p['estimate']) / total
        pool = sorted(r for r, v in residuals.items() if required <= v.keys())
        pool_blocks = sorted({blocks[r] for r in pool})
        support.append(dict(period=period, paired_validation_runs=pool, validation_blocks=pool_blocks,
                            states=states, status='available' if len(pool) >= 5 and len(pool_blocks) >= 2 else 'insufficient'))
        for replica in range(n_replicas):
            selected = rng.choice(train_blocks, size=len(train_blocks), replace=True)
            multiplicity = Counter(selected.tolist())
            donors = [r for r in train if multiplicity[blocks[r['run']]]]
            # Derive dependence from this draw's actual donor brackets, before
            # choosing innovations. Original brackets can acquire shared donors.
            local_donors = {group: [r for r in donors if r['group'] == group] for group in groups}
            target_examples, target_groups, target_audits = {}, {}, {}
            for i in indices:
                prediction = predictions[i]
                row = target_rows[prediction['run'], prediction['state']]
                group = row['group']
                target = {k: row[k] for k in ('run', 'period', 'position', 'group')}
                target['count'] = prediction['count']
                example = neighbor_example(target, local_donors.get(group, []))
                target_examples[i], target_groups[i] = example, group
                target_audits[i] = dict(prediction_index=i, run=prediction['run'],
                    state=prediction['state'], method=prediction['method'],
                    donors=[] if example is None else example['donors'],
                    status='no_training_bracket' if example is None else 'pending',
                    cluster=None, residual_run=None)
            clusters = _clusters([target_audits[i] for i in indices
                                  if target_examples[i] is not None], blocks)
            audit.append(dict(period=period, replica=replica, sampled_blocks=selected.tolist(),
                              sampled_runs=sorted({r['run'] for r in donors}),
                              training_runs=sorted({r['run'] for r in train}),
                              targets=[target_audits[i] for i in indices]))
            innovations = {}
            if len(pool) >= 5 and len(pool_blocks) >= 2:
                for cluster in sorted(set(clusters.values())):
                    block = rng.choice(pool_blocks)
                    innovations[cluster] = int(rng.choice([r for r in pool if blocks[r] == block]))
            for i in indices:
                if target_examples[i] is not None:
                    cluster = clusters[predictions[i]['run']]
                    target_audits[i].update(cluster=cluster, residual_run=innovations.get(cluster))
            for group in groups:
                local = local_donors[group]
                examples = _examples(local, local, blocks, hide_block=True)
                expanded = [(r, e) for r, e in examples for _ in range(multiplicity[blocks[r['run']]])]
                relevant = [i for i in indices if target_groups[i] == group]
                if not relevant:
                    continue
                fitted = {}
                for method in methods:
                    if method == 'linear' or len(expanded) < 2:
                        continue
                    family = method.removesuffix('_hybrid')
                    parameters = fits[group]['models'][family]['selected']['hybrid']
                    if parameters is not None:
                        fitted[method] = fit_model(family, np.array([e['features'] for _, e in expanded]),
                            np.array([r['values'] / r['count'] for r, _ in expanded]),
                            parameters, seed=seed + replica)
                for i in relevant:
                    p = predictions[i]
                    example = target_examples[i]
                    if example is None:
                        continue
                    if p['method'] == 'linear':
                        estimate = example['linear']
                    elif p['method'] in fitted:
                        rate = fitted[p['method']].predict(example['features'][None, :])[0]
                        estimate = hybrid_prediction(rate, example['linear'].sum())
                        if estimate is None:
                            target_audits[i]['status'] = 'zero_predicted_shape'
                            continue
                    else:
                        target_audits[i]['status'] = 'unavailable_model'
                        continue
                    means[replica, i] = estimate
                    source = target_audits[i]['residual_run']
                    if source is not None:
                        residual = residuals[source][(p['state'], p['method'])]
                        draws[replica, i] = np.maximum(estimate + residual * estimate.sum(), 0.)
                        target_audits[i]['status'] = 'available'
                    else:
                        target_audits[i]['status'] = 'insufficient_residual_support'
            if (replica + 1) % 8 == 0 or replica + 1 == n_replicas:
                complete = int(np.isfinite(draws[:replica + 1, indices]).all(axis=(1, 2)).sum())
                print(f'{period}: flux replicas {replica + 1}/{n_replicas}, '
                      f'{complete} complete', flush=True)
    target_summary = []
    for i, p in enumerate(predictions):
        values = draws[:, i]
        valid = np.all(np.isfinite(values), axis=1)
        row = dict(**keys[i], requested_replicas=n_replicas, valid_replicas=int(valid.sum()))
        for level, quantiles in ((68, (.16, .84)), (95, (.025, .975))):
            if valid.sum() >= 2:
                low, high = np.quantile(values[valid], quantiles, axis=0)
                ilo, ihi = np.quantile(values[valid].sum(axis=1), quantiles)
                row[f'coverage{level}'] = float(np.mean((p['truth'] >= low) & (p['truth'] <= high)))
                row[f'integral_covered{level}'] = bool(ilo <= p['truth'].sum() <= ihi)
            else:
                row[f'coverage{level}'] = row[f'integral_covered{level}'] = None
        target_summary.append(row)
    return dict(keys=keys, draws=draws, model_draws=means, bootstrap_audit=audit,
                residual_support=support, target_summary=target_summary, seed=seed,
                requested_replicas=n_replicas, status='exploratory_covariance',
                caveats=['full validation residual plus bootstrap may double count fitting variance',
                         'shared-donor/block innovations impose assumed dependence, not measured correlations',
                         'finite development sample; no independent coverage or mean-bias certification'])


def closure_replicas(result):
    """Keep aligned replica IDs and failed NaNs through the extraction boundary."""
    output = {}
    for i, key in enumerate(result['keys']):
        period = output.setdefault(key['method'], {}).setdefault(
            key['period'], [{} for _ in range(result['requested_replicas'])])
        for replica, mapping in enumerate(period):
            mapping[(key['run'], key['state'])] = result['draws'][replica, i]
    return output
