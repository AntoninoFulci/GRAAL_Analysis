"""Explicit switches choose work; external artifacts never enable producers."""
from pathlib import Path

import pytest

from graal_workflow.stage_configuration import normalize_stage_configuration
from graal_workflow import models

REPO = Path(__file__).resolve().parents[1]
PROFILE_STAGES = ('selection', 'monte_carlo', 'bdt', 'reconstruction', 'extraction', 'plots')


def configuration(tmp_path, **changes):
    stages = {name: {'common': {'enabled': False}} for name in PROFILE_STAGES}
    stages.update({name: {'enabled': False} for name in ('preanalysis', 'calibration', 'flux_study', 'comparison')})
    data = dict(schema_version=1, campaign=dict(mode='test_data', repo_root=str(REPO), output_dir=str(tmp_path / 'campaign')),
                profiles=dict(uv=dict(enabled=True), vis=dict(enabled=False)), stages=stages)
    for key, value in changes.items():
        if key in stages:
            stages[key] = value
        else:
            data[key] = value
    return normalize_stage_configuration(data, source=tmp_path / 'config.yaml')


def test_disabled_selected_dependency_does_not_enable_selection(tmp_path):
    from graal_workflow.stage_planning import build_stage_plan
    cfg = configuration(tmp_path, reconstruction={'common': {'enabled': True}})
    with pytest.raises(models.PipelineError, match='selected.uv'):
        build_stage_plan(cfg)


def test_external_selected_and_model_bind_only_reconstruction(tmp_path):
    from graal_workflow.stage_planning import build_stage_plan
    cfg = configuration(tmp_path, reconstruction={'common': {'enabled': True, 'chi2_cut': 7.0}},
                        inputs=dict(selected=dict(uv=str(tmp_path / 'selected')), bdt=dict(uv=str(tmp_path / 'model'))))
    plan = build_stage_plan(cfg)
    stages = models.flatten_stages(plan.entries)
    assert [stage.kind for stage in stages] == ['reconstruct_chi2', 'reconstruct_bdt']
    assert all(str(tmp_path / 'selected') in stage.argv for stage in stages)
    assert str(tmp_path / 'model') in stages[1].argv
    assert all(stage.argv[stage.argv.index('--chi2-cut') + 1] == '7.0' for stage in stages)
    assert plan.products['selected.uv'].producer is None


def test_active_producer_and_external_product_is_ambiguous(tmp_path):
    from graal_workflow.stage_planning import build_stage_plan
    cfg = configuration(tmp_path, selection={'common': {'enabled': True}},
                        inputs=dict(preanalysis_dir=str(tmp_path / 'h80'), selected=dict(uv=str(tmp_path / 'selected'))))
    with pytest.raises(models.PipelineError, match='selected.uv.*ON'):
        build_stage_plan(cfg)


def test_mc_only_has_no_h80_selected_or_calibration_dependency(tmp_path):
    from graal_workflow.stage_planning import build_stage_plan
    cfg = configuration(tmp_path, monte_carlo={'common': {'enabled': True, 'events_per_channel': 13, 'channels': ['eta_pi0']}, 'uv': {'force': True}})
    plan = build_stage_plan(cfg)
    assert len(plan.entries) == 2  # generation and channel status
    group = plan.entries[0]
    assert isinstance(group, models.ArtifactGroup) and group.force is True
    assert '(13,' in group.stages[0].argv[-1]
    assert not any(plan.requirements.values())


def test_plot_only_receives_explicit_reconstruction_without_extraction(tmp_path):
    from graal_workflow.stage_planning import build_stage_plan
    cfg = configuration(tmp_path, plots={'common': {'enabled': True, 'mass': False, 'dalitz': True}},
                        inputs=dict(reconstruction=dict(uv=dict(chi2=str(tmp_path / 'chi2.root'), bdt=str(tmp_path / 'bdt.root')))))
    plan = build_stage_plan(cfg)
    assert len(plan.entries) == 1
    argv = plan.entries[0].argv
    assert '--reconstruction-only' in argv and '--no-mass' in argv and '--dalitz' in argv
    assert '--campaign' not in argv
    assert plan.requirements[plan.entries[0].name] == ('reconstruction.uv',)


def test_bdt_upstream_bindings_can_be_external(tmp_path):
    from graal_workflow.stage_planning import build_stage_plan
    cfg = configuration(tmp_path, bdt={'common': {'enabled': True, 'training_seed': 17}},
                        inputs=dict(selected=dict(uv=str(tmp_path / 'selected')), mc=dict(uv=str(tmp_path / 'mc'))))
    plan = build_stage_plan(cfg)
    group, = plan.entries
    assert group.inputs[0] == tmp_path / 'selected'
    assert len(group.inputs) > 1 and all(p.parent == tmp_path / 'mc' for p in group.inputs[1:])
    assert group.stages[-1].argv[group.stages[-1].argv.index('--seed') + 1] == '17'


def test_extraction_only_maps_every_scientific_option(tmp_path):
    from graal_workflow.stage_planning import build_stage_plan
    cfg = configuration(tmp_path, extraction={'common': {'enabled': True, 'estimator': 'ratio', 'phi_bins': 8,
                        'best_binning': True, 'mass_bins': 7, 'by_period': False, 'workers': 2,
                        'bootstrap_replicas': 19, 'bootstrap_seed': 23, 'candle_enabled': False}},
                        execution={'cpus': 3}, inputs=dict(calibration=dict(root=str(tmp_path/'flux.root'), qa=str(tmp_path/'flux.qa.json')),
                        reconstruction=dict(uv=dict(chi2=str(tmp_path/'chi2.root'), bdt=str(tmp_path/'bdt.root')))))
    plan = build_stage_plan(cfg)
    stage, = plan.entries
    assert stage.kind == 'extract'
    assert '--by-period' not in stage.argv and '--candle-mass-half-width' not in stage.argv
    assert '--best-binning' in stage.argv
    for flag, value in {'--estimator': 'ratio', '--phi-bins': '8', '--mass-bins': '7', '--workers': '2',
                        '--bootstrap-replicas': '19', '--bootstrap-seed': '23', '--flux-file': str(tmp_path/'flux.root')}.items():
        assert stage.argv[stage.argv.index(flag)+1] == value
    assert plan.requirements[stage.name] == ('reconstruction.uv', 'calibration')


def test_profile_overrides_reach_each_command_independently(tmp_path):
    from graal_workflow.stage_planning import build_stage_plan
    cfg = configuration(tmp_path, profiles={'uv': {'enabled': True}, 'vis': {'enabled': True}},
                        reconstruction={'common': {'enabled': True, 'chi2_cut': 6}, 'vis': {'chi2_cut': 8}},
                        inputs={'selected': {'uv': str(tmp_path/'uv'), 'vis': str(tmp_path/'vis')},
                                'bdt': {'uv': str(tmp_path/'bu'), 'vis': str(tmp_path/'bv')}})
    for entry in build_stage_plan(cfg).entries:
        assert entry.argv[entry.argv.index('--chi2-cut')+1] == ('6.0' if entry.profile == 'uv' else '8.0')


def test_mc_only_ignores_unrelated_common_inputs(tmp_path):
    from graal_workflow.stage_planning import build_stage_plan
    (tmp_path/'config/support').mkdir(parents=True)
    (tmp_path/'config/support/common_inputs.json').write_text('not json')
    cfg = configuration(tmp_path, campaign={'mode': 'test_data', 'repo_root': str(tmp_path)},
                        monte_carlo={'common': {'enabled': True}})
    assert build_stage_plan(cfg).entries


def test_partial_plan_does_not_impose_mc_threshold(tmp_path):
    from graal_workflow.stage_planning import build_stage_plan
    cfg = configuration(tmp_path, profiles={'uv': {'enabled': True, 'energy_edges_gev': [.7, .8]}, 'vis': {'enabled': False}},
                        plots={'common': {'enabled': True}},
                        inputs={'reconstruction': {'uv': {'chi2': str(tmp_path/'c.root'), 'bdt': str(tmp_path/'b.root')}}})
    assert len(build_stage_plan(cfg).entries) == 1


def test_reconstruction_plots_never_replace_extraction_plot_directory(tmp_path):
    from graal_workflow.stage_planning import build_stage_plan
    cfg = configuration(tmp_path, plots={'common': {'enabled': True}}, extraction={'common': {'enabled': True}},
                        inputs={'reconstruction': {'uv': {'chi2': str(tmp_path/'c.root'), 'bdt': str(tmp_path/'b.root')}},
                                'calibration': {'root': str(tmp_path/'f.root'), 'qa': str(tmp_path/'f.json')}})
    extract, plots = build_stage_plan(cfg).entries
    extract_dir = Path(extract.argv[extract.argv.index('--plots-dir') + 1])
    plots_dir = Path(plots.argv[plots.argv.index('--output-dir') + 1])
    assert plots_dir.parent == extract_dir and plots_dir != extract_dir


def test_explicit_common_manifest_does_not_read_unrelated_default(tmp_path, monkeypatch):
    from graal_workflow import stage_planning
    (tmp_path/'config/support').mkdir(parents=True)
    (tmp_path/'config/support/common_inputs.json').write_text('malformed unused default')
    reference = tmp_path/'chosen-common.json'
    cfg = configuration(tmp_path, campaign={'mode': 'test_data', 'repo_root': str(tmp_path)},
                        calibration={'enabled': True, 'common_inputs': str(reference)},
                        inputs={'preanalysis_dir': str(tmp_path/'h80')})
    monkeypatch.setattr(stage_planning, 'load_common_inputs', lambda *a, **kw: {'inputs': {
        'run_catalog': tmp_path/'catalog.csv', 'run_quality': tmp_path/'quality.json', 'raw_flux': tmp_path/'flux.root'}})
    plan = stage_planning.build_stage_plan(cfg)
    assert plan.paths.manifest == tmp_path/'catalog.csv'


def test_trima_preset_plans_ajaka_uv_and_matching_low_vis_without_duplicate_analysis():
    from graal_workflow.cli import parse_args
    from graal_workflow.stage_planning import build_stage_plan

    config = parse_args([str(REPO / 'config/pipeline_trima_uv_vis_ajaka.yaml'), '--check']).stage_configuration
    plan = build_stage_plan(config)
    stages = models.flatten_stages(plan.entries)
    extracts = [stage for stage in stages if stage.kind == 'extract']
    assert {stage.profile for stage in extracts} == {'uv', 'vis'}
    assert len(extracts) == 2
    for stage in extracts:
        expected = ('0.93', '1.1', '1.2', '1.3', '1.4', '1.5') if stage.profile == 'uv' else ('0.93', '1.1')
        start = stage.argv.index('--energy-edges') + 1
        assert stage.argv[start:start + len(expected)] == expected
        assert stage.argv[stage.argv.index('--workers') + 1] == '40'
    comparisons = [stage for stage in stages if stage.kind == 'comparison']
    assert len(comparisons) == 1
    assert plan.requirements[comparisons[0].name] == ('extraction.uv', 'extraction.vis')
    assert config.data['execution']['cpus'] == 40
    assert config.data['campaign']['output_dir'] == REPO / 'results/trima_uv_vis_ajaka'
