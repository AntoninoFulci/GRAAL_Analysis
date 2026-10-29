"""Structured plans retain explicit cache inputs and per-unit force decisions."""
from dataclasses import replace
from pathlib import Path

from graal_workflow import artifact_manifest as cache, execution, models
from graal_workflow.paths import build_paths, mode_config


def test_external_bdt_inputs_and_hyperparams_enter_cache_signature(tmp_path, monkeypatch):
    paths = build_paths(mode_config('production', tmp_path))
    selected, mc, params = tmp_path / 'selected', tmp_path / 'mc.root', tmp_path / 'custom.json'
    stages = tuple(models.Stage(kind, ('python', '--hyperparams', str(params)) if kind == 'train' else ('python',),
                                kind=kind, profile='uv') for kind in ('beam_spectrum', 'features', 'train'))
    group = models.ArtifactGroup('bdt', 'uv', stages, paths.bdt_dir('uv'), inputs=(selected, mc))
    monkeypatch.setattr(cache, 'inventory', lambda values: list(values))
    monkeypatch.setattr(cache, 'source_fingerprint', lambda values: list(values))
    monkeypatch.setattr(execution, '_source_files', lambda *args: ())
    item, validator = execution.artifact_cache_item(group, (group,), paths)
    assert item.signature['selected'] == [selected]
    assert item.signature['mc'] == [mc]
    assert item.signature['hyperparams'] == [params]


def test_force_and_gate_follow_each_entry_without_legacy_metadata(tmp_path, monkeypatch):
    mode = mode_config('production', tmp_path)
    paths = build_paths(mode)
    stage = models.Stage('uv:generate:eta_pi0', ('root',), kind='generate', profile='uv', channel='eta_pi0', seed_key='uv:eta_pi0')
    group = models.ArtifactGroup('mc', 'uv', (stage,), paths.mc_dir('uv') / 'signal.root', 'eta_pi0', force=False)
    monkeypatch.setattr(execution, '_stage_sources', lambda *a: ())
    monkeypatch.setattr(cache, 'inventory', lambda *a: [])
    monkeypatch.setattr(execution, 'artifact_cache_item', lambda *a: ('item', 'validate'))
    monkeypatch.setattr(execution, '_write_campaign_artifacts', lambda *a: (_ for _ in ()).throw(AssertionError('legacy metadata')))
    observed = []
    monkeypatch.setattr(execution, 'run_cached_stages', lambda *a, **kw: observed.append(kw['force']) or {'action': 'RUN'})
    outcomes = execution.execute_cached_plan((group,), mode, paths, force_mc=True,
                   before_entry=lambda entry: observed.append(entry), write_legacy_metadata=False)
    assert observed == [group, False]
    assert outcomes == [{'action': 'RUN'}]


def test_cache_staging_rewrites_outputs_but_preserves_sibling_inputs(tmp_path):
    import subprocess
    from graal_workflow.paths import prepare_output_dirs
    mode = mode_config('test_data', tmp_path)
    paths = build_paths(mode)
    prepare_output_dirs(paths)
    destination = paths.bdt_dir('uv')
    external = destination.with_name('uv-selected')
    params = destination.with_name('uv-reference.json')
    stages = (models.Stage('train', ('python', '--out-dir', str(destination/'artifacts/stage1'),
              '--selected-dir', str(external), '--hyperparams', str(params))),)
    item = models.CacheItem('bdt', destination.with_suffix('.json'), (destination,), {})
    observed = []
    def runner(argv, **kwargs):
        observed.append(argv)
        return subprocess.CompletedProcess(argv, 0)
    execution.run_cached_stages(stages, paths, item, destination, lambda p: None, production=False, runner=runner)
    command, = observed
    assert command[command.index('--selected-dir')+1] == str(external)
    assert command[command.index('--hyperparams')+1] == str(params)
    assert command[command.index('--out-dir')+1] != str(destination/'artifacts/stage1')
