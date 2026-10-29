"""Policy edits invalidate observable source identity and are recorded by campaigns."""
import json
from pathlib import Path

from graal_workflow import execution, paths as workflow_paths


def test_observable_fingerprint_changes_when_only_quality_policy_changes(tmp_path):
    config = workflow_paths.mode_config('production', tmp_path)
    paths = workflow_paths.build_paths(config)
    policy = tmp_path / 'config/support/run_quality_exclusions.json'
    policy.parent.mkdir(parents=True)
    policy.write_text('first policy')
    module = tmp_path / '06_calibration/run_quality.py'
    module.parent.mkdir()
    module.write_text('# quality loader')
    before = execution.cache.source_fingerprint(execution._source_files(paths, '08_observable_extraction'))
    policy.write_text('updated policy')
    after = execution.cache.source_fingerprint(execution._source_files(paths, '08_observable_extraction'))
    assert before != after


def test_campaign_inventory_records_quality_policy_identity(tmp_path):
    from calibration.run_quality import DEFAULT_RUN_QUALITY_PATH, load_run_quality
    config = workflow_paths.mode_config('production', tmp_path)
    paths = workflow_paths.build_paths(config)
    paths.output_root.mkdir(parents=True)
    paths.preanalysis_dir.mkdir(parents=True)
    for profile in ('uv', 'vis'):
        (paths.preanalysis_dir / f'pre_analisi_1998_{profile}.root').write_bytes(b'fixture')
    policy = tmp_path / 'config/support/run_quality_exclusions.json'
    policy.parent.mkdir(parents=True)
    policy.write_bytes(DEFAULT_RUN_QUALITY_PATH.read_bytes())
    sources = execution.cache.inventory(execution._source_files(paths, '08_observable_extraction'))
    execution._write_campaign_artifacts(paths, [], sources)
    inventory = json.loads((paths.output_root / 'metadata/pipeline_artifacts.json').read_text())
    assert inventory['run_quality']['sha256'] == load_run_quality(policy)['sha256']
    assert inventory['source_files'] == sources
    assert str(policy.resolve()) in {row['path'] for row in sources}
    assert {record['run'] for record in inventory['run_quality']['excluded_runs']} == {1322, 1441, 1454, 1482, 1970, 1988, 2055, 2064, 2607, 2804, 3585, 3776}
