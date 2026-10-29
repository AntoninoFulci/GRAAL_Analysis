"""Structured launch settings are strict and independent across profiles."""
from pathlib import Path

import pytest
import yaml

from graal_workflow.cli import parse_args

PROFILE_STAGES = ('selection', 'monte_carlo', 'bdt', 'reconstruction', 'extraction', 'plots')
COMMON_STAGES = ('preanalysis', 'calibration', 'flux_study', 'comparison')


def configuration():
    return {
        'schema_version': 1,
        'campaign': {'mode': 'test_data'},
        'profiles': {'uv': {'enabled': True}, 'vis': {'enabled': True}},
        'stages': {
            **{name: {'common': {'enabled': False}} for name in PROFILE_STAGES},
            **{name: {'enabled': False} for name in COMMON_STAGES},
        },
    }


def write_config(tmp_path, values):
    path = tmp_path / 'campaign.yaml'
    path.write_text(yaml.safe_dump(values))
    return path


def test_common_profile_cli_and_leaf_precedence(tmp_path):
    values = configuration()
    values['stages']['extraction'] = {'common': {'enabled': True, 'phi_bins': 8}, 'uv': {'phi_bins': 16}}
    path = write_config(tmp_path, values)
    args = parse_args([str(path), '--phi-bins', '12', '--set', 'stages.extraction.vis.phi_bins=16', '--check'])
    config = args.stage_configuration
    assert config.data['stages']['extraction']['uv']['phi_bins'] == 12
    assert config.data['stages']['extraction']['vis']['phi_bins'] == 16
    assert config.data['execution']['check_only'] is True
    assert config.source == path and config.source_text == path.read_text()
    assert 'stages.extraction.vis.phi_bins=16' in config.overrides
    assert config.data['stages']['monte_carlo']['uv']['events_per_channel'] == 100_000


def test_yaml_and_cli_paths_have_distinct_origins(tmp_path, monkeypatch):
    values = configuration()
    values['campaign']['output_dir'] = 'output'
    values['inputs'] = {'selected': {'uv': 'external/uv'}}
    values['stages']['bdt']['common']['hyperparams'] = '~/parameters.json'
    path = write_config(tmp_path, values)
    other = tmp_path / 'elsewhere'
    other.mkdir()
    monkeypatch.chdir(other)
    config = parse_args([str(path), '--output-dir', 'cli-output', '--set', 'inputs.selected.vis=cli-vis']).stage_configuration
    assert config.data['campaign']['output_dir'] == other / 'cli-output'
    assert config.data['inputs']['selected']['uv'] == tmp_path / 'external/uv'
    assert config.data['inputs']['selected']['vis'] == other / 'cli-vis'
    assert config.data['stages']['bdt']['uv']['hyperparams'] == Path.home() / 'parameters.json'


@pytest.mark.parametrize('key,value,error', [
    ('execution.cpus', 0, 'execution.cpus'),
    ('execution.seed', True, 'execution.seed'),
    ('profiles.uv.energy_edges_gev', [1.2, 1.1], 'profiles.uv.energy_edges_gev'),
    ('profiles.vis.energy_edges_gev', [1.2, 1.5], 'profiles.vis.energy_edges_gev'),
    ('stages.reconstruction.common.chi2_cut', float('nan'), 'chi2_cut'),
    ('stages.bdt.common.validation_fraction', 1.0, 'validation_fraction'),
    ('stages.extraction.common.phi_bins', 7, 'phi_bins'),
    ('stages.selection.common.force', True, 'force'),
    ('stages.preanalysis.force', False, 'stages.preanalysis.force'),
    ('stages.plots.common.typo', True, 'stages.plots.common.typo'),
    ('inputs.selected.uv', None, 'inputs.selected.uv'),
    ('inputs.unknown', '/tmp', 'inputs.unknown'),
    ('stages.monte_carlo.common.channels', ['fake'], 'channels'),
    ('stages.bdt.common.training_seed', -1, 'training_seed'),
])
def test_invalid_nested_values_report_full_path(tmp_path, capsys, key, value, error):
    values = configuration()
    node = values
    parts = key.split('.')
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value
    with pytest.raises(SystemExit):
        parse_args([str(write_config(tmp_path, values))])
    assert error in capsys.readouterr().err


@pytest.mark.parametrize('location', ['stages.plots', 'stages.calibration.enabled', 'profiles.uv.enabled'])
def test_switches_are_explicit(tmp_path, capsys, location):
    values = configuration()
    node = values
    parts = location.split('.')
    for part in parts[:-1]:
        node = node[part]
    del node[parts[-1]]
    with pytest.raises(SystemExit):
        parse_args([str(write_config(tmp_path, values))])
    assert location in capsys.readouterr().err


@pytest.mark.parametrize('overrides', [
    ['execution.cpus=2', 'execution.cpus=3'],
    ['execution={cpus: 2}'], ['execution.cpus=two'], ['unknown.key=2'],
    ['execution.cpus'], ['inputs.raw_dir=null'], ['schema_version=2'],
])
def test_invalid_set_is_rejected(tmp_path, overrides):
    path = write_config(tmp_path, configuration())
    with pytest.raises(SystemExit):
        parse_args([str(path), *[item for value in overrides for item in ('--set', value)]])


def test_cli_force_overrides_both_profiles_and_set_last(tmp_path):
    values = configuration()
    values['stages']['monte_carlo']['common']['enabled'] = True
    path = write_config(tmp_path, values)
    result = parse_args([str(path), '--force-mc', '--set', 'stages.monte_carlo.uv.force=false']).stage_configuration.data
    assert result['stages']['monte_carlo']['uv']['force'] is False
    assert result['stages']['monte_carlo']['vis']['force'] is True


def test_legacy_check_has_no_structured_configuration():
    args = parse_args(['--mode', 'test_data', '--check'])
    assert args.check is True and args.stage_configuration is None
    with pytest.raises(SystemExit):
        parse_args(['--mode', 'test_data', '--set', 'execution.cpus=2'])


def test_common_set_overrides_both_profiles_without_aliasing(tmp_path):
    values = configuration()
    values['stages']['extraction']['uv'] = {'phi_bins': 16}
    result = parse_args([str(write_config(tmp_path, values)), '--set', 'stages.extraction.common.phi_bins=8']).stage_configuration.data
    assert result['stages']['extraction']['uv']['phi_bins'] == 8
    assert result['stages']['extraction']['vis']['phi_bins'] == 8
    result['stages']['extraction']['uv']['phi_bins'] = 12
    assert result['stages']['extraction']['vis']['phi_bins'] == 8


def test_cli_mode_changes_implicit_mc_budget(tmp_path):
    args = parse_args([str(write_config(tmp_path, configuration())), '--mode', 'production'])
    assert args.stage_configuration.data['stages']['monte_carlo']['uv']['events_per_channel'] == 1_000_000


@pytest.mark.parametrize('change,error', [
    ({'stages.comparison.enabled': True, 'profiles.vis.enabled': False}, 'comparison.enabled'),
    ({'stages.monte_carlo.common.enabled': True, 'stages.monte_carlo.common.channels': ['pi0pi0']}, 'channels'),
    ({'stages.bdt.common.enabled': True, 'stages.monte_carlo.common.channels': ['pi0pi0']}, 'channels'),
    ({'stages.extraction.common.workers': 4, 'execution.cpus': 2}, 'workers'),
])
def test_cross_field_constraints(tmp_path, capsys, change, error):
    values = configuration()
    for key, value in change.items():
        node = values
        parts = key.split('.')
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
    with pytest.raises(SystemExit):
        parse_args([str(write_config(tmp_path, values))])
    assert error in capsys.readouterr().err


def test_structured_duplicate_and_mixed_keys_rejected(tmp_path, capsys):
    path = write_config(tmp_path, configuration())
    original = path.read_text()
    for added, error in [('schema_version: 1\n', 'duplicate'), ('mode: production\n', 'mode')]:
        path.write_text(original + added)
        with pytest.raises(SystemExit):
            parse_args([str(path)])
        assert error in capsys.readouterr().err


def test_disabled_profile_may_omit_per_stage_switch(tmp_path):
    values = configuration()
    values['profiles']['vis']['enabled'] = False
    for stage in PROFILE_STAGES:
        values['stages'][stage] = {'uv': {'enabled': False}}
    result = parse_args([str(write_config(tmp_path, values))]).stage_configuration.data
    assert result['stages']['selection']['vis']['enabled'] is False


def test_master_seed_zero_is_rejected_before_planning(tmp_path, capsys):
    values = configuration()
    values['execution'] = {'seed': 0}
    with pytest.raises(SystemExit):
        parse_args([str(write_config(tmp_path, values))])
    assert 'execution.seed' in capsys.readouterr().err


@pytest.mark.parametrize('field,value', [('phi_bins', 8), ('best_binning', True),
                                         ('candle_enabled', False), ('candle_mass_half_width_gev', 0.1)])
def test_comparison_requires_compatible_profile_definitions(tmp_path, capsys, field, value):
    values = configuration()
    values['stages']['comparison']['enabled'] = True
    values['stages']['extraction']['uv'] = {field: value}
    with pytest.raises(SystemExit):
        parse_args([str(write_config(tmp_path, values))])
    assert field in capsys.readouterr().err


def test_comparison_does_not_restrict_independent_mass_bins_or_seeds(tmp_path):
    values = configuration()
    values['stages']['comparison']['enabled'] = True
    values['stages']['extraction']['uv'] = {'mass_bins': 20, 'bootstrap_seed': 1, 'candle_balance_seed': 2}
    assert parse_args([str(write_config(tmp_path, values))]).stage_configuration is not None
