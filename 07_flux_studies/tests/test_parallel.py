"""Parallel holdouts retain the serial predictive random stream."""
import numpy as np
import pytest

from flux_studies.tests.helpers import audit_inputs, study_audit
from flux_studies.study_missing_flux import main, run_study
from flux_studies.validation import evaluate_holdouts


def test_parallel_holdouts_preserve_shared_audit_and_predictive_replicas():
    audit = study_audit(12)
    for row in audit['metadata'].values():
        row['exposure'] = dict(value=10., error=1., unit='s', definition='live', uncertainty_group='shared')
    kwargs = dict(mode='offline', n_splits=3, seed=42, n_replicas=4, mask_patterns=(('POL1',),))
    serial = run_study(audit, **kwargs)
    parallel = run_study(audit, **kwargs, workers=2)
    assert serial['evaluation']['folds'] == parallel['evaluation']['folds']
    assert serial['evaluation']['excluded'] == parallel['evaluation']['excluded']
    assert all(context['audit'] is audit for context in parallel['evaluation']['contexts'].values())
    a, b = serial['evaluation']['predictions'], parallel['evaluation']['predictions']
    assert len(a) == len(b)
    for left, right in zip(a, b):
        for key in ('target_key', 'status', 'donor_keys', 'alpha', 'valid_replicas'):
            assert left[key] == right[key]
        for key in ('estimate', 'truth', 'interval68', 'interval95'):
            if left[key] is None:
                assert right[key] is None
            else:
                np.testing.assert_allclose(left[key], right[key], rtol=1e-12, atol=1e-12)
    for key in ('replica_ids', 'mean_replicas', 'replicas', 'valid'):
        np.testing.assert_allclose(serial['uncertainty'][key], parallel['uncertainty'][key],
                                   rtol=1e-12, atol=1e-12, equal_nan=True)


def test_flux_study_cli_accepts_positive_workers(tmp_path):
    inputs = audit_inputs(tmp_path)
    argv = [item for name, path in inputs.items() for item in ('--' + name.replace('_', '-'), str(path))]
    assert main([*argv, '--output-dir', str(tmp_path / 'out'), '--workers', '2']) == 0
    with pytest.raises(SystemExit):
        main([*argv, '--output-dir', str(tmp_path / 'invalid'), '--workers', '0'])
    assert not (tmp_path / 'invalid').exists()


def test_parallel_holdout_failure_propagates():
    audit = study_audit(6)
    audit['histograms'][(1, 'POL1')][0] = np.nan
    with pytest.raises(ValueError, match='finite'):
        evaluate_holdouts(audit, mode='offline', n_splits=3, mask_patterns=(('POL1',),),
                          seed=42, calibrate_uncertainty=False, workers=2)
