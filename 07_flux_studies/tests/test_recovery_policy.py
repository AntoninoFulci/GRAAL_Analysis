"""Current recovery must not resurrect excluded runs or retired models."""
import pytest


def test_active_models_and_rejected_retired_families():
    from flux_studies.neighbor_models import FAMILIES, GRIDS, DEFAULTS
    from flux_studies.neighbor_validation import evaluate_neighbors
    assert set(FAMILIES) == set(GRIDS) == set(DEFAULTS) == {'extra_trees', 'kernel_ridge'}
    for family in ('ridge', 'mlp', 'cnn1d'):
        with pytest.raises(ValueError, match='model family'):
            evaluate_neighbors([], block_size=3, seed=142, models=(family,))


def test_global_policy_contains_full_campaign_anomalies():
    from calibration.run_quality import excluded_run_numbers
    assert excluded_run_numbers() == {
        1322, 1441, 1454, 1482, 1970, 1988, 2055, 2064, 2607, 2804, 3585, 3776}


def test_old_inventory_cannot_reintroduce_anomalies():
    from flux_studies.realistic_gaps import recovery_targets
    inventory = {'missing': [
        dict(run=run, state='POL1', period='p', group=['p', 'P', 'UV', 'POL1'],
             position=15., count=20, status='candidate')
        for run in (100, 2607)]}
    targets = recovery_targets(inventory, excluded_runs={2607})
    assert [r['run'] for r in targets] == [100]
    assert targets[0]['group'] == ('p', 'P', 'UV', 'POL1')
