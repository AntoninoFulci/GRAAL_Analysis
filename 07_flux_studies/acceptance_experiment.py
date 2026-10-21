"""Frozen blocked development and internal confirmation of flux acceptance."""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import time

import numpy as np

from calibration.calibration_qa import sha256_file
from calibration.run_quality import DEFAULT_RUN_QUALITY_PATH, load_run_quality
from flux_studies.acceptance_scan import POLICIES, state_diagnostics, decide_runs
from flux_studies.calibrated_data import load_calibrated_dataset
from flux_studies.neighbor_validation import evaluate_neighbors, split_runs
from flux_studies.reporting import publish_output, write_json

PRIMARY = 'extra_trees_hybrid'
DEVELOPMENT = tuple(dict(index=i, seed=20261020 + 101 * i, block_size=1 if i % 2 == 0 else 3)
                    for i in range(10))
CONFIRMATION = dict(seed=20271103, block_size=3)


def _runs_by_period(records):
    result = defaultdict(set)
    for row in records:
        result[row['period']].add(row['run'])
    return result


def reserve_outer(records, *, seed):
    """Freeze approximately 20% of whole three-run blocks before development."""
    result = {}
    for period, runs in sorted(_runs_by_period(records).items()):
        roles, blocks = split_runs(runs, block_size=3, seed=seed)
        result[period] = [dict(run=r, role='test' if roles.get(r) == 'test' else 'train',
                               block=blocks.get(r, i // 3)) for i, r in enumerate(sorted(runs))]
    return result


def trial_partition(records, outer, *, phase, seed, block_size):
    if phase not in ('development', 'confirmation'):
        raise ValueError('unknown experiment phase')
    universe = _runs_by_period(records)
    if set(outer) != set(universe):
        raise ValueError('outer partition period mismatch')
    held = set()
    for period, assignments in outer.items():
        if len({r['run'] for r in assignments}) != len(assignments) or {
                r['run'] for r in assignments} != universe[period]:
            raise ValueError('outer partition run mismatch')
        if any(r['role'] not in ('train', 'test') for r in assignments):
            raise ValueError('invalid outer role')
        held.update(r['run'] for r in assignments if r['role'] == 'test')
    usable = [r for r in records if phase == 'confirmation' or r['run'] not in held]
    plan = {}
    for period, runs in sorted(universe.items()):
        development = sorted(runs - held)
        roles, blocks = split_runs(development, block_size=block_size, seed=seed)
        if not roles:
            roles = dict.fromkeys(development, 'train')
            blocks = {r: i // block_size for i, r in enumerate(development)}
        local = [dict(run=r,
                      role=roles[r] if phase == 'development' else
                      ('validation' if roles[r] == 'validation' else 'train'),
                      block=blocks[r] + 1000000) for r in development]
        if phase == 'confirmation':
            local.extend(dict(r) for r in outer[period] if r['role'] == 'test')
        if local:
            plan[period] = sorted(local, key=lambda r: r['run'])
    return plan, usable


def mask_templates(inventory, *, excluded_runs):
    groups = defaultdict(set)
    for row in inventory['missing']:
        if row['run'] not in excluded_runs and row.get('missing_reason', 'missing_calibrated') == 'missing_calibrated':
            groups[row['period'], row['run']].add(row['state'])
    result = defaultdict(list)
    for (period, run), states in sorted(groups.items()):
        result[period].append(sorted(states))
    return dict(result)


def trial_masks(plan, templates, *, seed):
    """Match empirical state-pattern frequencies; gap size remains a stress axis."""
    rng = np.random.default_rng(seed)
    masks = []
    for period, assignments in sorted(plan.items()):
        choices = templates.get(period, [['POL1', 'POL2', 'BREM']])
        for row in assignments:
            if row['role'] == 'test':
                states = choices[int(rng.integers(len(choices)))]
                masks.extend(dict(period=period, run=row['run'], state=s) for s in states)
    return masks


def _data(paths):
    from flux_studies.study_native_recovery import load_cached_counts
    counts, sources = load_cached_counts(paths['counts_cache'])
    dataset = load_calibrated_dataset(paths['manifest'], paths['calibrated_flux'], counts,
                                      representation='native_strip', run_quality_path=paths['run_quality'])
    return dataset, sources


def prepare_experiment(paths, output_dir, *, replicas=128, periods=None):
    from flux_studies.strip_audit import audit_native_strips
    if replicas < 32:
        raise ValueError('scan requires at least 32 replicas')
    paths = {k: str(Path(v).resolve()) for k, v in paths.items()}
    with publish_output(output_dir, paths.values()) as directory:
        dataset, sources = _data(paths)
        available = {r['period'] for r in dataset['records']}
        periods = sorted(available if periods is None else set(periods))
        if not periods or not set(periods) <= available:
            raise ValueError('requested periods must have clean calibrated records')
        dataset['records'] = [r for r in dataset['records'] if r['period'] in periods]
        quality = load_run_quality(paths['run_quality'])
        excluded = {r['run'] for r in quality['excluded_runs']}
        audit = audit_native_strips(paths['manifest'], paths['calibrated_flux'], paths['raw_flux'],
                                   runs={r['run'] for r in dataset['records']})
        if audit['status'] != 'verified':
            raise ValueError('native strip audit failed')
        outer = reserve_outer(dataset['records'], seed=20261021)
        inventory = json.loads(Path(paths['inventory']).read_text())
        protocol = dict(schema_version=1, frozen_utc=datetime.now(timezone.utc).isoformat(),
                        paths=paths, input_sha256={k: sha256_file(v) for k, v in paths.items()},
                        development=list(DEVELOPMENT), confirmation=CONFIRMATION,
                        outer=outer, outer_seed=20261021, replicas=replicas, policies=POLICIES,
                        templates=mask_templates(inventory, excluded_runs=excluded),
                        excluded_runs=sorted(excluded), methods=[PRIMARY], model_families=['extra_trees', 'kernel_ridge'],
                        outer_interpretation='Internally reserved for this scan; previously inspected experimental campaign.',
                        dependence='Development repetitions share runs and are correlated; no independent-trial confidence claims.',
                        mask_interpretation='Empirical missing-state patterns sampled per run; one/three-run blocked gap stress tests, not exact historical gap placement.',
                        baseline='All masked runs removed at every policy; oracle matched to accepted sample.',
                        screening='Worst-point paired bias <=0.10 oracle sigma, representation <=0.05, conditional flux std <=0.30; coverage and failed fits retained.',
                        production_adopted=False, source_count=len(dataset['records']),
                        resource_limit_cores=40, periods=periods)
        write_json(directory / 'protocol.json', protocol)
        write_json(directory / 'strip_audit.json', audit)
        write_json(directory / 'h80_sources.json', sources)
        write_json(directory / 'run_quality.json', quality)
    return Path(output_dir) / 'protocol.json'


def _masked_reference_rows(study, masks, records):
    """Keep unreconstructible masked runs in the baseline's missing universe."""
    existing = {(p['period'], p['run'], p['state']) for p in study['predictions'] if p['role'] == 'test'}
    lookup = {(r['period'], r['run'], r['state']): r for r in records}
    extra = []
    for mask in masks:
        key = mask['period'], mask['run'], mask['state']
        if key not in existing:
            row = lookup[key]
            extra.append(dict(**mask, role='test', method='masked_reference_only',
                              count=row['count'], donors=[], truth=row['values'], estimate=np.full(128, np.nan)))
    return {**study, 'predictions': study['predictions'] + extra}


def policy_coverage(study, uncertainty, accepted):
    """Evaluate held-out truth only after decisions have been frozen."""
    from flux_studies.flux_uncertainty import _clusters
    from flux_studies.native_diagnostics import clustered_coverage_intervals
    selected = [p for p in study['predictions'] if p['role'] == 'test' and
                p['method'] == PRIMARY and p['run'] in accepted]
    clusters = {}
    for period, assignments in study['splits'].items():
        clusters[period] = _clusters([p for p in selected if p['period'] == period],
                                    {a['run']: a['block'] for a in assignments})
    rows = [r for r in uncertainty['target_summary'] if r['method'] == PRIMARY and r['run'] in accepted]
    return clustered_coverage_intervals(rows, clusters, seed=20261020)


def run_trial(protocol_path, output_dir, *, phase, trial_index=0, selection_path=None, workers=1):
    from flux_studies.flux_uncertainty import neighbor_replicas, closure_replicas
    from flux_studies.flux_observable_closure import run_observable_closure
    from flux_studies.study_calibrated_neighbors import _write_benchmark
    from flux_studies.study_realistic_gaps import restrict_test_states
    from threadpoolctl import threadpool_limits
    protocol_path = Path(protocol_path)
    protocol = json.loads(protocol_path.read_text())
    digest = sha256_file(protocol_path)
    if protocol['policies'] != list(POLICIES):
        raise ValueError('policy code differs from frozen protocol')
    if phase not in ('development', 'confirmation'):
        raise ValueError('invalid phase')
    spec = protocol['development'][trial_index] if phase == 'development' else protocol['confirmation']
    policies = list(POLICIES)
    inputs = [protocol_path, *protocol['paths'].values()]
    if phase == 'confirmation':
        if selection_path is None:
            raise ValueError('confirmation requires frozen development selection')
        from flux_studies.acceptance_report import validate_selection
        _, selection, _, _ = validate_selection(protocol_path, selection_path)
        policies = [p for p in POLICIES if p['name'] == selection.get('selected_policy')]
        if len(policies) != 1:
            raise ValueError('no feasible development policy selected; confirmation not authorized')
        inputs.append(selection_path)
    for key, path in protocol['paths'].items():
        if sha256_file(path) != protocol['input_sha256'][key]:
            raise ValueError(f'input differs from frozen protocol: {key}')
    started = time.monotonic()
    with publish_output(output_dir, inputs) as directory, threadpool_limits(limits=1):
        dataset, sources = _data(protocol['paths'])
        dataset['records'] = [r for r in dataset['records'] if r['period'] in protocol['periods']]
        plan, records = trial_partition(dataset['records'], protocol['outer'], phase=phase,
                                       seed=spec['seed'], block_size=spec['block_size'])
        masks = trial_masks(plan, protocol['templates'], seed=spec['seed'] + 1)
        write_json(directory / 'partition.json', plan)
        write_json(directory / 'masks.json', masks)
        print(f"{phase} {spec}: {len(records)} spectra, {len(masks)} masked states", flush=True)
        study = evaluate_neighbors(records, seed=spec['seed'], block_size=spec['block_size'],
                                   models=('extra_trees', 'kernel_ridge'), split_plan=plan)
        study = restrict_test_states(study, masks)
        _write_benchmark(directory, {**dataset, 'records': records}, [study], sources=sources)
        uncertainty = neighbor_replicas(records, study, methods=(PRIMARY,),
                                        n_replicas=protocol['replicas'], seed=spec['seed'] + 10000)
        np.savez_compressed(directory / 'flux_replicas.npz', draws=uncertainty['draws'],
                            model_draws=uncertainty['model_draws'])
        write_json(directory / 'flux_uncertainty.json', {k: v for k, v in uncertainty.items()
                                                       if k not in ('draws', 'model_draws')})
        study = _masked_reference_rows(study, masks, records)
        diagnostics = state_diagnostics(records, study, uncertainty, excluded_runs=protocol['excluded_runs'])
        if {(r['period'], r['run'], r['state']) for r in diagnostics} != {
                (r['period'], r['run'], r['state']) for r in masks}:
            raise ValueError('acceptance diagnostics do not cover every requested mask')
        write_json(directory / 'state_diagnostics.json', diagnostics)
        replicas = closure_replicas(uncertainty)
        cache = {}
        for policy in policies:
            destination = directory / 'policies' / policy['name']
            destination.mkdir(parents=True)
            decision = decide_runs(diagnostics, policy, excluded_runs=protocol['excluded_runs'])
            write_json(destination / 'decision.json', decision)
            accepted = set(decision['accepted_runs'])
            print(f"{policy['name']}: {len(accepted)} accepted masked runs (diagnostic only)", flush=True)
            identity = tuple(sorted(accepted))
            if identity in cache:
                shutil.copytree(cache[identity] / 'closure', destination / 'closure')
                shutil.copyfile(cache[identity] / 'coverage.json', destination / 'coverage.json')
                write_json(destination / 'reuse.json', dict(source_policy=cache[identity].name,
                           reason='Identical accepted run set, same predictions and aligned replicas.'))
                continue
            paths = protocol['paths']
            run_observable_closure([p for p in study['predictions'] if p['role'] == 'test'],
                representation='native_strip', flux_path=paths['calibrated_flux'],
                manifest_path=paths['manifest'], reco_paths={'uv': paths['reco_uv'], 'vis': paths['reco_vis']},
                output_dir=destination / 'closure', methods=(PRIMARY,), workers=workers,
                flux_replicas=replicas, flux_replica_count=protocol['replicas'],
                run_quality_path=paths['run_quality'], accepted_runs=accepted,
                analysis_runs={r['run'] for r in records})
            write_json(destination / 'coverage.json', policy_coverage(study, uncertainty, accepted))
            cache[identity] = destination
        write_json(directory / 'trial.json', dict(phase=phase, seed=spec['seed'], block_size=spec['block_size'],
                   trial_index=trial_index if phase == 'development' else None,
                   protocol_sha256=digest, status='complete', elapsed_seconds=time.monotonic()-started,
                   workers=workers, selection_sha256=sha256_file(selection_path) if selection_path else None,
                   production_adopted=False))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare = commands.add_parser('prepare')
    for key in ('manifest', 'raw-flux', 'calibrated-flux', 'counts-cache', 'inventory', 'reco-uv', 'reco-vis'):
        prepare.add_argument('--' + key, type=Path, required=True)
    prepare.add_argument('--run-quality', type=Path, default=DEFAULT_RUN_QUALITY_PATH)
    prepare.add_argument('--replicas', type=int, default=128)
    prepare.add_argument('--periods', nargs='+', help='Optional limited smoke-test scope; full experiment omits this')
    prepare.add_argument('--output-dir', type=Path, required=True)
    trial = commands.add_parser('trial')
    trial.add_argument('--protocol', type=Path, required=True)
    trial.add_argument('--phase', choices=('development', 'confirmation'), default='development')
    trial.add_argument('--trial-index', type=int, choices=range(len(DEVELOPMENT)), default=0)
    trial.add_argument('--selection', type=Path)
    trial.add_argument('--workers', type=int, default=1)
    trial.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == 'prepare':
        paths = {k: getattr(args, k) for k in ('manifest', 'raw_flux', 'calibrated_flux', 'counts_cache',
                 'inventory', 'reco_uv', 'reco_vis', 'run_quality')}
        print(prepare_experiment(paths, args.output_dir, replicas=args.replicas, periods=args.periods))
    else:
        if not 1 <= args.workers <= 4:
            parser.error('workers must be 1..4; farm array concurrency is capped at ten')
        run_trial(args.protocol, args.output_dir, phase=args.phase, trial_index=args.trial_index,
                  selection_path=args.selection, workers=args.workers)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
