"""Campaign publication groups reports while preserving scientific ROOT bytes."""
import hashlib
import json

import pytest

from graal_workflow import paths, models


def test_campaign_paths_group_scientific_outputs(tmp_path):
    locations = paths.build_paths(paths.mode_config('production', tmp_path))
    assert locations.profile_root('uv') == locations.output_root / 'root/uv'
    assert locations.calibrated_flux == locations.output_root / 'root/common/flux_calibrated.root'
    assert locations.combined_dir == locations.output_root / 'plots/common'
    assert locations.command_log == locations.output_root / 'metadata/pipeline_commands.log'


def test_report_publication_preserves_root_and_resolves_period_index(tmp_path):
    from graal_workflow.publication import organize_campaign_reports
    campaign = tmp_path / 'campaign'
    root = campaign / 'root/uv/beam_asymmetry'
    period = root / 'periods/P1'
    period.mkdir(parents=True)
    scientific = period / 'beam_asymmetry.root'
    scientific.write_bytes(b'immutable scientific result')
    before = scientific.read_bytes()
    (period / 'fit_diagnostics.pdf').write_bytes(b'%PDF-period')
    (root / 'figure4_experimental.pdf').write_bytes(b'%PDF-duplicate')
    index = root / 'periods/index.json'
    index.write_text(json.dumps({'periods': [{'period': 'P1', 'root': 'P1/beam_asymmetry.root'}]}))
    calibration = campaign / 'root/common/flux_calibrated.qa.json'
    calibration.parent.mkdir(parents=True)
    calibration_bytes = b'{"qa": true}'
    calibration.write_bytes(calibration_bytes)
    organize_campaign_reports(campaign)
    assert scientific.read_bytes() == before
    assert not list(campaign.rglob('figure4_experimental.pdf'))
    assert (campaign / 'plots/uv/periods/P1/fit_diagnostics.pdf').read_bytes() == b'%PDF-period'
    relocated = campaign / 'metadata/uv/beam_asymmetry/periods/index.json'
    data = json.loads(relocated.read_text())
    assert (relocated.parent / data['periods'][0]['root']).resolve() == scientific.resolve()
    assert (campaign / 'metadata/common/flux_calibrated.qa.json').read_bytes() == calibration_bytes
    inventory = json.loads((campaign / 'metadata/output_layout.json').read_text())
    entry = next(row for row in inventory['relocations'] if row['source'].endswith('fit_diagnostics.pdf'))
    assert entry['sha256'] == hashlib.sha256(b'%PDF-period').hexdigest()
    organize_campaign_reports(campaign)
    assert json.loads((campaign / 'metadata/output_layout.json').read_text()) == inventory


def test_report_publication_never_overwrites_conflicting_report(tmp_path):
    from graal_workflow.publication import organize_campaign_reports
    source = tmp_path / 'root/common/qa.json'
    target = tmp_path / 'metadata/common/qa.json'
    for file, content in ((source, b'new'), (target, b'old')):
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(content)
    with pytest.raises(models.PipelineError, match='conflicting'):
        organize_campaign_reports(tmp_path)
    assert source.read_bytes() == b'new'
    assert target.read_bytes() == b'old'


def test_report_publication_failure_restores_reports_and_previous_histograms(tmp_path, monkeypatch):
    from pathlib import Path
    from graal_workflow.publication import organize_campaign_reports
    report = tmp_path / 'root/common/qa.json'
    histograms = tmp_path / 'plots/uv/istogrammi.root'
    old = tmp_path / 'root/uv/istogrammi.root'
    for file, content in ((report, b'{"qa": true}'), (histograms, b'new histograms'), (old, b'previous histograms')):
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(content)
    replace = Path.replace

    def fail_manifest_commit(source, destination):
        if source.name == 'output_layout.json.tmp':
            raise OSError('publication failed')
        return replace(source, destination)

    monkeypatch.setattr(Path, 'replace', fail_manifest_commit)
    with pytest.raises(OSError, match='publication failed'):
        organize_campaign_reports(tmp_path)
    assert report.read_bytes() == b'{"qa": true}'
    assert histograms.read_bytes() == b'new histograms'
    assert old.read_bytes() == b'previous histograms'
    assert not list((tmp_path / 'metadata').rglob('*.*'))
