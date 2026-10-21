"""Selection must preserve missing evidence and the frozen trial denominator."""
import hashlib
import json

import pytest

from flux_studies.acceptance_report import collect_scan
from flux_studies.acceptance_scan import POLICIES


NAMES = ('strict_1', 'strict_2', 'moderate_3', 'loose_4', 'loose_5')
METHOD = 'extra_trees_hybrid'
KEY = dict(estimator='ratio', pair='p_eta', energy_bin=0, mass_bin=0)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def protocol_file(tmp_path, expected=1):
    path = tmp_path / 'protocol.json'
    write(path, dict(development=[dict(index=i, seed=i + 1, block_size=5) for i in range(expected)],
                     confirmation=dict(seed=2, block_size=5), policies=list(POLICIES)))
    return path


def trial(tmp_path, seed=1, *, ratios=(.9, .8, .7, .6, .5), expected=1):
    protocol = protocol_file(tmp_path, expected)
    directory = tmp_path / f'trial_{seed}'
    write(directory / 'trial.json', dict(phase='development', seed=seed, block_size=5,
                                        trial_index=seed - 1,
                                        protocol_sha256=hashlib.sha256(protocol.read_bytes()).hexdigest(),
                                        status='complete'))
    for name, ratio in zip(NAMES, ratios):
        base = directory / 'policies' / name
        write(base / 'decision.json', dict(policy=name, accepted_runs=[10], rejected_runs=[],
                                           state_decisions=[dict(run=10, state='POL1', period='p', accepted=True)]))
        coverage = dict(observed=.7, interval95=[.5, 1.], nominal_inside_interval=True,
                        status='conditional_diagnostic', evaluable_targets=8, donor_clusters=5)
        write(base / 'coverage.json', [dict(period='p', state='POL1', method=METHOD,
                                            coverage68=coverage, coverage95=coverage)])
        period = dict(period='p', accepted_runs=[10], recovered_events=100,
                      target_states=[dict(run=10, state='POL1')],
                      acceptance=dict(representation=dict(status='passed')),
                      scenarios={m: dict(points=[KEY], estimable_points=1)
                                 for m in ('native_truth', 'without_recovery', METHOD)},
                      comparisons=[dict(**KEY, scenario=METHOD, reference='native_truth',
                                        status='matched', delta_over_nominal_stat=.05)],
                      flux_replica_results={METHOD: dict(requested_replicas=40, complete_replicas=40)},
                      recovery_precision=[dict(**KEY, method=METHOD, status='matched',
                                               missing_oracle=False, missing_recovered=False,
                                               missing_without_recovery=False,
                                               precision_ratio=ratio, flux_over_oracle_stat=.2)])
        write(base / 'closure' / 'observable_closure.json', dict(accepted_runs=[10], periods=[period]))
    return directory


def change(directory, policy, filename, edit):
    path = directory / 'policies' / policy / filename
    data = json.loads(path.read_text())
    edit(data)
    write(path, data)


def collect(paths):
    return collect_scan(paths, protocol_path=paths[0].parent / 'protocol.json')


def test_feasible_ranking_and_strict_tie(tmp_path):
    directory = trial(tmp_path, ratios=(.9, .8, .7, .7, .95))
    report = collect([directory])
    assert report['status'] == 'complete'
    assert report['selected_policy'] == 'moderate_3'
    assert report['production_adopted'] is False
    assert report['independent_confirmation'] is False


def test_incomplete_trials_preserve_denominator_and_never_select(tmp_path):
    directory = trial(tmp_path, expected=2)
    report = collect([directory])
    assert report['status'] == 'incomplete'
    assert report['expected_trials'] == 2
    assert report['completed_trials'] == 1
    assert report['selected_policy'] is None
    (directory / 'policies' / 'strict_1' / 'coverage.json').unlink()
    assert collect([directory])['status'] == 'incomplete'


def test_confirmation_duplicate_and_protocol_mismatch_rejected(tmp_path):
    directory = trial(tmp_path, expected=2)
    with pytest.raises(ValueError, match='duplicate'):
        collect([directory, directory])
    metadata = json.loads((directory / 'trial.json').read_text())
    for field, value, message in [('phase', 'confirmation', 'development'),
                                  ('protocol_sha256', 'other', 'protocol')]:
        write(directory / 'trial.json', {**metadata, field: value})
        with pytest.raises(ValueError, match=message):
            collect([directory])
    other = trial(tmp_path / 'elsewhere', seed=1, expected=2)
    write(directory / 'trial.json', metadata)
    with pytest.raises(ValueError, match='duplicate'):
        collect([directory, other])


@pytest.mark.parametrize('failure', ['coverage', 'bias', 'flux', 'replicas', 'precision', 'lost_fit'])
def test_unavailable_or_failed_evidence_cannot_win(tmp_path, failure):
    directory = trial(tmp_path)
    if failure == 'coverage':
        change(directory, 'loose_5', 'coverage.json',
               lambda data: data[0]['coverage68'].update(interval95=None, nominal_inside_interval=None))
    else:
        def edit(data):
            p = data['periods'][0]
            if failure == 'bias':
                p['comparisons'][0]['delta_over_nominal_stat'] = .101
            elif failure == 'flux':
                p['recovery_precision'][0]['flux_over_oracle_stat'] = float('nan')
            elif failure == 'replicas':
                p['flux_replica_results'][METHOD]['complete_replicas'] = 35
            elif failure == 'precision':
                p['recovery_precision'][0]['precision_ratio'] = None
            else:
                p['recovery_precision'] = []
        change(directory, 'loose_5', 'closure/observable_closure.json', edit)
    report = collect([directory])
    assert report['selected_policy'] == 'loose_4'
    assert not report['policies'][-1]['feasible']
    assert report['policies'][-1]['reasons']


def test_no_acceptance_cannot_be_an_optimum(tmp_path):
    directory = trial(tmp_path)
    for name in NAMES:
        change(directory, name, 'decision.json', lambda data: data.update(accepted_runs=[]))
        def edit(data):
            data['accepted_runs'] = []
            p = data['periods'][0]
            p.update(accepted_runs=[], target_states=[], recovered_events=0)
        change(directory, name, 'closure/observable_closure.json', edit)
    report = collect([directory])
    assert report['selected_policy'] is None
    assert all(p['recovered_events'] == 0 for p in report['policies'])
    assert all(p['precision_objective'] is None for p in report['policies'])


def test_zero_acceptance_repetition_does_not_invent_gain(tmp_path):
    one, two = trial(tmp_path, expected=2), trial(tmp_path, seed=2, expected=2)
    change(two, 'loose_5', 'decision.json', lambda data: data.update(accepted_runs=[]))
    def edit(data):
        data['accepted_runs'] = []
        data['periods'][0].update(accepted_runs=[], target_states=[], recovered_events=0)
    change(two, 'loose_5', 'closure/observable_closure.json', edit)
    report = collect([one, two])
    policy = report['policies'][-1]
    assert policy['no_recovery_trials'] == 1
    assert policy['trials'][1]['precision_median'] is None


def test_no_feasible_improvement_is_explicit(tmp_path):
    directory = trial(tmp_path, ratios=(1., 1.1, 1.2, 1.3, 1.4))
    report = collect([directory])
    assert report['selected_policy'] is None
    assert report['selection_reasons']


def test_missing_accepted_state_and_fixed_point_fail_closed(tmp_path):
    directory = trial(tmp_path)
    change(directory, 'loose_5', 'decision.json',
           lambda data: data['state_decisions'].append(
               dict(run=10, state='BREM', period='p', accepted=True)))
    change(directory, 'loose_4', 'closure/observable_closure.json',
           lambda data: data['periods'][0]['scenarios']['native_truth'].update(points=[]))
    assert collect([directory])['selected_policy'] == 'moderate_3'


def test_verified_empty_recovery_contributes_neutral_not_gain(tmp_path):
    directory = trial(tmp_path)
    change(directory, 'loose_5', 'decision.json', lambda data: data.update(accepted_runs=[]))
    def edit(data):
        data['accepted_runs'] = []
        p = data['periods'][0]
        p.update(accepted_runs=[], target_states=[], recovered_events=0)
        for scenario in p['scenarios'].values():
            scenario['points'][0].update(sigma=.2, stat_low=.1, stat_high=.1)
    change(directory, 'loose_5', 'closure/observable_closure.json', edit)
    p = collect([directory])['policies'][-1]
    assert p['trials'][0]['objective_contribution'] == 1.
    assert p['precision_objective'] is None
    assert not p['feasible']


def test_cli_publishes_plots_and_integrity(tmp_path):
    from flux_studies.acceptance_report import main
    directory = trial(tmp_path)
    output = tmp_path / 'report'
    assert main(['--trials', str(directory), '--protocol', str(tmp_path / 'protocol.json'),
                 '--output-dir', str(output)]) == 0
    assert json.loads((output / 'summary.json').read_text())['selected_policy'] == 'loose_5'
    for filename in ('summary.csv', 'acceptance_scan.png', 'period_screens.png', 'input_integrity.json'):
        assert (output / filename).stat().st_size > 0


def test_confirmation_is_bound_to_exact_selection_and_never_reselects(tmp_path):
    from flux_studies.acceptance_report import confirm_scan
    development = trial(tmp_path / 'dev')
    selection = tmp_path / 'selection.json'
    write(selection, collect([development]))
    confirmation = trial(tmp_path / 'confirmation', seed=2)
    meta_path = confirmation / 'trial.json'
    metadata = json.loads(meta_path.read_text())
    protocol = development.parent / 'protocol.json'
    with pytest.raises(ValueError, match='confirmation'):
        confirm_scan(confirmation, selection, protocol_path=protocol)
    metadata.update(phase='confirmation', trial_index=None,
                    selection_sha256=hashlib.sha256(selection.read_bytes()).hexdigest())
    write(meta_path, metadata)
    # Missing alternate-policy files are irrelevant to this locked evaluation.
    for name in NAMES[:-1]:
        (confirmation / 'policies' / name / 'decision.json').unlink()
    report = confirm_scan(confirmation, selection, protocol_path=protocol)
    assert report['selected_policy'] == 'loose_5'
    assert report['diagnostic_passed']
    assert not report['production_adopted']
    assert not report['independent_confirmation']
    change(confirmation, 'loose_5', 'closure/observable_closure.json',
           lambda data: data['periods'][0]['comparisons'][0].update(delta_over_nominal_stat=.2))
    report = confirm_scan(confirmation, selection, protocol_path=protocol)
    assert report['selected_policy'] == 'loose_5'
    assert not report['diagnostic_passed']
    selection.write_text(selection.read_text() + '\n')
    with pytest.raises(ValueError, match='selection.*hash'):
        confirm_scan(confirmation, selection, protocol_path=protocol)


def test_favorable_subset_cannot_shrink_frozen_denominator(tmp_path):
    directory = trial(tmp_path, expected=10)
    report = collect([directory])
    assert report['expected_trials'] == 10
    assert report['completed_trials'] == 1
    assert report['status'] == 'incomplete'
    assert report['selected_policy'] is None
    with pytest.raises(TypeError):
        collect_scan([directory], protocol_path=tmp_path / 'protocol.json', expected_trials=1)


@pytest.mark.parametrize(('field', 'value'), [('seed', 99), ('block_size', 1), ('trial_index', 9)])
def test_development_metadata_must_match_frozen_schedule(tmp_path, field, value):
    directory = trial(tmp_path)
    metadata = json.loads((directory / 'trial.json').read_text())
    write(directory / 'trial.json', {**metadata, field: value})
    with pytest.raises(ValueError, match='schedule'):
        collect([directory])


def test_renamed_policy_and_modified_registry_cannot_select(tmp_path):
    directory = trial(tmp_path)
    change(directory, 'loose_5', 'decision.json', lambda data: data.update(policy='strict_1'))
    with pytest.raises(ValueError, match='policy'):
        collect([directory])
    protocol = tmp_path / 'protocol.json'
    data = json.loads(protocol.read_text())
    data['policies'] = data['policies'][:-1]
    write(protocol, data)
    with pytest.raises(ValueError, match='polic'):
        collect([directory])


@pytest.mark.parametrize(('target', 'field', 'value'), [
    ('trial', 'seed', 99), ('trial', 'block_size', 3), ('trial', 'trial_index', 0),
    ('selection', 'expected_trials', 0), ('selection', 'development_schedule', []),
    ('selection', 'completed_trial_indices', []),
])
def test_confirmation_cannot_change_frozen_schedule(tmp_path, target, field, value):
    from flux_studies.acceptance_report import confirm_scan
    development = trial(tmp_path / 'dev')
    selection_path = tmp_path / 'selection.json'
    selection = collect([development])
    if target == 'selection':
        selection[field] = value
    write(selection_path, selection)
    confirmation = trial(tmp_path / 'confirmation', seed=2)
    metadata = json.loads((confirmation / 'trial.json').read_text())
    metadata.update(phase='confirmation', trial_index=None,
                    selection_sha256=hashlib.sha256(selection_path.read_bytes()).hexdigest())
    if target == 'trial':
        metadata[field] = value
    write(confirmation / 'trial.json', metadata)
    with pytest.raises(ValueError, match='schedule|selection'):
        confirm_scan(confirmation, selection_path, protocol_path=development.parent / 'protocol.json')


@pytest.mark.parametrize('failure', ['incomplete', 'infeasible', 'subset'])
def test_validate_selection_blocks_invalid_selection_before_confirmation(tmp_path, failure):
    from flux_studies.acceptance_report import validate_selection
    directory = trial(tmp_path)
    selection = collect([directory])
    if failure == 'incomplete':
        selection['status'] = 'incomplete'
    elif failure == 'infeasible':
        selection['policies'][-1]['feasible'] = False
    else:
        selection['completed_trial_indices'] = []
    path = tmp_path / 'selection.json'
    write(path, selection)
    with pytest.raises(ValueError, match='selection'):
        validate_selection(tmp_path / 'protocol.json', path)
