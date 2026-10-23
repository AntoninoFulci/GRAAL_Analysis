"""Explicit artifact ownership and stable, label-independent workflow controls."""
from dataclasses import replace
import hashlib
from pathlib import Path

import pytest

from graal_workflow import execution, models, paths as workflow_paths, planning, resources


def make_plan(tmp_path, **kwargs):
    config = workflow_paths.mode_config('production', tmp_path)
    paths = workflow_paths.build_paths(config)
    return config, paths, planning.build_pipeline_plan(config, paths, models.PreflightResult('root'), **kwargs)


def test_planner_declares_complete_artifact_groups(tmp_path):
    _, paths, plan = make_plan(tmp_path, flux_study='audit')
    groups = [entry for entry in plan if isinstance(entry, models.ArtifactGroup)]
    for profile, channels in [('uv', models.UV_CHANNELS), ('vis', models.VIS_CHANNELS)]:
        selected = next(g for g in groups if g.kind == 'selected' and g.profile == profile)
        assert selected.destination == paths.selected_dir(profile)
        assert tuple(s.kind for s in selected.stages) == ('select',)
        mc = [g for g in groups if g.kind == 'mc' and g.profile == profile]
        assert tuple(g.channel for g in mc) == channels
        assert all(len(g.stages) == 1 and g.stages[0].channel == g.channel for g in mc)
        assert len({g.destination for g in mc}) == len(channels)
        bdt = next(g for g in groups if g.kind == 'bdt' and g.profile == profile)
        assert tuple(s.kind for s in bdt.stages) == ('beam_spectrum', 'features', 'train')
    stages = models.flatten_stages(plan)
    assert [s.name for s in stages[:2]] == ['common:calibrate_flux', 'common:flux_audit']
    assert stages[-1].name == 'campaign:plots'
    assert all(stage.seed_key == stage.name for stage in stages)


def test_labels_do_not_control_resources_or_seeds(tmp_path):
    _, _, plan = make_plan(tmp_path)
    renamed = tuple(replace(entry, stages=tuple(replace(s, name='display only') for s in entry.stages))
                    if isinstance(entry, models.ArtifactGroup) else replace(entry, name='display only')
                    for entry in plan)
    original = resources.configure_resources(plan, cpus=4, seed=123)
    changed = resources.configure_resources(renamed, cpus=4, seed=123)
    assert [s.argv for s in models.flatten_stages(original)] == [s.argv for s in models.flatten_stages(changed)]
    for stage in models.flatten_stages(original):
        if stage.kind == 'generate':
            expected = int.from_bytes(hashlib.sha256(f'123:{stage.seed_key}'.encode()).digest()[:4], 'big') or 1
            assert stage.argv[-1].endswith(f',{expected})')
    group = next(entry for entry in plan if isinstance(entry, models.ArtifactGroup) and entry.kind == 'mc')
    changed_key = replace(group, stages=(replace(group.stages[0], seed_key='new stream'),))
    assert resources.configure_resources((group,), cpus=1, seed=123)[0].stages[0].argv != resources.configure_resources((changed_key,), cpus=1, seed=123)[0].stages[0].argv


@pytest.mark.parametrize('kinds', [(), ('beam_spectrum',), ('beam_spectrum', 'train'), ('features', 'beam_spectrum', 'train')])
def test_incomplete_bdt_group_rejected(kinds, tmp_path):
    stages = tuple(models.Stage('any label', (), kind=kind, profile='uv', seed_key=kind) for kind in kinds)
    with pytest.raises(models.PipelineError, match='incomplete.*BDT'):
        models.ArtifactGroup('bdt', 'uv', stages, tmp_path)


def test_cache_group_and_staging_keep_metadata_after_label_rename(tmp_path, monkeypatch):
    config, paths, plan = make_plan(tmp_path)
    workflow_paths.prepare_output_dirs(paths)
    group = next(entry for entry in plan if isinstance(entry, models.ArtifactGroup) and entry.kind == 'selected')
    renamed = replace(group, stages=(replace(group.stages[0], name='unrelated label'),))
    paths.preanalysis_dir.mkdir(parents=True, exist_ok=True)
    (paths.preanalysis_dir / "pre_analisi_uv.root").write_bytes(b"input")
    recorded = []
    monkeypatch.setattr(execution, '_stage_sources', lambda *_: (Path(__file__),))
    monkeypatch.setattr(execution, '_source_files', lambda *_: (Path(__file__),))
    monkeypatch.setattr(execution, '_write_campaign_artifacts', lambda *_: None)
    def capture(stages, paths, item, destination, validate, **kwargs):
        recorded.append((item, destination))
        return {'name': item.name}
    monkeypatch.setattr(execution, 'run_cached_stages', capture)
    execution.execute_cached_plan((group,), config, paths)
    execution.execute_cached_plan((renamed,), config, paths)
    assert recorded[0] == recorded[1]


def test_energy_and_best_binning_transformations_preserve_metadata(tmp_path):
    from graal_common.physics.energy_binning import EnergyBinning
    _, _, plan = make_plan(tmp_path, energy_binnings={'uv': EnergyBinning((.9313, 1., 1.1))}, best_binning=True)
    configured = resources.configure_resources(plan, cpus=4, seed=123)
    bdt = next(g for g in configured if isinstance(g, models.ArtifactGroup) and g.kind == 'bdt' and g.profile == 'uv')
    assert bdt.energy_range == (.9313, 1.1)
    for stage in models.flatten_stages(configured):
        assert stage.seed_key == stage.name
        if stage.kind == 'extract':
            assert '--best-binning' in stage.argv
        if stage.profile == 'uv' and stage.kind in ('beam_spectrum', 'features', 'reconstruct_chi2', 'reconstruct_bdt', 'extract'):
            assert '--energy-edges' in stage.argv


def test_staging_rewrite_preserves_all_stage_metadata(tmp_path, monkeypatch):
    _, paths, plan = make_plan(tmp_path)
    workflow_paths.prepare_output_dirs(paths)
    group = next(g for g in plan if isinstance(g, models.ArtifactGroup) and g.kind == 'bdt')
    seen = []
    monkeypatch.setattr(execution, 'execute_plan', lambda stages, *_a, **_k: seen.extend(stages))
    item = models.CacheItem('bdt:uv', tmp_path / 'manifest.json', (group.destination,), {})
    execution.run_cached_stages(group.stages, paths, item, group.destination, lambda _: None, production=False)
    assert len(seen) == 3
    for original, staged in zip(group.stages, seen, strict=True):
        assert replace(staged, argv=original.argv) == original
        assert staged.argv != original.argv


@pytest.mark.parametrize('kind', ['selected', 'mc', 'bdt'])
def test_incomplete_single_command_groups_rejected(tmp_path, kind):
    with pytest.raises(models.PipelineError, match='incomplete'):
        models.ArtifactGroup(kind, 'uv', (), tmp_path)


def cache_fixture(tmp_path, monkeypatch):
    """Exercise real cache publication with small deterministic stand-in payloads."""
    import subprocess
    config, paths, plan = make_plan(tmp_path)
    workflow_paths.prepare_output_dirs(paths)
    paths.preanalysis_dir.mkdir(parents=True, exist_ok=True)
    (paths.preanalysis_dir / 'pre_analisi_uv.root').write_bytes(b'input v1')
    paths.hyperparams.parent.mkdir(parents=True, exist_ok=True)
    paths.hyperparams.write_text('{}')
    selected = next(g for g in plan if isinstance(g, models.ArtifactGroup) and g.kind == 'selected' and g.profile == 'uv')
    mc = next(g for g in plan if isinstance(g, models.ArtifactGroup) and g.kind == 'mc' and g.profile == 'uv')
    bdt = next(g for g in plan if isinstance(g, models.ArtifactGroup) and g.kind == 'bdt' and g.profile == 'uv')
    groups = tuple(replace(g, stages=tuple(replace(s, argv=('produce', str(g.destination / f'{s.kind}.payload') if g.kind != 'mc' else str(g.destination))) for s in g.stages)) for g in (selected, mc, bdt))
    monkeypatch.setattr(execution, '_stage_sources', lambda *_: (Path(__file__),))
    monkeypatch.setattr(execution, '_source_files', lambda *_: (Path(__file__),))
    def validate(destination, *_args, **_kwargs):
        assert destination.exists()
        if destination.is_dir():
            assert any(destination.iterdir())
        else:
            assert destination.read_bytes()
    monkeypatch.setattr(execution.cache, 'validate_selected', validate)
    monkeypatch.setattr(execution.cache, 'validate_mc', validate)
    monkeypatch.setattr(execution.cache, 'validate_bdt', validate)
    outcomes, calls = [], []
    monkeypatch.setattr(execution, '_write_campaign_artifacts', lambda _, rows, sources: outcomes.append(list(rows)))
    def runner(argv, **kwargs):
        calls.append(argv)
        path = Path(argv[1])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'payload {len(calls)}')
        return subprocess.CompletedProcess(argv, 0)
    return config, paths, groups, outcomes, calls, runner


def test_renamed_group_cache_hits_force_and_upstream_invalidation(tmp_path, monkeypatch):
    config, paths, groups, outcomes, calls, runner = cache_fixture(tmp_path, monkeypatch)
    def run(plan=groups, **kwargs):
        execution.execute_cached_plan(plan, config, paths, runner=runner, **kwargs)
        return [row['action'] for row in outcomes[-1]]
    assert run() == ['RUN', 'RUN', 'RUN']
    assert len(calls) == 5
    renamed = tuple(replace(g, stages=tuple(replace(s, name='human display') for s in g.stages)) for g in groups)
    assert run(renamed) == ['SKIP', 'SKIP', 'SKIP']
    assert len(calls) == 5
    assert run(force_selected=True) == ['RUN', 'SKIP', 'RUN']
    assert run(force_mc=True) == ['SKIP', 'RUN', 'RUN']
    assert run(force_bdt=True) == ['SKIP', 'SKIP', 'RUN']
    (paths.preanalysis_dir / 'pre_analisi_uv.root').write_bytes(b'changed upstream input')
    assert run() == ['RUN', 'SKIP', 'RUN']
    paths.hyperparams.write_text('{"changed": true}')
    assert run() == ['SKIP', 'SKIP', 'RUN']
    for group in groups:
        manifest = group.destination.with_suffix('.manifest.json') if group.kind == 'mc' else group.destination.parent / 'uv.manifest.json'
        assert manifest.is_file()


@pytest.mark.parametrize('kind', ['selected', 'mc', 'bdt'])
def test_group_forced_failure_preserves_payload_and_manifest(tmp_path, monkeypatch, kind):
    import subprocess
    config, paths, groups, _, _, runner = cache_fixture(tmp_path, monkeypatch)
    execution.execute_cached_plan(groups, config, paths, runner=runner)
    group = next(g for g in groups if g.kind == kind)
    manifest = group.destination.with_suffix('.manifest.json') if kind == 'mc' else group.destination.parent / 'uv.manifest.json'
    original_manifest = manifest.read_bytes()
    payloads = tuple(group.destination.rglob('*')) if group.destination.is_dir() else (group.destination,)
    original = {p: p.read_bytes() for p in payloads if p.is_file()}
    def broken(argv, **kwargs):
        runner(argv, **kwargs)
        return subprocess.CompletedProcess(argv, 1)
    with pytest.raises(models.PipelineError, match='failed with exit 1'):
        execution.execute_cached_plan(groups, config, paths, runner=broken, **{f'force_{kind}': True})
    assert {p: p.read_bytes() for p in original} == original
    assert manifest.read_bytes() == original_manifest


@pytest.mark.parametrize('kind', ['select', 'generate', 'beam_spectrum', 'features', 'train'])
def test_cache_commands_require_explicit_groups_before_dispatch(tmp_path, monkeypatch, kind):
    config, paths, _ = make_plan(tmp_path)
    stage = models.Stage('unrelated label', ('must-not-run',), kind=kind, profile='uv', seed_key='stable')
    monkeypatch.setattr(execution, '_stage_sources', lambda *_: pytest.fail('inventory before plan validation'))
    with pytest.raises(models.PipelineError, match='requires an artifact group'):
        execution.execute_cached_plan((stage,), config, paths, runner=lambda *_a, **_k: pytest.fail('dispatched incomplete group'))
