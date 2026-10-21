"""Native CLI requests must verify bin identity before model fitting."""
from pathlib import Path

import numpy as np
import pytest

from flux_studies import study_calibrated_neighbors as cli


@pytest.mark.parametrize('audit_status, expected', [('verified', 0), ('failed', 1)])
def test_native_cli_requires_audit_and_accepts_retained_families(tmp_path, monkeypatch, audit_status, expected):
    source = tmp_path / 'source'
    source.write_text('input')
    monkeypatch.setattr(cli, 'count_h80', lambda paths: ({}, []))
    def dataset(*args, **kwargs):
        assert kwargs['representation'] == 'native_strip'
        return dict(records=[], exclusions=[], energy_edges=None, representation='native_strip')
    monkeypatch.setattr(cli, 'load_calibrated_dataset', dataset)
    import flux_studies.strip_audit as audit
    monkeypatch.setattr(audit, 'audit_native_strips', lambda *args, **kwargs: dict(status=audit_status))
    fits = []
    def evaluate(*args, **kwargs):
        assert kwargs['models'] == ('extra_trees', 'kernel_ridge')
        fits.append(True)
        return dict(predictions=[], exclusions=[], fits=[], splits={}, block_size=3, status='insufficient_data')
    monkeypatch.setattr(cli, 'evaluate_neighbors', evaluate)
    monkeypatch.setattr(cli, '_write_benchmark', lambda *args, **kwargs: None)
    output = tmp_path / 'output'
    result = cli.main(['--manifest', str(source), '--calibrated-flux', str(source),
        '--h80', str(source), '--output-dir', str(output), '--block-size', '3',
        '--representation', 'native_strip', '--raw-flux', str(source), '--models', 'extra_trees', 'kernel_ridge'])
    assert result == expected
    assert len(fits) == (1 if expected == 0 else 0)
    assert (output / 'strip_audit.json').exists() == (expected == 0)
