"""Frozen external criteria, metadata-only eligibility, and explicit evidence gates.

No numerical scientific criterion has a default. Passing these software checks
is conditional on the declared normalization and systematic evidence; it does
not turn measured-reference uncertainties into zero.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

import numpy as np

RULE_FIELDS = ('max_gap', 'min_count', 'min_replicas', 'min_groups',
               'max_relative_integral_std', 'min_valid_replica_fraction')
LIMIT_FIELDS = ('max_abs_shift_stat', 'max_representation_shift_stat',
                'max_model_shift_stat', 'max_shift_std_stat',
                'max_combined_precision_ratio', 'max_missing_fraction',
                'min_complete_replicas', 'min_coverage_groups',
                'min_coverage68', 'min_coverage95', 'max_coverage_interval_width')
CONFIG_FIELDS = ('inputs', 'input_sha256', 'cohort_runs', 'energy_edges', 'assignments',
                 'masks', 'seed', 'replicas', 'min_groups', 'coverage_resamples',
                 'parameters', 'rule', 'normalization_domains', 'limits', 'history',
                 'point_universe', 'systematics', 'selection')


def _canonical(payload):
    return json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _numeric_fields(payload, fields):
    for name in fields:
        value = payload.get(name)
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not np.isfinite(value) or value < 0):
            raise ValueError(f'explicit finite nonnegative criterion required: {name}')
        if name.startswith('min_') and name not in ('min_coverage68', 'min_coverage95',
                                                   'min_valid_replica_fraction'):
            if value < 1 or value != int(value):
                raise ValueError(f'positive integer support required: {name}')
    for name in ('min_valid_replica_fraction', 'max_missing_fraction',
                 'min_coverage68', 'min_coverage95', 'max_coverage_interval_width'):
        if name in fields and payload[name] > 1:
            raise ValueError(f'fraction outside [0,1]: {name}')


def _validate_config(config):
    from calibration.calibration_qa import sha256_file
    missing = set(CONFIG_FIELDS) - config.keys()
    if missing:
        raise ValueError(f'missing frozen protocol fields: {sorted(missing)}')
    _numeric_fields(config['rule'], RULE_FIELDS)
    _numeric_fields(config['limits'], LIMIT_FIELDS)
    selection = config['selection']
    if not isinstance(selection, dict):
        raise ValueError('explicit selection specification required')
    for name in ('objective', 'stopping_rule'):
        value = selection.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f'explicit nonempty selection {name} required')
    candidates = selection.get('candidate_rules')
    if not isinstance(candidates, list) or not candidates:
        raise ValueError('nonempty bounded candidate_rules list required')
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ValueError('candidate rules must contain numeric rule dictionaries')
        _numeric_fields(candidate, RULE_FIELDS)
    if config['rule'] not in candidates:
        raise ValueError('selected rule is outside the declared candidate_rules')
    reports = selection.get('development_reports')
    if not isinstance(reports, list) or not reports:
        raise ValueError('authenticated development_reports required')
    seen_reports = set()
    for report in reports:
        if not isinstance(report, dict) or not isinstance(report.get('path'), str):
            raise ValueError('invalid development report identity')
        path, digest = Path(report['path']), report.get('sha256')
        if (not path.is_absolute() or not path.is_file() or not isinstance(digest, str)
                or len(digest) != 64 or sha256_file(path) != digest):
            raise ValueError(f'development report identity mismatch: {path}')
        if path.resolve() in seen_reports:
            raise ValueError('duplicate development report identity')
        seen_reports.add(path.resolve())
    edges = np.asarray(config['energy_edges'], dtype=float)
    if (edges.ndim != 1 or len(edges) < 2 or not np.all(np.isfinite(edges))
            or np.any(np.diff(edges) <= 0)):
        raise ValueError('invalid frozen energy edges')
    for name in ('seed', 'replicas', 'min_groups', 'coverage_resamples'):
        value = config[name]
        if isinstance(value, bool) or not isinstance(value, int) or value < (0 if name == 'seed' else 1):
            raise ValueError(f'invalid frozen {name}')
    if config['replicas'] < 2 or config['coverage_resamples'] < 2:
        raise ValueError('at least two replicas/resamples required')
    if not config['parameters'] or not config['cohort_runs'] or not config['point_universe']:
        raise ValueError('frozen parameters, cohort and point universe must be nonempty')
    cohort = config['cohort_runs']
    if len(set(cohort)) != len(cohort):
        raise ValueError('duplicate frozen cohort run')
    universe = [tuple(point) for point in config['point_universe']]
    if any(len(point) != 5 for point in universe) or len(set(universe)) != len(universe):
        raise ValueError('point universe requires unique period/estimator/pair/energy/mass keys')
    assignments = config['assignments']
    if {item['run'] for item in assignments} != set(cohort):
        raise ValueError('partition assignments must cover exactly the declared cohort')
    from flux_studies.energy_validation import validate_partitions
    validate_partitions([], assignments)
    if any(run not in cohort or state not in ('BREM','POL1','POL2') for run,state in config['masks']):
        raise ValueError('invalid frozen mask')
    history = config['history']
    if not history.get('final_interpretation') or 'previously_used_runs' not in history:
        raise ValueError('final history and interpretation must be explicit')
    previous = set(history['previously_used_runs'])
    if any(row['role'] == 'final' and row['run'] in previous for row in assignments):
        raise ValueError('previously used runs cannot be final verification')
    if not isinstance(config['systematics'], dict) or not config['systematics'].get('scope'):
        raise ValueError('systematic uncertainty scope must be explicit')
    identities = config['input_sha256']
    if not isinstance(identities, dict) or not identities:
        raise ValueError('input identity snapshots required')
    for path, digest in identities.items():
        if (not Path(path).is_absolute() or not isinstance(digest, str) or len(digest) != 64
                or not Path(path).is_file() or sha256_file(Path(path)) != digest):
            raise ValueError(f'input identity mismatch: {path}')


def _exclusive_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (_canonical(payload) + '\n').encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())


def freeze_protocol(config, path):
    """Publish a new immutable snapshot; existing snapshots are never replaced."""
    _validate_config(config)
    config = json.loads(_canonical(config))
    result = dict(schema_version=1, config=config,
                  sha256=hashlib.sha256(_canonical(config).encode()).hexdigest())
    _exclusive_json(path, result)
    return result


def load_protocol(path):
    result = json.loads(Path(path).read_text())
    if result.get('schema_version') != 1:
        raise ValueError('unsupported frozen protocol schema')
    digest = hashlib.sha256(_canonical(result['config']).encode()).hexdigest()
    if digest != result.get('sha256'):
        raise ValueError('frozen protocol digest mismatch')
    _validate_config(result['config'])
    return result


def claim_final(path):
    """Consume the one final attempt before computation, including failed runs."""
    frozen = load_protocol(path)
    marker = Path(str(path) + '.final-attempt.json')
    receipt = dict(protocol_sha256=frozen['sha256'],
                   attempted_at=datetime.now(timezone.utc).isoformat(),
                   marker_path=str(marker.resolve()), status='attempt_claimed')
    _exclusive_json(marker, receipt)
    return receipt


def _verification_identity(protocol_path, report_path):
    from calibration.calibration_qa import sha256_file
    frozen = load_protocol(protocol_path)
    attempt_path = Path(str(protocol_path) + '.final-attempt.json')
    attempt_hash = sha256_file(attempt_path)
    attempt = json.loads(attempt_path.read_text())
    report_path = Path(report_path).resolve(strict=True)
    report_hash = sha256_file(report_path)
    report = json.loads(report_path.read_text())
    if (attempt.get('protocol_sha256') != frozen['sha256']
            or attempt.get('status') != 'attempt_claimed'
            or report.get('phase') != 'verification'
            or report.get('protocol_sha256') != frozen['sha256']
            or report.get('input_sha256') != frozen['config']['input_sha256']):
        raise ValueError('verification does not match frozen protocol and final attempt')
    if sha256_file(report_path) != report_hash or sha256_file(attempt_path) != attempt_hash:
        raise ValueError('verification identity changed while authenticating')
    return report, dict(protocol_sha256=frozen['sha256'], report_path=str(report_path),
                        report_sha256=report_hash, attempt_sha256=attempt_hash)


def complete_verification(protocol_path, report_path):
    """Bind the published verification to its consumed attempt exactly once.

    Failed scientific qualification is still a completed verification; the
    attempt remains consumed and the failure report cannot be replaced.
    """
    _, identity = _verification_identity(protocol_path, report_path)
    receipt = dict(identity, completed_at=datetime.now(timezone.utc).isoformat(),
                   status='verification_completed')
    _exclusive_json(Path(str(protocol_path) + '.final-result.json'), receipt)
    return receipt


def load_verified_result(protocol_path, report_path):
    """Reject relabelled, relocated or edited reports before applying recovery."""
    report, identity = _verification_identity(protocol_path, report_path)
    receipt = json.loads(Path(str(protocol_path) + '.final-result.json').read_text())
    if (receipt.get('status') != 'verification_completed'
            or any(receipt.get(key) != value for key,value in identity.items())):
        raise ValueError('verification result identity differs from completed final attempt')
    return report


def decide_energy_runs(predictions, uncertainty, inventory, axes, rule,
                       normalization_domains, *, masked_states=()):
    """Apply declared metadata gates without accessing truth or observable fits."""
    _numeric_fields(rule, RULE_FIELDS)
    rows = inventory['inventory'] if isinstance(inventory, dict) else inventory
    lookup = {(r['run'], r['state']): r for r in rows}
    summaries = {(r['run'], r['state'], r['method']): r
                 for r in uncertainty.get('target_summary', [])}
    support = {(tuple(r.get('domain', [r['period']])), r.get('state')): r
               for r in uncertainty.get('residual_support', [])}
    domains = {(r['period'], r['state']) for r in normalization_domains
               if r.get('qualified') is True and r.get('evidence')}
    masked_states = set(map(tuple, masked_states))
    decisions, seen = [], set()
    for prediction in predictions:
        if prediction['method'] != 'extra_trees_hybrid':
            continue
        key = prediction['run'], prediction['state']
        if key in seen:
            raise ValueError('duplicate hybrid target decision')
        seen.add(key)
        row = lookup.get(key)
        reasons = []
        if row is None:
            reasons.append('missing_inventory')
        else:
            status = row['measurement_status']
            if status != 'missing_histogram' and not (key in masked_states and status == 'measured_valid'):
                reasons.append('not_a_missing_or_explicitly_masked_measurement')
            if 'run_quality' in row.get('reasons', []):
                reasons.append('run_quality')
        if key not in axes:
            reasons.append('insufficient_independent_axis')
        energy_support = np.asarray(prediction.get('energy_support'), dtype=float)
        if (energy_support.shape != (2,) or not np.all(np.isfinite(energy_support))
                or energy_support[1] <= energy_support[0]):
            reasons.append('missing_donor_energy_support')
        elif key in axes:
            axis_edges = np.asarray(axes[key].edges, dtype=float)
            if axis_edges[0] < energy_support[0] or axis_edges[-1] > energy_support[1]:
                reasons.append('uncovered_donor_energy_support')
        if (prediction['period'], prediction['state']) not in domains:
            reasons.append('unqualified_normalization_domain')
        if prediction.get('status') != 'available':
            reasons.append('unavailable_prediction')
        count, gap = prediction.get('count'), prediction.get('gap')
        if count is None or not np.isfinite(count) or count < rule['min_count']:
            reasons.append('insufficient_inclusive_count')
        if gap is None or not np.isfinite(gap) or gap < 0 or gap > rule['max_gap']:
            reasons.append('donor_gap')
        if len(set(prediction.get('donors', []))) != 2:
            reasons.append('invalid_donor_pair')
        estimate = np.asarray(prediction.get('estimate'), dtype=float)
        if (estimate.ndim != 1 or not np.all(np.isfinite(estimate)) or np.any(estimate < 0)
                or estimate.sum() <= 0):
            reasons.append('invalid_prediction')
        summary = summaries.get((*key, 'extra_trees_hybrid'), {})
        valid, requested = summary.get('valid_replicas', 0), summary.get('requested_replicas', 0)
        if (valid < rule['min_replicas'] or requested <= 0 or valid > requested
                or valid / requested < rule['min_valid_replica_fraction']):
            reasons.append('insufficient_replicas')
        relative = summary.get('relative_integral_uncertainty')
        if relative is None or not np.isfinite(relative) or relative < 0 or relative > rule['max_relative_integral_std']:
            reasons.append('integral_uncertainty')
        domain = tuple(prediction['group'][:-1]) if 'group' in prediction else (prediction['period'],)
        local = support.get((domain, prediction['state']), support.get((domain, None), {}))
        if local.get('status') != 'available' or local.get('n_groups', 0) < rule['min_groups']:
            reasons.append('insufficient_residual_groups')
        decisions.append(dict(run=key[0], state=key[1], period=prediction['period'], domain=list(domain),
                              accepted=not reasons, reasons=reasons))
    joint = {tuple(r['domain']): r for r in uncertainty.get('joint_state_support', [])}
    for domain in {tuple(r['domain']) for r in decisions if r['accepted']}:
        polarized = [r for r in decisions if r['accepted'] and tuple(r['domain']) == domain
                     and r['state'] in ('POL1','POL2')]
        if {r['state'] for r in polarized} == {'POL1','POL2'}:
            evidence = joint.get(domain, {})
            if (evidence.get('status') != 'available' or evidence.get('n_groups', 0) < rule['min_groups']
                    or set(evidence.get('states', [])) != {'POL1','POL2'}):
                for row in polarized:
                    row['accepted'] = False
                    row['reasons'].append('insufficient_joint_polarized_support')
    accepted_states = {(r['run'],r['state']) for r in decisions if r['accepted']}
    run_decisions = []
    for run in sorted({r['run'] for r in decisions}):
        missing = []
        for state in ('POL1', 'POL2'):
            key = run, state
            row = lookup.get(key, {})
            measured = (key not in masked_states and row.get('measurement_status') == 'measured_valid'
                        and 'run_quality' not in row.get('reasons', []))
            if not measured and key not in accepted_states:
                missing.append(state)
        run_decisions.append(dict(run=run, accepted=not missing,
                                  reasons=[] if not missing else ['unavailable_polarized_states'],
                                  unavailable_states=missing))
    return dict(accepted_runs=[r['run'] for r in run_decisions if r['accepted']],
                state_decisions=decisions, run_decisions=run_decisions)


def qualify_energy(closure, coverage, limits, *, point_universe=None, systematics=None):
    """Qualify only supplied frozen points, grouped evidence and joint precision."""
    _numeric_fields(limits, LIMIT_FIELDS)
    closures = [closure] if isinstance(closure, dict) else closure
    if not any(r.get('accepted_runs') and r.get('counts', {}).get('recovered_pol_events', 1) > 0
               for r in closures):
        return dict(status='no_recovery', reasons=['no_run_accepted'], checks=[], qualified_domains=[])
    reasons, checks = [], []
    insufficient = False

    def check(name, available, passed, **details):
        nonlocal insufficient
        checks.append(dict(name=name, available=bool(available), passed=bool(available and passed), **details))
        if not available:
            insufficient = True
            reasons.append(f'{name}:insufficient_evidence')
        elif not passed:
            reasons.append(f'{name}:failed')

    check('systematics', bool(systematics and systematics.get('evidence') and systematics.get('scope')),
          bool(systematics and systematics.get('status') == 'qualified'))
    universe = set(map(tuple, point_universe or []))
    check('frozen_point_universe', bool(universe), bool(universe))
    by_period = {r.get('period'): r for r in closures}
    for period, estimator, pair, energy, mass in sorted(universe):
        result = by_period.get(period, {})
        key = estimator,pair,energy,mass
        label = ':'.join(map(str,(period,*key)))
        rows = result.get('comparisons', [])
        for reference, scenario, bound in [('C','B','max_abs_shift_stat'),
                                           ('C','D','max_representation_shift_stat'),
                                           ('D','B','max_model_shift_stat')]:
            found = [r for r in rows if r.get('reference') == reference and r.get('scenario') == scenario
                     and (r.get('estimator'),r.get('pair'),r.get('energy_bin'),r.get('mass_bin')) == key]
            row = found[0] if len(found) == 1 else {}
            value = row.get('delta_over_nominal_stat')
            available = value is not None and np.isfinite(value)
            check(f'{label}:{scenario}-{reference}:shift', available,
                  available and abs(value) <= limits[bound], value=value, limit=limits[bound])
            paired = result.get('uncertainty', {}).get('paired', {}).get(f'{scenario}-{reference}', {})
            summaries = [r for r in paired.get('points', []) if tuple(r['key']) == key]
            summary = summaries[0] if len(summaries) == 1 else {}
            std, stat = summary.get('shift_std'), row.get('nominal_stat')
            supported = (summary.get('successful', 0) >= limits['min_complete_replicas']
                         and std is not None and np.isfinite(std) and stat is not None and stat > 0)
            check(f'{label}:{scenario}-{reference}:shift_uncertainty', supported,
                  supported and std/stat <= limits['max_shift_std_stat'],
                  successful=summary.get('successful', 0))
        # Joint replicas include synchronized event and flux fluctuations. A
        # statistical fit error alone is never promoted to combined precision.
        pairs = []
        uncertainty = result.get('uncertainty', {})
        for replica in uncertainty.get('scenario_replicas', []):
            values = []
            for name in ('A','B'):
                found = [r for r in replica.get('scenarios', {}).get(name, []) if tuple(r['key']) == key]
                values.append(found[0]['sigma'] if len(found) == 1 else np.nan)
            if np.all(np.isfinite(values)):
                pairs.append(values)
        supported = len(pairs) >= limits['min_complete_replicas'] and uncertainty.get('flux_propagated', False)
        ratio = None
        if supported:
            stds = np.std(np.asarray(pairs), axis=0, ddof=1)
            supported = bool(stds[0] > 0 and np.all(np.isfinite(stds)))
            if supported:
                ratio = float(stds[1]/stds[0])
        check(f'{label}:combined_precision', supported,
              supported and ratio <= limits['max_combined_precision_ratio'], ratio=ratio)
    # Every declared period/state report must be supported independently.
    reports = [coverage] if isinstance(coverage, dict) else coverage
    check('coverage_domains', bool(reports), bool(reports))
    expected_domains = {(r.get('period'),m['state']) for r in closures
                        for m in r.get('masked_states', [])
                        if m['run'] in r.get('accepted_runs', []) and m['state'] != 'BREM'}
    actual_domains = [(r.get('period'),r.get('state')) for r in reports]
    check('coverage_domain_completeness',
          bool(expected_domains) and expected_domains <= set(actual_domains),
          len(actual_domains) == len(set(actual_domains)))
    for index, report in enumerate(reports):
        label = f"coverage:{report.get('period',index)}:{report.get('state','unspecified')}"
        supported = report.get('n_groups', 0) >= limits['min_coverage_groups']
        check(label+':groups', supported, supported)
        for level in ('68','95'):
            row = report.get('levels', {}).get(level, {})
            bins, integral = row.get('bin_coverage'), row.get('integral_coverage')
            interval = row.get('grouped_diagnostic_interval95')
            available = (bins is not None and integral is not None and interval is not None)
            values = np.asarray([*(bins or []),integral] if available else [], dtype=float)
            bounds = np.asarray(interval if interval is not None else [],dtype=float)
            available = bool(available and len(values) > 1 and np.all(np.isfinite(values))
                             and bounds.ndim == 2 and bounds.shape[0] == 2
                             and bounds.shape[1] >= len(values)
                             and np.all(np.isfinite(bounds)) and np.all(bounds[1] >= bounds[0]))
            check(label+':'+level, available,
                  available and np.min(values) >= limits['min_coverage'+level]
                  and np.max(bounds[1,:len(values)]-bounds[0,:len(values)]) <= limits['max_coverage_interval_width'])
            expected = report.get('expected_targets', 0)
            check(label+':'+level+':availability', expected > 0,
                  expected > 0 and row.get('unavailable',expected)/expected <= limits['max_missing_fraction'])
    status = 'insufficient_evidence' if insufficient else 'failed' if reasons else 'qualified'
    tested_periods = {point[0] for point in universe}
    qualified_domains = {(r.get('period'),m['state']) for r in closures
                         if r.get('period') in tested_periods
                         and r.get('counts', {}).get('recovered_pol_events', 0) > 0
                         for m in r.get('masked_states', [])
                         if m['run'] in r.get('accepted_runs', []) and m['state'] in ('POL1','POL2')}
    return dict(status=status,
                reasons=reasons, checks=checks,
                qualified_domains=[dict(period=period,state=state) for period,state in sorted(qualified_domains)]
                    if status == 'qualified' else [],
                interpretation='conditional on declared normalization and systematic evidence; frozen domain only')
