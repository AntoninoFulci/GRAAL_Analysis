"""Publication must never turn a partial or changed campaign into latest results."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pytest


def campaign(tmp_path, name='run', mode='production', date='2026-11-03T10:00:00+00:00'):
    from graal_workflow.report_manifest import complete_campaign
    root = tmp_path / name
    (root / 'plots/uv').mkdir(parents=True)
    (root / 'metadata').mkdir()
    (root / 'plots/uv/fit_diagnostics.pdf').write_bytes(b'%PDF-test')
    (root / 'metadata/effective_configuration.json').write_text(json.dumps({
        'campaign': {'mode': mode}, 'profiles': {'uv': {'enabled': True}},
        'stages': {'extraction': {'uv': {'phi_bins': 12}}},
    }))
    (root / 'metadata/stage_warnings.json').write_text('["Historical input contract"]')
    complete_campaign(root, repo_root=tmp_path, mode=mode,
                      now=datetime.fromisoformat(date))
    return root


def test_completion_records_report_bytes_and_mode_without_rewriting_inputs(tmp_path):
    root = campaign(tmp_path, mode='test_data')
    record = json.loads((root / 'metadata/report_manifest.json').read_text())
    assert record['status'] == 'complete'
    assert record['mode'] == 'test_data'
    assert record['completed_at'] == '2026-11-03T10:00:00+00:00'
    plot = next(f for f in record['files'] if f['path'].endswith('.pdf'))
    assert plot['sha256'] == hashlib.sha256(b'%PDF-test').hexdigest()
    assert (root / plot['path']).read_bytes() == b'%PDF-test'


@pytest.mark.parametrize('change', ['edit', 'add', 'remove', 'symlink'])
def test_changed_report_is_rejected_before_output_exists(tmp_path, change):
    from graal_workflow.analysis_site import build_site
    root = campaign(tmp_path)
    plot = root / 'plots/uv/fit_diagnostics.pdf'
    if change == 'edit':
        plot.write_bytes(b'%PDF-changed')
    elif change == 'add':
        (plot.parent / 'later.pdf').write_bytes(b'%PDF-new')
    elif change == 'remove':
        plot.unlink()
    else:
        plot.unlink()
        other = tmp_path / 'external.pdf'
        other.write_bytes(b'%PDF-test')
        plot.symlink_to(other)
    output = tmp_path / 'site'
    with pytest.raises(ValueError):
        build_site([root], output, repo_root=tmp_path, thumbnails=False)
    assert not output.exists()


def test_export_contains_all_plots_provenance_and_local_documentation(tmp_path):
    from graal_workflow.analysis_site import build_site
    root = campaign(tmp_path)
    wiki = tmp_path / 'wiki'
    wiki.mkdir()
    (wiki / 'Home.md').write_text('# GRAAL documentation\nScientific workflow.')
    output = tmp_path / 'site'
    data = build_site([root], output, repo_root=tmp_path, thumbnails=False)
    assert data['campaigns'][0]['status'] == 'complete'
    assert data['campaigns'][0]['warnings'] == ['Historical input contract']
    assert data['campaigns'][0]['configuration']['stages']['extraction']['uv']['phi_bins'] == 12
    assert len(data['campaigns'][0]['plots']) == 1
    assert (output / data['campaigns'][0]['plots'][0]['url']).read_bytes() == b'%PDF-test'
    assert (output / 'index.html').is_file()
    assert (output / 'assets/site.js').is_file()
    assert (output / 'docs/Home.md').is_file()
    assert not list(output.rglob('*.root'))


def test_latest_production_not_displaced_by_newer_diagnostic_and_history_stays_separate(tmp_path):
    from graal_workflow.analysis_site import build_site
    old = campaign(tmp_path, 'old', date='2026-11-01T12:00:00+00:00')
    new = campaign(tmp_path, 'new')
    diagnostic = campaign(tmp_path, 'diagnostic', mode='test_data', date='2026-11-04T12:00:00+00:00')
    data = build_site([diagnostic, old, new], tmp_path / 'site', repo_root=tmp_path, thumbnails=False)
    assert data['latest'] == 'new'
    assert {r['id'] for r in data['campaigns']} == {'old', 'new', 'diagnostic'}
    assert all(len(r['plots']) == 1 for r in data['campaigns'])


def test_historical_export_requires_opt_in_and_never_writes_completion(tmp_path):
    from graal_workflow.analysis_site import build_site
    root = tmp_path / 'historical'
    (root / 'uv/plots').mkdir(parents=True)
    (root / 'uv/plots/old.pdf').write_bytes(b'%PDF-old')
    with pytest.raises(ValueError, match='manifest'):
        build_site([root], tmp_path / 'refused', repo_root=tmp_path, thumbnails=False)
    data = build_site([root], tmp_path / 'site', repo_root=tmp_path, historical=True, thumbnails=False)
    report = data['campaigns'][0]
    assert report['status'] == 'historical'
    assert report['completed_at'] is None
    assert data['latest'] is None
    assert not (root / 'metadata').exists()


@pytest.mark.parametrize('destination', ['inside', 'ancestor', 'occupied'])
def test_export_cannot_destroy_source_or_existing_site(tmp_path, destination):
    from graal_workflow.analysis_site import build_site
    root = campaign(tmp_path)
    output = {'inside': root / 'site', 'ancestor': tmp_path, 'occupied': tmp_path / 'site'}[destination]
    if destination == 'occupied':
        output.mkdir()
        (output / 'index.html').write_text('previous report')
    with pytest.raises(ValueError):
        build_site([root], output, repo_root=tmp_path, thumbnails=False)
    assert (root / 'plots/uv/fit_diagnostics.pdf').read_bytes() == b'%PDF-test'
    if destination == 'occupied':
        assert (output / 'index.html').read_text() == 'previous report'


def test_unsafe_manifest_paths_and_malformed_status_are_rejected(tmp_path):
    from graal_workflow.analysis_site import build_site
    root = campaign(tmp_path)
    manifest = root / 'metadata/report_manifest.json'
    data = json.loads(manifest.read_text())
    data['files'][0]['path'] = '../../outside.txt'
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        build_site([root], tmp_path / 'site', repo_root=tmp_path, thumbnails=False)


def test_output_urls_and_embedded_json_cannot_inject_markup(tmp_path):
    from graal_workflow.analysis_site import build_site
    from graal_workflow.report_manifest import complete_campaign
    root = campaign(tmp_path)
    plot = root / 'plots/uv/a # "plot".pdf'
    plot.write_bytes(b'%PDF-special')
    (root / 'metadata/stage_warnings.json').write_text('["</script><script>alert(1)</script>"]')
    complete_campaign(root, repo_root=tmp_path, mode='production')
    output = tmp_path / 'site'
    data = build_site([root], output, repo_root=tmp_path, thumbnails=False)
    assert '%23' in next(p['url'] for p in data['campaigns'][0]['plots'] if 'a #' in p['path'])
    assert '</script><script>alert(1)' not in (output / 'index.html').read_text()


def test_release_archive_round_trip_and_cli(tmp_path):
    from graal_workflow.analysis_site import main
    from graal_workflow.site_bundle import unpack_site
    root = campaign(tmp_path)
    output = tmp_path / 'build/site'
    assert main([str(root), '--output', str(output), '--repo-root', str(tmp_path),
                 '--zip', '--no-thumbnails']) == 0
    destination = tmp_path / 'deploy'
    unpack_site(output.parent / 'graal-report.zip', destination)
    assert (destination / 'index.html').read_bytes() == (output / 'index.html').read_bytes()
    assert (destination / 'campaigns/run/files/plots/uv/fit_diagnostics.pdf').read_bytes() == b'%PDF-test'


@pytest.mark.parametrize('name', ['../escape', '/absolute', 'assets/../../escape', 'assets\\escape'])
def test_release_archive_cannot_escape_deployment(tmp_path, name):
    import zipfile
    from graal_workflow.site_bundle import unpack_site
    archive = tmp_path / 'bad.zip'
    with zipfile.ZipFile(archive, 'w') as bundle:
        bundle.writestr(name, 'bad')
    with pytest.raises(ValueError):
        unpack_site(archive, tmp_path / 'deploy')
    assert not (tmp_path / 'deploy').exists()
    assert not (tmp_path / 'escape').exists()


def test_release_archive_requires_valid_report_index(tmp_path):
    import zipfile
    from graal_workflow.site_bundle import unpack_site
    archive = tmp_path / 'bad.zip'
    with zipfile.ZipFile(archive, 'w') as bundle:
        bundle.writestr('index.html', 'broken')
        bundle.writestr('site.json', '{}')
    with pytest.raises(ValueError):
        unpack_site(archive, tmp_path / 'deploy')
    assert not (tmp_path / 'deploy').exists()


def test_deployment_rejects_browser_index_different_from_verified_index(tmp_path):
    from graal_workflow.analysis_site import build_site
    from graal_workflow.site_bundle import validate_site
    root = campaign(tmp_path)
    site = tmp_path / 'site'
    build_site([root], site, repo_root=tmp_path, thumbnails=False)
    index = site / 'index.html'
    index.write_text(index.read_text().replace('"latest": "run"', '"latest": "other"'))
    with pytest.raises(ValueError, match='index'):
        validate_site(site)


def test_deployment_rejects_plot_link_to_another_campaign(tmp_path):
    from graal_workflow.analysis_site import build_site
    from graal_workflow.site_bundle import validate_site
    one = campaign(tmp_path, 'one')
    two = campaign(tmp_path, 'two')
    site = tmp_path / 'site'
    data = build_site([one, two], site, repo_root=tmp_path, thumbnails=False)
    data['campaigns'][0]['plots'][0]['url'] = data['campaigns'][1]['plots'][0]['url']
    (site / 'site.json').write_text(json.dumps(data))
    template = Path(__file__).parents[1] / 'graal_workflow/web_assets/index.html'
    (site / 'index.html').write_text(template.read_text().replace('REPORT_DATA', json.dumps(data)))
    with pytest.raises(ValueError, match='campaign'):
        validate_site(site)


def test_malformed_provenance_cannot_break_browser_after_successful_build(tmp_path):
    from graal_workflow.analysis_site import build_site
    root = campaign(tmp_path)
    manifest = root / 'metadata/report_manifest.json'
    data = json.loads(manifest.read_text())
    data['source_revision'] = None
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        build_site([root], tmp_path / 'site', repo_root=tmp_path, thumbnails=False)
