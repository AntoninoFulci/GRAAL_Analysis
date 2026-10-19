"""Frozen development exclusions must be explicit, validated and reproducible."""
import copy
import hashlib
import json

import numpy as np
import pytest


def test_default_policy_has_reasoned_atomic_exclusions_and_content_identity():
    from calibration.run_quality import DEFAULT_RUN_QUALITY_PATH, load_run_quality, excluded_run_numbers
    policy = load_run_quality()
    assert excluded_run_numbers() == {1322, 1441, 1454, 1482, 1970, 1988, 2055, 2064}
    assert policy['sha256'] == hashlib.sha256(DEFAULT_RUN_QUALITY_PATH.read_bytes()).hexdigest()
    assert all(item['reason'] and item['evidence'] for item in policy['excluded_runs'])


@pytest.mark.parametrize('mutation', ['version', 'duplicate', 'reason', 'evidence', 'nonfinite', 'ratio'])
def test_malformed_policy_fails_closed(tmp_path, mutation):
    from calibration.run_quality import DEFAULT_RUN_QUALITY_PATH, load_run_quality
    policy = json.loads(DEFAULT_RUN_QUALITY_PATH.read_text())
    if mutation == 'version': policy['schema_version'] = 99
    if mutation == 'duplicate': policy['excluded_runs'].append(copy.deepcopy(policy['excluded_runs'][0]))
    if mutation == 'reason': policy['excluded_runs'][0]['reason'] = ''
    if mutation == 'evidence': policy['excluded_runs'][0]['evidence'] = []
    if mutation == 'nonfinite': policy['excluded_runs'][0]['evidence'][0]['flux_per_event'] = float('nan')
    if mutation == 'ratio': policy['excluded_runs'][0]['evidence'][0]['ratio_to_period_state_median'] = 1.
    path = tmp_path / 'policy.json'
    path.write_text(json.dumps(policy))
    with pytest.raises(ValueError, match='run quality'):
        load_run_quality(path)


def test_missing_policy_is_not_silently_disabled(tmp_path):
    from calibration.run_quality import load_run_quality
    with pytest.raises(FileNotFoundError, match='run quality'):
        load_run_quality(tmp_path / 'absent.json')


def test_diagnostic_criterion_is_period_state_relative_and_never_changes_policy():
    from calibration.run_quality import diagnose_flux_per_event, excluded_run_numbers
    rows = [dict(run=i, period='p', state='POL1', count=10, values=np.array([100.])) for i in range(1, 6)]
    rows += [dict(run=6, period='p', state='POL1', count=10, values=np.array([10001.])),
             dict(run=7, period='p', state='POL1', count=10, values=np.array([.999])),
             dict(run=8, period='other', state='BREM', count=10, values=np.array([1e9]))]
    findings = diagnose_flux_per_event(rows)
    assert {row['run'] for row in findings} == {6, 7}
    assert findings[0]['period_state_median'] == 10
    assert excluded_run_numbers() == {1322, 1441, 1454, 1482, 1970, 1988, 2055, 2064}
    assert diagnose_flux_per_event(rows, reference_medians={('p', 'POL1'): 100., ('other', 'BREM'): 1e8})[0]['run'] == 7


def test_diagnostic_accepts_numpy_counts_and_keeps_threshold_boundaries():
    from calibration.run_quality import diagnose_flux_per_event
    rows = [dict(run=i, period='p', state='BREM', count=np.int64(10), values=np.array([value]))
            for i, value in enumerate([1., 10000., .99, 10001., 0., float('nan')], 1)]
    assert {row['run'] for row in diagnose_flux_per_event(
        rows, reference_medians={('p', 'BREM'): 10.})} == {3, 4}


def _user_policy():
    from calibration.run_quality import DEFAULT_RUN_QUALITY_PATH
    policy = json.loads(DEFAULT_RUN_QUALITY_PATH.read_text())
    policy['schema_version'] = 2
    policy['evidence_sources']['benchmark.csv'] = 'a' * 64
    policy['excluded_runs'] = [dict(
        run=1441, period='1998_uv', reason='Explicit user exclusion after inspection.',
        decision_basis='user_requested_development_benchmark_errors',
        evidence=[dict(state='BREM', source='benchmark.csv', method='linear', role='test',
                       event_count=10, true_integral=100., predicted_integral=120.,
                       relative_integral_error=.2, relative_l1=.3, shape_l1=.1)])]
    return policy


def test_user_exclusion_accepts_benchmark_evidence_without_factor100_claim(tmp_path):
    from calibration.run_quality import load_run_quality, excluded_run_numbers
    policy = _user_policy()
    path = tmp_path / 'policy.json'
    path.write_text(json.dumps(policy))
    assert excluded_run_numbers(path) == {1441}
    assert load_run_quality(path)['excluded_runs'][0]['evidence'][0]['relative_integral_error'] == .2


@pytest.mark.parametrize('mutation', ['basis', 'missing_basis', 'source', 'method', 'role',
                                     'state', 'nonfinite', 'integral', 'l1', 'count', 'shape'])
def test_user_exclusion_rejects_untraceable_or_inconsistent_evidence(tmp_path, mutation):
    from calibration.run_quality import load_run_quality
    policy = _user_policy()
    item = policy['excluded_runs'][0]
    row = item['evidence'][0]
    if mutation == 'basis': item['decision_basis'] = 'automatic_error_threshold'
    if mutation == 'missing_basis': del item['decision_basis']
    if mutation == 'source': row['source'] = 'unrecorded.csv'
    if mutation == 'method': row['method'] = 'unknown'
    if mutation == 'role': row['role'] = 'independent_test'
    if mutation == 'state': row['state'] = 'POL1'
    if mutation == 'nonfinite': row['relative_integral_error'] = float('nan')
    if mutation == 'integral': row['predicted_integral'] = 130.
    if mutation == 'l1': row['relative_l1'] = .01
    if mutation == 'count': row['event_count'] = 1.5
    if mutation == 'shape': row['shape_l1'] = 3.
    path = tmp_path / 'policy.json'
    path.write_text(json.dumps(policy))
    with pytest.raises(ValueError, match='run quality'):
        load_run_quality(path)
