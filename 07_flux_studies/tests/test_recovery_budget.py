"""Event accounting is run-atomic, disjoint and tied to the full h80 sample."""
import pytest

from flux_studies.recovery_budget import recovery_budget


def inputs():
    missing = [
        dict(run=r, state=s, period='p', count=10, status='candidate',
             missing_reason='missing_calibrated')
        for r, s in ((1, 'BREM'), (2, 'POL1'), (2, 'POL2'), (3, 'BREM'))]
    support = [dict(run=r['run'], state=r['state'], method='extra_trees_hybrid',
                    supported=(r['run'], r['state']) != (2, 'POL2'),
                    blockers=['flux_uncertainty_not_calibrated']) for r in missing]
    counts = [dict(run=r, state=s, count=10) for r in (1, 2, 3)
              for s in ('POL1', 'POL2', 'BREM')]
    reco = [dict(run=r, state=s, h80_count=10, reconstructed=2,
                 reconstructed_energy_window=1) for r in (1, 2, 3)
            for s in ('POL1', 'POL2', 'BREM')]
    return missing, support, counts, reco


def test_budget_counts_whole_supported_runs_once_excludes_anomalies():
    missing, support, counts, reco = inputs()
    result = recovery_budget(missing, support, counts, reco, excluded_runs={3})
    assert result['summary']['supported_missing_states'] == 2
    assert result['summary']['potential_runs'] == 1
    assert result['summary']['potential_h80_events'] == 30
    assert result['summary']['potential_sigma_events_energy_window'] == 2
    assert result['summary']['production_accepted_runs'] == 0
    assert [r['run'] for r in result['runs'] if r['potential']] == [1]
    assert result['runs'][1]['blockers'] == [
        'flux_uncertainty_not_calibrated', 'unsupported_missing_states']


@pytest.mark.parametrize('defect', ['duplicate_count', 'duplicate_support', 'count_mismatch', 'reco_mismatch'])
def test_budget_rejects_ambiguous_or_mismatched_sources(defect):
    missing, support, counts, reco = inputs()
    if defect == 'duplicate_count':
        counts.append(counts[0])
    elif defect == 'duplicate_support':
        support.append(support[0])
    elif defect == 'count_mismatch':
        missing[0]['count'] = 99
    else:
        reco[0]['h80_count'] = 99
    with pytest.raises(ValueError):
        recovery_budget(missing, support, counts, reco, excluded_runs=set())


@pytest.mark.parametrize('profile,expected', [('uv', 1), ('vis', 3)])
def test_reconstructed_budget_uses_beam_specific_energy_window(monkeypatch, profile, expected):
    import json
    from contextlib import nullcontext
    from types import SimpleNamespace
    import numpy as np
    import uproot
    from flux_studies.recovery_budget import read_reconstructed_counts
    metadata = dict(beam_profile=profile, output_tree='reco', counts_by_run_state=[
        dict(run=1, polarization=1, raw_input=10, skipped_no_tagger=2, written=4)])
    arrays = dict(RunNumber=np.ones(4, dtype=int), Polarization=np.ones(4, dtype=int),
                  beam={'fE': np.array([.94, 1.0, 1.02, 1.4])})
    source = dict(reconstruction_provenance=SimpleNamespace(member=lambda _: json.dumps(metadata)),
                  reco=SimpleNamespace(arrays=lambda _: arrays))
    monkeypatch.setattr(uproot, 'open', lambda _: nullcontext(source))
    rows = read_reconstructed_counts(['fixture.root'])
    assert rows == [dict(run=1, state='POL1', h80_count=8, reconstructed=4,
                         reconstructed_energy_window=expected)]
