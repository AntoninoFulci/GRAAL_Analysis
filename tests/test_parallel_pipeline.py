from pathlib import Path
import subprocess
import threading

import pytest

from scripts import run_pipeline as pipeline
from scripts.parallel_pipeline import configure_resources


def test_budget_reaches_native_and_process_stages(tmp_path):
    config = pipeline.mode_config('production', tmp_path)
    paths = pipeline.build_paths(config)
    stages = pipeline.build_pipeline_plan(config, paths, pipeline.PreflightResult('root'))
    configured = configure_resources(stages, cpus=40, seed=123)
    by_name = {stage.name: stage.argv for stage in configured}
    for name, flag in [('common:calibrate_flux', '--threads'), ('uv:select', '--threads'),
                       ('vis:train', '--nthread'), ('uv:features', '--workers'),
                       ('uv:reconstruct_chi2', '--workers')]:
        argv = by_name[name]
        assert argv[argv.index(flag) + 1] == '40'
    for profile in ('uv', 'vis'):
        argv = by_name[f'{profile}:extract']
        assert argv[argv.index('--workers') + 1] == '1'
    assert '--seed-policy' in by_name['uv:features']
    generated = [stage.argv[-1] for stage in configured if ':generate:' in stage.name]
    assert len(generated) == len(set(generated))
    assert all(call.endswith(')') and call.rsplit(',', 1)[-1][:-1].isdigit() for call in generated)
    assert configured == configure_resources(stages, cpus=40, seed=123)


def test_extraction_override_preserves_other_stage_budgets(tmp_path):
    config = pipeline.mode_config('production', tmp_path)
    stages = pipeline.build_pipeline_plan(config, pipeline.build_paths(config),
                                          pipeline.PreflightResult('root'))
    configured = configure_resources(stages, cpus=40, seed=123, extraction_workers=8)
    by_name = {stage.name: stage.argv for stage in configured}
    for profile in ('uv', 'vis'):
        extract = by_name[f'{profile}:extract']
        reco = by_name[f'{profile}:reconstruct_bdt']
        assert extract[extract.index('--workers') + 1] == '8'
        assert reco[reco.index('--workers') + 1] == '40'


@pytest.mark.parametrize('workers', [0, -1, True, 1.5, 41])
def test_extraction_workers_must_fit_total_budget(workers):
    with pytest.raises(ValueError, match='positive integer|CPU budget'):
        configure_resources((), cpus=40, seed=123, extraction_workers=workers)


def test_extraction_worker_cli_default_override_and_validation():
    parser = pipeline.build_parser()
    assert parser.parse_args(['--mode', 'production']).extraction_workers == 1
    assert parser.parse_args(['--mode', 'production', '--extraction-workers', '8']).extraction_workers == 8
    with pytest.raises(SystemExit):
        parser.parse_args(['--mode', 'production', '--extraction-workers', '0'])


def test_extraction_budget_error_preserves_existing_campaign(tmp_path):
    output = tmp_path / 'results/test_existing'
    output.mkdir(parents=True)
    marker = output / 'keep.txt'
    marker.write_text('previous campaign')
    args = pipeline.build_parser().parse_args([
        '--mode', 'test_data', '--output-dir', str(output),
        '--cpus', '4', '--extraction-workers', '8',
    ])
    with pytest.raises(pipeline.PipelineError, match='must not exceed --cpus'):
        pipeline.run(args, repo_root=tmp_path)
    assert marker.read_text() == 'previous campaign'
    assert not (output / 'pipeline_commands.log').exists()


def test_parallel_mc_bounded_and_published_with_manifests(tmp_path, monkeypatch):
    config = pipeline.mode_config('production', tmp_path)
    paths = pipeline.build_paths(config)
    pipeline.prepare_output_dirs(paths)
    stages = tuple(pipeline.Stage(f'uv:generate:{name}', (name,)) for name in ('eta_pi0', 'pi0pi0', '3pi0'))
    lock = threading.Lock()
    active = peak = 0
    gate = threading.Barrier(2)
    seen = []
    def fake_cached(group, paths, item, destination, validate, **kwargs):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
            ordinal = len(seen)
            seen.append(item.name)
        if ordinal < 2:
            gate.wait(timeout=5)
        with lock:
            active -= 1
        return {'name': item.name, 'action': 'RUN'}
    monkeypatch.setattr(pipeline, 'run_cached_stages', fake_cached)
    monkeypatch.setattr(pipeline.cache, 'source_fingerprint', lambda _: 'hash')
    writes = []
    monkeypatch.setattr(pipeline, '_write_campaign_artifacts', lambda paths, outcomes: writes.append(list(outcomes)))
    pipeline.execute_cached_plan(stages, config, paths, cpus=2)
    assert peak == 2
    assert [row['name'] for row in writes[-1]] == ['mc:uv:eta_pi0', 'mc:uv:pi0pi0', 'mc:uv:3pi0']


def test_current_h80_validation_rejects_legacy_and_allows_empty(tmp_path):
    import ROOT
    from scripts.artifact_manifest import validate_current_preanalysis
    path = tmp_path / 'empty.root'
    file = ROOT.TFile(str(path), 'RECREATE')
    tree = ROOT.TTree('h80', 'h80')
    tree.Write()
    file.Close()
    with pytest.raises(ValueError, match='tagger|current|branches'):
        validate_current_preanalysis([path])
