"""Runtime checks protect external products and remain read-only in check mode."""
from copy import deepcopy
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from graal_workflow.models import ModeConfig, PipelineError, Stage
from graal_workflow.paths import build_paths
from graal_workflow.stage_configuration import StageConfiguration, normalize_stage_configuration


def settings(root, *, mode='production'):
    profile_stages = ('selection', 'monte_carlo', 'bdt', 'reconstruction', 'extraction', 'plots')
    common_stages = ('preanalysis', 'calibration', 'flux_study', 'comparison')
    return normalize_stage_configuration({
        'schema_version': 1, 'campaign': {'mode': mode, 'repo_root': str(root),
                                          'output_dir': str(root / ('results' if mode == 'production' else 'results_test') / 'new')},
        'profiles': {'uv': {'enabled': True}, 'vis': {'enabled': True}},
        'stages': {**{k: {'common': {'enabled': False}} for k in profile_stages},
                   **{k: {'enabled': False} for k in common_stages}},
    })


def make_plan(root, *, entries=(), products=None, requirements=None, mode='production'):
    config = settings(root, mode=mode)
    model = ModeConfig(mode, root, root / 'unused-h80', root / 'results/new', 10)
    paths = build_paths(model, config.data['campaign']['output_dir'])
    return SimpleNamespace(configuration=config, mode=model, paths=paths,
                           entries=entries, products=products or {}, requirements=requirements or {})


def workflow():
    return importlib.import_module('graal_workflow.staged_workflow')


def test_compare_reports_scientific_key_and_values(tmp_path):
    module = workflow()
    current = settings(tmp_path).data
    previous = deepcopy(current)
    previous['stages']['extraction']['uv']['phi_bins'] = 8
    reference = tmp_path / 'prior/metadata'
    reference.mkdir(parents=True)
    (reference / 'effective_configuration.json').write_text(json.dumps(previous, default=str))
    warnings = module.compare_configurations(current, reference.parent)
    assert any('stages.extraction.uv.phi_bins' in message and '8' in message and '12' in message for message in warnings)


@pytest.mark.parametrize('payload', [None, '[]', '{}', '{broken'])
def test_missing_or_malformed_comparison_is_blocking(tmp_path, payload):
    module = workflow()
    if payload is not None:
        metadata = tmp_path / 'prior/metadata'
        metadata.mkdir(parents=True)
        (metadata / 'effective_configuration.json').write_text(payload)
    with pytest.raises(PipelineError, match='compare_to'):
        module.compare_configurations(settings(tmp_path).data, tmp_path / 'prior')


def test_unconsumed_external_input_inside_output_is_protected(tmp_path):
    module = workflow()
    plan = make_plan(tmp_path)
    external = plan.paths.output_root / 'external/selected'
    plan.configuration.data['inputs']['selected']['uv'] = external
    with pytest.raises(PipelineError, match='overlap'):
        module.validate_output_safety(plan)
    assert not plan.paths.output_root.exists()


def test_external_input_alias_is_protected(tmp_path):
    module = workflow()
    plan = make_plan(tmp_path)
    target = tmp_path / 'results/new'
    target.mkdir(parents=True)
    link = tmp_path / 'alias'
    link.symlink_to(target, target_is_directory=True)
    plan.configuration.data['inputs']['selected']['uv'] = link / 'selected'
    with pytest.raises(PipelineError, match='overlap'):
        module.validate_output_safety(plan)


def test_empty_plan_preflight_does_not_require_raw_root_training_or_manifest(tmp_path):
    module = workflow()
    plan = make_plan(tmp_path)
    imported = []
    assert module.preflight_stage_plan(plan, import_module=lambda name: imported.append(name), which=lambda _: None) == []
    assert imported == []
    assert not (tmp_path / 'results').exists()


def test_plot_preflight_does_not_import_training_or_require_root_executable(tmp_path, monkeypatch):
    module = workflow()
    source = tmp_path / 'reconstruction.root'
    source.write_bytes(b'external')
    stage = Stage('uv:plots', ('python', '-m', 'plots'), kind='plots', profile='uv')
    product = SimpleNamespace(kind='reconstruction', profile='uv', value={'chi2': source, 'bdt': source}, producer=None)
    plan = make_plan(tmp_path, entries=(stage,), products={'reconstruction.uv': product},
                     requirements={stage.name: ('reconstruction.uv',)})
    monkeypatch.setattr(module, 'validate_product', lambda *args, **kwargs: [])
    imported = []
    module.preflight_stage_plan(plan, import_module=lambda name: imported.append(name), which=lambda _: None)
    assert 'ROOT' in imported
    assert 'xgboost' not in imported and 'sklearn' not in imported


def test_check_returns_without_locks_output_or_jobs(tmp_path, monkeypatch):
    module = workflow()
    plan = make_plan(tmp_path)
    plan.configuration.data['execution']['check_only'] = True
    monkeypatch.setattr(module, 'build_stage_plan', lambda *args, **kwargs: plan)
    for name in ('pipeline_lock', 'prepare_output_dirs', 'execute_cached_plan'):
        monkeypatch.setattr(module, name, lambda *args, **kwargs: pytest.fail('check mode must not write or execute'))
    assert module.run_stage_configuration(plan.configuration, repo_root=tmp_path) == 0
    assert not plan.paths.output_root.exists()


def test_occupied_production_reports_diff_before_error_without_modifying(tmp_path, monkeypatch, capsys):
    module = workflow()
    plan = make_plan(tmp_path)
    metadata = plan.paths.output_root / 'metadata'
    metadata.mkdir(parents=True)
    previous = deepcopy(plan.configuration.data)
    previous['stages']['extraction']['uv']['phi_bins'] = 8
    source = json.dumps(previous, default=str)
    (metadata / 'effective_configuration.json').write_text(source)
    monkeypatch.setattr(module, 'build_stage_plan', lambda *args, **kwargs: plan)
    with pytest.raises(PipelineError, match='not empty'):
        module.run_stage_configuration(plan.configuration, repo_root=tmp_path, assume_yes=True)
    output = capsys.readouterr()
    assert 'phi_bins' in output.out + output.err
    assert (metadata / 'effective_configuration.json').read_text() == source


def test_dependency_gate_revalidates_generated_product_before_consumer(tmp_path, monkeypatch):
    module = workflow()
    selected = tmp_path / 'generated'
    stage = Stage('uv:reconstruction', ('python',), kind='reconstruct_chi2', profile='uv')
    product = SimpleNamespace(kind='selected', profile='uv', value=selected, producer='uv:select')
    plan = make_plan(tmp_path, entries=(stage,), products={'selected.uv': product},
                     requirements={stage.name: ('selected.uv',)})
    validated = []
    def validate(kind, value, **kwargs):
        if not value.is_dir():
            raise PipelineError('generated selected missing')
        validated.append((kind, value))
        return []
    monkeypatch.setattr(module, 'validate_product', validate)
    gate = module.dependency_gate(plan, [])
    with pytest.raises(PipelineError, match='generated selected missing'):
        gate(stage)
    selected.mkdir()
    gate(stage)
    assert validated == [('selected', selected)]


def test_empty_plan_execution_records_reviewable_metadata(tmp_path):
    module = workflow()
    config = settings(tmp_path)
    assert module.run_stage_configuration(config, repo_root=tmp_path, assume_yes=True) == 0
    metadata = tmp_path / 'results/new/metadata'
    effective = json.loads((metadata / 'effective_configuration.json').read_text())
    assert effective['campaign']['repo_root'] == str(tmp_path)
    assert effective['campaign']['output_dir'] == str(tmp_path / 'results/new')
    artifacts = json.loads((metadata / 'stage_artifacts.json').read_text())
    assert artifacts['inputs'] == {} and artifacts['outputs'] == {}
    assert artifacts['source_files'] and artifacts['outcomes'] == []


def test_active_cache_symlink_cannot_write_outside_managed_root(tmp_path):
    from graal_workflow.models import ArtifactGroup
    module = workflow()
    external = tmp_path / 'protected-science'
    external.mkdir()
    cache_root = tmp_path / 'results/_cache'
    cache_root.parent.mkdir()
    cache_root.symlink_to(external, target_is_directory=True)
    stage = Stage('uv:select', ('python',), kind='select', profile='uv')
    group = ArtifactGroup('selected', 'uv', (stage,), cache_root / '03_selected/uv')
    plan = make_plan(tmp_path, entries=(group,))
    with pytest.raises(PipelineError, match='symlink'):
        module.validate_output_safety(plan)


def test_existing_mc_cache_file_is_not_mistaken_for_unwritable_parent(tmp_path):
    from graal_workflow.models import ArtifactGroup
    module = workflow()
    destination = tmp_path / 'results/_cache/04_mc/uv/mc.root'
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b'existing cache')
    stage = Stage('uv:generate:eta_pi0', ('root',), kind='generate', profile='uv', channel='eta_pi0', seed_key='mc')
    group = ArtifactGroup('mc', 'uv', (stage,), destination, channel='eta_pi0')
    module.validate_output_safety(make_plan(tmp_path, entries=(group,)))


def test_preanalysis_can_use_new_directory_within_campaign(tmp_path):
    module = workflow()
    plan = make_plan(tmp_path)
    data = plan.configuration.data
    data['stages']['preanalysis'].update(enabled=True, output_dir=plan.paths.output_root / 'root/h80')
    data['inputs']['raw_dir'] = tmp_path / 'raw'
    module.validate_output_safety(plan)


def test_occupied_flux_diagnostics_are_not_replaced(tmp_path):
    module = workflow()
    destination = tmp_path / 'results_test/diagnostics/new/missing_flux'
    destination.mkdir(parents=True)
    evidence = destination / 'report.json'
    evidence.write_text('historical diagnostic')
    stage = Stage('common:flux_audit', ('python', '--output-dir', str(destination)), kind='flux_audit')
    with pytest.raises(PipelineError, match='diagnostic output is not empty'):
        module.validate_output_safety(make_plan(tmp_path, entries=(stage,)))
    assert evidence.read_text() == 'historical diagnostic'


def test_dependency_gate_detects_external_change_before_consumer(tmp_path, monkeypatch):
    module = workflow()
    source = tmp_path / 'selected'
    source.mkdir()
    payload = source / 'input.root'
    payload.write_bytes(b'original')
    product = SimpleNamespace(kind='selected', profile='uv', value=source, producer=None)
    stage = Stage('uv:reconstruction', ('python',), kind='reconstruct_chi2', profile='uv')
    plan = make_plan(tmp_path, entries=(stage,), products={'selected.uv': product},
                     requirements={stage.name: ('selected.uv',)})
    identities = module._identities(plan)
    gate = module.dependency_gate(plan, [], identities)
    payload.write_bytes(b'changed contents')
    with pytest.raises(PipelineError, match='changed before consumption'):
        gate(stage)


def test_publication_identities_follow_qa_relocation(tmp_path):
    module = workflow()
    plan = make_plan(tmp_path)
    qa = plan.paths.output_root / 'root/common/flux_calibrated.qa.json'
    qa.parent.mkdir(parents=True)
    qa.write_text('{"scientific": "evidence"}')
    identities = {'calibration': module.cache.inventory((qa,))}
    module.organize_campaign_reports(plan.paths.output_root)
    result = module._published_identities(plan, identities)
    assert result['calibration'][0]['produced_path'] == str(qa)
    assert Path(result['calibration'][0]['path']).read_text() == '{"scientific": "evidence"}'


def test_training_diagnostics_preflight_requires_root(tmp_path):
    module = workflow()
    stage = Stage('uv:train', ('python', '--feature-diagnostics-dir', str(tmp_path / 'features')), kind='train', profile='uv')
    imported = []
    module.preflight_stage_plan(make_plan(tmp_path, entries=(stage,)), import_module=lambda name: imported.append(name))
    assert 'ROOT' in imported


def test_cache_manifest_sidecar_cannot_overwrite_declared_input(tmp_path):
    from graal_workflow.models import ArtifactGroup
    module = workflow()
    destination = tmp_path / 'results/_cache/04_mc/uv/mc.root'
    stage = Stage('uv:generate:eta_pi0', ('root',), kind='generate', profile='uv', channel='eta_pi0', seed_key='mc')
    group = ArtifactGroup('mc', 'uv', (stage,), destination, channel='eta_pi0')
    plan = make_plan(tmp_path, entries=(group,))
    plan.configuration.data['stages']['bdt']['uv']['hyperparams'] = destination.with_suffix('.manifest.json')
    with pytest.raises(PipelineError, match='overlap'):
        module.validate_output_safety(plan)


def test_resolved_common_input_under_active_cache_is_protected(tmp_path):
    from dataclasses import replace
    from graal_workflow.models import ArtifactGroup
    module = workflow()
    destination = tmp_path / 'results/_cache/03_selected/uv'
    selection = Stage('uv:select', ('python',), kind='select', profile='uv')
    group = ArtifactGroup('selected', 'uv', (selection,), destination)
    calibration = Stage('common:calibrate_flux', ('python',), kind='calibrate_flux')
    plan = make_plan(tmp_path, entries=(group, calibration))
    plan.paths = replace(plan.paths, raw_flux=destination / 'raw_flux.root')
    with pytest.raises(PipelineError, match='resolved raw flux'):
        module.validate_output_safety(plan)


def test_preanalysis_cannot_share_flux_diagnostic_destination(tmp_path):
    module = workflow()
    target = tmp_path / 'results_test/diagnostics/new/missing_flux'
    stage = Stage('common:flux_audit', ('python', '--output-dir', str(target)), kind='flux_audit')
    plan = make_plan(tmp_path, entries=(stage,))
    plan.configuration.data['stages']['preanalysis'].update(enabled=True, output_dir=target)
    with pytest.raises(PipelineError, match='overlap'):
        module.validate_output_safety(plan)


@pytest.mark.parametrize('key,action', [
    ('stages.extraction.uv.phi_bins', 'rebuild extraction and comparison'),
    ('stages.reconstruction.uv.missing_mass_window_gev', 'require compatible reconstruction and rebuild downstream'),
    ('profiles.uv.energy_edges_gev', 'revalidate upstream energy coverage and rebuild extraction'),
])
def test_comparison_warnings_explain_affected_stage(key, action):
    module = workflow()
    warning = module._differences({key: 2}, {key: 1})[0]
    assert f'action={action}' in warning


def test_production_campaign_cannot_claim_reserved_cache(tmp_path):
    from dataclasses import replace
    module = workflow()
    plan = make_plan(tmp_path)
    plan.paths = replace(plan.paths, output_root=plan.paths.artifact_root)
    with pytest.raises(PipelineError, match='reserved.*cache'):
        module.validate_output_safety(plan)
    assert not plan.paths.output_root.exists()
