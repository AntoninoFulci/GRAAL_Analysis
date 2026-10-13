"""Run an opt-in experimental flux study; never publish production exposures."""
from __future__ import annotations

from collections import defaultdict
import sys

from flux_studies.audit_flux import build_parser, audit_kwargs, input_paths, audit_flux
from flux_studies.metadata import STATES, GROUP_FIELDS, eligible, compatible
from flux_studies.reporting import publish_output, write_audit, write_study


def run_study(audit, *, mode, n_splits, seed, n_replicas, mask_patterns):
    if mode not in ('offline', 'causal') or n_splits < 2 or n_replicas < 2:
        raise ValueError('invalid study mode, folds or replicas')
    if not mask_patterns or any(not p or len(set(p)) != len(p) or any(s not in STATES for s in p) for p in mask_patterns):
        raise ValueError('mask patterns require distinct POL1/POL2/BREM states')
    result = dict(schema_version=1, status='not_executable', reasons=[], candidates=[],
                  mode=mode, seed=seed, folds=n_splits, replicas=n_replicas,
                  mask_patterns=mask_patterns, adoption='not_assessed',
                  protocol=['Supply acquisition intervals, configuration and laser identities.',
                            'Supply independent exposure values, units, definitions and uncertainties for absolute flux.',
                            'Predefine physical adoption criteria before using a final validation sample.',
                            'Synthetic candidates are not production measurements.'])
    usable = {key: row for key, row in audit['metadata'].items() if eligible(row)}
    if not usable:
        result['reasons'] = ['acquisition_metadata_unavailable_or_incomplete']
        return result
    from flux_studies.validation import evaluate_holdouts, _predict, _choose_alpha, _training_residuals
    from flux_studies.uncertainty import joint_replicas, paired_metrics
    missing = defaultdict(list)
    for row in audit['rows']:
        if 'missing_raw' in row['problems']:
            missing[row['run_number']].append(row['state'])
    patterns = tuple(dict.fromkeys([tuple(p) for p in mask_patterns] + [tuple(s for s in STATES if s in states) for states in missing.values()]))
    evaluation = evaluate_holdouts(audit, mode=mode, n_splits=n_splits, mask_patterns=patterns, seed=seed)
    if not evaluation['predictions']:
        result.update(status='insufficient_data', reasons=['no_eligible_holdouts'])
        return result
    uncertainty = joint_replicas(evaluation, seed=seed, n_replicas=n_replicas)
    metrics = paired_metrics(evaluation['predictions'])
    result.update(status='exploratory', evaluation=evaluation, uncertainty=uncertainty, metrics=metrics,
                  reasons=['physical_adoption_criteria_not_supplied'], mask_patterns=patterns)
    contexts, candidates = {}, []
    for run, states in missing.items():
        pattern = tuple(s for s in STATES if s in states)
        for state in pattern:
            key = (run, state)
            if key not in usable:
                continue
            query = usable[key]
            group = tuple(query[f] for f in GROUP_FIELDS)
            train = sorted({k[0] for k, row in usable.items() if k in audit['histograms'] and compatible(row, query)
                            and k[0] != run and (mode == 'offline' or row['end'] < query['start'])})
            if len(train) < 2:
                continue
            alpha = _choose_alpha(audit, train, group, pattern, state, mode)
            for domain in ('shape', 'absolute'):
                if domain == 'absolute' and query.get('exposure') is None:
                    continue
                cid = ('candidate', group, pattern, state, domain, tuple(train))
                residuals = _training_residuals(audit, train, group, pattern, state, mode, domain)
                contexts[cid] = dict(audit=audit, runs=train, pattern=pattern, mode=mode, domain=domain, alpha=alpha, residuals=residuals)
                for method in ('nearest', 'mean', 'median', 'linear', 'ridge'):
                    if not residuals.get(method):
                        continue
                    p = _predict(audit, train, key, pattern, mode, domain, method, alpha)
                    if p['status'] != 'ok':
                        continue
                    p.update(run_number=run, state=state, method=method, domain=domain, context_id=cid,
                             target_key=(run, state, mode, 'candidate', pattern, domain), training_runs=train,
                             mask=pattern, mode=mode, provenance='synthetic', reason='missing_raw',
                             physical_status='experimental_candidate', conditions=query, seed=seed)
                    candidates.append(p)
    result['candidates'] = candidates
    if candidates:
        result['candidate_uncertainty'] = joint_replicas(dict(predictions=candidates, contexts=contexts), seed=seed, n_replicas=n_replicas)
    result['candidate_exclusions'] = [dict(run_number=run, state=state, reason='insufficient_compatible_training_or_residuals')
                                      for run, states in missing.items() for state in states
                                      if not any(p['run_number']==run and p['state']==state for p in candidates)]
    return result


def main(argv=None):
    parser = build_parser()
    parser.description = __doc__
    parser.add_argument('--mode', choices=('offline','causal'), default='offline')
    parser.add_argument('--folds', type=int, default=5)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--replicas', type=int, default=200)
    parser.add_argument('--mask-states', action='append', help='comma-separated missing states; repeat for multiple patterns')
    args = parser.parse_args(argv)
    try:
        patterns = tuple(tuple(s.strip() for s in p.split(',')) for p in args.mask_states) if args.mask_states else tuple((s,) for s in STATES)
        if args.folds < 2 or args.replicas < 2 or args.seed < 0:
            raise ValueError('folds/replicas must be >= 2 and seed nonnegative')
        with publish_output(args.output_dir, input_paths(args)) as staged:
            audit = audit_flux(**audit_kwargs(args))
            study = run_study(audit, mode=args.mode, n_splits=args.folds, seed=args.seed, n_replicas=args.replicas, mask_patterns=patterns)
            write_audit(staged, audit)
            write_study(staged, audit, study)
        print(f"Flux study: {study['status']}; {study['reasons']}\nOutput: {args.output_dir}")
        return 0
    except (ValueError, OSError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
