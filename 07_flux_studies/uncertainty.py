"""Paired hold-out metrics and aligned predictive replicas.

Intervals are exploratory empirical intervals. Donor/model variation and
calibration-residual variation are saved separately, with coverage measured
only on outer hold-outs. No automatic scientific adoption is inferred.
"""
from __future__ import annotations

from collections import defaultdict
from itertools import combinations
import math
import numpy as np

from flux_studies.methods import project_shape
from flux_studies.metadata import GROUP_FIELDS, eligible, temporal_run_blocks
from flux_studies.validation import _predict


def paired_metrics(predictions):
    groups = defaultdict(list)
    for row in predictions:
        groups[row['method']].append(row)
    coverage, metrics, matched = {}, {}, {}
    for method, rows in groups.items():
        valid = [r for r in rows if r['status'] == 'ok']
        coverage[method] = dict(eligible=len(rows), success=len(valid), failed=len(rows)-len(valid))
        matched[method] = {}
        domain_metrics = {}
        for domain in ('shape', 'absolute'):
            selected = [r for r in valid if r['domain'] == domain]
            if not selected:
                continue
            residuals = np.array([r['estimate']-r['truth'] for r in selected])
            metrics_row = dict(count=len(selected), per_strip_bias=residuals.mean(axis=0),
                               per_strip_mae=np.abs(residuals).mean(axis=0))
            if domain == 'shape':
                metrics_row['mean_l1'] = float(np.abs(residuals).sum(axis=1).mean())
            else:
                relative = [(r['estimate'].sum()-r['truth'].sum())/r['truth'].sum()
                            for r in selected if r['truth'].sum() > 0]
                metrics_row['integral_relative_bias'] = float(np.mean(relative)) if relative else None
                metrics_row['zero_integral_truth'] = sum(r['truth'].sum() == 0 for r in selected)
            for level in (68, 95):
                with_intervals = [r for r in selected if r.get(f'interval{level}') is not None]
                metrics_row[f'interval{level}_targets'] = len(with_intervals)
                metrics_row[f'coverage{level}'] = (float(np.mean([
                    np.mean((r['truth'] >= r[f'interval{level}'][0]) & (r['truth'] <= r[f'interval{level}'][1]))
                    for r in with_intervals])) if with_intervals else None)
            domain_metrics[domain] = metrics_row
            for row in selected:
                matched[method][tuple(row['target_key'])] = float(np.abs(row['estimate']-row['truth']).sum())
        metrics[method] = domain_metrics
    pairs = []
    for left, right in combinations(sorted(matched), 2):
        common = matched[left].keys() & matched[right].keys()
        for domain in ('shape', 'absolute'):
            keys = {tuple(row['target_key']) for row in predictions if row['domain'] == domain}
            selected = common & keys
            if selected:
                differences = [matched[left][key]-matched[right][key] for key in sorted(selected)]
                pairs.append(dict(left=left, right=right, domain=domain, common_targets=len(selected),
                                  mean_l1_difference=float(np.mean(differences)), target_keys=sorted(selected)))
    strata = {}
    for label in ('single_donor', 'period_edge', 'interior', 'multiple_missing'):
        selected = [r for r in predictions if (r.get('multiple_missing') if label == 'multiple_missing' else r.get('stratum') == label)]
        strata[label] = {method: dict(eligible=sum(r['method'] == method for r in selected),
                                     success=sum(r['method'] == method and r['status'] == 'ok' for r in selected))
                         for method in groups}
    return dict(coverage=coverage, metrics=metrics, pairs=pairs, strata=strata)


def _exposure_draws(metadata, rng, common):
    multipliers = {}
    for key in sorted(metadata):
        exposure = metadata[key].get('exposure')
        if exposure is None or exposure.get('error') is None:
            continue
        relative = exposure['error'] / exposure['value']
        identity = exposure.get('uncertainty_group') or ('independent', key)
        if identity not in common:
            common[identity] = rng.normal()
        variance = math.log1p(relative*relative)
        multipliers[key] = math.exp(-variance/2 + math.sqrt(variance)*common[identity])
    return multipliers


def bootstrap_blocks(metadata, runs):
    """At most three contiguous blocks of indivisible acquisition clusters."""
    clusters = temporal_run_blocks(metadata, runs)
    if not clusters:
        return []
    return [[run for i in chunk for run in clusters[int(i)]]
            for chunk in np.array_split(np.arange(len(clusters)), min(3, len(clusters)))]


def joint_replicas(evaluation, *, seed, n_replicas):
    if n_replicas < 2:
        raise ValueError('at least two replicas are required')
    predictions, contexts = evaluation['predictions'], evaluation['contexts']
    rng = np.random.default_rng(seed)
    means = np.full((n_replicas, len(predictions), 128), np.nan)
    totals = np.full_like(means, np.nan)
    for replica in range(n_replicas):
        sampled_runs, exposure_draws, block_choices, shared_nuisances = {}, {}, {}, {}
        for index, p in enumerate(predictions):
            if p['status'] != 'ok':
                continue
            context = contexts[p['context_id']]
            audit = context['audit']
            # All states/methods for this outer fold use the same block weights.
            group = tuple(audit['metadata'][(p['run_number'], p['state'])][f] for f in GROUP_FIELDS)
            identity = (p['context_id'][0], group, tuple(context['runs']))
            if identity not in sampled_runs:
                members = {key: row for key, row in audit['metadata'].items()
                           if eligible(row) and tuple(row[f] for f in GROUP_FIELDS) == group}
                blocks = bootstrap_blocks(members, context['runs'])
                if not blocks:
                    continue
                sampled_runs[identity] = [int(run) for b in rng.integers(0, len(blocks), len(blocks)) for run in blocks[b]]
            audit_identity = id(audit)
            if audit_identity not in exposure_draws:
                exposure_draws[audit_identity] = _exposure_draws(audit['metadata'], rng, shared_nuisances)
            key = (p['run_number'], p['state'])
            if p['domain'] == 'absolute':
                relevant = [key, *p['donor_keys']]
                if any(audit['metadata'][k].get('exposure') is None or audit['metadata'][k]['exposure'].get('error') is None for k in relevant):
                    continue
            result = _predict(audit, sampled_runs[identity], key, context['pattern'],
                              context['mode'], context['domain'], p['method'], context['alpha'],
                              exposure_draws[audit_identity])
            if result['status'] != 'ok':
                continue
            if p['domain'] == 'absolute' and any(
                    audit['metadata'][k]['exposure'].get('error') is None
                    for k in result['donor_keys']):
                continue
            estimate = result['estimate']
            means[replica, index] = estimate
            residuals = context['residuals'].get(p['method'], [])
            if len({r['run_number'] for r in residuals}) < 2:
                continue
            # Select calibration blocks with shared indices; innovations for a target
            # are paired across methods when their available block/run sets agree.
            residual_blocks = sorted({r['block'] for r in residuals})
            innovation_id = (identity, key, tuple(residual_blocks))
            if innovation_id not in block_choices:
                block_choices[innovation_id] = (rng.random(), rng.random())
            u, v = block_choices[innovation_id]
            selected_block = residual_blocks[min(int(u*len(residual_blocks)), len(residual_blocks)-1)]
            pool = sorted((r for r in residuals if r['block'] == selected_block), key=lambda r:r['run_number'])
            residual = pool[min(int(v*len(pool)), len(pool)-1)]['values']
            prediction = estimate + residual * (estimate.sum() if p['domain'] == 'absolute' else 1.)
            try:
                prediction = project_shape(prediction) if p['domain'] == 'shape' else np.maximum(prediction, 0)
            except ValueError:
                continue
            totals[replica, index] = prediction
    valid = np.all(np.isfinite(totals), axis=2)
    covariance = {}
    for index, p in enumerate(predictions):
        values = totals[valid[:, index], index]
        p['valid_replicas'] = len(values)
        for level, bounds in ((68, (.16, .84)), (95, (.025, .975))):
            p[f'interval{level}'] = np.quantile(values, bounds, axis=0) if len(values) >= 2 else None
        if len(values) >= 2:
            covariance[index] = np.cov(values, rowvar=False, ddof=1)
    return dict(replica_ids=np.arange(n_replicas), target_keys=[p['target_key'] for p in predictions],
                mean_replicas=means, replicas=totals, valid=valid, covariance=covariance,
                seed=seed, interval_kind='exploratory_block_bootstrap_plus_training_oof_residuals')
