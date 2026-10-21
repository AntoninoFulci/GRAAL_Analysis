"""Conservative development screening; never production or independent validation."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import median

from flux_studies.acceptance_scan import POLICIES
from flux_studies.reporting import publish_output, write_csv, write_json


METHOD = 'extra_trees_hybrid'
POINT_FIELDS = ('estimator', 'pair', 'energy_bin', 'mass_bin')
ARTIFACTS = ('decision.json', 'closure/observable_closure.json', 'coverage.json')
INTERPRETATION = (
    'Conditional development diagnostic over correlated repetitions. Worst-point '
    'paired bias screening does not certify independent mean bias; clustered '
    'coverage remains conditional. No independent confirmation or production adoption.'
)


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _key(row):
    return tuple(row.get(field) for field in POINT_FIELDS)


def _points(period, scenario):
    return {_key(row): row for row in period.get('scenarios', {}).get(scenario, {}).get('points', [])}


def _fixed_points(payloads):
    """Baseline-estimable union of oracle bins, fixed across the entire ladder."""
    oracles, baselines = {}, {}
    for _, closure, _ in payloads.values():
        for period in closure.get('periods', []):
            name = period['period']
            oracles.setdefault(name, set()).update(_points(period, 'native_truth'))
            baselines.setdefault(name, []).append(set(_points(period, 'without_recovery')))
    return {name: points & set.union(*baselines[name]) for name, points in oracles.items()}


def _neutral_verified(closure):
    """No recovered runs must leave the finite observable sample unchanged."""
    seen = False
    for period in closure.get('periods', []):
        if period.get('accepted_runs') or period.get('target_states') or period.get('recovered_events') != 0:
            return False
        baseline = _points(period, 'without_recovery')
        oracle, recovered = _points(period, 'native_truth'), _points(period, METHOD)
        if set(baseline) != set(oracle) or set(baseline) != set(recovered):
            return False
        for key, point in baseline.items():
            for field in ('sigma', 'stat_low', 'stat_high'):
                value = point.get(field)
                if not _finite(value) or any(p[key].get(field) != value for p in (oracle, recovered)):
                    return False
            seen = True
    return seen


def _screen(decision, closure, coverage, fixed, seed):
    reasons, periods, ratios = [], [], []
    accepted = set(decision.get('accepted_runs', []))
    closure_accepted = set(closure.get('accepted_runs', []))
    period_accepted = {run for p in closure.get('periods', []) for run in p.get('accepted_runs', [])}
    if accepted != closure_accepted or accepted != period_accepted:
        reasons.append('accepted_run_mismatch')
    expected_states = {(r.get('period'), r.get('run'), r.get('state'))
                       for r in decision.get('state_decisions', []) if r.get('run') in accepted}
    actual_states = {(p.get('period'), r.get('run'), r.get('state'))
                     for p in closure.get('periods', []) for r in p.get('target_states', [])}
    if expected_states != actual_states or {r[1] for r in expected_states} != accepted:
        reasons.append('accepted_state_mismatch')
    if any(r.get('accepted') is not True for r in decision.get('state_decisions', [])
           if r.get('run') in accepted):
        reasons.append('accepted_state_not_passed')
    events = sum(p.get('recovered_events', 0) for p in closure.get('periods', [])
                 if _finite(p.get('recovered_events')))
    result = dict(seed=seed, accepted_runs=len(accepted), recovered_events=events,
                  precision_median=None, objective_contribution=None,
                  max_abs_bias=None, max_flux=None, periods=periods, reasons=reasons,
                  coverage=coverage, state_decisions=decision.get('state_decisions', []))
    if not accepted:
        neutral = _neutral_verified(closure)
        result.update(status='no_recovery', neutral_verified=neutral,
                      objective_contribution=1.0 if neutral else None)
        if not neutral:
            reasons.append('no_recovery_neutrality_unavailable')
        return result
    for period in closure.get('periods', []):
        if not period.get('accepted_runs'):
            # These fixed bins still belong in the trial objective. Otherwise a
            # policy could improve its median merely by omitting a hard period.
            required = fixed.get(period['period'], set())
            if required:
                if (_neutral_verified(dict(periods=[period]))
                        and required <= set(_points(period, 'native_truth'))):
                    ratios.extend([1.] * len(required))
                else:
                    reasons.append(f"{period['period']}:no_recovery_neutrality_unavailable")
            continue
        name, failures = period['period'], []
        row = dict(period=name, recovered_events=period.get('recovered_events'),
                   precision_median=None, max_abs_bias=None, max_flux=None, reasons=failures)
        periods.append(row)
        if not _finite(row['recovered_events']) or row['recovered_events'] < 0:
            failures.append('recovered_events_unavailable')
        if period.get('acceptance', {}).get('representation', {}).get('status') != 'passed':
            failures.append('representation_not_passed')
        oracle = _points(period, 'native_truth')
        recovered = _points(period, METHOD)
        baseline = _points(period, 'without_recovery')
        required = fixed.get(name, set())
        if not oracle or not required:
            failures.append('no_comparable_oracle_points')
        if not required <= set(oracle) or not required <= set(baseline):
            failures.append('fixed_comparison_points_missing')
        if not set(oracle) <= set(recovered):
            failures.append('oracle_recovery_fit_loss')
        replica = period.get('flux_replica_results', {}).get(METHOD, {})
        requested, complete = replica.get('requested_replicas'), replica.get('complete_replicas')
        if not (_finite(requested) and _finite(complete) and requested >= complete >= 32
                and complete >= .90 * requested):
            failures.append('insufficient_complete_replicas')
        comparisons = [r for r in period.get('comparisons', [])
                       if r.get('reference') == 'native_truth' and r.get('scenario') == METHOD]
        comp = {_key(r): r for r in comparisons}
        precision_rows = [r for r in period.get('recovery_precision', []) if r.get('method') == METHOD]
        precision = {_key(r): r for r in precision_rows}
        if len(comp) != len(comparisons) or len(precision) != len(precision_rows):
            failures.append('duplicate_observable_points')
        biases, fluxes, local_ratios = [], [], []
        for key in oracle:
            comparison, point = comp.get(key, {}), precision.get(key, {})
            bias, flux = comparison.get('delta_over_nominal_stat'), point.get('flux_over_oracle_stat')
            if comparison.get('status') != 'matched' or not _finite(bias):
                failures.append('paired_bias_unavailable')
            else:
                biases.append(abs(bias))
                if abs(bias) > .10:
                    failures.append('bias_budget_exceeded')
            if point.get('missing_recovered', True) or not _finite(flux) or flux < 0:
                failures.append('flux_contribution_unavailable')
            else:
                fluxes.append(flux)
                if flux > .30:
                    failures.append('flux_budget_exceeded')
        for key in required:
            point = precision.get(key, {})
            ratio = point.get('precision_ratio')
            if (point.get('status') != 'matched' or not _finite(ratio) or ratio <= 0
                    or any(point.get(flag, True) for flag in
                           ('missing_oracle', 'missing_recovered', 'missing_without_recovery'))):
                failures.append('precision_unavailable')
            else:
                local_ratios.append(ratio)
        states = {r.get('state') for r in period.get('target_states', [])
                  if r.get('run') in set(period['accepted_runs'])}
        if not states or None in states:
            failures.append('accepted_states_unavailable')
        for state in states:
            matches = [r for r in coverage if r.get('period') == name
                       and r.get('state') == state and r.get('method') == METHOD]
            if len(matches) != 1:
                failures.append(f'coverage_unavailable:{state}')
                continue
            for metric, nominal in (('coverage68', .68), ('coverage95', .95)):
                evidence = matches[0].get(metric, {})
                interval = evidence.get('interval95')
                if not (isinstance(interval, list) and len(interval) == 2
                        and all(_finite(v) for v in interval)
                        and interval[0] <= nominal <= interval[1]
                        and evidence.get('nominal_inside_interval') is True
                        and evidence.get('status') == 'conditional_diagnostic'
                        and _finite(evidence.get('observed')) and 0 <= evidence['observed'] <= 1
                        and _finite(evidence.get('evaluable_targets')) and evidence['evaluable_targets'] > 0
                        and _finite(evidence.get('donor_clusters')) and evidence['donor_clusters'] >= 5):
                    failures.append(f'coverage_not_supported:{state}:{metric}')
        row.update(precision_median=median(local_ratios) if local_ratios else None,
                   max_abs_bias=max(biases, default=None), max_flux=max(fluxes, default=None),
                   status='failed' if failures else 'passed')
        ratios.extend(local_ratios)
        reasons.extend(f'{name}:{reason}' for reason in dict.fromkeys(failures))
    result.update(precision_median=median(ratios) if ratios else None,
                  max_abs_bias=max((r['max_abs_bias'] for r in periods if r['max_abs_bias'] is not None), default=None),
                  max_flux=max((r['max_flux'] for r in periods if r['max_flux'] is not None), default=None))
    if not ratios:
        reasons.append('precision_unavailable')
    result['objective_contribution'] = result['precision_median']
    result['status'] = 'failed' if reasons else 'passed'
    return result


def _read_protocol(protocol_path):
    """The hashed protocol, rather than caller arguments, owns the denominator."""
    raw = Path(protocol_path).read_bytes()
    protocol = json.loads(raw)
    if protocol.get('policies') != list(POLICIES):
        raise ValueError('frozen protocol policies differ from the policy registry')
    schedule = protocol.get('development')
    if not isinstance(schedule, list) or not schedule:
        raise ValueError('frozen development schedule is empty or invalid')
    seeds = set()
    for index, item in enumerate(schedule):
        if (not isinstance(item, dict) or type(item.get('index')) is not int
                or item['index'] != index or type(item.get('seed')) is not int
                or type(item.get('block_size')) is not int or item['block_size'] <= 0
                or item['seed'] in seeds):
            raise ValueError('frozen development schedule has invalid identities')
        seeds.add(item['seed'])
    confirmation = protocol.get('confirmation', {})
    if (type(confirmation.get('seed')) is not int
            or type(confirmation.get('block_size')) is not int or confirmation['block_size'] <= 0):
        raise ValueError('frozen confirmation schedule is invalid')
    return protocol, hashlib.sha256(raw).hexdigest()


def _check_schedule(metadata, specification):
    if any(type(metadata.get(field)) is not int or metadata[field] != specification[field]
           for field in ('seed', 'block_size')):
        raise ValueError('trial seed/block_size differs from frozen schedule')


def collect_scan(trial_dirs, *, protocol_path):
    """Read frozen development artifacts; return a report without writing files."""
    protocol, protocol_sha256 = _read_protocol(protocol_path)
    schedule = protocol['development']
    expected_trials = len(schedule)
    directories = [Path(path).resolve() for path in trial_dirs]
    if len(set(directories)) != len(directories):
        raise ValueError('duplicate trial directory')
    if len(directories) > expected_trials:
        raise ValueError('more trial directories than expected_trials')
    policies = [dict(name=p['name'], thresholds=p, trials=[]) for p in POLICIES]
    incomplete, seeds, completed, inputs = [], set(), 0, [str(protocol_path)]
    indices, completed_indices = set(), []
    for directory in directories:
        try:
            metadata = json.loads((directory / 'trial.json').read_text())
        except (OSError, ValueError) as exc:
            incomplete.append(dict(directory=str(directory), reason=f'trial_metadata_unavailable: {exc}'))
            continue
        inputs.append(str(directory / 'trial.json'))
        if metadata.get('phase') != 'development':
            raise ValueError('only development trials may be used for selection')
        if metadata.get('protocol_sha256') != protocol_sha256:
            raise ValueError('trial protocol hash mismatch')
        index = metadata.get('trial_index')
        if type(index) is not int or not 0 <= index < expected_trials:
            raise ValueError('trial index is absent from frozen development schedule')
        if index in indices:
            raise ValueError('duplicate trial index')
        indices.add(index)
        _check_schedule(metadata, schedule[index])
        seed = metadata.get('seed')
        if not isinstance(seed, int) or isinstance(seed, bool):
            raise ValueError('trial seed must be an integer')
        if seed in seeds:
            raise ValueError('duplicate trial seed')
        seeds.add(seed)
        if metadata.get('status') != 'complete':
            incomplete.append(dict(directory=str(directory), seed=seed, reason='trial_not_complete'))
            continue
        payloads = {}
        for policy in policies:
            base = directory / 'policies' / policy['name']
            try:
                paths = [base / filename for filename in ARTIFACTS]
                payload = tuple(json.loads(path.read_text()) for path in paths)
                if not (isinstance(payload[0], dict) and isinstance(payload[1], dict)
                        and isinstance(payload[2], list)):
                    raise ValueError('invalid artifact top-level type')
            except (OSError, ValueError) as exc:
                incomplete.append(dict(directory=str(directory), seed=seed,
                                       policy=policy['name'], reason=f'artifact_unavailable: {exc}'))
                continue
            if payload[0].get('policy') != policy['name']:
                raise ValueError('decision policy does not match policy directory')
            payloads[policy['name']] = payload
            inputs.extend(map(str, paths))
        if len(payloads) != len(policies):
            continue
        completed += 1
        completed_indices.append(index)
        fixed = _fixed_points(payloads)
        for policy in policies:
            policy['trials'].append(_screen(*payloads[policy['name']], fixed, seed))
    all_complete = completed == expected_trials
    for policy in policies:
        trials = policy['trials']
        reasons = [f"seed={t['seed']}:{reason}" for t in trials for reason in t['reasons']]
        events = sum(t['recovered_events'] for t in trials)
        contributions = [t['objective_contribution'] for t in trials]
        objective = median(contributions) if (len(contributions) == expected_trials
                                              and all(_finite(v) for v in contributions) and events > 0) else None
        if not all_complete:
            reasons.append('incomplete_trial_denominator')
        if events <= 0:
            reasons.append('no_recovered_events')
        if objective is None:
            reasons.append('objective_unavailable')
        elif objective >= 1:
            reasons.append('no_conditional_precision_improvement')
        policy.update(feasible=not reasons, reasons=reasons, precision_objective=objective,
                      recovered_events=events, accepted_runs=sum(t['accepted_runs'] for t in trials),
                      no_recovery_trials=sum(t['status'] == 'no_recovery' for t in trials),
                      completed_trials=len(trials), expected_trials=expected_trials,
                      max_abs_bias=max((t['max_abs_bias'] for t in trials if t['max_abs_bias'] is not None), default=None),
                      max_flux=max((t['max_flux'] for t in trials if t['max_flux'] is not None), default=None))
    feasible = [p for p in policies if p['feasible']]
    winner = min(feasible, key=lambda p: p['precision_objective']) if feasible else None
    return dict(status='complete' if all_complete else 'incomplete', expected_trials=expected_trials,
                completed_trials=completed, protocol_sha256=protocol_sha256,
                development_schedule=schedule, completed_trial_indices=sorted(completed_indices),
                missing_trial_indices=sorted(set(range(expected_trials)) - set(completed_indices)),
                selected_policy=winner['name'] if winner else None,
                selection_reasons=[] if winner else ['No policy passes every fixed development diagnostic and improves precision.'],
                production_adopted=False, independent_confirmation=False,
                method=METHOD, diagnostic_budgets=dict(representation=.05, paired_bias=.10,
                                                       flux_contribution=.30, minimum_replicas=32,
                                                       minimum_replica_fraction=.90),
                interpretation=INTERPRETATION, policies=policies, incomplete_trials=incomplete,
                objective_definition='Median across frozen development trials of trial median conditional precision_ratio on baseline-estimable union of oracle keys across policies. Every accepted policy must retain all fixed keys. Verified identical no-recovery samples contribute neutral 1, never an observed gain. Correlated repetitions; strict registry order breaks ties.',
                input_files=inputs)


def validate_selection(protocol_path, selection_path):
    """Validate the locked selection before any confirmation data are read."""
    protocol, protocol_sha256 = _read_protocol(protocol_path)
    selection_bytes = Path(selection_path).read_bytes()
    selection = json.loads(selection_bytes)
    if selection.get('protocol_sha256') != protocol_sha256:
        raise ValueError('selection protocol hash mismatch')
    selected = selection.get('selected_policy')
    if (selection.get('status') != 'complete' or selected not in {p['name'] for p in POLICIES}
            or selection.get('expected_trials') != len(protocol['development'])
            or selection.get('completed_trials') != len(protocol['development'])
            or selection.get('development_schedule') != protocol['development']
            or selection.get('completed_trial_indices') != list(range(len(protocol['development'])))
            or not any(p.get('name') == selected and p.get('feasible') is True
                       for p in selection.get('policies', []))):
        raise ValueError('confirmation requires a complete feasible development selection')
    return protocol, selection, protocol_sha256, hashlib.sha256(selection_bytes).hexdigest()


def confirm_scan(trial_dir, selection_path, *, protocol_path):
    """Evaluate only the locked selected policy on one internal confirmation."""
    directory, selection_path = Path(trial_dir), Path(selection_path)
    protocol, selection, protocol_sha256, selection_hash = validate_selection(protocol_path, selection_path)
    metadata = json.loads((directory / 'trial.json').read_text())
    if metadata.get('phase') != 'confirmation':
        raise ValueError('confirmation evaluation requires a confirmation trial')
    _check_schedule(metadata, protocol['confirmation'])
    if metadata.get('trial_index') is not None:
        raise ValueError('confirmation trial index differs from frozen schedule')
    if metadata.get('protocol_sha256') != protocol_sha256:
        raise ValueError('confirmation protocol hash mismatch')
    if metadata.get('selection_sha256') != selection_hash:
        raise ValueError('confirmation selection file hash mismatch')
    if metadata.get('status') != 'complete':
        raise ValueError('confirmation trial is incomplete')
    selected = selection.get('selected_policy')
    paths = [directory / 'policies' / selected / name for name in ARTIFACTS]
    decision, closure, coverage = (json.loads(path.read_text()) for path in paths)
    if decision.get('policy') != selected:
        raise ValueError('confirmation decision policy does not match selected policy')
    fixed = _fixed_points({selected: (decision, closure, coverage)})
    screened = _screen(decision, closure, coverage, fixed, metadata.get('seed'))
    reasons = list(screened['reasons'])
    if screened['recovered_events'] <= 0:
        reasons.append('no_recovered_events')
    objective = screened['objective_contribution']
    if not _finite(objective) or objective >= 1:
        reasons.append('no_conditional_precision_improvement')
    return dict(status='complete', phase='confirmation', selected_policy=selected,
                protocol_sha256=protocol_sha256, selection_sha256=selection_hash,
                diagnostic_passed=not reasons, reasons=reasons, trial=screened,
                production_adopted=False, independent_confirmation=False,
                interpretation='Conditional internal confirmation of the locked development choice; '
                               'no reselection. The campaign was examined previously. ' + INTERPRETATION,
                input_files=[str(protocol_path), str(selection_path), str(directory / 'trial.json'),
                             *map(str, paths)])


def plot_report(report, output_dir):
    """Visualize the conditional diagnostics, preserving unavailable entries."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np

    policies = report['policies']
    names = [p['name'] for p in policies]
    x = list(range(len(names)))
    fig, axes = plt.subplots(3, 1, figsize=(9, 10), sharex=True)
    axes[0].plot(x, [p['recovered_events'] for p in policies], 'o-')
    axes[0].set_ylabel('Recovered events, summed trials')
    axes[1].plot(x, [p['precision_objective'] for p in policies], 'o-')
    axes[1].axhline(1, color='grey', linestyle='--')
    axes[1].set_ylabel('Median conditional precision ratio')
    for field, label, budget in (('max_abs_bias', 'Worst paired bias / stat', .10),
                                  ('max_flux', 'Worst flux spread / stat', .30)):
        axes[2].plot(x, [p[field] for p in policies], 'o-', label=label)
        axes[2].axhline(budget, color='grey', linestyle='--', alpha=.6)
    axes[2].legend()
    axes[2].set_xticks(x, names, rotation=20)
    for ax in axes:
        ax.grid(alpha=.2)
    fig.suptitle('Correlated development diagnostics — no production adoption')
    fig.tight_layout()
    fig.savefig(Path(output_dir) / 'acceptance_scan.png', dpi=160)
    plt.close(fig)
    periods = sorted({r['period'] for p in policies for t in p['trials'] for r in t['periods']})
    if periods:
        values = np.full((len(periods), len(policies)), np.nan)
        for j, p in enumerate(policies):
            for i, period in enumerate(periods):
                rows = [r for t in p['trials'] for r in t['periods'] if r['period'] == period]
                if rows:
                    values[i, j] = float(all(r['status'] == 'passed' for r in rows))
        fig, ax = plt.subplots(figsize=(9, max(3, .5 * len(periods))))
        ax.imshow(values, vmin=0, vmax=1, cmap='RdYlGn', aspect='auto')
        ax.set_xticks(x, names, rotation=20)
        ax.set_yticks(range(len(periods)), periods)
        ax.set_title('Accepted-period screens: green pass, red fail, blank unavailable')
        fig.tight_layout()
        fig.savefig(Path(output_dir) / 'period_screens.png', dpi=160)
        plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trials', nargs='+', type=Path, required=True)
    parser.add_argument('--protocol', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args(argv)
    report = collect_scan(args.trials, protocol_path=args.protocol)
    with publish_output(args.output_dir, report['input_files']) as output:
        # Read under the publication integrity window as well.
        report = collect_scan(args.trials, protocol_path=args.protocol)
        write_json(output / 'summary.json', report)
        write_csv(output / 'summary.csv', [{k: v for k, v in p.items() if k != 'trials'}
                                          for p in report['policies']])
        plot_report(report, output)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
